"""
用户相关 API
支持: 手机验证码登录、邮箱验证码登录、用户名密码登录、刷新令牌
"""

import json
import os
import logging
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User as DBUser, UserCredential
from web.backend.services.content_safety import moderate_profile_field
from web.backend.models.user import (
    Token,
    UserCreate,
    UserCreateByPhone,
    PhoneLogin,
    PhonePasswordLogin,
    EmailLogin,
    EmailPasswordLogin,
    EmailRegister,
    SendEmailCode,
    RefreshTokenRequest,
    UserProfileUpdate,
    BindPhoneRequest,
    BindEmailRequest,
    SetPasswordRequest,
    ResetPasswordRequest,
    CredentialResponse,
)
from web.backend.models.sms import SendSMSCode
from web.backend.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    auth,
    get_current_user,
    get_current_user_optional,
    get_password_hash,
    verify_password,
)
from web.backend.services.sms import create_sms_code, verify_sms_code, send_sms
from web.backend.services.audit import AuditLogService
from web.backend.utils.uid import generate_uid
from web.backend.services.email_service import (
    create_email_code,
    verify_email_code,
    send_email_code,
)
from web.backend.services.email_service import (
    create_email_code,
    verify_email_code,
    send_email_code,
)
from web.backend.services.user_serializer import get_user_response as _get_user_response
from web.backend.services.credential import (
    bind_credential,
    find_credential,
    find_user_by_credential,
    get_user_credentials,
    unbind_credential,
)
from web.backend.exceptions import CredentialConflictError, CredentialNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()
profile_router = APIRouter()
GENERIC_REGISTRATION_ERROR = "注册信息无效，请检查输入"

ACCESS_TOKEN_EXPIRE = timedelta(
    minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
)


def _login_response(user: DBUser, db: Session) -> dict[str, object]:
    # Sync legacy user fields from UserCredential table so phone/email are
    # present in the login response (prevents "lost" phone/email on Profile page)
    _sync_legacy_user_fields(db, user)
    db.commit()
    db.refresh(user)

    is_admin = bool(getattr(user, 'is_admin', False))
    access_token = create_access_token(data={"sub": user.username}, is_admin=is_admin)
    refresh_token = create_refresh_token(data={"sub": user.username}, db=db, is_admin=is_admin)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": _get_user_response(user, include_private=True, include_sensitive=True),
    }


def _password_hash_from_credential(
    password_credential: Optional[UserCredential],
) -> Optional[str]:
    if password_credential is None:
        return None
    credential_data = cast(
        Optional[str], cast(object, password_credential.credential_data)
    )
    if credential_data is None:
        return None
    try:
        payload = json.loads(credential_data)
    except json.JSONDecodeError:
        return None
    hashed_password = payload.get("hashed_password")
    return hashed_password if isinstance(hashed_password, str) else None


def _db_user_id(user: DBUser) -> int:
    return cast(int, cast(object, user.id))


def _credential_value(credential: Optional[UserCredential]) -> Optional[str]:
    if credential is None:
        return None
    return cast(Optional[str], cast(object, credential.cred_id))


def _sync_legacy_user_fields(db: Session, user: DBUser) -> None:
    user_id = _db_user_id(user)
    phone_credential = find_credential(db, user_id, "phone")
    email_credential = find_credential(db, user_id, "email")
    password_credential = find_credential(db, user_id, "password")
    wechat_credential = find_credential(db, user_id, "wechat")
    alipay_credential = find_credential(db, user_id, "alipay")

    setattr(user, "phone", _credential_value(phone_credential))
    setattr(user, "email", _credential_value(email_credential))
    setattr(
        user, "hashed_password", _password_hash_from_credential(password_credential)
    )
    setattr(user, "wechat_id", _credential_value(wechat_credential))
    setattr(user, "alipay_id", _credential_value(alipay_credential))
    db.add(user)


