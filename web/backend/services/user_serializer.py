"""用户数据序列化 — 将 DBUser 转为 API 响应字典。"""

from datetime import datetime
from typing import Optional, cast

from web.backend.database.models import User as DBUser
from web.backend.utils.redact import mask_phone, mask_email, mask_name


def get_user_response(
    db_user: DBUser,
    include_private: bool = False,
    include_sensitive: bool = False,
) -> dict[str, object]:
    """将 DBUser 转为 API 响应字典。

    Args:
        db_user: 数据库用户对象
        include_private: 是否包含私密字段（脱敏后的手机号、邮箱等）
        include_sensitive: 是否返回原始敏感数据（仅限自用户端点）

    Returns:
        用户信息字典，用于 API 响应
    """
    created_at = cast(Optional[datetime], cast(object, db_user.created_at))
    response = {
        "id": db_user.id,
        "uid": db_user.uid,
        "username": db_user.username,
        "avatar_url": db_user.avatar_url,
        "is_active": db_user.is_active,
        "is_admin": db_user.is_admin,
        "is_doctor": db_user.is_doctor,
        "is_verified": getattr(db_user, "real_name_verified", False),
        "user_status": getattr(db_user, "user_status", "normal"),
        "muted_until": getattr(db_user, "muted_until", None),
        "created_at": created_at.isoformat() if created_at else None,
    }
    if include_private:
        response.update(
            {
                "email": mask_email(db_user.email) if not include_sensitive else db_user.email,
                "phone": mask_phone(db_user.phone) if not include_sensitive else db_user.phone,
                "patient_relation": db_user.patient_relation,
                "wechat_id": db_user.wechat_id,
                "alipay_id": db_user.alipay_id,
                "privacy_mode": db_user.privacy_mode,
                "is_discoverable": db_user.privacy_mode,  # clearer alias: True = visible to others
                "phone_discoverable": db_user.phone_discoverable,
            }
        )
    return cast(dict[str, object], response)
