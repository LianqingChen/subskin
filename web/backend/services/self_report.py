"""用户自报事实与微询问调度（图像数据库专项 SS-32/33，设计见 docs/research/2026-10-06-strategy/08）。

原则：一次只问一件事，紧跟用户刚做完的动作；每题都能答“不知道”；有频率上限；跳过后冷却。
答案是 T1（用户事实），不是临床标签。本模块只做服务层，不依赖 FastAPI。

频率规则：
- 每个 session（一次打开）最多展示 1 题；
- 任意 7 天内最多展示 3 题；
- 某题被跳过后 14 天内不再主动出现；
- checklist（用户主动点开的资料包补全清单）不受上述限制，也不占用每周额度。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from web.backend.models.self_report import MicroAskLog, SelfReportFact
from web.backend.models.vasi import VASIAssessment

logger = logging.getLogger(__name__)

QUESTION_VERSION = "1"
WEEKLY_CAP = 3
WEEKLY_WINDOW = timedelta(days=7)
SKIP_COOLDOWN = timedelta(days=14)


class SelfReportError(ValueError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def _opts(*pairs):
    return [{"value": v, "label": l} for v, l in pairs]


UNKNOWN = ("unknown", "不确定")

# 文案为草案，上线前由产品/PI 复核；选项值（value）是稳定的存储编码，改文案不改 value。
QUESTIONS: Dict[str, Dict[str, Any]] = {
    "Q1": {
        "id": "Q1", "scope": "body_site", "multi": False,
        "text": "这处白斑大概出现多久了？",
        "options": _opts(("lt3m", "不到3个月"), ("3to12m", "3–12个月"), ("1to3y", "1–3年"),
                         ("gt3y", "3年以上"), UNKNOWN),
        "repeat_after_days": None,
    },
    "Q2": {
        "id": "Q2", "scope": "body_site", "multi": False,
        "text": "最近一段时间，这里有变化吗？",
        "options": _opts(("expanded", "扩大了"), ("new_spots", "出现新的"), ("unchanged", "没变化"),
                         ("shrunk", "缩小了"), ("repigmenting", "颜色变淡了"), UNKNOWN),
        "repeat_after_days": 28,
    },
    "Q3": {
        "id": "Q3", "scope": "user", "multi": True,
        "text": "这段时间用过哪些治疗？",
        "options": _opts(("topical", "外用药"), ("phototherapy", "光疗"), ("oral", "口服药"),
                         ("surgery", "手术或移植"), ("none", "没有治疗"), UNKNOWN),
        "exclusive": ("none", "unknown"),
        "repeat_after_days": 90,
    },
    "Q4": {
        "id": "Q4", "scope": "user", "multi": False,
        "text": "医生确诊过吗？",
        "options": _opts(("yes", "是"), ("no", "否，还没看过"), UNKNOWN),
        "repeat_after_days": None,
    },
    "Q5": {
        "id": "Q5", "scope": "user", "multi": False,
        "text": "医生有说是哪一类吗？",
        "options": _opts(("segmental", "节段型"), ("nonsegmental", "非节段型"), ("mixed", "混合型"),
                         ("unknown", "没说过或不记得")),
        "requires": {"Q4": "yes"},
        "repeat_after_days": None,
    },
    "Q6": {
        "id": "Q6", "scope": "body_site", "multi": False,
        "text": "白斑出现前，这个位置受过外伤或摩擦吗？",
        "options": _opts(("yes", "有"), ("no", "没有"), ("unknown", "不知道")),
        "repeat_after_days": None,
    },
    "Q7": {
        "id": "Q7", "scope": "user", "multi": False,
        "text": "家人或你本人有甲状腺等免疫相关的疾病吗？",
        "options": _opts(("yes", "有"), ("no", "没有"), ("unknown", "不知道"), ("prefer_not", "不想回答")),
        "repeat_after_days": None,
    },
}

# 触发时机 → 候选题（按优先级）。Q6/Q7 只在 checklist 中出现。
TRIGGERS: Dict[str, List[str]] = {
    "record_saved": ["Q1", "Q2"],
    "compare_viewed": ["Q3"],
    "checklist": ["Q4", "Q5", "Q3", "Q6", "Q7"],
}


def _public(q: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": q["id"], "text": q["text"], "options": q["options"], "multi": q["multi"],
        "scope": q["scope"], "version": QUESTION_VERSION,
    }


def _key_site(q: Dict[str, Any], body_site: Optional[str]) -> Optional[str]:
    return body_site if q["scope"] == "body_site" else None


def _latest_fact(db: Session, user_id: int, qid: str, site: Optional[str]) -> Optional[SelfReportFact]:
    query = db.query(SelfReportFact).filter_by(user_id=user_id, question_id=qid)
    query = query.filter(SelfReportFact.body_site == site) if site else query.filter(SelfReportFact.body_site.is_(None))
    return query.order_by(SelfReportFact.id.desc()).first()


def _assessments(db: Session, user_id: int, body_site: Optional[str]):
    q = db.query(VASIAssessment).filter(VASIAssessment.user_id == user_id)
    if body_site:
        q = q.filter(VASIAssessment.body_site == body_site)
    return q


def _gate_open(db: Session, user_id: int, qid: str, body_site: Optional[str], now: datetime) -> bool:
    """题目自身的触发前提（与频率规则无关）。"""
    if qid == "Q1":
        return _assessments(db, user_id, body_site).count() >= 1
    if qid == "Q2":
        rows = _assessments(db, user_id, body_site).order_by(VASIAssessment.created_at.asc()).all()
        if len(rows) >= 2:
            return True
        return bool(rows) and rows[0].created_at is not None and now - rows[0].created_at >= timedelta(days=7)
    return True


def _requires_met(db: Session, user_id: int, q: Dict[str, Any]) -> bool:
    for dep, expected in (q.get("requires") or {}).items():
        fact = _latest_fact(db, user_id, dep, None)
        if fact is None or json.loads(fact.answer_json) != expected:
            return False
    return True


def _answered_and_fresh(db: Session, user_id: int, q: Dict[str, Any], site: Optional[str], now: datetime) -> bool:
    """已作答且无需重问 → True。"""
    fact = _latest_fact(db, user_id, q["id"], site)
    if fact is None:
        return False
    repeat = q.get("repeat_after_days")
    return repeat is None or now - fact.answered_at < timedelta(days=repeat)


def _recently_skipped(db: Session, user_id: int, qid: str, site: Optional[str], now: datetime) -> bool:
    query = db.query(MicroAskLog).filter_by(user_id=user_id, question_id=qid, event="skipped")
    query = query.filter(MicroAskLog.body_site == site) if site else query.filter(MicroAskLog.body_site.is_(None))
    last = query.order_by(MicroAskLog.id.desc()).first()
    return last is not None and now - last.created_at < SKIP_COOLDOWN


def next_questions(
    db: Session,
    user_id: int,
    trigger: str,
    *,
    body_site: Optional[str] = None,
    session_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """返回此刻该问的题（普通触发最多 1 题，checklist 可多题）。会记录 shown。"""
    if trigger not in TRIGGERS:
        raise SelfReportError("BAD_TRIGGER", "未知的触发时机")
    now = now or datetime.utcnow()
    is_checklist = trigger == "checklist"

    if not is_checklist:
        shown_week = (
            db.query(MicroAskLog)
            .filter(
                MicroAskLog.user_id == user_id,
                MicroAskLog.event == "shown",
                MicroAskLog.created_at >= now - WEEKLY_WINDOW,
            )
            .count()
        )
        if shown_week >= WEEKLY_CAP:
            return []
        if session_id and db.query(MicroAskLog).filter_by(
            user_id=user_id, session_id=session_id, event="shown"
        ).first():
            return []

    picked: List[Dict[str, Any]] = []
    for qid in TRIGGERS[trigger]:
        q = QUESTIONS[qid]
        site = _key_site(q, body_site)
        if q["scope"] == "body_site" and not body_site:
            continue
        if _answered_and_fresh(db, user_id, q, site, now):
            continue
        if not _requires_met(db, user_id, q):
            continue
        if not is_checklist:
            if not _gate_open(db, user_id, qid, body_site, now):
                continue
            if _recently_skipped(db, user_id, qid, site, now):
                continue
        picked.append(q)
        if not is_checklist:
            break

    for q in picked:
        db.add(MicroAskLog(
            user_id=user_id, question_id=q["id"], body_site=_key_site(q, body_site),
            event="listed" if is_checklist else "shown", session_id=session_id, created_at=now,
        ))
    if picked:
        db.commit()
    return [_public(q) for q in picked]


def _validate_answer(q: Dict[str, Any], answer: Any) -> Any:
    valid = {o["value"] for o in q["options"]}
    if q["multi"]:
        if not isinstance(answer, list) or not answer:
            raise SelfReportError("BAD_ANSWER", "该题需要选择列表")
        items = list(dict.fromkeys(answer))  # 去重并保持顺序
        if any(not isinstance(i, str) or i not in valid for i in items):
            raise SelfReportError("BAD_ANSWER", "选项不在题目范围内")
        exclusive = set(q.get("exclusive", ()))
        if len(items) > 1 and exclusive.intersection(items):
            raise SelfReportError("BAD_ANSWER", "“没有治疗”和“不确定”不能与其他选项同时选择")
        return items
    if not isinstance(answer, str) or answer not in valid:
        raise SelfReportError("BAD_ANSWER", "选项不在题目范围内")
    return answer


def record_answer(
    db: Session,
    user_id: int,
    question_id: str,
    answer: Any,
    *,
    body_site: Optional[str] = None,
    profile_id: Optional[int] = None,
    session_id: Optional[str] = None,
    source: str = "micro_ask",
) -> SelfReportFact:
    q = QUESTIONS.get(question_id)
    if q is None:
        raise SelfReportError("BAD_QUESTION", "未知的题目")
    if q["scope"] == "body_site" and not body_site:
        raise SelfReportError("SITE_REQUIRED", "该题需要指定部位")
    value = _validate_answer(q, answer)
    if profile_id is not None:
        from web.backend.database.models import PatientProfile

        if not db.query(PatientProfile.id).filter_by(id=profile_id, user_id=user_id).first():
            raise SelfReportError("FORBIDDEN_PROFILE", "档案不属于当前用户")
    site = _key_site(q, body_site)
    fact = SelfReportFact(
        user_id=user_id, profile_id=profile_id, question_id=question_id,
        question_version=QUESTION_VERSION, body_site=site,
        answer_json=json.dumps(value, ensure_ascii=False), source=source,
    )
    db.add(fact)
    db.add(MicroAskLog(
        user_id=user_id, question_id=question_id, body_site=site, event="answered", session_id=session_id,
    ))
    db.commit()
    db.refresh(fact)
    return fact


def dismiss(
    db: Session,
    user_id: int,
    question_id: str,
    *,
    body_site: Optional[str] = None,
    session_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> None:
    q = QUESTIONS.get(question_id)
    if q is None:
        raise SelfReportError("BAD_QUESTION", "未知的题目")
    db.add(MicroAskLog(
        user_id=user_id, question_id=question_id, body_site=_key_site(q, body_site),
        event="skipped", session_id=session_id, created_at=now or datetime.utcnow(),
    ))
    db.commit()


def latest_facts(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """每个（题目, 部位）只返回最新一条。"""
    rows = (
        db.query(SelfReportFact)
        .filter_by(user_id=user_id)
        .order_by(SelfReportFact.id.desc())
        .all()
    )
    seen, out = set(), []
    for r in rows:
        key = (r.question_id, r.body_site)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "question_id": r.question_id, "question_version": r.question_version,
            "body_site": r.body_site, "answer": json.loads(r.answer_json),
            "source": r.source, "answered_at": r.answered_at,
        })
    return out
