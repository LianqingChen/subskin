"""
用户相关 API
"""

import os
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.models.user import (
    Token,
    User,
    UserCreate,
    UserCreateByPhone,
    PhoneLogin,
)
from web.backend.models.sms import SendSMSCode
from web.backend.services.auth import (
    authenticate_user,
    create_access_token,
    auth,
    get_password_hash,
)
from web.backend.services.sms import create_sms_code, verify_sms_code, send_sms

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """用户登录获取令牌"""
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(auth)):
    """获取当前用户信息"""
    return current_user


@router.post("/register", response_model=User)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """注册新用户"""
    # 检查用户名是否已存在
    from database.models import User as DBUser

    existing = db.query(DBUser).filter(DBUser.username == user_create.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在"
        )
    # 创建新用户
    db_user = DBUser(
        username=user_create.username,
        email=user_create.email,
        hashed_password=get_password_hash(user_create.password),
        is_active=True,
        is_admin=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return User(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        phone=db_user.phone,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
    )


@router.post("/send-sms")
def send_sms_code(data: SendSMSCode, db: Session = Depends(get_db)):
    """发送短信验证码"""
    code = create_sms_code(db, data.phone)
    success = send_sms(data.phone, code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="短信发送失败"
        )
    # 开发模式返回验证码方便测试
    sms_provider = os.getenv("SMS_PROVIDER", "log")
    if sms_provider == "log":
        return {"status": "ok", "code": code, "message": "开发模式，验证码已返回"}
    return {"status": "ok", "message": "验证码已发送"}


@router.post("/register-by-phone", response_model=Token)
def register_by_phone(data: UserCreateByPhone, db: Session = Depends(get_db)):
    """手机号验证码注册"""
    # 验证验证码
    if not verify_sms_code(db, data.phone, data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期"
        )
    # 检查手机号是否已注册
    from database.models import User as DBUser

    existing = db.query(DBUser).filter(DBUser.phone == data.phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该手机号已注册"
        )
    # 使用手机号作为用户名
    username = data.phone
    # 创建新用户
    db_user = DBUser(
        username=username,
        phone=data.phone,
        hashed_password=get_password_hash(data.password) if data.password else None,
        is_active=True,
        is_admin=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    # 生成 token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login-by-phone", response_model=Token)
def login_by_phone(data: PhoneLogin, db: Session = Depends(get_db)):
    """手机号验证码登录"""
    # 验证验证码
    if not verify_sms_code(db, data.phone, data.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码错误或已过期"
        )
    # 查找用户
    from database.models import User as DBUser

    user = db.query(DBUser).filter(DBUser.phone == data.phone).first()
    if not user:
        # 自动注册 - 如果手机号不存在则创建匿名用户
        user = DBUser(
            username=data.phone,
            phone=data.phone,
            hashed_password=None,
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    # 生成 token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
