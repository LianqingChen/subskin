"""UserCredential service — lookup, bind, unbind, verify."""

from __future__ import annotations

from typing import Optional, cast

from sqlalchemy.orm import Session

from web.backend.database.models import User, UserCredential
from web.backend.exceptions import CredentialConflictError, CredentialNotFoundError


def _normalize_credential_value(cred_type: str, cred_id: str) -> str:
    normalized = (cred_id or "").strip()
    if cred_type == "email":
        return normalized.lower()
    return normalized


def _stored_credential_id(user_id: int, cred_type: str, cred_id: str) -> str:
    normalized = _normalize_credential_value(cred_type, cred_id)
    if cred_type == "password":
        return f"password:{user_id}"
    return normalized


def _credential_label(cred_type: str) -> str:
    return {
        "phone": "手机号",
        "email": "邮箱",
        "wechat": "微信",
        "alipay": "支付宝",
        "password": "密码",
    }.get(cred_type, "凭证")


def find_user_by_credential(
    db: Session, cred_type: str, cred_id: str
) -> Optional[User]:
    lookup_value = _normalize_credential_value(cred_type, cred_id)
    credential = (
        db.query(UserCredential)
        .filter(UserCredential.cred_type == cred_type)
        .filter(UserCredential.cred_id == lookup_value)
        .first()
    )
    if credential is None:
        return None
    return db.query(User).filter(User.id == credential.user_id).first()


def find_credential(
    db: Session, user_id: int, cred_type: str
) -> Optional[UserCredential]:
    return (
        db.query(UserCredential)
        .filter(UserCredential.user_id == user_id)
        .filter(UserCredential.cred_type == cred_type)
        .first()
    )


def bind_credential(
    db: Session,
    user_id: int,
    cred_type: str,
    cred_id: str,
    verified: bool = False,
    credential_data: Optional[str] = None,
) -> UserCredential:
    existing_for_user = find_credential(db, user_id, cred_type)
    if existing_for_user is not None:
        raise CredentialConflictError(
            f"您已绑定{_credential_label(cred_type)}"
        )

    stored_cred_id = _stored_credential_id(user_id, cred_type, cred_id)
    existing = (
        db.query(UserCredential)
        .filter(UserCredential.cred_type == cred_type)
        .filter(UserCredential.cred_id == stored_cred_id)
        .first()
    )
    existing_user_id = (
        cast(Optional[int], cast(object, existing.user_id)) if existing else None
    )
    if existing is not None and existing_user_id != user_id:
        raise CredentialConflictError(
            f"该{_credential_label(cred_type)}已绑定其他账号"
        )

    credential = UserCredential(
        user_id=user_id,
        cred_type=cred_type,
        cred_id=stored_cred_id,
        verified=verified,
        credential_data=credential_data,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


def unbind_credential(db: Session, credential_id: int, user_id: int) -> bool:
    credential = (
        db.query(UserCredential)
        .filter(UserCredential.id == credential_id)
        .filter(UserCredential.user_id == user_id)
        .first()
    )
    if credential is None:
        raise CredentialNotFoundError("凭证不存在")

    credential_count = (
        db.query(UserCredential).filter(UserCredential.user_id == user_id).count()
    )
    if credential_count < 2:
        return False

    db.delete(credential)
    db.commit()
    return True


def verify_credential(db: Session, credential_id: int) -> bool:
    credential = (
        db.query(UserCredential).filter(UserCredential.id == credential_id).first()
    )
    if credential is None:
        return False
    setattr(credential, "verified", True)
    db.commit()
    return True


def user_has_password(db: Session, user_id: int) -> bool:
    credential = find_credential(db, user_id, "password")
    if credential is None:
        return False
    return cast(Optional[str], cast(object, credential.credential_data)) is not None


def get_user_credentials(db: Session, user_id: int) -> list[UserCredential]:
    return (
        db.query(UserCredential)
        .filter(UserCredential.user_id == user_id)
        .order_by(UserCredential.created_at.asc(), UserCredential.id.asc())
        .all()
    )
