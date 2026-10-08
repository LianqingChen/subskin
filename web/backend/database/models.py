"""
数据库 ORM 模型
"""

import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    DateTime,
    Text,
    UniqueConstraint,
)
from sqlalchemy import JSON, text
from sqlalchemy.orm import relationship, relationship as orm_relationship

from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SMSCode(Base):
    """短信验证码"""

    __tablename__ = "sms_codes"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    expired_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
    locked = Column(Boolean, default=False)


class EmailVerificationCode(Base):
    """邮箱验证码"""

    __tablename__ = "email_verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False)
    purpose = Column(String, nullable=False, default="login")  # login, register, reset
    created_at = Column(DateTime, default=_utcnow)
    expired_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
    locked = Column(Boolean, default=False)


class OAuthState(Base):
    """OAuth状态参数（CSRF防护）"""

    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, nullable=False)  # wechat, alipay
    created_at = Column(DateTime, default=_utcnow)
    expired_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    user_id = Column(Integer, nullable=True)  # 登录成功后关联用户


class RefreshToken(Base):
    """刷新令牌"""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)
    expired_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    avatar_url = Column(String, nullable=True)
    wechat_id = Column(String, unique=True, index=True, nullable=True)
    alipay_id = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)  # 社交登录用户可无密码
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    # token 版本号：+1 即作废该用户全部存量 access token（改密/注销/登出全部设备）
    token_version = Column(Integer, default=0, nullable=False, server_default="0")
    is_test = Column(Boolean, default=False)
    is_doctor = Column(Boolean, default=False)  # 认证医生标识
    real_name_verified = Column(Boolean, default=False)  # 实名认证标识
    pwa_installed = Column(Boolean, default=False)
    pwa_installed_at = Column(DateTime, nullable=True)
    privacy_mode = Column(
        Boolean, default=True, nullable=False
    )  # WARNING: True = discoverable/open (NOT "private"). Use is_discoverable in API layer. False = hidden.
    phone_discoverable = Column(
        Boolean, default=True, nullable=False
    )  # True = 允许他人通过手机号匹配到我 (only effective when privacy_mode=True)
    patient_relation = Column(
        String, nullable=True
    )  # 白友=本人, 白友父母, 白友伴侣, 白友朋友, 医护人员, 其他
    default_tracker_profile_id = Column(
        Integer, ForeignKey("patient_profiles.id"), nullable=True
    )
    default_report_profile_id = Column(
        Integer, ForeignKey("patient_profiles.id"), nullable=True
    )
    default_diary_profile_id = Column(
        Integer, ForeignKey("patient_profiles.id"), nullable=True
    )
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user_status = Column(String(20), default="normal", nullable=False, index=True)  # normal/muted/banned
    muted_until = Column(DateTime, nullable=True)
    banned_at = Column(DateTime, nullable=True)
    ban_reason = Column(String(500), nullable=True)
    violation_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)

    comments = relationship("Comment", back_populates="author")
    patient_profiles = relationship(
        "PatientProfile",
        back_populates="user",
        foreign_keys="PatientProfile.user_id",
        cascade="all, delete-orphan",
    )
    default_tracker_profile = relationship(
        "PatientProfile", foreign_keys=[default_tracker_profile_id], post_update=True
    )
    default_report_profile = relationship(
        "PatientProfile", foreign_keys=[default_report_profile_id], post_update=True
    )
    default_diary_profile = relationship(
        "PatientProfile", foreign_keys=[default_diary_profile_id], post_update=True
    )


class UserCredential(Base):
    """用户登录凭证"""

    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cred_type = Column(String(20), nullable=False)
    cred_id = Column(String(255), nullable=False)
    verified = Column(Boolean, default=False)
    credential_data = Column(Text, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("cred_type", "cred_id", name="uq_cred_type_id"),
        Index("idx_cred_user", "user_id"),
        Index("idx_cred_lookup", "cred_type", "cred_id"),
    )

    user = relationship("User", backref="credentials")


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    relationship = Column(String, nullable=False, default="本人")
    gender = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)
    diagnosis_date = Column(Date, nullable=True)
    vitiligo_type = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_self = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = orm_relationship(
        "User", back_populates="patient_profiles", foreign_keys=[user_id]
    )


class UserEvent(Base):
    """用户行为事件追踪"""

    __tablename__ = "user_events"
    __table_args__ = (
        Index("idx_events_created_type", "created_at", "event_type"),
        Index("idx_events_created_type_path", "created_at", "event_type", "page_path"),
        Index("idx_events_created_uid", "created_at", "uid"),
    )

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String, index=True, nullable=True)
    session_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False, index=True)
    element_id = Column(String, nullable=True, index=True)
    page_path = Column(String, nullable=True)
    element_text = Column(String, nullable=True)
    extra_data = Column(Text, nullable=True)
    client_fingerprint = Column(String, nullable=True, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)


class GuestUsage(Base):
    """访客每日使用量追踪（按客户端指纹）"""

    __tablename__ = "guest_usages"

    id = Column(Integer, primary_key=True, index=True)
    client_fingerprint = Column(String, nullable=False, index=True)
    question_count = Column(Integer, default=0)
    date = Column(String, nullable=False, index=True)  # YYYY-MM-DD format
    created_at = Column(DateTime, default=_utcnow)


