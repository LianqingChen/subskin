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
from sqlalchemy import JSON
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    """对话历史（用于RAG多轮对话）"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    """单条消息"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)  # user/assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommunityCategory(Base):
    """社区帖子分类"""

    __tablename__ = "community_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Post(Base):
    """社区帖子"""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_json = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    content_preview = Column(Text, nullable=True)  # 前100字预览
    post_type = Column(String(20), nullable=True, default="long")  # image/video/text/long
    video_url = Column(String, nullable=True)  # 视频文件URL
    video_thumbnail = Column(String, nullable=True)  # 视频封面
    read_count = Column(Integer, default=0)  # 阅读数
    dwell_time = Column(Integer, default=0)  # 平均停留时间(秒)
    category_id = Column(
        Integer, ForeignKey("community_categories.id"), nullable=False, index=True
    )
    is_private = Column(Boolean, default=False, index=True)
    draft_expires_at = Column(DateTime, nullable=True, index=True)
    diary_date = Column(Date, nullable=True, index=True)
    mood = Column(String, nullable=True)  # 心情标签: 💪坚持中 / 😔低落 / 🎉好转 / 🤔疑问
    is_anonymous = Column(Boolean, default=False)  # 匿名发布
    moderation_status = Column(String(20), default="normal", nullable=False, index=True)  # normal/flagged/blocked/approved
    city = Column(String(100), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    image_url = Column(String, nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="likes")
    user = relationship("User", backref="post_likes")


class PostComment(Base):
    """帖子评论"""

    __tablename__ = "post_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("Post", back_populates="comments")
    author = relationship("User", backref="post_comments")


class Tag(Base):
    """标签"""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    """用户通知"""

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("CommunityCategory", backref="generated_posts")
    published_post = relationship("Post", backref="generated_from")
