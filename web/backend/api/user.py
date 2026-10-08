"""
用户相关 API
支持: 手机验证码登录、邮箱验证码登录、用户名密码登录、刷新令牌
"""
from web.backend.utils.timeutils import iso_utc

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
from web.backend.database.models import User as DBUser, UserCredential, UserAssistantPreference
from web.backend.services.content_safety import moderate_profile_field
from web.backend.models.user import (
    AssistantPreferenceResponse,
    AssistantPreferenceUpdate,
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
    bump_token_version,
    auth,
    get_current_user,
    get_current_user_optional,
    get_password_hash,
    verify_password,
)
from web.backend.services.sms import create_sms_code, verify_sms_code, send_sms
from web.backend.services.audit import AuditLogService
from web.backend.utils.uid import generate_uid
from web.backend.utils.password_policy import validate_password_strength
from web.backend.utils.upload_validation import validate_avatar_upload
from web.backend.utils.redact import looks_like_phone
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
    access_token = create_access_token(
        data={"sub": user.username},
        is_admin=is_admin,
        token_version=int(getattr(user, "token_version", 0) or 0),
    )
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
    strength_error = validate_password_strength(password)
    if strength_error is not None:
        raise HTTPException(status_code=400, detail=strength_error)
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


def _generate_default_username(db: Session, phone: str) -> str:
    """为手机号注册用户生成友好默认昵称。

    不能直接把手机号设为 username：username 会出现在公开主页、帖子/评论作者等
    渠道，等于泄露 L3 手机号。这里用「白友+后4位」，冲突时追加随机后缀。
    """
    import secrets

    base = f"白友{phone[-4:]}"
    candidate = base
    for _ in range(10):
        exists = db.query(DBUser).filter(DBUser.username == candidate).first()
        if not exists:
            return candidate
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
    return f"{base}{secrets.randbelow(9_000_000) + 1_000_000}"


def _save_avatar_file(user_id: int, filename: str, content: bytes) -> str:
    upload_dir = Path("data/uploads/avatar")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 扩展名白名单 + 魔数校验（Content-Type 可伪造，不可作为依据）
    ext = validate_avatar_upload(filename, content)
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    new_filename = f"{user_id}_{file_hash}{ext}"
    file_path = upload_dir / new_filename
    _ = file_path.write_bytes(content)

    return f"/uploads/avatar/{new_filename}"


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    _check_login_attempt_limit(request, form_data.username)
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        _record_login_failure(request, form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _clear_login_failures(form_data.username)
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
    if looks_like_phone(nickname):
        return {"available": False, "reason": "昵称不能是手机号，请注意隐私保护"}

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
        if looks_like_phone(username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="昵称不能是手机号，请注意隐私保护",
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

    # Phone and email are L3 credentials and MUST NOT be changed via this
    # endpoint — they require OTP verification through the dedicated bind
    # endpoints (``/api/user/bind-phone``, ``/api/user/bind-email``) so that a
    # compromised session cannot silently swap the recovery contact.
    if "phone" in updates or "email" in updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号/邮箱修改请使用「换绑手机号」「换绑邮箱」流程（需验证码校验）",
        )

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
    content = await file.read()
    try:
        avatar_url = _save_avatar_file(
            cast(int, cast(object, current_user.id)),
            file.filename or "avatar.jpg",
            content,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    setattr(current_user, "avatar_url", avatar_url)
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
async def register(user_create: UserCreate, request: Request, db: Session = Depends(get_db)):
    _check_ip_register_limit(request)
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


# ── 验证码发送 IP 维度限速（P2-7）──
# 服务层已有按目标号码的限速（60s 冷却 + 每号每日上限），此处补充按 IP
# 限制，防止攻击者对大量不同号码各发少量验证码实施分布式骚扰/刷费用。
import threading as _threading
import time as _time

_ip_code_send_log: dict = {}
_ip_code_send_lock = _threading.Lock()

# 注册接口 IP 限速（2026-08-30 加固）：每 IP 每小时最多 10 次注册尝试
_ip_register_log: dict = {}
_ip_register_lock = _threading.Lock()


def _check_ip_register_limit(request: Request) -> None:
    from web.backend.utils.client_ip import get_real_client_ip

    limit = int(os.getenv("REGISTER_IP_LIMIT", "10"))
    window = 3600
    ip = get_real_client_ip(request)
    now = _time.time()
    with _ip_register_lock:
        timestamps = [t for t in _ip_register_log.get(ip, []) if now - t < window]
        if len(timestamps) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="注册操作过于频繁，请稍后再试",
            )
        timestamps.append(now)
        _ip_register_log[ip] = timestamps
        if len(_ip_register_log) > 10000:
            stale = [k for k, v in _ip_register_log.items() if not v or now - v[-1] >= window]
            for k in stale:
                _ip_register_log.pop(k, None)


def _check_ip_code_send_limit(request: Request) -> None:
    """每 IP 每小时最多发送 CODE_SEND_IP_LIMIT（默认20）次验证码。"""
    from web.backend.utils.client_ip import get_real_client_ip

    limit = int(os.getenv("CODE_SEND_IP_LIMIT", "20"))
    window = int(os.getenv("CODE_SEND_IP_WINDOW_SECONDS", "3600"))
    ip = get_real_client_ip(request)
    now = _time.time()
    with _ip_code_send_lock:
        timestamps = _ip_code_send_log.get(ip, [])
        timestamps = [ts for ts in timestamps if now - ts < window]
        if len(timestamps) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="操作过于频繁，请稍后再试",
            )
        timestamps.append(now)
        _ip_code_send_log[ip] = timestamps
        # 防止字典无限增长
        if len(_ip_code_send_log) > 10000:
            stale = [k for k, v in _ip_code_send_log.items() if not v or now - v[-1] >= window]
            for k in stale:
                _ip_code_send_log.pop(k, None)