def _upsert_password_credential(db: Session, user: DBUser, password: str) -> None:
    user_id = _db_user_id(user)
    password_hash = get_password_hash(password)
    credential_payload = json.dumps(
        {"hashed_password": password_hash}, ensure_ascii=False
    )
    password_credential = find_credential(db, user_id, "password")
    if password_credential is not None:
        setattr(password_credential, "credential_data", credential_payload)
        setattr(password_credential, "verified", True)
        setattr(password_credential, "updated_at", datetime.now(timezone.utc))
    else:
        bind_credential(
            db,
            user_id,
            "password",
            "password",
            verified=True,
            credential_data=credential_payload,
        )
    setattr(user, "hashed_password", password_hash)
    db.add(user)


def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _ensure_unique_user_field(
    db: Session,
    current_user: DBUser,
    field_name: str,
    value: Optional[str],
    detail: str,
):
    if not value:
        return

    existing = (
        db.query(DBUser)
        .filter(getattr(DBUser, field_name) == value)
        .filter(DBUser.id != current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _save_avatar_file(user_id: int, filename: str, content: bytes) -> str:
    upload_dir = Path("data/uploads/avatar")
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_hash = hashlib.sha256(content).hexdigest()[:16]
    ext = Path(filename).suffix or ".jpg"
    new_filename = f"{user_id}_{file_hash}{ext}"
    file_path = upload_dir / new_filename
    _ = file_path.write_bytes(content)

    return f"/uploads/avatar/{new_filename}"


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _login_response(user, db)


@router.get("/me")
@profile_router.get("/me")
async def read_users_me(current_user: DBUser = Depends(auth), db: Session = Depends(get_db)):
    # Sync legacy fields so phone/email from UserCredential populate the
    # User table columns (these go stale when creds change outside login)
    _sync_legacy_user_fields(db, current_user)
    db.commit()
    db.refresh(current_user)
    return _get_user_response(current_user, include_private=True, include_sensitive=True)


@router.get("/check-nickname")
@profile_router.get("/check-nickname")
async def check_nickname_availability(
    nickname: str,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_user_optional),
):
    nickname = nickname.strip()
    if not nickname or len(nickname) < 2:
        return {"available": False, "reason": "昵称至少2个字符"}
    if len(nickname) > 20:
        return {"available": False, "reason": "昵称最多20个字符"}

    existing = db.query(DBUser).filter(DBUser.username == nickname).first()
    if existing and (not current_user or existing.id != current_user.id):
        return {"available": False, "reason": "该昵称已被使用"}
    return {"available": True}


@router.put("/me")
@profile_router.put("/me")
async def update_users_me(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    updates = payload.model_dump(exclude_unset=True)

    if "username" in updates:
        username = _normalize_optional_string(updates["username"])
        if not username or len(username) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="用户名至少2个字符"
            )
        _ensure_unique_user_field(
            db, current_user, "username", username, "用户名已存在"
        )
        setattr(current_user, "username", username)
        import threading
        threading.Thread(
            target=moderate_profile_field,
            args=(current_user.id, "username", username),
            daemon=True,
        ).start()

    if "phone" in updates:
        phone = _normalize_optional_string(updates["phone"])
        if phone and not re.match(r"^1[3-9]\d{9}$", phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="请输入有效的手机号"
            )
        _ensure_unique_user_field(db, current_user, "phone", phone, "手机号已被使用")
        setattr(current_user, "phone", phone)

    if "email" in updates:
        email = _normalize_optional_string(updates["email"])
        _ensure_unique_user_field(db, current_user, "email", email, "邮箱已被使用")
        setattr(current_user, "email", email)

    if "patient_relation" in updates:
        relation = _normalize_optional_string(updates["patient_relation"])
        if relation is not None:
            allowed = {
                "本人",
                "父母",
                "孩子",
                "伴侣",
                "朋友",
                "医护人员",
                "其他",
                "患者父母",
                "患者伴侣",
                "患者朋友",
            }
            if relation not in allowed:
                raise HTTPException(status_code=400, detail="无效的与白友关系")
            setattr(current_user, "patient_relation", relation)

    db.commit()
    db.refresh(current_user)
    return _get_user_response(current_user, include_private=True, include_sensitive=True)


@router.post("/me/avatar")
@profile_router.post("/me/avatar")
async def upload_user_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请上传图片文件"
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件不能为空"
        )

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="图片大小不能超过5MB"
        )

    setattr(
        current_user,
        "avatar_url",
        _save_avatar_file(
            cast(int, cast(object, current_user.id)),
            file.filename or "avatar.jpg",
            content,
        ),
    )
    db.commit()
    db.refresh(current_user)
    import threading
    threading.Thread(
        target=moderate_profile_field,
        args=(current_user.id, "avatar", current_user.avatar_url or ""),
        daemon=True,
    ).start()
    return _get_user_response(current_user, include_private=True, include_sensitive=True)


