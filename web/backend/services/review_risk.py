"""医评风控规则引擎（服务端）。

设计依据：``docs/specs/2026-09-11-medical-review-v3-design.md`` 第五节，
法规约束见 ``docs/specs/2026-09-11-medical-review-research.md`` E 节。

本模块是**纯函数**模块（不导入 FastAPI / SQLAlchemy），便于单测与复用：

1. 统一评分体系常量 —— 6 维就医体验档位 + **疗效/医术维度黑名单**
   （《广告法》16 条、《医疗广告管理办法》7 条：不得宣传治愈率、有效率、
   不得利用患者名义作证明，因此平台既不采集也不聚合疗效维度）。
2. 文本风险扫描 —— 情绪宣泄、断言性指控、指名贬损、组织化维权、疗效夸大、
   联系方式与引流、他人病历号。评分可解释（每命中一项都有标签与改写建议）。
3. 医生称谓脱敏 —— 只保留「张医生（皮肤科）」式不可识别称谓
   （《基本医疗卫生与健康促进法》57 条 + 名誉权判例）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── 统一评价体系常量 ────────────────────────────────────────────────────────

#: 6 维就医体验（维度名对齐国家卫健委满意度调查的维度名，见调研报告 C 节）
EXPERIENCE_DIMENSIONS: Tuple[str, ...] = (
    "挂号与预约",
    "候诊与流程",
    "医患沟通",
    "费用与告知",
    "复诊与连续性",
    "环境与隐私",
)

#: 四档 + 「没体验过」不适用档（非对称档位，减少情绪极化与刷分动机）
EXPERIENCE_LEVELS: Tuple[str, ...] = ("satisfied", "neutral", "unsatisfied", "na")

EXPERIENCE_LEVEL_LABELS: Dict[str, str] = {
    "satisfied": "满意",
    "neutral": "一般",
    "unsatisfied": "不满意",
    "na": "没体验过",
}

#: 禁止采集/聚合的评价维度（命中即拒绝写入）
BANNED_DIMENSIONS: Tuple[str, ...] = (
    "疗效", "治愈", "治愈率", "有效率", "好转率", "好转", "医术", "技术水平",
    "诊断准确", "误诊率", "死亡率", "复发率", "并发症", "根治", "排名", "排行",
    "最好", "第一", "推荐度",
)

#: 禁止出现在评价中的疗效/推广类用语（好评差评同一词库）
#: 调研实测：好大夫被拒评价中约 85% 是好评 —— 只审差评会漏掉变相推荐位。
PROMOTION_TERMS: Tuple[str, ...] = (
    "根治", "治愈", "包治", "断根", "永不复发", "100%治愈", "百治百愈",
    "偏方根治", "祖传秘方", "特效药", "包好", "药到病除", "一劳永逸",
    "彻底治愈", "永不扩散", "保证治好", "完全康复", "痊愈了", "治好了",
    "都去这家", "强烈推荐这家", "必须去", "别去别家", "包治百病",
)

#: 侮辱性言辞（名誉权判例中直接导致败诉的表述类型）
INSULT_TERMS: Tuple[str, ...] = (
    "骗子", "骗钱", "黑心", "无良", "谋财害命", "没医德", "医德败坏",
    "庸医", "垃圾医院", "垃圾医生", "坑人", "害人", "不要脸", "畜生",
    "去死", "滚出", "黑店", "抢钱",
)

#: 断言性指控（无证据的结论性指控）
DEFAMATION_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"就是(?:误诊|错诊)", "断言「就是误诊」"),
    (r"肯定(?:是|就是)(?:医疗事故|误诊|治坏)", "断言「肯定是医疗事故」"),
    (r"(?:害|毁)(?:了)?我", "断言对方「害了我」"),
    (r"(?:把|给)我(?:治|看)(?:坏|死|残)", "断言被治坏/治残"),
    (r"(?:根本|完全)不(?:会|懂)(?:看病|治疗)", "断言医生不会看病"),
)

#: 组织化 / 聚众维权 / 曝光（平台不承载组织化维权，应引导到法定渠道）
ORGANIZED_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"大家一起", "号召「大家一起」"),
    (r"维权群", "提及「维权群」"),
    (r"曝光(?:他|她|这家|该院)", "号召「曝光」"),
    (r"(?:联名|集体)(?:投诉|举报|上访)", "号召联名/集体投诉"),
    (r"(?:拉|建)(?:个)?群", "组织建群"),
)

#: 引流/广告
AD_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"(?:加|留)(?:我)?(?:微信|weixin|vx|v信|扣扣|qq)", "引导加私人联系方式"),
    (r"(?:私聊|私信)我", "引导私聊"),
    (r"(?:代购|转卖|出售)(?:药|号|名额)", "药品/号源交易"),
)

#: 他人病历/住院/检验单号（《医疗纠纷预防和处理条例》15/42 条：可复制 ≠ 可公开）
RECORD_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"病历号\s*[:：]?\s*\w{4,}", "出现病历号"),
    (r"住院号\s*[:：]?\s*\w{4,}", "出现住院号"),
    (r"(?:检验|检查)单号\s*[:：]?\s*\w{4,}", "出现检验/检查单号"),
)

#: 转述/无亲身经历的线索（好大夫评价规范要求「内容须基于事实、有亲身经历」）
HEARSAY_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"(?:听|据)(?:说|朋友说|别人说|同事说)", "内容含转述（非亲身经历）"),
    (r"(?:网上|群里)(?:都)?(?:说|传)", "内容含网传信息"),
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


# ── 风险标签 ────────────────────────────────────────────────────────────────


@dataclass
class RiskFlag:
    """一条命中的风险规则。"""

    code: str
    category: str
    weight: int
    detail: str
    hint: str = ""          # 给作者的改写建议
    hard_block: bool = False  # 是否强制拦截（不可仅靠确认绕过）

    def to_dict(self) -> dict:
        return {
            "code": self.code, "category": self.category, "weight": self.weight,
            "detail": self.detail, "hint": self.hint, "hard_block": self.hard_block,
        }


@dataclass
class RiskAssessment:
    """风险评分结果（可解释）。"""

    score: int = 0
    level: str = "safe"          # safe / watch / restricted / high
    flags: List[RiskFlag] = field(default_factory=list)
    blocked: bool = False        # 是否必须拦截提交
    hints: List[str] = field(default_factory=list)

    @property
    def categories(self) -> List[str]:
        seen: List[str] = []
        for flag in self.flags:
            if flag.category not in seen:
                seen.append(flag.category)
        return seen

    def to_dict(self) -> dict:
        return {
            "score": self.score, "level": self.level, "blocked": self.blocked,
            "categories": self.categories, "hints": self.hints,
            "flags": [f.to_dict() for f in self.flags],
        }


def level_for_score(score: int) -> str:
    """评分 → 风险档位（与设计文档 5.2 的分档一致）。"""
    if score >= 80:
        return "high"
    if score >= 60:
        return "restricted"
    if score >= 30:
        return "watch"
    return "safe"


def moderation_status_for_level(level: str) -> str:
    """风险档位 → ``hospital_reviews.moderation_status``。"""
    return {"high": "blocked", "restricted": "restricted", "watch": "flagged"}.get(level, "approved")


def aggregate_delay_seconds(level: str) -> int:
    """聚合冷处理时长（**只延迟进入聚合，不延迟发布**）。

    - safe：无需复核，立即可聚合（否则每条评价都要等 30 分钟才出现在标签云里，
      对正常用户是无谓的成本）；
    - watch（30 分钟）：情绪化/结论性表述，给人工复核留窗口，同时钝化瞬时刷评；
    - restricted / high：本来就不进聚合，无需延迟。

    调用方还可叠加异常集中度检查（同一用户短时间内对同一医院的重复评价）延长冷处理。
    """
    return {"watch": 1800}.get(level, 0)


# ── 医生称谓脱敏 ────────────────────────────────────────────────────────────



def sanitize_doctor_name(raw: Optional[str], department: Optional[str] = None) -> Optional[str]:
    """把用户填写的医生标识转成不可识别的称谓。

    《基本医疗卫生与健康促进法》第 57 条（医疗卫生人员人格尊严不受侵犯）
    与多起名誉权判例（指名贬损被判赔/道歉）要求平台不能公开展示可识别的
    医护人员身份，因此这里统一收敛为「张医生（皮肤科）」形式：

    - ``张三`` / ``张三医生`` / ``张医生`` → ``张医生``
    - ``张三丰主任医师`` → ``张主任``
    - 无法识别姓氏 → ``某医生``
    - 科室本身不构成个人身份，可保留（对齐「张医生（皮肤科）」范式）
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None

    if "主任" in text:
        honorific = "主任"
    elif "教授" in text:
        honorific = "教授"
    else:
        honorific = "医生"

    core = re.sub(
        r"(主任医师|副主任医师|主治医师|住院医师|主任|教授|医师|医生|大夫|老师)",
        "", text,
    ).strip("　 ·,，.。")
    match = re.search(r"[\u4e00-\u9fa5A-Za-z]", core)
    label = f"{match.group(0)}{honorific}" if match else f"某{honorific}"

    dept = re.sub(r"[（）()\s]", "", (department or ""))[:20]
    return f"{label}（{dept}）" if dept else label