# ── 密码登录失败限速（防暴力破解）──
# 按 (IP, 账号) 滑动窗口统计失败次数：超限时暂时拒绝密码登录（不影响
# 验证码登录），登录成功后清除该账号计数。
_login_fail_log: dict = {}
_login_fail_lock = _threading.Lock()


def _login_fail_key(request: Request, identifier: str) -> str:
    from web.backend.utils.client_ip import get_real_client_ip

    return f"{get_real_client_ip(request)}|{identifier.strip().lower()}"


def _check_login_attempt_limit(request: Request, identifier: str) -> None:
    """同一 (IP, 账号) 窗口内密码失败超过 LOGIN_FAIL_LIMIT（默认5）次时拒绝密码登录。"""
    limit = int(os.getenv("LOGIN_FAIL_LIMIT", "5"))
    window = int(os.getenv("LOGIN_FAIL_WINDOW_SECONDS", "900"))
    key = _login_fail_key(request, identifier)
    now = _time.time()
    with _login_fail_lock:
        timestamps = [ts for ts in _login_fail_log.get(key, []) if now - ts < window]
        _login_fail_log[key] = timestamps
        if len(timestamps) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"密码错误次数过多，请 {max(window // 60, 1)} 分钟后再试，或使用验证码登录",
            )


def _record_login_failure(request: Request, identifier: str) -> None:
    key = _login_fail_key(request, identifier)
    window = int(os.getenv("LOGIN_FAIL_WINDOW_SECONDS", "900"))
    now = _time.time()
    with _login_fail_lock:
        timestamps = [ts for ts in _login_fail_log.get(key, []) if now - ts < window]
        timestamps.append(now)
        _login_fail_log[key] = timestamps
        # 防止字典无限增长
        if len(_login_fail_log) > 10000:
            stale = [k for k, v in _login_fail_log.items() if not v or now - v[-1] >= window]
            for k in stale:
                _login_fail_log.pop(k, None)


