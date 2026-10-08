"""
自然周/自然月健康报告自动生成 + 站内通知。

用法（建议每天凌晨由 systemd timer 运行一次）：
    /root/subskin/.venv/bin/python /root/subskin/scripts/auto_generate_reports.py

逻辑：
- 今天是周一 → 为「上周（自然周：周一~周日）有数据」的用户自动生成健康周报；
- 今天是当月 1 号 → 为「上月（自然月）有数据」的用户自动生成健康月报；
- 幂等：同用户同周期已存在报告则跳过（不会重复生成）；
- 生成成功后发站内通知（ref_type='skin_report', ref_id=报告ID），用户点击即可查看；
- 单个用户失败不影响其他用户（错误隔离 + 日志）。

数据源：白斑照片/测评(VASI)/体检报告/分享日记/AI问答，任一有数据即纳入。
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import List, Set, Tuple

# 项目根目录入 path，保证 web.backend.* 可导入（与后端一致）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _bootstrap_db_env() -> None:
    """加载后端 .env 并把相对 sqlite 路径归一为绝对路径。

    后端 systemd 使用 EnvironmentFile=web/backend/.env（DATABASE_URL=sqlite:///./data/subskin.db）
    且 WorkingDirectory=/root/subskin，实际库为 /root/subskin/data/subskin.db。
    这里显式加载同一份 .env 并归一化，避免被外部 shell 导出的（可能指向旧库的）DATABASE_URL 干扰。
    """
    env_file = Path(PROJECT_ROOT) / "web" / "backend" / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                # 覆盖式加载：以后端 .env 为准，避免被外部 shell 导出的旧 DATABASE_URL 干扰
                os.environ[k] = v
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite:///./"):
        abs_path = str((Path(PROJECT_ROOT) / db_url[len("sqlite:///./"):]).resolve())
        os.environ["DATABASE_URL"] = "sqlite:///" + abs_path


_bootstrap_db_env()

from sqlalchemy import or_  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("auto_generate_reports")

# 单次运行安全上限：每个周期最多处理这么多用户，避免极端情况长时间占用
MAX_USERS_PER_PERIOD = 500


def _period_datetime_range(d_start: date, d_end: date):
    from datetime import datetime

    start = datetime(d_start.year, d_start.month, d_start.day)
    end = start + timedelta(days=(d_end - d_start).days + 1)
    return start, end


def _active_user_ids(db, d_start: date, d_end: date) -> Set[int]:
    """返回周期内有任一数据源的活跃用户 id 集合。"""
    from web.backend.database.models import (
        Conversation,
        MedicalReport,
        Message,
        Post,
        PostImage,
    )
    from web.backend.models.vasi import VASIAssessment

    start_dt, end_dt = _period_datetime_range(d_start, d_end)
    ids: Set[int] = set()

    def _collect(rows):
        for (u,) in rows:
            if u:
                ids.add(int(u))

    # 1. 白斑照片（日记图，按拍摄日期或创建时间）
    _collect(
        db.query(PostImage.user_id)
        .filter(
            PostImage.user_id.isnot(None),
            or_(
                PostImage.capture_date.between(d_start, d_end),
                PostImage.created_at.between(start_dt, end_dt),
            ),
        )
        .all()
    )

    # 2. VASI 测评
    _collect(
        db.query(VASIAssessment.user_id)
        .filter(
            VASIAssessment.user_id.isnot(None),
            VASIAssessment.created_at.between(start_dt, end_dt),
        )
        .all()
    )

    # 3. 体检报告
    _collect(
        db.query(MedicalReport.user_id)
        .filter(
            MedicalReport.user_id.isnot(None),
            MedicalReport.created_at.between(start_dt, end_dt),
        )
        .all()
    )

    # 4. 分享/日记帖子
    _collect(
        db.query(Post.user_id)
        .filter(
            Post.user_id.isnot(None),
            or_(
                Post.diary_date.between(d_start, d_end),
                Post.created_at.between(start_dt, end_dt),
            ),
        )
        .all()
    )

    # 5. AI 问答（用户消息）
    _collect(
        db.query(Conversation.user_id)
        .join(Message, Message.conversation_id == Conversation.conversation_id)
        .filter(
            Conversation.user_id.isnot(None),
            Message.role == "user",
            Message.created_at.between(start_dt, end_dt),
        )
        .distinct()
        .all()
    )

    return ids


def _run_period(period_type: str, anchor: date) -> int:
    """为指定周期（weekly/monthly）的活跃用户生成报告并通知，返回成功数。"""
    from web.backend.database.database import SessionLocal
    from web.backend.services.skin_report import (
        PERIOD_TYPE_NAMES,
        _period_window,
        generate_periodic_report,
    )
    from web.backend.api.notifications import create_notification

    period_name = PERIOD_TYPE_NAMES.get(period_type, period_type)
    d_start, d_end = _period_window(period_type, anchor)
    logger.info("开始生成%s：%s ~ %s", period_name, d_start.isoformat(), d_end.isoformat())

    # 先查活跃用户（独立 session，避免长事务）
    probe_db = SessionLocal()
    try:
        user_ids = _active_user_ids(probe_db, d_start, d_end)
    finally:
        probe_db.close()

    if not user_ids:
        logger.info("%s 无活跃用户，跳过", period_name)
        return 0

    user_ids = sorted(user_ids)[:MAX_USERS_PER_PERIOD]
    logger.info("%s 活跃用户 %d 人，开始逐个生成", period_name, len(user_ids))

    success = 0
    for idx, user_id in enumerate(user_ids, 1):
        db = SessionLocal()
        try:
            report, created = generate_periodic_report(
                db, user_id, period_type, anchor_date=anchor
            )
            if created:
                create_notification(
                    db,
                    user_id,
                    type="system",
                    title=f"你的健康{period_name}已生成",
                    body=f"{d_start.strftime('%m月%d日')}~{d_end.strftime('%m月%d日')}的白斑、心情、体检变化已汇总，点击查看",
                    ref_type="skin_report",
                    ref_id=report.id,
                )
                success += 1
                logger.info("[%d/%d] 用户 %s 已生成%s #%s", idx, len(user_ids), user_id, period_name, report.id)
            else:
                logger.info("[%d/%d] 用户 %s 已存在%s，跳过", idx, len(user_ids), user_id, period_name)
        except Exception:
            logger.exception("[%d/%d] 用户 %s 生成%s失败", idx, len(user_ids), user_id, period_name)
            db.rollback()
        finally:
            db.close()

    logger.info("%s 完成：成功 %d / 活跃 %d", period_name, success, len(user_ids))
    return success


def main() -> None:
    today = date.today()
    periods: List[Tuple[str, date]] = []

    # 自然周：今天是周一 → 生成「上周」
    if today.weekday() == 0:
        periods.append(("weekly", today - timedelta(days=7)))
    # 自然月：今天是 1 号 → 生成「上月」
    if today.day == 1:
        if today.month == 1:
            anchor = date(today.year - 1, 12, 1)
        else:
            anchor = date(today.year, today.month - 1, 1)
        periods.append(("monthly", anchor))

    if not periods:
        logger.info("今天无需自动生成（非周一/非月初），退出")
        return

    started = time.time()
    for period_type, anchor in periods:
        _run_period(period_type, anchor)
    logger.info("自动生成全部完成，耗时 %.1fs", time.time() - started)


if __name__ == "__main__":
    main()
