#!/usr/bin/env python3
"""一次性脚本：轮换存量管理员的弱口令（幂等）。

背景：
- .env 中 ADMIN_USER/ADMIN_PASS 已轮换为强随机值，但 init_db 只在
  首次初始化时创建管理员（database/init_db.py L140-141），不影响存量记录。
- 若存量管理员账号密码仍是 "admin" 等弱口令，本脚本将其更新为
  .env 中新的 ADMIN_PASS。

行为（幂等）：
1. 找出所有 is_admin=True 的用户；
2. 逐个用弱口令候选列表（默认 ["admin", "123456", "password"]，
   可用 --weak 追加）校验 users.hashed_password 与
   user_credentials(cred_type='password') 中的哈希；
3. 仅当命中弱口令时，更新为新密码哈希（两处都更新）；已非弱口令则跳过。

用法：
    python scripts/rotate_admin_password.py [--db data/subskin.db] [--dry-run]
    python scripts/rotate_admin_password.py --weak admin --weak admin123

注意：请在部署窗口执行；执行前建议备份数据库文件。
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / "web" / "backend" / ".env")

from passlib.context import CryptContext  # noqa: E402

DEFAULT_WEAK_PASSWORDS = ["admin", "123456", "password", "admin123"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _matches_any_weak(plain_hash: str, weak_list) -> bool:
    if not plain_hash:
        return False
    for weak in weak_list:
        try:
            if pwd_context.verify(weak, plain_hash):
                return True
        except Exception:
            continue
    return False


def _extract_hash_from_credential_data(credential_data) -> str:
    """user_credentials.credential_data 兼容两种格式：JSON 或裸哈希。"""
    if not credential_data:
        return ""
    try:
        payload = json.loads(credential_data)
        if isinstance(payload, dict):
            return payload.get("hashed_password") or ""
    except (ValueError, TypeError):
        pass
    return credential_data


def main() -> int:
    parser = argparse.ArgumentParser(description="轮换存量管理员弱口令")
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "data" / "subskin.db"),
        help="SQLite 数据库路径（默认 data/subskin.db）",
    )
    parser.add_argument(
        "--weak",
        action="append",
        default=None,
        help="追加弱口令候选（可多次指定）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只报告不修改")
    args = parser.parse_args()

    new_password = os.getenv("ADMIN_PASS", "")
    if not new_password or new_password in ("admin", ""):
        print("❌ .env 中 ADMIN_PASS 未配置或仍是弱口令，请先轮换 .env")
        return 1
    if len(new_password) < 12:
        print("❌ ADMIN_PASS 长度不足 12 位，拒绝执行")
        return 1

    weak_list = list(DEFAULT_WEAK_PASSWORDS) + (args.weak or [])

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        return 1

    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{db_path}")
    new_hash = pwd_context.hash(new_password)
    rotated = 0

    with engine.begin() as conn:
        admins = conn.execute(
            text("SELECT id, username, hashed_password FROM users WHERE is_admin = 1")
        ).fetchall()
        if not admins:
            print("ℹ️  未找到管理员账号，无需处理")
            return 0

        for row in admins:
            user_id, username, hashed = row[0], row[1], row[2] or ""
            cred_row = conn.execute(
                text(
                    "SELECT id, credential_data FROM user_credentials "
                    "WHERE user_id = :uid AND cred_type = 'password'"
                ),
                {"uid": user_id},
            ).fetchone()
            cred_hash = (
                _extract_hash_from_credential_data(cred_row[1]) if cred_row else ""
            )

            user_weak = _matches_any_weak(hashed, weak_list)
            cred_weak = _matches_any_weak(cred_hash, weak_list)

            if not (user_weak or cred_weak):
                print(f"⏭️  管理员 {username}(id={user_id}) 非弱口令，跳过")
                continue

            print(
                f"🔐 管理员 {username}(id={user_id}) 命中弱口令"
                f"（users表={'是' if user_weak else '否'}, credentials表={'是' if cred_weak else '否'}）"
            )
            if args.dry_run:
                rotated += 1
                continue

            if user_weak:
                conn.execute(
                    text(
                        "UPDATE users SET hashed_password = :h, "
                        "updated_at = datetime('now') WHERE id = :uid"
                    ),
                    {"h": new_hash, "uid": user_id},
                )
            if cred_row is not None and cred_weak:
                new_cred_data = json.dumps(
                    {"hashed_password": new_hash}, ensure_ascii=False
                )
                conn.execute(
                    text(
                        "UPDATE user_credentials SET credential_data = :d, "
                        "verified = 1, updated_at = datetime('now') WHERE id = :cid"
                    ),
                    {"d": new_cred_data, "cid": cred_row[0]},
                )
            rotated += 1

    verb = "将被轮换" if args.dry_run else "已轮换"
    print(f"✅ 完成：{verb} {rotated} 个弱口令管理员账号")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