@router.post("/register")
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(DBUser).filter(DBUser.username == user_create.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_REGISTRATION_ERROR,
        )

    if user_create.email:
        email_existing = find_user_by_credential(db, "email", user_create.email)
        if email_existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=GENERIC_REGISTRATION_ERROR,
            )

    password_hash = get_password_hash(user_create.password)
    db_user = DBUser(
        username=user_create.username,
        email=user_create.email,
        hashed_password=password_hash,
        is_active=True,
        is_admin=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    if user_create.email:
        try:
            bind_credential(
                db, _db_user_id(db_user), "email", user_create.email, verified=True
            )
        except CredentialConflictError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    try:
        bind_credential(
            db,
            _db_user_id(db_user),
            "password",
            "password",
            verified=True,
            credential_data=json.dumps(
                {"hashed_password": password_hash}, ensure_ascii=False
            ),
        )
    except CredentialConflictError:
        pass
    _sync_legacy_user_fields(db, db_user)
    db.commit()
    db.refresh(db_user)
    return _get_user_response(db_user, include_private=True, include_sensitive=True)


@router.post("/send-sms")
def send_sms_code(data: SendSMSCode, db: Session = Depends(get_db)):
    code = create_sms_code(db, data.phone)
    success, actual_code = send_sms(data.phone, code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="短信发送失败"
        )
    sms_provider = os.getenv("SMS_PROVIDER", "log")
    if os.getenv("ENV") == "development" and sms_provider == "log":
        return {"status": "ok", "code": code, "message": "开发模式，验证码已返回"}
    return {"status": "ok", "message": "验证码已发送"}


@router.post("/send-email-code")
def send_email_verification_code(data: SendEmailCode, db: Session = Depends(get_db)):
    code = create_email_code(db, data.email, purpose=data.purpose)
    success = send_email_code(data.email, code, purpose=data.purpose)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="邮件发送失败"
        )
    email_provider = os.getenv("EMAIL_PROVIDER", "log")
    if os.getenv("ENV") == "development" and email_provider == "log":
        return {"status": "ok", "code": code, "message": "开发模式，验证码已返回"}
    return {"status": "ok", "message": "验证码已发送"}


