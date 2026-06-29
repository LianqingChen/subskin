"""Admin authorization helpers.

The admin phone allowlist is read from the ``ADMIN_PHONES`` environment variable
(comma-separated). Phone numbers must NOT be hardcoded in source — see AGENTS.md
L3 data rules. Runtime auto-promotion of ``is_admin`` has been removed: admin
status is granted only through explicit provisioning (``create_admin.py`` /
``init_db`` / DB migration). The allowlist here is a read-only secondary gate
for already-admin users, retained for backward compatibility with operators who
still appear in it.
"""
from __future__ import annotations

import os
from typing import Set

from fastapi import Depends, HTTPException

from web.backend.database.models import User
from web.backend.services.auth import get_current_user


def _load_admin_phone_allowlist() -> Set[str]:
    raw = os.environ.get("ADMIN_PHONES", "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def admin_phone_allowlist() -> Set[str]:
    """Return the admin phone allowlist from env (never hardcoded)."""
    return _load_admin_phone_allowlist()


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Require an already-provisioned admin user.

    A user is admin when ``User.is_admin`` is True. The env allowlist is a
    secondary gate: a user on the allowlist who is NOT yet ``is_admin`` is
    rejected (no runtime DB mutation). Provision admins via ``create_admin.py``
    or a DB migration instead.
    """
    is_admin = bool(getattr(current_user, "is_admin", False))
    if is_admin:
        return current_user

    phone = getattr(current_user, "phone", None)
    if phone and phone in _load_admin_phone_allowlist():
        # Allowlist match but is_admin not yet provisioned — reject and surface
        # a clear message so the operator runs the provisioning step.
        raise HTTPException(
            status_code=403,
            detail="需要管理员权限，请联系管理员开通 is_admin 后再访问",
        )

    raise HTTPException(status_code=403, detail="需要管理员权限")
