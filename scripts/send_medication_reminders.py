"""用药提醒 Web Push 定时发送脚本。

用法（建议由 systemd timer 每分钟运行一次）：
    /root/subskin/.venv/bin/python /root/subskin/scripts/send_medication_reminders.py

逻辑：
- 扫描所有启用中的用药提醒，判断当前时间槽（HH:MM）是否命中 reminder_times
  且日期命中频率（daily / twice_daily / weekly+reminder_days / custom）；
- 命中且未在本次时间槽推送过（last_push_time 防重）→ 向该用户所有活跃的
  Web Push 订阅发送通知（"用药提醒：该吃XX了"）；
- 推送端点 404/410 → 标记订阅失效；单条失败不影响其他（错误隔离 + 日志）。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _bootstrap_db_env() -> None:
    """加载后端 .env 并把相对 sqlite 路径归一为绝对路径（与 auto_generate_reports 一致）。"""
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
                os.environ[k] = v
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite:///./"):
        abs_path = str((Path(PROJECT_ROOT) / db_url[len("sqlite:///./"):]).resolve())
        os.environ["DATABASE_URL"] = "sqlite:///" + abs_path


_bootstrap_db_env()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("medication-reminder")

from web.backend.database.database import SessionLocal  # noqa: E402
from web.backend.database.models import MedicationReminder, PushSubscription  # noqa: E402
from web.backend.services.web_push import send_web_push, PushEndpointGone  # noqa: E402

# 频率 → 命中规则
_FREQ_DAYS = {
    "daily": None,          # 每天
    "twice_daily": None,    # 每天（时间由 reminder_times 决定，空则默认 08:00/20:00）
    "weekly": None,         # 每周（按 reminder_days，默认全周）
    "custom": None,         # 自定义（按 reminder_days，默认全周）
}


def _due_today(reminder: MedicationReminder, now: datetime) -> bool:
    """按频率与日期判断今天是否提醒。"""
    freq = reminder.frequency or "daily"
    if freq in ("daily", "twice_daily"):
        return True
    days = None
    if reminder.reminder_days:
        try:
            days = json.loads(reminder.reminder_days)
        except Exception:
            days = None
    if not days:
        return True  # 未指定日期 → 视为每天
    # 1=周一 ... 7=周日（ISO weekday：周一=1）
    return now.isoweekday() in days


def _due_times(reminder: MedicationReminder) -> list:
    times = []
    if reminder.reminder_times:
        try:
            times = [str(t)[:5] for t in json.loads(reminder.reminder_times)]
        except Exception:
            times = []
    if not times and (reminder.frequency == "twice_daily"):
        times = ["08:00", "20:00"]
    return [t for t in times if len(t) == 5 and ":" in t]


def main() -> None:
    now = datetime.now()
    slot = now.strftime("%Y-%m-%d %H:%M")

    db = SessionLocal()
    sent_count = 0
    reminders = []
    try:
        reminders = (
            db.query(MedicationReminder)
            .filter(MedicationReminder.is_active.is_(True))
            .all()
        )
        for r in reminders:
            if not _due_today(r, now):
                continue
            if now.strftime("%H:%M") not in _due_times(r):
                continue
            if r.last_push_time == slot:
                continue  # 本时间槽已推送

            subs = (
                db.query(PushSubscription)
                .filter(
                    PushSubscription.user_id == r.user_id,
                    PushSubscription.is_active.is_(True),
                )
                .all()
            )
            if not subs:
                # 无订阅也记录槽位，避免每分钟重复扫描
                r.last_push_time = slot
                continue

            dosage = f" · {r.dosage}" if r.dosage else ""
            body = f"该吃「{r.medication_name}」了{dosage}"
            if r.notes:
                body += f"（{r.notes}）"
            payload = {
                "title": "用药提醒",
                "body": body,
                "tag": f"subskin-med-{r.id}",
            }
            for sub in subs:
                try:
                    ok = send_web_push(
                        sub.endpoint, sub.p256dh_key, sub.auth_key, payload
                    )
                    if ok:
                        sent_count += 1
                except PushEndpointGone:
                    sub.is_active = False
                    logger.info("订阅端点失效，标记停用 user=%s endpoint=%s...", r.user_id, sub.endpoint[:80])
            r.last_push_time = slot
        db.commit()
    finally:
        db.close()
    logger.info("用药提醒扫描完成：发送 %s 条（时间槽 %s，共 %s 条提醒）", sent_count, slot, len(reminders))


if __name__ == "__main__":
    main()
