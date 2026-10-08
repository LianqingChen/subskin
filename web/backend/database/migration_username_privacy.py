"""一次性迁移：把 username 直接等于手机号（或呈手机号格式）的存量用户
改名为脱敏形式 138****2222，消除 L3 手机号通过公开渠道泄露。

背景：早期 register_by_phone 将 username 设为手机号，而 username 会出现在
公开主页、帖子/评论作者、关注列表等渠道。

幂等：重复执行不会产生副作用。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy.orm import Session  # noqa: E402

from web.backend.database.database import SessionLocal  # noqa: E402
from web.backend.database.models import User, PatientProfile  # noqa: E402

PHONE_RE = re.compile(r"^1\d{10}$")


def _mask(phone: str) -> str:
    return f"{phone[:3]}****{phone[7:]}"


def migrate(db: Session) -> int:
    changed = 0
    users = db.query(User).all()
    taken = {u.username for u in users}
    for user in users:
        username = (user.username or "").strip()
        if not username:
            continue
        # 仅处理：username 与绑定手机号一致，或 username 本身是手机号格式
        if username == (user.phone or "").strip() or PHONE_RE.match(username):
            source = user.phone or username
            new_name = _mask(source)
            base = new_name
            suffix = 1
            while new_name in taken:
                suffix += 1
                new_name = f"{base}_{suffix}"
            user.username = new_name
            taken.discard(username)
            taken.add(new_name)
            changed += 1
            print(f"user id={user.id}: {username[:3]}*** -> {new_name}")
    db.commit()

    # 白友档案（patient_profiles）的 name 同样可能是手机号（历史上自动档案直接
    # 用 username=手机号 作为档案名）。对手机号格式的档案名做脱敏。
    phone_by_user = {u.id: (u.phone or "").strip() for u in users}
    username_by_user = {u.id: (u.username or "").strip() for u in users}
    profiles = db.query(PatientProfile).all()
    profile_changed = 0
    for profile in profiles:
        name = (profile.name or "").strip()
        if not name:
            continue
        owner_phone = phone_by_user.get(profile.user_id, "")
        if name == owner_phone or PHONE_RE.match(name):
            # 优先回退到该用户当前的（已脱敏）昵称，否则用手机号脱敏形式
            fallback = username_by_user.get(profile.user_id) or ""
            profile.name = fallback if fallback and not PHONE_RE.match(fallback) else _mask(owner_phone or name)
            profile_changed += 1
            print(f"patient_profile id={profile.id}: {name[:3]}*** -> {profile.name}")
    db.commit()
    changed += profile_changed
    return changed


def main() -> None:
    db = SessionLocal()
    try:
        n = migrate(db)
        print(f"done, {n} users renamed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