@router.post("/register-by-phone", response_model=Token)
def register_by_phone(data: UserCreateByPhone, db: Session = Depends(get_db)):
    if not verify_sms_code(db, data.phone, data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期"
        )

    existing = find_user_by_credential(db, "phone", data.phone)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该手机号已注册，请直接登录",
        )

    user = DBUser(
        uid=generate_uid(data.phone, db),
        username=data.phone,
        phone=data.phone,
        hashed_password=get_password_hash(data.password) if data.password else None,
        is_active=True,
        is_admin=data.phone in set(os.getenv("ADMIN_PHONES", "").split(",")) if os.getenv("ADMIN_PHONES") else False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        bind_credential(db, _db_user_id(user), "phone", data.phone, verified=True)
    except CredentialConflictError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if data.password:
        _upsert_password_credential(db, user, data.password)
    _sync_legacy_user_fields(db, user)
    db.commit()
    db.refresh(user)

    return _login_response(user, db)


@router.post("/login-by-phone", response_model=Token)
def login_by_phone(data: PhoneLogin, db: Session = Depends(get_db)):
    if not verify_sms_code(db, data.phone, data.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码错误或已过期"
        )

    user = find_user_by_credential(db, "phone", data.phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该手机号未注册，请先注册",
        )

    phone_credential = find_credential(db, _db_user_id(user), "phone")
    if phone_credential is not None:
        setattr(phone_credential, "last_used_at", datetime.now(timezone.utc))
        db.commit()

    return _login_response(user, db)


@router.post("/login-by-phone-password", response_model=Token)
def login_by_phone_password(data: PhonePasswordLogin, db: Session = Depends(get_db)):
    user = find_user_by_credential(db, "phone", data.phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    password_credential = find_credential(db, _db_user_id(user), "password")
    hashed_password = _password_hash_from_credential(password_credential)
    if not hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未设置密码，请使用验证码登录",
        )

    if not verify_password(data.password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    if not cast(bool, cast(object, user.is_active)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用"
        )

    setattr(password_credential, "last_used_at", datetime.now(timezone.utc))
    db.commit()

    return _login_response(user, db)


@router.post("/login-by-email", response_model=Token)
def login_by_email(data: EmailLogin, db: Session = Depends(get_db)):
    if not verify_email_code(db, data.email, data.code, purpose="login"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码错误或已过期"
        )

    user = find_user_by_credential(db, "email", data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该邮箱未注册，请先注册",
        )

    email_credential = find_credential(db, _db_user_id(user), "email")
    if email_credential is not None:
        setattr(email_credential, "last_used_at", datetime.now(timezone.utc))
        db.commit()

    return _login_response(user, db)


@router.post("/register-by-email", response_model=Token)
def register_by_email(data: EmailRegister, db: Session = Depends(get_db)):
    if not verify_email_code(db, data.email, data.code, purpose="register"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期"
        )

    existing_email = find_user_by_credential(db, "email", data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已注册，请直接登录",
        )

    username = data.username.strip() if data.username.strip() else data.email.split("@")[0][:20]

    existing = db.query(DBUser).filter(DBUser.username == username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_REGISTRATION_ERROR,
        )

    password_hash = get_password_hash(data.password)
    user = DBUser(
        uid=generate_uid(data.email, db),
        username=username,
        email=data.email,
        hashed_password=password_hash,
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        bind_credential(db, _db_user_id(user), "email", data.email, verified=True)
    except CredentialConflictError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    try:
        bind_credential(
            db,
            _db_user_id(user),
            "password",
            "password",
            verified=True,
            credential_data=json.dumps(
                {"hashed_password": password_hash}, ensure_ascii=False
            ),
        )
    except CredentialConflictError:
        pass
    _sync_legacy_user_fields(db, user)
    db.commit()
    db.refresh(user)

    return _login_response(user, db)


@router.post("/login-by-email-password", response_model=Token)
def login_by_email_password(data: EmailPasswordLogin, db: Session = Depends(get_db)):
    user = find_user_by_credential(db, "email", data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    password_credential = find_credential(db, _db_user_id(user), "password")
    hashed_password = _password_hash_from_credential(password_credential)
    if not hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未设置密码，请使用验证码登录",
        )

    if not verify_password(data.password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    if not cast(bool, cast(object, user.is_active)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    setattr(password_credential, "last_used_at", datetime.now(timezone.utc))
    db.commit()
    return _login_response(user, db)


@router.post("/bind-phone")
def bind_phone(
    data: BindPhoneRequest,
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    if not verify_sms_code(db, data.phone, data.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    try:
        credential = bind_credential(
            db, _db_user_id(current_user), "phone", data.phone, verified=True
        )
    except CredentialConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _sync_legacy_user_fields(db, current_user)
    db.commit()
    return {"detail": "手机号绑定成功", "credential_id": credential.id}


@router.post("/bind-email")
def bind_email(
    data: BindEmailRequest,
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    if not verify_email_code(db, data.email, data.code, purpose="bind"):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    try:
        credential = bind_credential(
            db, _db_user_id(current_user), "email", data.email, verified=True
        )
    except CredentialConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _sync_legacy_user_fields(db, current_user)
    db.commit()
    return {"detail": "邮箱绑定成功", "credential_id": credential.id}


@router.delete("/credentials/{credential_id}")
def unbind_credential_endpoint(
    credential_id: int,
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    try:
        success = unbind_credential(db, credential_id, _db_user_id(current_user))
    except CredentialNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not success:
        raise HTTPException(status_code=400, detail="无法解绑最后一个登录方式")

    _sync_legacy_user_fields(db, current_user)
    db.commit()
    return {"detail": "解绑成功"}


@router.get("/credentials", response_model=list[CredentialResponse])
def list_credentials(
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    return get_user_credentials(db, _db_user_id(current_user))


@router.post("/set-password")
def set_password(
    data: SetPasswordRequest,
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    _upsert_password_credential(db, current_user, data.password)
    _sync_legacy_user_fields(db, current_user)
    db.commit()
    return {"detail": "密码设置成功"}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    if data.cred_type == "phone":
        if not verify_sms_code(db, data.credential_id, data.code):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")
    else:
        if not verify_email_code(db, data.credential_id, data.code, purpose="reset"):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

    user = find_user_by_credential(db, data.cred_type, data.credential_id)
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")

    _upsert_password_credential(db, user, data.new_password)
    _sync_legacy_user_fields(db, user)
    db.commit()
    return {"detail": "密码重置成功"}


@router.post("/refresh-token", response_model=Token)
def refresh_token(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    user = verify_refresh_token(data.refresh_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期"
        )

    _ = revoke_refresh_token(data.refresh_token, db)
    access_token = create_access_token(data={"sub": user.username})
    new_refresh_token = create_refresh_token(data={"sub": user.username}, db=db)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": _get_user_response(user, include_private=True, include_sensitive=True),
    }


@router.post("/logout")
def logout(current_user: DBUser = Depends(auth), db: Session = Depends(get_db)):
    _ = revoke_all_user_tokens(cast(int, cast(object, current_user.id)), db)
    return {"status": "ok", "message": "已退出登录"}


class PWAStatusRequest(BaseModel):
    installed: bool
    uid: Optional[str] = None
    timestamp: Optional[str] = None


class PrivacyModeRequest(BaseModel):
    privacy_mode: bool


class PhoneDiscoverableRequest(BaseModel):
    phone_discoverable: bool


@router.get("/privacy-mode")
def get_privacy_mode(current_user: DBUser = Depends(auth)):
    return {"privacy_mode": current_user.privacy_mode}


@router.put("/privacy-mode")
def update_privacy_mode(
    body: PrivacyModeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    old_value = cast(bool, cast(object, current_user.privacy_mode))
    setattr(current_user, "privacy_mode", body.privacy_mode)
    setattr(current_user, "phone_discoverable", body.privacy_mode)
    db.commit()
    try:
        _ = AuditLogService(db).create_log(
            user_id=cast(int, cast(object, current_user.id)),
            action="export",
            target_type="user",
            target_id=cast(int, cast(object, current_user.id)),
            scope="private",
            detail=json.dumps(
                {
                    "privacy_mode_from": old_value,
                    "privacy_mode_to": body.privacy_mode,
                    "phone_discoverable_synced": body.privacy_mode,
                },
                ensure_ascii=False,
            ),
            revokeable=True,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for privacy mode toggle", exc_info=True)
    return {
        "status": "ok",
        "privacy_mode": cast(bool, cast(object, current_user.privacy_mode)),
        "phone_discoverable": cast(bool, cast(object, current_user.phone_discoverable)),
    }


@router.get("/phone-discoverable")
def get_phone_discoverable(current_user: DBUser = Depends(auth)):
    return {"phone_discoverable": current_user.phone_discoverable}


@router.put("/phone-discoverable")
def update_phone_discoverable(
    body: PhoneDiscoverableRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    old_value = cast(bool, cast(object, current_user.phone_discoverable))
    setattr(current_user, "phone_discoverable", body.phone_discoverable)
    db.commit()
    try:
        _ = AuditLogService(db).create_log(
            user_id=cast(int, cast(object, current_user.id)),
            action="export",
            target_type="user",
            target_id=cast(int, cast(object, current_user.id)),
            scope="private",
            detail=json.dumps(
                {"phone_discoverable_from": old_value, "phone_discoverable_to": body.phone_discoverable},
                ensure_ascii=False,
            ),
            revokeable=True,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for phone discoverable toggle", exc_info=True)
    return {
        "status": "ok",
        "phone_discoverable": cast(bool, cast(object, current_user.phone_discoverable)),
    }


@router.post("/pwa-status")
def update_pwa_status(
    body: PWAStatusRequest,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_user_optional),
):
    if not current_user:
        return {"status": "skipped", "reason": "not_authenticated"}

    if body.installed and not cast(bool, cast(object, current_user.pwa_installed)):
        setattr(current_user, "pwa_installed", True)
        setattr(current_user, "pwa_installed_at", datetime.now(timezone.utc))
    elif not body.installed:
        setattr(current_user, "pwa_installed", False)
        setattr(current_user, "pwa_installed_at", None)

    db.commit()
    return {
        "status": "ok",
        "pwa_installed": cast(bool, cast(object, current_user.pwa_installed)),
    }


# ── admin user management ─────────────────────────────────────────────

from fastapi import Query as _Query
from web.backend.services.audit import AuditLogService
from sqlalchemy import or_ as _or_


class UserStatusUpdateRequest(BaseModel):
    action: str  # ban, unban, mute, unmute
    reason: Optional[str] = None
    duration_hours: Optional[int] = None  # for mute


admin_router = APIRouter()


@admin_router.get("/users")
async def admin_list_users(
    page: int = _Query(1, ge=1),
    page_size: int = _Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    query = db.query(DBUser)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            _or_(
                DBUser.username.ilike(search_term),
                DBUser.email.ilike(search_term),
                DBUser.phone.ilike(search_term),
            )
        )

    if status == "banned":
        query = query.filter(DBUser.user_status == "banned")
    elif status == "muted":
        query = query.filter(DBUser.user_status == "muted")
    elif status == "normal":
        query = query.filter(
            (DBUser.user_status == None) | (DBUser.user_status == "normal")
        )

    total = query.count()
    users = query.order_by(DBUser.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": u.id,
                "uid": u.uid,
                "username": u.username,
                "email": u.email,
                "phone": u.phone,
                "avatar_url": u.avatar_url,
                "is_admin": u.is_admin,
                "is_active": getattr(u, "is_active", True),
                "user_status": u.user_status or "normal",
                "muted_until": u.muted_until.isoformat() if getattr(u, "muted_until", None) else None,
                "banned_at": u.banned_at.isoformat() if getattr(u, "banned_at", None) else None,
                "ban_reason": u.ban_reason,
                "violation_count": u.violation_count or 0,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@admin_router.put("/users/{user_id}/status")
async def admin_update_user_status(
    user_id: int,
    body: UserStatusUpdateRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    target = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    action = body.action
    now = datetime.now(timezone.utc)

    if action == "ban":
        target.user_status = "banned"
        target.banned_at = now
        target.ban_reason = body.reason or "管理员封号"
    elif action == "unban":
        target.user_status = "normal"
        target.banned_at = None
        target.ban_reason = None
    elif action == "mute":
        target.user_status = "muted"
        hours = body.duration_hours or 24
        target.muted_until = now + timedelta(hours=hours)
    elif action == "unmute":
        target.user_status = "normal"
        target.muted_until = None
    else:
        raise HTTPException(status_code=400, detail=f"未知操作: {action}")

    db.commit()

    AuditLogService.log(
        db=db,
        action="admin_update_user_status",
        actor_id=current_user.id,
        target_type="user",
        target_id=str(target.id),
        details={"action": action, "reason": body.reason},
    )

    return {"status": "ok", "action": action, "user_id": user_id}


class VerifyUserRequest(BaseModel):
    verified: bool


@admin_router.put("/users/{user_id}/verify")
async def admin_set_user_verified(
    user_id: int,
    body: VerifyUserRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    target = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    target.real_name_verified = body.verified
    db.commit()

    AuditLogService.log(
        db=db,
        action="admin_set_user_verified",
        actor_id=current_user.id,
        target_type="user",
        target_id=str(target.id),
        details={"verified": body.verified},
    )

    return {"status": "ok", "verified": body.verified, "user_id": user_id}