def _clear_login_failures(identifier: str) -> None:
    suffix = f"|{identifier.strip().lower()}"
    with _login_fail_lock:
        for k in [k for k in _login_fail_log if k.endswith(suffix)]:
            _login_fail_log.pop(k, None)


@router.post("/send-sms")
def send_sms_code(data: SendSMSCode, request: Request, db: Session = Depends(get_db)):
    _check_ip_code_send_limit(request)
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
def send_email_verification_code(data: SendEmailCode, request: Request, db: Session = Depends(get_db)):
    _check_ip_code_send_limit(request)
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
def register_by_phone(data: UserCreateByPhone, request: Request, db: Session = Depends(get_db)):
    _check_ip_register_limit(request)
    if data.password is not None:
        strength_error = validate_password_strength(data.password)
        if strength_error is not None:
            raise HTTPException(status_code=400, detail=strength_error)
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

    # Admin status is never auto-granted at registration time. Provision admins
    # explicitly via create_admin.py / DB migration. ADMIN_PHONES env is only a
    # read-only secondary gate on already-admin sessions (see services/admin_auth.py).
    user = DBUser(
        uid=generate_uid(data.phone, db),
        username=_generate_default_username(db, data.phone),
        phone=data.phone,
        hashed_password=get_password_hash(data.password) if data.password else None,
        is_active=True,
        is_admin=False,
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
def login_by_phone_password(
    data: PhonePasswordLogin, request: Request, db: Session = Depends(get_db)
):
    _check_login_attempt_limit(request, data.phone)
    user = find_user_by_credential(db, "phone", data.phone)
    if not user:
        _record_login_failure(request, data.phone)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    password_credential = find_credential(db, _db_user_id(user), "password")
    hashed_password = _password_hash_from_credential(password_credential)
    if not hashed_password:
        _record_login_failure(request, data.phone)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未设置密码，请使用验证码登录",
        )

    if not verify_password(data.password, hashed_password):
        _record_login_failure(request, data.phone)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    if not cast(bool, cast(object, user.is_active)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用"
        )

    _clear_login_failures(data.phone)
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
def login_by_email_password(
    data: EmailPasswordLogin, request: Request, db: Session = Depends(get_db)
):
    _check_login_attempt_limit(request, data.email)
    user = find_user_by_credential(db, "email", data.email)
    if not user:
        _record_login_failure(request, data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    password_credential = find_credential(db, _db_user_id(user), "password")
    hashed_password = _password_hash_from_credential(password_credential)
    if not hashed_password:
        _record_login_failure(request, data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未设置密码，请使用验证码登录",
        )

    if not verify_password(data.password, hashed_password):
        _record_login_failure(request, data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    if not cast(bool, cast(object, user.is_active)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    _clear_login_failures(data.email)
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
    # 已设有密码的用户必须先验证旧密码，防止会话被劫持后被攻击者静默换密
    # 实现持久化账号接管。首次设置密码（社交登录用户）无旧密码可验，豁免。
    existing_hash = cast(Optional[str], cast(object, current_user.hashed_password))
    if existing_hash:
        if not data.old_password:
            raise HTTPException(
                status_code=400,
                detail="请先输入当前密码后再设置新密码",
            )
        if not verify_password(data.old_password, existing_hash):
            raise HTTPException(status_code=400, detail="当前密码不正确")

    _upsert_password_credential(db, current_user, data.password)
    _sync_legacy_user_fields(db, current_user)
    db.commit()
    # 改密后立即作废所有存量会话（refresh token + access token 版本号）
    try:
        revoke_all_user_tokens(_db_user_id(current_user), db)
        bump_token_version(_db_user_id(current_user), db)
    except Exception:
        db.rollback()
    return {"detail": "密码设置成功，其他设备已强制下线"}


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
    # Revoke all existing refresh tokens so active sessions on other devices
    # are forced to re-authenticate with the new password. Access tokens are
    # revoked immediately via token_version bump.
    try:
        revoke_all_user_tokens(cast(int, cast(object, user.id)), db)
        bump_token_version(cast(int, cast(object, user.id)), db)
    except Exception:
        db.rollback()

    # 为刚通过验证码认证的当前会话补发一对新令牌。否则本端持有的 access token
    # 过期（默认 30 分钟）后，刷新令牌已被吊销会导致用户在应用内被静默登出。
    # 旧令牌已全部吊销，其他设备/会话仍被强制下线，安全属性不变。
    is_admin = bool(getattr(user, "is_admin", False))
    access_token = create_access_token(
        data={"sub": user.username},
        is_admin=is_admin,
        token_version=int(getattr(user, "token_version", 0) or 0),
    )
    refresh_token_value = create_refresh_token(
        data={"sub": user.username}, db=db, is_admin=is_admin
    )
    return {
        "detail": "密码重置成功",
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
    }


@router.post("/refresh-token", response_model=Token)
def refresh_token(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    user = verify_refresh_token(data.refresh_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期"
        )

    _ = revoke_refresh_token(data.refresh_token, db)
    access_token = create_access_token(
        data={"sub": user.username},
        token_version=int(getattr(user, "token_version", 0) or 0),
    )
    new_refresh_token = create_refresh_token(data={"sub": user.username}, db=db)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": _get_user_response(user, include_private=True, include_sensitive=True),
    }


class DeleteAccountRequest(BaseModel):
    confirm: str
    password: Optional[str] = None
    code: Optional[str] = None


@router.post("/delete-account")
def delete_account(
    data: DeleteAccountRequest,
    request: Request,
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    """注销账户（被遗忘权）。需强身份验证：有密码验密码，否则验手机/邮箱 OTP。"""
    if data.confirm != "DELETE":
        raise HTTPException(status_code=400, detail="请输入 DELETE 以确认注销")

    user_id = _db_user_id(current_user)
    phone = getattr(current_user, "phone", None)
    email = getattr(current_user, "email", None)
    hashed = cast(Optional[str], cast(object, current_user.hashed_password))

    if hashed:
        if not data.password or not verify_password(data.password, hashed):
            raise HTTPException(status_code=403, detail="密码验证失败，无法注销")
    elif phone:
        if not data.code or not verify_sms_code(db, phone, data.code):
            raise HTTPException(status_code=403, detail="验证码错误或已过期，无法注销")
    elif email:
        if not data.code or not verify_email_code(db, email, data.code, purpose="reset"):
            raise HTTPException(status_code=403, detail="验证码错误或已过期，无法注销")
    else:
        # 无任何可用凭证的账户（理论不应存在）：拒绝，走人工客服通道
        raise HTTPException(status_code=403, detail="账户缺少可验证凭证，请联系客服注销")

    # 注销前先留审计记录（AccountDeletion 内部会清凭证但保留 audit_logs）
    try:
        AuditLogService(db).create_log(
            user_id=user_id,
            action="account.delete",
            target_type="user",
            target_id=user_id,
            scope="private",
            detail="{}",
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for account deletion %s", user_id, exc_info=True)

    from web.backend.services.account_deletion import delete_user_account

    result = delete_user_account(db, current_user)
    return {"status": "ok", "message": "账户已注销，个人数据已删除", "detail": result}


@router.post("/logout")
def logout(current_user: DBUser = Depends(auth), db: Session = Depends(get_db)):
    _ = revoke_all_user_tokens(cast(int, cast(object, current_user.id)), db)
    # 登出即作废本用户全部 access token（含当前会话），防止 token 残留复用
    try:
        bump_token_version(_db_user_id(current_user), db)
    except Exception:
        db.rollback()
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


# ── 小白管家外观偏好 ──

_ASSISTANT_PREF_DEFAULTS = AssistantPreferenceResponse()

# 收紧后的白名单：旧版形象/风格值（logo/butterfly/robot/animated/gradient）一律回退默认，
# 避免存量偏好返回前端不认识的值导致渲染空白。
_VALID_MASCOTS = {"real"}
_VALID_STYLES = {"circle", "rounded"}


def _build_pref_response(
    mascot, style, size, position, greeting, enabled
) -> AssistantPreferenceResponse:
    return AssistantPreferenceResponse(
        mascot=mascot if mascot in _VALID_MASCOTS else _ASSISTANT_PREF_DEFAULTS.mascot,
        style=style if style in _VALID_STYLES else _ASSISTANT_PREF_DEFAULTS.style,
        size=size or _ASSISTANT_PREF_DEFAULTS.size,
        position=position or _ASSISTANT_PREF_DEFAULTS.position,
        greeting=greeting or _ASSISTANT_PREF_DEFAULTS.greeting,
        enabled=enabled if enabled is not None else True,
    )


@router.get("/assistant-preference", response_model=AssistantPreferenceResponse)
async def get_assistant_preference(
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    """获取当前用户的小白管家外观偏好（未设置时返回默认值）。"""
    pref = (
        db.query(UserAssistantPreference)
        .filter(UserAssistantPreference.user_id == current_user.id)
        .first()
    )
    if pref is None:
        return _ASSISTANT_PREF_DEFAULTS
    return _build_pref_response(
        pref.mascot, pref.style, pref.size, pref.position, pref.greeting, pref.enabled,
    )


@router.put("/assistant-preference", response_model=AssistantPreferenceResponse)
async def update_assistant_preference(
    body: AssistantPreferenceUpdate,
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    """更新小白管家外观偏好（字段白名单校验由 Literal 类型保证，仅更新传入字段）。"""
    pref = (
        db.query(UserAssistantPreference)
        .filter(UserAssistantPreference.user_id == current_user.id)
        .first()
    )
    if pref is None:
        pref = UserAssistantPreference(user_id=current_user.id)
        db.add(pref)

    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(pref, field, value)

    try:
        db.commit()
        db.refresh(pref)
    except Exception as exc:
        db.rollback()
        logger.error("更新管家偏好失败: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")

    return _build_pref_response(
        pref.mascot, pref.style, pref.size, pref.position, pref.greeting, pref.enabled,
    )


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

    def _mask_phone(p: Optional[str]) -> Optional[str]:
        if not p or len(p) < 7:
            return p
        return f"{p[:3]}****{p[-4:]}"

    def _mask_email(e: Optional[str]) -> Optional[str]:
        if not e or "@" not in e:
            return e
        local, domain = e.split("@", 1)
        if len(local) <= 2:
            return f"{local[0:1]}***@{domain}" if local else e
        return f"{local[:2]}***@{domain}"

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": u.id,
                "uid": u.uid,
                "username": u.username,
                # L3 PII: mask in the bulk list. Use the reveal endpoint to
                # view full contact info (audit-logged).
                "email": _mask_email(u.email),
                "phone": _mask_phone(u.phone),
                "avatar_url": u.avatar_url,
                "is_admin": u.is_admin,
                "is_active": getattr(u, "is_active", True),
                "user_status": u.user_status or "normal",
                "muted_until": iso_utc(u.muted_until) if getattr(u, "muted_until", None) else None,
                "banned_at": iso_utc(u.banned_at) if getattr(u, "banned_at", None) else None,
                "ban_reason": u.ban_reason,
                "violation_count": u.violation_count or 0,
                "created_at": iso_utc(u.created_at) if u.created_at else None,
            }
            for u in users
        ],
    }


@admin_router.get("/users/{user_id}/contact")
async def admin_reveal_user_contact(
    user_id: int,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reveal full phone/email for a user. Audit-logged to deter abuse."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    target = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        AuditLogService.log(
            db=db,
            action="admin.reveal_contact",
            actor_id=current_user.id,
            target_type="user",
            target_id=target.id,
            details={"reason": "admin_contact_reveal"},
        )
        db.commit()
    except Exception:
        db.rollback()
    return {
        "id": target.id,
        "username": target.username,
        "email": target.email,
        "phone": target.phone,
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
