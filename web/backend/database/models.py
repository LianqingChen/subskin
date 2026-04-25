"""
数据库 ORM 模型
"""

import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
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
    token = Column(String, unique=True, nullable=False, index=True)
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
    pwa_installed = Column(Boolean, default=False)
    pwa_installed_at = Column(DateTime, nullable=True)
    privacy_mode = Column(
        Boolean, default=True, nullable=False
    )  # True = eye open = info visible
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
    source = Column(String, nullable=True)  # 来源（PubMed/ClinicalTrial/指南等）
    source_url = Column(String, nullable=True)
    category = Column(String, nullable=True)  # 分类
    embedding = Column(Text, nullable=True)  # 向量（JSON格式）
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
    diary_date = Column(Date, nullable=True, index=True)
    mood = Column(String, nullable=True)  # 心情标签: 💪坚持中 / 😔低落 / 🎉好转 / 🤔疑问
    is_anonymous = Column(Boolean, default=False)  # 匿名发布
    city = Column(String(100), nullable=True, index=True)  # 发布时所在城市
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
    title = Column(String, nullable=False)
    tags = Column(String, nullable=True)
    interpretation_json = Column(JSON, nullable=True)  # AI解读结果
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", backref="medical_reports")
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