class Comment(Base):
    """评论模型"""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    page_path = Column(String, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved = Column(Boolean, default=False)  # 需要审核
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    author = relationship("User", back_populates="comments")


class Document(Base):
    """知识库文档（用于RAG）"""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
    source_tier = Column(String, default="C", nullable=True)
    authority_weight = Column(Float, default=1.0, nullable=True)
    pub_date = Column(String, nullable=True)
    embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Conversation(Base):
    """对话历史（用于RAG多轮对话）"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Message(Base):
    """单条消息"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)  # user/assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class CommunityCategory(Base):
    """社区帖子分类"""

    __tablename__ = "community_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


class Post(Base):
    """社区帖子"""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_json = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    # 结构化治疗经验分享 JSON（method/duration/effect_rating/cost_range/side_effects/vasi_assessment_ids）
    treatment_share_json = Column(Text, nullable=True)
    content_preview = Column(Text, nullable=True)  # 前100字预览
    post_type = Column(String(20), nullable=True, default="long")  # image/video/text/long/treatment
    video_url = Column(String, nullable=True)  # 视频文件URL
    video_thumbnail = Column(String, nullable=True)  # 视频封面
    read_count = Column(Integer, default=0)  # 阅读数
    share_count = Column(Integer, default=0)  # 转发/分享数
    dwell_time = Column(Integer, default=0)  # 平均停留时间(秒)
    category_id = Column(
        Integer, ForeignKey("community_categories.id"), nullable=False, index=True
    )
    is_private = Column(Boolean, default=False, index=True)
    draft_expires_at = Column(DateTime, nullable=True, index=True)
    diary_date = Column(Date, nullable=True, index=True)
    diary_type = Column(String(20), nullable=True, index=True)  # medication/phototherapy/mood/diet/general
    mood = Column(String, nullable=True)  # 心情标签: 💪坚持中 / 😔低落 / 🎉好转 / 🤔疑问
    # AI 增强（日记合并到社区后，发帖自动提取；仅自己可见，不进 feed）
    ai_summary = Column(Text, nullable=True)  # AI 生成的摘要
    ai_extracted_json = Column(Text, nullable=True)  # 完整提取结果 JSON（心情/睡眠/用药等）
    is_anonymous = Column(Boolean, default=False)  # 匿名发布
    moderation_status = Column(String(20), default="normal", nullable=False, index=True)  # normal/flagged/blocked/approved
    city = Column(String(100), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    author = relationship("User", backref="posts")
    category = relationship("CommunityCategory", backref="posts")
    images = relationship(
        "PostImage", back_populates="post", cascade="all, delete-orphan"
    )
    likes = relationship(
        "PostLike", back_populates="post", cascade="all, delete-orphan"
    )
    comments = relationship(
        "PostComment", back_populates="post", cascade="all, delete-orphan"
    )
    tags = relationship("Tag", secondary="post_tags", backref="posts")
    audios = relationship(
        "PostAudio", back_populates="post", cascade="all, delete-orphan"
    )
    attachments = relationship(
        "PostAttachment", back_populates="post", cascade="all, delete-orphan"
    )
    versions = relationship(
        "PostVersion", back_populates="post", cascade="all, delete-orphan"
    )
    collection_items = relationship(
        "CollectionItem", back_populates="post", cascade="all, delete-orphan"
    )
    bookmarks = relationship(
        "Bookmark", back_populates="post", cascade="all, delete-orphan"
    )
    interaction_logs = relationship(
        "UserInteractionLog", back_populates="post", cascade="all, delete-orphan"
    )


class PostImage(Base):
    """帖子图片"""

    __tablename__ = "post_images"
    __table_args__ = (
        Index("idx_post_image_user_date", "user_id", "capture_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 冗余，便于按用户查图/历史对比
    image_url = Column(String, nullable=False)
    body_site = Column(String(50), nullable=True)  # 照片对应身体部位
    capture_date = Column(Date, nullable=True, index=True)  # 拍摄/记录日期（支持历史补录）
    visual_analysis_json = Column(Text, nullable=True)  # 轻量视觉分析结果
    analysis_status = Column(String(20), default="pending")  # pending/analyzing/light_done/failed
    vasi_assessment_id = Column(Integer, nullable=True)  # 关联深度 VASI 评估
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    post = relationship("Post", back_populates="images")


class PostLike(Base):
    """帖子点赞"""

    __tablename__ = "post_likes"
    __table_args__ = (
        # Prevent double-like races: Bookmark and Follow already have analogous
        # unique constraints. Without this, two concurrent toggle_like requests
        # can both INSERT, producing duplicate (post_id, user_id) rows and
        # inflating like counts.
        UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)

    post = relationship("Post", back_populates="likes")
    user = relationship("User", backref="post_likes")


class PostComment(Base):
    """帖子评论"""

    __tablename__ = "post_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    post = relationship("Post", back_populates="comments")
    author = relationship("User", backref="post_comments")


class Tag(Base):
    """标签"""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


class PostTag(Base):
    """帖子-标签关联"""

    __tablename__ = "post_tags"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("post_id", "tag_id"),)


class PostAudio(Base):
    """帖子音频"""

    __tablename__ = "post_audios"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    audio_url = Column(String, nullable=False)
    duration = Column(Integer, default=0)
    file_size = Column(Integer, default=0)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    post = relationship("Post", back_populates="audios")


class PostAttachment(Base):
    """帖子文件附件"""

    __tablename__ = "post_attachments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    file_url = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer, default=0)
    file_type = Column(String, default="")
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    post = relationship("Post", back_populates="attachments")


class Collection(Base):
    """收藏夹（个人知识库文件夹）"""

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    is_public = Column(Boolean, default=False)
    share_slug = Column(String, unique=True, nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    author = relationship("User", backref="collections")
    items = relationship(
        "CollectionItem", back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionItem(Base):
    """收藏夹条目（帖子 <-> 收藏夹多对多）"""

    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(
        Integer, ForeignKey("collections.id"), nullable=False, index=True
    )
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    sort_order = Column(Integer, default=0)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    collection = relationship("Collection", back_populates="items")
    post = relationship("Post", back_populates="collection_items")

    __table_args__ = (UniqueConstraint("collection_id", "post_id"),)


class PostVersion(Base):
    """帖子版本历史"""

    __tablename__ = "post_versions"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_json = Column(Text, nullable=True)
    edit_summary = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    post = relationship("Post", back_populates="versions")
    editor = relationship("User")


class Bookmark(Base):
    """帖子书签（用户快速收藏）"""

    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (UniqueConstraint("user_id", "post_id"),)

    user = relationship("User", backref="bookmarks")
    post = relationship("Post", back_populates="bookmarks")


class UserInteractionLog(Base):
    """用户交互行为日志（推荐算法数据源）"""

    __tablename__ = "user_interaction_logs"
    __table_args__ = (
        Index("idx_interaction_user_post", "user_id", "post_id"),
        Index("idx_interaction_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    action_type = Column(String(20), nullable=False, index=True)  # click/read_end/like/bookmark/comment/share/skip
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", backref="interaction_logs")
    post = relationship("Post", back_populates="interaction_logs")


class MedicalReport(Base):
    """体检报告"""

    __tablename__ = "medical_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    patient_profile_id = Column(
        Integer, ForeignKey("patient_profiles.id"), nullable=True
    )
    title = Column(String, nullable=False)
    tags = Column(String, nullable=True)
    interpretation_json = Column(JSON, nullable=True)  # AI解读结果
    parsed_sections = Column(JSON, nullable=True)  # 结构化分区[{section_name,risk,indicators,abnormal_items}]
    extracted_patient_info_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", backref="medical_reports")
    patient_profile = relationship("PatientProfile", foreign_keys=[patient_profile_id])
    files = relationship(
        "MedicalReportFile", backref="report", cascade="all, delete-orphan"
    )


class MedicalReportFile(Base):
    """体检报告附件"""

    __tablename__ = "medical_report_files"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(
        Integer, ForeignKey("medical_reports.id"), nullable=False, index=True
    )
    file_url = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String, nullable=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


class AuditLog(Base):
    """审计日志 — 用户授权分享/公开操作的不可篡改记录

    记录 who/what/when/scope/revokeable，确保用户隐私授权可追溯。
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(
        String(50), nullable=False, index=True
    )  # share, publish, revoke, delete, export
    target_type = Column(
        String(50), nullable=False
    )  # post, comment, assessment, collection
    target_id = Column(Integer, nullable=True)  # 目标对象的 ID
    scope = Column(
        String(20), nullable=False, default="public"
    )  # public, followers, specific_users, private
    detail = Column(Text, nullable=True)  # JSON 格式的详细信息
    revokeable = Column(Boolean, default=True, nullable=False)  # 该操作是否可撤销
    revoked_at = Column(DateTime, nullable=True)  # 撤销时间（不可删除，仅标记撤销）
    ip_address = Column(String(45), nullable=True)  # 操作者 IP（脱敏后存储）
    created_at = Column(DateTime, default=_utcnow, nullable=False, index=True)


class EncyclopediaArticle(Base):
    """百科文章主表"""

    __tablename__ = "encyclopedia_articles"
    __table_args__ = (
        Index("idx_enc_articles_category", "category"),
        Index("idx_enc_articles_published", "is_published"),
    )

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(String(500), nullable=True)
    icon = Column(String(20), nullable=True)
    order = Column(Integer, default=0)
    is_published = Column(Boolean, default=True, index=True)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    revisions = relationship(
        "EncyclopediaRevision", back_populates="article", cascade="all, delete-orphan"
    )
    comments = relationship(
        "EncyclopediaComment", back_populates="article", cascade="all, delete-orphan"
    )


class EncyclopediaRevision(Base):
    """百科修订记录"""

    __tablename__ = "encyclopedia_revisions"
    __table_args__ = (
        Index("idx_enc_rev_article", "article_id"),
        Index("idx_enc_rev_status", "status"),
        Index("idx_enc_rev_user", "user_id"),
        Index("idx_enc_rev_article_status", "article_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("encyclopedia_articles.id"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    change_summary = Column(String(500), nullable=True)

    change_type = Column(String(20), nullable=False, default="suggest")

    status = Column(String(20), nullable=False, default="pending")

    diff_preview = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment = Column(String(500), nullable=True)

    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)

    article = relationship(
        "EncyclopediaArticle", back_populates="revisions", foreign_keys=[article_id]
    )
    author = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    votes = relationship(
        "EncyclopediaVote", back_populates="revision", cascade="all, delete-orphan"
    )


class EncyclopediaComment(Base):
    """百科评论/讨论"""

    __tablename__ = "encyclopedia_comments"
    __table_args__ = (
        Index("idx_enc_comment_article", "article_id"),
        Index("idx_enc_comment_parent", "parent_id"),
        Index("idx_enc_comment_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("encyclopedia_articles.id"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(
        Integer, ForeignKey("encyclopedia_comments.id"), nullable=True
    )
    content = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    article = relationship("EncyclopediaArticle", back_populates="comments")
    author = relationship("User", foreign_keys=[user_id])
    replies = relationship(
        "EncyclopediaComment",
        back_populates="parent_comment",
        remote_side=[id],
    )
    parent_comment = relationship(
        "EncyclopediaComment",
        back_populates="replies",
        remote_side=[parent_id],
    )


class EncyclopediaVote(Base):
    """修订投票/评估"""

    __tablename__ = "encyclopedia_votes"
    __table_args__ = (
        UniqueConstraint(
            "revision_id", "user_id", name="uq_enc_vote_revision_user"
        ),
        Index("idx_enc_vote_revision", "revision_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    revision_id = Column(
        Integer, ForeignKey("encyclopedia_revisions.id"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote_type = Column(String(10), nullable=False)
    comment = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    revision = relationship("EncyclopediaRevision", back_populates="votes")
    voter = relationship("User", foreign_keys=[user_id])


class UserFollow(Base):
    """用户关注关系"""

    __tablename__ = "user_follows"

    id = Column(Integer, primary_key=True, index=True)
    followee_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    follower_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at = Column(DateTime, default=_utcnow)

    followee = relationship("User", foreign_keys=[followee_id], backref="followers_rel")
    follower = relationship("User", foreign_keys=[follower_id], backref="following_rel")

    __table_args__ = (UniqueConstraint("followee_id", "follower_id"),)


class UserBlock(Base):
    """用户拉黑关系"""

    __tablename__ = "user_blocks"

    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    blocked_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at = Column(DateTime, default=_utcnow)

    blocker = relationship("User", foreign_keys=[blocker_id], backref="blocks_rel")
    blocked = relationship("User", foreign_keys=[blocked_id], backref="blocked_by_rel")

    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id"),)


class UserReport(Base):
    """用户举报记录"""

    __tablename__ = "user_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    target_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    post_id = Column(
        Integer, ForeignKey("posts.id"), nullable=True, index=True
    )
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    reporter = relationship("User", foreign_keys=[reporter_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


class ContentModeration(Base):
    """内容风控记录"""

    __tablename__ = "content_moderations"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    comment_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content_type = Column(String(20), nullable=False)  # post/comment/profile
    content_snapshot = Column(Text, nullable=True)
    risk_level = Column(String(20), nullable=False, index=True)  # critical/high/medium/low
    risk_categories = Column(JSON, nullable=True)  # ["涉政","色情"]
    auto_action = Column(String(20), nullable=False)  # blocked/flagged/none
    ai_reason = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending/approved/rejected/escalated
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    post = relationship("Post", foreign_keys=[post_id])
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class UserViolation(Base):
    """用户违规档案"""

    __tablename__ = "user_violations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    violation_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    status = Column(String(20), default="normal", nullable=False, index=True)  # normal/muted/banned
    muted_until = Column(DateTime, nullable=True)
    banned_at = Column(DateTime, nullable=True)
    ban_reason = Column(String(500), nullable=True)
    warning_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", foreign_keys=[user_id])


class UserViolationLog(Base):
    """违规操作明细"""

    __tablename__ = "user_violation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    moderation_id = Column(Integer, ForeignKey("content_moderations.id"), nullable=True)
    action = Column(String(20), nullable=False)  # warn/mute/ban/unmute/unban
    duration_hours = Column(Integer, nullable=True)
    reason = Column(String(500), nullable=True)
    operated_by = Column(Integer, nullable=True)  # null=system, else admin user_id
    created_at = Column(DateTime, default=_utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id])


class UserNotification(Base):
    """站内通知"""

    __tablename__ = "user_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(30), nullable=False, index=True)  # like/comment/follow/bookmark/collect/system/moderation/mute/ban/post_approved/post_rejected
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ref_type = Column(String(20), nullable=True)  # post/comment/user
    ref_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    related_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id], backref="user_notifications")
    actor = relationship("User", foreign_keys=[actor_id])


# ── IM 即时通讯 ──


class ImFriendRequest(Base):
    """好友请求"""

    __tablename__ = "im_friend_requests"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String(200), nullable=True)  # 验证消息
    status = Column(String(20), default="pending", index=True)  # pending/accepted/declined
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("from_user_id", "to_user_id"),)


class ImConversation(Base):
    """IM会话（私聊/群聊）"""

    __tablename__ = "im_conversations"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(10), default="private", index=True)  # private/group
    name = Column(String(100), nullable=True)  # 群名称
    avatar = Column(String(500), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 群主
    announcement = Column(Text, nullable=True)
    last_message_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ImConversationMember(Base):
    """会话成员"""

    __tablename__ = "im_conversation_members"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("im_conversations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), default="member")  # owner/admin/member
    mute_until = Column(DateTime, nullable=True)
    nickname_in_group = Column(String(50), nullable=True)
    is_pinned = Column(Boolean, default=False)
    last_read_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, default=_utcnow)

    __table_args__ = (UniqueConstraint("conversation_id", "user_id"),)


class ImMessage(Base):
    """IM消息"""

    __tablename__ = "im_messages"
    __table_args__ = (Index("idx_im_msg_conv_created", "conversation_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("im_conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    msg_type = Column(String(20), default="text", index=True)  # text/image/video/file/voice/system/share_post
    content = Column(Text, nullable=True)  # 文本内容
    metadata_json = Column(JSON, nullable=True)  # 媒体元数据
    reply_to_id = Column(Integer, ForeignKey("im_messages.id"), nullable=True)
    status = Column(String(20), default="sent")  # sent/delivered/read
    is_recalled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow, index=True)


class LLMModuleConfig(Base):
    """LLM 模块配置"""

    __tablename__ = "llm_module_configs"

    id = Column(Integer, primary_key=True, index=True)
    module_key = Column(String(50), unique=True, nullable=False, index=True)
    module_name = Column(String(100), nullable=False)
    module_description = Column(String(500), nullable=True)
    provider = Column(String(50), nullable=False, default="dashscope")
    chat_model = Column(String(100), nullable=True)
    vision_model = Column(String(100), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    api_key = Column(String(500), nullable=True)
    base_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class LLMPrompt(Base):
    """模块级提示词配置（管理后台可编辑，用于白斑识别等准确度持续迭代）"""

    __tablename__ = "llm_prompts"
    __table_args__ = (UniqueConstraint("module_key", "prompt_key", name="uq_llm_prompt_module_key"),)

    id = Column(Integer, primary_key=True, index=True)
    module_key = Column(String(50), nullable=False, index=True)
    prompt_key = Column(String(80), nullable=False)
    prompt_name = Column(String(120), nullable=False)
    prompt_text = Column(Text, nullable=False)  # 当前生效的提示词模板
    default_text = Column(Text, nullable=True)  # 内置默认模板（用于「恢复默认」）
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    updated_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ImMessageRead(Base):
    """消息已读追踪"""

    __tablename__ = "im_message_reads"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("im_messages.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    read_at = Column(DateTime, default=_utcnow)

    __table_args__ = (UniqueConstraint("message_id", "user_id"),)


class ImMessageModeration(Base):
    """IM消息风控"""

    __tablename__ = "im_message_moderations"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("im_messages.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content_snapshot = Column(Text, nullable=True)
    risk_level = Column(String(20), nullable=False, index=True)
    risk_categories = Column(JSON, nullable=True)
    auto_action = Column(String(20), default="flagged")
    ai_reason = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    status = Column(String(20), default="pending", index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)


class Notification(Base):
    """用户通知 (DEPRECATED: 请使用 UserNotification)
    
    此模型已被 UserNotification 替代，保留仅为兼容旧数据库表。
    新代码应使用 UserNotification (user_notifications 表)。
    """

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # 触发者 (可为空，如系统通知)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    type = Column(String(20), nullable=False, index=True)  # like/comment/follow/bookmark/collect/system/moderation
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    # 关联对象
    ref_type = Column(String(20), nullable=True)  # post/comment/user
    ref_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id], backref="notifications")
    actor = relationship("User", foreign_keys=[actor_id])


class AdminGeneratedPost(Base):
    """管理员自动生成的内容草稿"""
    __tablename__ = "admin_generated_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    content_json = Column(Text, nullable=True)
    content_preview = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("community_categories.id"), nullable=False)
    post_type = Column(String(20), default="long", nullable=False)
    images = Column(Text, nullable=True)  # JSON array of image URLs
    tag_names = Column(Text, nullable=True)  # JSON array of tag names
    city = Column(String(100), nullable=True)
    mood = Column(String(50), nullable=True)
    source_type = Column(String(50), nullable=True)  # pubmed/crossref/cma/foundation/news
    source_refs = Column(Text, nullable=True)  # JSON array of source references
    status = Column(String(20), default="draft", nullable=False)  # draft/pending/published/rejected
    ai_confidence = Column(Float, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    published_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # admin user id
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    category = relationship("CommunityCategory", backref="generated_posts")
    published_post = relationship("Post", backref="generated_from")


# ── 用药提醒 ──


class MedicationReminder(Base):
    """用药提醒"""

    __tablename__ = "medication_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    medication_name = Column(String(100), nullable=False)  # 药品名称
    dosage = Column(String(100), nullable=True)  # 剂量
    frequency = Column(String(50), nullable=False)  # daily/twice_daily/weekly/custom
    reminder_times = Column(Text, nullable=True)  # JSON array of times ["08:00", "20:00"]
    reminder_days = Column(Text, nullable=True)  # JSON array of days [1,2,3,4,5,6,7] (1=Monday)
    notes = Column(Text, nullable=True)  # 备注
    is_active = Column(Boolean, default=True, index=True)
    push_subscription_id = Column(Integer, nullable=True)  # 关联的推送订阅
    last_push_time = Column(String(16), nullable=True)  # 上次推送的时间槽 "YYYY-MM-DD HH:MM"（防重复推送）
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", backref="medication_reminders")


class PushSubscription(Base):
    """Web Push 订阅"""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    endpoint = Column(String(500), nullable=False, unique=True)
    p256dh_key = Column(String(200), nullable=False)
    auth_key = Column(String(100), nullable=False)
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", backref="push_subscriptions")


# ── AI病情日记 ──


class DiaryEntry(Base):
    """AI病情日记 — 对话式记录 + AI结构化提取"""

    __tablename__ = "diary_entries"
    __table_args__ = (
        Index("idx_diary_user_date", "user_id", "entry_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("patient_profiles.id"), nullable=True)

    # 原始输入
    raw_text = Column(Text, nullable=False)  # 用户原始输入
    input_type = Column(String(20), default="text")  # text/voice/quick

    # AI结构化提取结果
    mood = Column(String(20), nullable=True)  # good/neutral/bad/anxious/hopeful
    sleep_quality = Column(String(20), nullable=True)  # good/fair/poor
    diet_notes = Column(Text, nullable=True)  # 饮食记录
    medication_taken = Column(Text, nullable=True)  # 用药记录 JSON
    stress_level = Column(Integer, nullable=True)  # 压力 1-5
    skin_condition = Column(String(50), nullable=True)  # stable/improving/spreading/new_spots
    treatment_events_json = Column(Text, nullable=True)  # 治疗事件 JSON
    ai_summary = Column(Text, nullable=True)  # AI生成的日记摘要
    ai_extracted_json = Column(Text, nullable=True)  # 完整AI提取结果

    # 关联
    vasi_assessment_id = Column(Integer, nullable=True)  # 关联VASI评估
    is_public = Column(Boolean, default=False)  # 是否公开到社区
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)  # 关联的社区帖子

    entry_date = Column(Date, nullable=False, index=True)  # 日记日期
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", backref="diary_entries")


class TreatmentEvent(Base):
    """治疗事件 — 从日记/帖子/报告中提取"""

    __tablename__ = "treatment_events"
    __table_args__ = (
        Index("idx_treatment_user_date", "user_id", "event_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("patient_profiles.id"), nullable=True)

    event_type = Column(String(30), nullable=False)  # medication/phototherapy/surgery/consultation/diagnosis
    event_date = Column(Date, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # 结构化字段
    medication_name = Column(String(100), nullable=True)
    dosage = Column(String(100), nullable=True)
    body_site = Column(String(50), nullable=True)
    doctor = Column(String(100), nullable=True)
    hospital = Column(String(200), nullable=True)
    cost = Column(Float, nullable=True)

    # 来源
    source = Column(String(20), default="manual")  # manual/diary_ai/post_ai/report_ai
    source_ref_id = Column(Integer, nullable=True)  # 关联的日记/帖子/报告ID

    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", backref="treatment_events")


# ── 日记图片（图文日记）──


class DiaryImage(Base):
    """日记图片 — 每张照片可标注部位/拍摄日期，并存储轻量视觉分析结果。

    与 DiaryEntry 为多对一关系；可选关联一次深度 VASI 评估（vasi_assessment_id）。
    """

    __tablename__ = "diary_images"
    __table_args__ = (
        Index("idx_diary_image_entry", "diary_entry_id"),
        Index("idx_diary_image_user_date", "user_id", "capture_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    diary_entry_id = Column(
        Integer, ForeignKey("diary_entries.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    image_url = Column(String, nullable=False)  # 受保护访问的图片URL
    image_key = Column(String, nullable=True)  # 存储key（预留）
    thumbnail_url = Column(String, nullable=True)  # 缩略图URL（预留）

    body_site = Column(String(50), nullable=True)  # 照片对应身体部位
    capture_date = Column(Date, nullable=True, index=True)  # 拍摄/记录日期（支持历史补录）

    # 轻量视觉分析结果 JSON：颜色/边界/面积印象/对比印象等定性描述
    visual_analysis_json = Column(Text, nullable=True)
    # 可选：触发深度 VASI 分析后关联的评估记录
    vasi_assessment_id = Column(Integer, nullable=True)
    # pending / analyzing / light_done / failed
    analysis_status = Column(String(20), default="pending")

    order_index = Column(Integer, default=0)  # 展示排序
    created_at = Column(DateTime, default=_utcnow)

    entry = relationship("DiaryEntry", backref="diary_images")
    user = relationship("User")


# ── 白斑变化报告 ──


class SkinReport(Base):
    """白斑变化分析报告 — 周报/月报/对比报告。

    聚合用户的日记、日记图片（轻量分析）与 VASI 评估（深度数值），
    由 AI 生成结构化指标与叙事文本，可导出网页/PDF/海报并发布到发现。
    """

    __tablename__ = "skin_reports"
    __table_args__ = (
        Index("idx_skin_report_user", "user_id", "created_at"),
        Index("idx_skin_report_shared", "share_token"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("patient_profiles.id"), nullable=True)

    # weekly / monthly / comparison
    report_type = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)

    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    body_site = Column(String(50), nullable=True)  # 聚焦部位，空表示全身概览

    # 源数据快照（日记/VASI/图片摘要），保证报告可复现
    source_data_json = Column(Text, nullable=True)
    # 结构化指标：VASI变化/面积变化/分型分期/心情趋势/用药依从性等
    metrics_json = Column(Text, nullable=True)

    # AI 生成的叙事文本（深度解读，可分段）
    narrative = Column(Text, nullable=True)
    insights_json = Column(Text, nullable=True)  # AI 洞察要点数组
    recommendations_json = Column(Text, nullable=True)  # AI 建议数组

    cover_composite_url = Column(String, nullable=True)  # 封面/前后对比合成图
    trend_chart_data = Column(Text, nullable=True)  # 趋势曲线数据 JSON（前端渲染用）

    # generating / completed / failed
    status = Column(String(20), default="generating", nullable=False)
    llm_module = Column(String(40), default="skin_report", nullable=True)
    error_message = Column(Text, nullable=True)

    is_public = Column(Boolean, default=False)  # 是否已分享到社区
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)  # 关联社区帖子
    share_token = Column(String(64), nullable=True, index=True)  # 公开访问 token

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", backref="skin_reports")


class SpotComparison(Base):
    """同部位两张白斑照片的配对对比识别结果 — 周报/月报的数据基元。

    ref_a / ref_b 为照片引用串："pi:{post_image_id}" 或 "va:{vasi_assessment_id}"，
    支持日记照片与 VASI 测评照片跨表配对。同一图对只计算一次（唯一索引缓存）。
    """

    __tablename__ = "spot_comparisons"
    __table_args__ = (
        Index("idx_spot_cmp_pair", "ref_a", "ref_b", unique=True),
        Index("idx_spot_cmp_user", "user_id", "body_site"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    ref_a = Column(String(40), nullable=False)  # 早期照片引用（旧）
    ref_b = Column(String(40), nullable=False)  # 近期照片引用（新）
    body_site = Column(String(50), nullable=True)  # 归一化部位 key

    # 识别结果：vlm(双图视觉对比) + cv(像素交叉验证) + merged(最终指标)
    metrics_json = Column(Text, nullable=True)
    model_version = Column(String(80), nullable=True)
    status = Column(String(20), default="completed", nullable=False)  # completed / failed
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


def ensure_spot_comparison_table() -> None:
    """创建 spot_comparisons 表（新表，additive only，安全可重复调用）。"""
    from web.backend.database.database import engine

    try:
        SpotComparison.__table__.create(engine, checkfirst=True)
        print("[migrate] spot_comparisons table ready")
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] spot_comparisons create failed: {e}")


def ensure_diary_columns() -> None:
    """为 diary_entries 增补图文日记所需列（additive only，安全可重复调用）。"""
    from sqlalchemy import inspect as sqla_inspect

    from web.backend.database.database import engine

    new_columns = {
        "images_count": ("INTEGER", "0"),
        "body_sites_json": ("TEXT", None),
        "report_eligible": ("BOOLEAN", "1"),
    }
    try:
        insp = sqla_inspect(engine)
        existing_columns = {c["name"] for c in insp.get_columns("diary_entries")}
        for col_name, (col_type, default_val) in new_columns.items():
            if col_name in existing_columns:
                continue
            try:
                default_clause = f" DEFAULT {default_val}" if default_val else ""
                sql = (
                    f"ALTER TABLE diary_entries ADD COLUMN {col_name} "
                    f"{col_type}{default_clause}"
                )
                with engine.connect() as conn:
                    conn.exec_driver_sql(sql)
                    conn.commit()
                print(f"[migrate] Added column diary_entries.{col_name} ({col_type})")
            except Exception as e:  # noqa: BLE001
                # 列可能已存在（并发启动），忽略
                print(f"[migrate] diary_entries.{col_name}: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] diary_entries migration check failed: {e}")


def ensure_post_columns() -> None:
    """为 posts 增补 AI 增强字段（additive only，安全可重复调用）。"""
    from sqlalchemy import inspect as sqla_inspect

    from web.backend.database.database import engine

    new_columns = {
        "ai_summary": ("TEXT", None),
        "ai_extracted_json": ("TEXT", None),
    }
    try:
        insp = sqla_inspect(engine)
        if not insp.has_table("posts"):
            return
        existing = {c["name"] for c in insp.get_columns("posts")}
        for col_name, (col_type, default_val) in new_columns.items():
            if col_name in existing:
                continue
            try:
                default_clause = f" DEFAULT {default_val}" if default_val else ""
                sql = f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}{default_clause}"
                with engine.connect() as conn:
                    conn.exec_driver_sql(sql)
                    conn.commit()
                print(f"[migrate] Added column posts.{col_name} ({col_type})")
            except Exception as e:  # noqa: BLE001
                print(f"[migrate] posts.{col_name}: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] posts migration check failed: {e}")


def ensure_post_image_columns() -> None:
    """为 post_images 增补视觉分析相关字段（additive only，安全可重复调用）。"""
    from sqlalchemy import inspect as sqla_inspect

    from web.backend.database.database import engine

    new_columns = {
        "user_id": ("INTEGER", None),
        "body_site": ("VARCHAR(50)", None),
        "capture_date": ("DATE", None),
        "visual_analysis_json": ("TEXT", None),
        "analysis_status": ("VARCHAR(20)", "'pending'"),
        "vasi_assessment_id": ("INTEGER", None),
    }
    try:
        insp = sqla_inspect(engine)
        if not insp.has_table("post_images"):
            return
        existing = {c["name"] for c in insp.get_columns("post_images")}
        for col_name, (col_type, default_val) in new_columns.items():
            if col_name in existing:
                continue
            try:
                default_clause = f" DEFAULT {default_val}" if default_val else ""
                sql = (
                    f"ALTER TABLE post_images ADD COLUMN {col_name} "
                    f"{col_type}{default_clause}"
                )
                with engine.connect() as conn:
                    conn.exec_driver_sql(sql)
                    conn.commit()
                print(f"[migrate] Added column post_images.{col_name} ({col_type})")
            except Exception as e:  # noqa: BLE001
                print(f"[migrate] post_images.{col_name}: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] post_images migration check failed: {e}")


# ── 医生认证 ──


class DoctorVerification(Base):
    """医生认证申请"""

    __tablename__ = "doctor_verifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    real_name = Column(String(50), nullable=False)  # 真实姓名
    hospital = Column(String(100), nullable=False)  # 医院
    department = Column(String(100), nullable=True)  # 科室
    title = Column(String(50), nullable=True)  # 职称 (主任医师/副主任医师/主治医师/住院医师)
    license_number = Column(String(50), nullable=True)  # 执业医师资格证号
    specialty = Column(String(200), nullable=True)  # 擅长领域
    proof_images = Column(Text, nullable=True)  # JSON array of proof image URLs
    status = Column(String(20), default="pending", index=True)  # pending/approved/rejected
    review_note = Column(Text, nullable=True)  # 审核备注
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 审核人
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", foreign_keys=[user_id], backref="doctor_verifications")
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class DoctorInvitation(Base):
    """医生邀请码"""

    __tablename__ = "doctor_invitations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # 邀请码
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # 创建人 (admin)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 使用人
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    creator = relationship("User", foreign_keys=[created_by], backref="created_invitations")
    user = relationship("User", foreign_keys=[used_by], backref="used_invitation")


class UserConsent(Base):
    """用户同意记录（2026-08-30 隐私加固补齐 — 此前 API 引用但模型缺失）

    consent_type: terms / privacy / ai_data / medical_photo
    is_active=False 的行表示撤销记录；判定有效同意须取该类型最新一行（含撤销行），
    仅当最新一行 is_active=True 才视为同意（见 services/consent.py:latest_consent）。
    """

    __tablename__ = "user_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    consent_type = Column(String(30), nullable=False, index=True)
    consent_version = Column(String(20), nullable=False)
    consented_at = Column(DateTime, default=_utcnow)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_fingerprint = Column(String, nullable=True)
    platform = Column(String(20), nullable=True)
    source = Column(String(30), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class UserAssistantPreference(Base):
    """小白管家外观偏好（用户主动设置的非敏感 UI 偏好，跨设备同步）"""

    __tablename__ = "user_assistant_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, index=True, nullable=False,
    )
    mascot = Column(String(20), nullable=True)   # real(金斑蝶)/deer(梅花鹿)
    style = Column(String(20), nullable=True)    # circle/rounded
    size = Column(String(10), nullable=True)     # small/medium/large
    position = Column(String(10), nullable=True) # right/left
    greeting = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", foreign_keys=[user_id])


class Hospital(Base):
    """医院/院区目录（医评 /hospitals 模块）。

    origin=official：平台按官方来源收录的目录条目（lat/lng 为城市中心，非院区导航坐标）。
    origin=community：病友自行补充的条目，前端必须明确标注「病友补充·待核实」。
    本表只存机构信息，不存医生个人联系方式；医生信息由病友评价自行填写（仅姓氏/职称/科室）。
    """

    __tablename__ = "hospitals"
    __table_args__ = (
        Index("idx_hospital_region", "province", "city"),
        Index("idx_hospital_origin_status", "origin", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, index=True, nullable=False)  # 稳定标识（前端离线兜底沿用同一 slug）
    name = Column(String(200), nullable=False)
    province = Column(String(50), nullable=False, index=True)
    city = Column(String(50), nullable=False, index=True)
    district = Column(String(50), nullable=True)      # 区/县
    address = Column(String(300), nullable=True)      # 详细地址/院区（病友补充条目由提交者填写）
    department = Column(String(100), nullable=True)   # 就诊科室
    kind = Column(String(50), nullable=True)          # 综合医院 / 皮肤病专科 / 其他
    features = Column(JSON, nullable=True)            # 官方提及的诊疗服务
    summary = Column(Text, nullable=True)
    source = Column(String(500), nullable=True)       # 官方来源链接
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    origin = Column(String(20), default="official", nullable=False)  # official / community
    status = Column(String(20), default="visible", nullable=False, index=True)  # visible / hidden
    checked_at = Column(String(20), nullable=True)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class HospitalReview(Base):
    """病友公开评价/分享（医院、医生、治疗方案、治疗经历）。

    公开可见性：status=visible 且 moderation_status!=blocked。
    主观体验（ratings/tags）与疗效自述（outcome）分开存储，避免把自述当疗效证据。
    """

    __tablename__ = "hospital_reviews"
    __table_args__ = (
        Index("idx_hospital_review_lookup", "hospital_id", "status", "moderation_status"),
        Index("idx_hospital_review_target", "target"),
        Index("idx_hospital_review_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target = Column(String(20), nullable=False, default="hospital")  # hospital/doctor/treatment/experience

    # 医生评价：仅「称呼 + 职称 + 科室」，禁止联系方式
    doctor_name = Column(String(40), nullable=True)
    doctor_title = Column(String(40), nullable=True)
    doctor_department = Column(String(60), nullable=True)
    # 治疗方案评价
    treatment_name = Column(String(120), nullable=True)
    treatment_detail = Column(String(500), nullable=True)

    visit_month = Column(String(7), nullable=True)   # YYYY-MM
    duration = Column(String(20), nullable=True)     # 治疗时长区间
    cost = Column(String(20), nullable=True)         # 每月自付费用区间
    outcome = Column(String(20), nullable=True)      # 效果自述（与主观评分分开）
    ratings = Column(JSON, nullable=True)            # 旧版 {"医护沟通": 4, ...}（保留兼容，不再新增）
    # 统一 6 维就医体验档位（v3 起唯一评分体系）：
    # {"医患沟通": "satisfied"|"neutral"|"unsatisfied"|"na", ...}
    # 不含任何疗效/医术维度 —— 合规红线见 review_risk.BANNED_DIMENSIONS
    experience_scores = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    # 凭证图（费用单/挂号单/处方/检查单；明确禁止病情照片）：[{"url": ..., "label": "费用单"}]
    # v3 起默认不公开：仅作者与管理员可读，公开层只显示「已上传」徽标
    images = Column(JSON, nullable=True)
    content = Column(Text, nullable=False)

    # approved / flagged / restricted / blocked
    # restricted = 公开但降权且不进聚合（举报阈值 / 风险分档触发），并非下架
    moderation_status = Column(String(20), default="approved", nullable=False)
    risk_reason = Column(String(500), nullable=True)
    # v3 风控留痕：规则分（可解释）+ 命中标签 + 受限原因 + 聚合冷处理截止时间
    risk_score = Column(Float, nullable=True)
    risk_flags = Column(JSON, nullable=True)
    restricted_reason = Column(String(300), nullable=True)
    aggregate_after = Column(DateTime, nullable=True)
    # PIPL 第 28/29 条：病情描述属敏感个人信息 → 单独同意留痕（禁止默认勾选）
    health_consent = Column(Boolean, default=False, nullable=False)
    appeal_status = Column(String(20), default="none", nullable=False)  # none/pending/resolved
    status = Column(String(20), default="visible", nullable=False)  # visible / deleted

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class HospitalReviewReport(Base):
    """用户对某条医评的举报（一人一条，唯一约束保证幂等）。

    达阈值后自动把被举报评价置为 restricted（不进聚合、排序垫底）并入后台队列。
    """

    __tablename__ = "hospital_review_reports"
    __table_args__ = (
        Index("idx_hospital_report_unique", "review_id", "reporter_id", unique=True),
        Index("idx_hospital_report_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("hospital_reviews.id"), nullable=False, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reason_code = Column(String(30), nullable=False)  # fake/abuse/privacy/ad/promotion/other
    detail = Column(String(500), nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending/upheld/dismissed
    handled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    handled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class HospitalReviewAppeal(Base):
    """评价申诉（被评价方 / 被误判作者双向共用）。

    《民法典》第 1028 条要求对失实内容及时更正或删除；本表提供可预期的救济通道，
    默认 3 个工作日时限（due_at），超时在管理后台标红。
    """

    __tablename__ = "hospital_review_appeals"
    __table_args__ = (Index("idx_hospital_appeal_status", "status", "due_at"),)

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("hospital_reviews.id"), nullable=False, index=True)
    # 申诉人身份：被评价机构 / 被评价医生 / 评价作者（认为自己被误判）/ 其他
    claimant_type = Column(String(20), nullable=False)  # hospital/doctor/author/other
    claimant_name = Column(String(80), nullable=False)
    contact = Column(String(120), nullable=False)       # 联系方式（仅管理员可见）
    reason = Column(Text, nullable=False)
    evidence_urls = Column(JSON, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending/accepted/rejected
    resolution = Column(String(300), nullable=True)
    resolved_action = Column(String(20), nullable=True)  # keep/request_edit/hide/append_note
    handled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    handled_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)  # 3 个工作日时限
    created_at = Column(DateTime, default=_utcnow)


class HospitalReviewHelpful(Base):
    """病友给评价点「有用」（一人一票，唯一约束保证幂等）。"""

    __tablename__ = "hospital_review_helpfuls"
    __table_args__ = (
        Index("idx_hospital_helpful_unique", "review_id", "user_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("hospital_reviews.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)


def ensure_hospital_tables() -> None:
    """创建医评相关表并补齐新列（additive only，安全可重复调用）。

    新表：hospitals / hospital_reviews / hospital_review_helpfuls
          + v3 新增 hospital_review_reports / hospital_review_appeals
    既有表只做 ADD COLUMN，绝不删除或重命名。
    """
    from sqlalchemy import inspect as sqla_inspect

    from web.backend.database.database import engine

    try:
        Hospital.__table__.create(engine, checkfirst=True)
        HospitalReview.__table__.create(engine, checkfirst=True)
        HospitalReviewHelpful.__table__.create(engine, checkfirst=True)
        HospitalReviewReport.__table__.create(engine, checkfirst=True)
        HospitalReviewAppeal.__table__.create(engine, checkfirst=True)
        inspector = sqla_inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("hospital_reviews")}
        # 列名 → DDL 类型（全部可空，带默认值，向后兼容既有行）
        additions = {
            "images": "JSON",
            "experience_scores": "JSON",
            "risk_score": "FLOAT",
            "risk_flags": "JSON",
            "restricted_reason": "VARCHAR(300)",
            "aggregate_after": "DATETIME",
            "health_consent": "BOOLEAN DEFAULT 0",
            "appeal_status": "VARCHAR(20) DEFAULT 'none'",
        }
        for name, ddl in additions.items():
            if name in columns:
                continue
            with engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE hospital_reviews ADD COLUMN {name} {ddl}"))
        print("[migrate] hospitals / hospital_reviews / hospital_review_helpfuls / reports / appeals tables ready")
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] hospital tables create failed: {e}")
