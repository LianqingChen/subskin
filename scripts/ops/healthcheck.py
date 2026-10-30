#!/usr/bin/env python
"""SubSkin health monitor with email alerts (run every minute by systemd).

A check alerts after FAIL_THRESHOLD consecutive failures, re-alerts at most every
REPEAT_SECONDS while still failing, and sends a recovery email when it clears.
Recipient: ALERT_EMAIL_TO if set, else the SMTP_FROM address.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import smtplib
import socket
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / "web" / "backend" / ".env"
BACKUP_DIR = REPO_ROOT / "data" / "backups"
STATE_FILE = Path("/var/lib/subskin-health/state.json")
FAIL_THRESHOLD = 3
REPEAT_SECONDS = 6 * 3600
DISK_MAX_PCT = 85
MEM_MIN_AVAIL_PCT = 10
BACKUP_MAX_AGE_H = 26
CERT_MIN_DAYS = 14
CERT_HOST = "subskin.cn"


def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("SMTP_", "ALERT_"))})
    return env


def http_ok(url: str, expect: str) -> tuple:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read(4096).decode("utf-8", "replace")
            if resp.status == 200 and expect in body:
                return True, f"HTTP {resp.status}"
            return False, f"HTTP {resp.status}, body: {body[:200]}"
    except Exception as e:  # noqa: BLE001 - any failure is a failed probe
        return False, f"{type(e).__name__}: {e}"


def check_backend() -> tuple:
    return http_ok("http://127.0.0.1:8000/api/health", '"ok"')


def check_site() -> tuple:
    return http_ok(f"https://{CERT_HOST}/version.json", "buildTime")


def check_disk() -> tuple:
    usage = shutil.disk_usage("/")
    pct = usage.used * 100 / usage.total
    return pct <= DISK_MAX_PCT, f"/ used {pct:.1f}% ({usage.free / 2**30:.1f} GB free)"


def check_memory() -> tuple:
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    pct = info["MemAvailable"] * 100 / info["MemTotal"]
    return pct >= MEM_MIN_AVAIL_PCT, f"MemAvailable {pct:.1f}% ({info['MemAvailable'] // 1024} MB)"


def check_backup() -> tuple:
    files = [p for p in BACKUP_DIR.glob("subskin-*") if p.is_file()] if BACKUP_DIR.exists() else []
    files = [p for p in files if p.name[8:9].isdigit()]
    if not files:
        return False, "no timestamped backups found"
    newest = max(files, key=lambda p: p.stat().st_mtime)
    age_h = (time.time() - newest.stat().st_mtime) / 3600
    return age_h <= BACKUP_MAX_AGE_H, f"newest {newest.name}, {age_h:.1f}h old"


def check_cert() -> tuple:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((CERT_HOST, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=CERT_HOST) as tls:
                not_after = tls.getpeercert()["notAfter"]
        expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), timezone.utc)
        days = (expires - datetime.now(timezone.utc)).days
        return days >= CERT_MIN_DAYS, f"expires {expires:%Y-%m-%d} ({days} days)"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


CHECKS = {
    "backend_api": check_backend,
    "site_frontend": check_site,
    "disk": check_disk,
    "memory": check_memory,
    "backup_fresh": check_backup,
    "tls_cert": check_cert,
}


def send_email(env: dict, subject: str, body: str) -> None:
    host = env.get("SMTP_HOST", "")
    port = int(env.get("SMTP_PORT", "465") or 465)
    user = env.get("SMTP_USER", "")
    password = env.get("SMTP_PASSWORD", "")
    from_name, from_addr = parseaddr(env.get("SMTP_FROM") or user)
    to_addr = parseaddr(env.get("ALERT_EMAIL_TO") or from_addr)[1]
    if not (host and user and password and to_addr):
        raise RuntimeError("SMTP not configured (SMTP_HOST/USER/PASSWORD/FROM)")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(from_name or "SubSkin Monitor", "utf-8")), from_addr))
    msg["To"] = to_addr
    server = smtplib.SMTP_SSL(host, port, timeout=20) if port == 465 else smtplib.SMTP(host, port, timeout=20)
    try:
        if port != 465:
            server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
    finally:
        server.quit()


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(STATE_FILE)


def run_checks(env: dict, verbose: bool) -> int:
    state = load_state()
    now = time.time()
    host = socket.gethostname()
    any_fail = False
    for name, fn in CHECKS.items():
        ok, detail = fn()
        s = state.setdefault(name, {"fails": 0, "alerted_at": 0, "alerting": False})
        if verbose:
            print(f"{'OK  ' if ok else 'FAIL'} {name}: {detail}")
        if ok:
            if s["alerting"]:
                _notify(env, f"[SubSkin 恢复] {name}", f"{name} 已恢复正常\n{detail}\n主机: {host}\n时间: {_ts()}")
            state[name] = {"fails": 0, "alerted_at": 0, "alerting": False, "detail": detail}
            continue
        any_fail = True
        s["fails"] += 1
        s["detail"] = detail
        due = s["fails"] >= FAIL_THRESHOLD and (not s["alerting"] or now - s["alerted_at"] >= REPEAT_SECONDS)
        if due and _notify(env, f"[SubSkin 告警] {name} 异常",
                           f"{name} 连续 {s['fails']} 次检查失败\n{detail}\n主机: {host}\n时间: {_ts()}\n"
                           f"排查: systemctl status subskin-backend / journalctl -u subskin-backend -n 100"):
            s["alerting"] = True
            s["alerted_at"] = now
    save_state(state)
    return 1 if any_fail else 0


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()


def _notify(env: dict, subject: str, body: str) -> bool:
    try:
        send_email(env, subject, body)
        print(f"alert sent: {subject}")
        return True
    except Exception as e:  # noqa: BLE001 - next run retries
        print(f"alert send FAILED ({subject}): {type(e).__name__}: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-alert", action="store_true", help="send one test email and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    env = load_env()
    if args.test_alert:
        ok = _notify(env, "[SubSkin 监控] 测试告警邮件",
                     f"这是一封测试邮件，说明 SubSkin 健康监控的邮件告警通道可用。\n主机: {socket.gethostname()}\n时间: {_ts()}")
        return 0 if ok else 1
    return run_checks(env, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