# ── 文本风险扫描 ────────────────────────────────────────────────────────────


def _add(flags: List[RiskFlag], code: str, category: str, weight: int, detail: str,
         hint: str = "", hard_block: bool = False) -> None:
    if any(f.code == code for f in flags):
        return
    flags.append(RiskFlag(code=code, category=category, weight=weight,
                          detail=detail, hint=hint, hard_block=hard_block))


def scan_text(
    text: str,
    doctor_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[RiskFlag]:
    """扫描评价文本，返回命中的风险标签列表。"""
    content = (text or "").strip()
    flags: List[RiskFlag] = []
    if not content:
        return flags

    for term in PROMOTION_TERMS:
        if term in content:
            _add(flags, f"promotion:{term}", "疗效夸大", 45,
                 f"出现「{term}」",
                 "请改为第一人称的过程描述，例如「我治疗后白斑有变化」，不要写「根治/治愈」。",
                 hard_block=True)
            break

    for term in INSULT_TERMS:
        if term in content:
            # 侮辱性言辞是《民法典》1025 条舆论监督抗辩明确排除的情形，也是判例中
            # 直接导致败诉的表述，因此硬拦截并给出「对事不对人」的改写建议
            # （《互联网信息服务管理办法》15 条禁止发布侮辱、诽谤他人的信息）。
            _add(flags, f"insult:{term}", "侮辱性言辞", 40,
                 f"出现「{term}」",
                 "把对人的评价改成对事的描述：把「XX 就是骗子」改成「我这次的费用构成没有提前告知」。",
                 hard_block=True)
            break

    for pattern, detail in DEFAMATION_PATTERNS:
        if re.search(pattern, content):
            _add(flags, f"defamation:{pattern}", "断言性指控", 35, detail,
                 "如果你认为诊疗存在问题，可以写清时间、经过和沟通过程，结论由鉴定或调解机构作出。")
            break

    if doctor_name and doctor_name.strip():
        if any(term in content for term in INSULT_TERMS) or re.search(r"(?:就是|肯定|根本).{0,6}(?:骗|坑|害|坏)", content):
            _add(flags, "named_accusation", "指名指控", 30,
                 "内容同时出现具体医护称谓与贬损性表述",
                 "建议只描述你经历的服务过程，不针对具体医护人员下结论。")

    for pattern, detail in ORGANIZED_PATTERNS:
        if re.search(pattern, content):
            _add(flags, f"organized:{pattern}", "组织化维权", 45, detail,
                 "组织集体维权不在本平台进行；可以走医院医患办、医疗纠纷人民调解委员会或 12345。",
                 hard_block=False)
            break

    for pattern, detail in AD_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            _add(flags, f"ad:{pattern}", "引流广告", 40, detail,
                 "请不要在评价里留联系方式或做药品、号源交易。",
                 hard_block=True)
            break

    for pattern, detail in RECORD_PATTERNS:
        if re.search(pattern, content):
            _add(flags, f"record:{pattern}", "他人病历信息", 40, detail,
                 "病历、检验单属于个人健康信息，请不要公开具体单号。")
            break

    if _PHONE_RE.search(content) or _ID_RE.search(content) or _EMAIL_RE.search(content):
        # 权重刻意 <30：联系方式会被自动脱敏，属于「可自动修复」而非需要人工复核的风险，
        # 不应因此把正常评价推进冷静确认或聚合冷处理。
        _add(flags, "contact_info", "联系方式", 20, "出现手机号/邮箱/证件号",
             "系统会自动脱敏，建议直接删除这些信息。")

    if any(p in content for p in ("加微信", "加个微信", "私聊", "私信")) and doctor_name:
        _add(flags, "solicit_contact", "引流广告", 30, "引导私下联系医护人员",
             "平台不允许通过评价建立私下联系。")

    for pattern, detail in HEARSAY_PATTERNS:
        if re.search(pattern, content):
            _add(flags, f"hearsay:{pattern}", "非亲身经历", 15, detail,
                 "只写你自己经历的部分更有参考价值。")
            break

    # 情绪强度：连续感叹号 / 连续问号 / 全大写英文
    if re.search(r"[!！]{3,}", content) or re.search(r"[?？]{4,}", content):
        _add(flags, "emotional_punctuation", "情绪强度", 12, "连续感叹号/问号",
             "语气平和的描述更容易被其他病友采信。")
    letters = re.findall(r"[A-Za-z]", content)
    if len(letters) >= 12 and all(c.isupper() for c in letters):
        _add(flags, "emotional_caps", "情绪强度", 10, "大段全大写英文",
             "建议改用正常大小写。")

    # 标签里若混入疗效类标签同样拦截（防止绕过正文校验）
    for tag in tags or []:
        if any(banned in str(tag) for banned in BANNED_DIMENSIONS):
            _add(flags, "banned_tag", "疗效夸大", 45, f"标签含禁止维度「{tag}」",
                 "疗效类标签不采集，请改用中性体验标签。", hard_block=True)
            break

    return flags


def score_review(
    text: str,
    doctor_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> RiskAssessment:
    """综合评分：命中权重求和（封顶 100）。"""
    flags = scan_text(text, doctor_name=doctor_name, tags=tags)
    score = min(100, sum(f.weight for f in flags))
    level = level_for_score(score)
    hints: List[str] = []
    for flag in flags:
        if flag.hint and flag.hint not in hints:
            hints.append(flag.hint)
    return RiskAssessment(
        score=score, level=level, flags=flags,
        blocked=any(f.hard_block for f in flags),
        hints=hints[:4],
    )


# ── 维度档位校验 ────────────────────────────────────────────────────────────


def clean_experience_scores(raw: Optional[Dict[str, str]]) -> Dict[str, str]:
    """校验并清洗 6 维体验档位。

    拒绝任何黑名单维度（疗效/医术等），拒绝非法档位取值。
    """
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if name not in EXPERIENCE_DIMENSIONS:
            continue
        level = str(value).strip()
        if level not in EXPERIENCE_LEVELS:
            continue
        out[name] = level
    return out


def dimension_distribution(rows) -> List[dict]:
    """把 (experience_scores) 行集合聚合为 6 维计数分布。

    输出包含「没体验过」档 —— 诚实度开关，也天然抑制刷分。
    """
    counts: Dict[str, Dict[str, int]] = {
        dim: {level: 0 for level in EXPERIENCE_LEVELS} for dim in EXPERIENCE_DIMENSIONS
    }
    total = 0
    for scores in rows:
        if not isinstance(scores, dict):
            continue
        total += 1
        for dim, level in scores.items():
            if dim in counts and level in counts[dim]:
                counts[dim][level] += 1
    return [
        {"dimension": dim, "total": sum(counts[dim].values()), **counts[dim]}
        for dim in EXPERIENCE_DIMENSIONS
    ]
