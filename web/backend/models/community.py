from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CategoryBase(BaseModel):
    name: str = Field(..., description="分类名称")
    description: Optional[str] = Field(None, description="分类描述")
    icon: Optional[str] = Field(None, description="分类图标")


class Category(CategoryBase):
    id: int
    post_count: int = Field(..., description="该分类下的帖子数")

    class Config:
        from_attributes = True


class PostImageBase(BaseModel):
    image_url: str = Field(..., description="图片URL")
    order: int = Field(..., description="图片顺序")


class PostImage(PostImageBase):
    id: int

    class Config:
        from_attributes = True


class PostAudioBase(BaseModel):
    audio_url: str = Field(..., description="音频URL")
    duration: int = Field(0, description="时长(秒)")
    file_size: int = Field(0, description="文件大小(字节)")
    order: int = Field(0, description="排序")


class PostAudio(PostAudioBase):
    id: int

    class Config:
        from_attributes = True


class PostAttachmentBase(BaseModel):
    file_url: str = Field(..., description="文件URL")
    file_name: str = Field(..., description="原始文件名")
    file_size: int = Field(0, description="文件大小(字节)")
    file_type: str = Field("", description="MIME类型")
    order: int = Field(0, description="排序")


class PostAttachment(PostAttachmentBase):
    id: int

    class Config:
        from_attributes = True


class TagBase(BaseModel):
    name: str = Field(..., description="标签名称")


class Tag(TagBase):
    id: int
    usage_count: int = Field(0, description="使用次数")

    class Config:
        from_attributes = True


class PostBase(BaseModel):
    title: str = Field(..., description="帖子标题")
    content: str = Field(..., description="帖子内容(HTML)")
    content_json: Optional[str] = Field(None, description="Tiptap JSON格式内容")
    post_type: Optional[str] = Field(None, description="内容类型: image/video/text/long")
    video_url: Optional[str] = Field(None, description="视频文件URL")
    video_thumbnail: Optional[str] = Field(None, description="视频封面URL")
    category_id: int = Field(..., description="分类ID")
    is_private: bool = Field(False, description="是否私密（日记默认私密）")
    diary_date: Optional[str] = Field(None, description="日记日期(YYYY-MM-DD)")
    mood: Optional[str] = Field(None, description="心情标签: 💪坚持中/😔低落/🎉好转/🤔疑问")
    is_anonymous: bool = Field(False, description="是否匿名发布")
    city: Optional[str] = Field(None, description="发布时所在城市")


class PostCreate(PostBase):
    images: Optional[List[str]] = Field(None, description="图片URL列表")
    tag_names: Optional[List[str]] = Field(None, description="标签名称列表(最多5个)")


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, description="帖子标题")
    content: Optional[str] = Field(None, description="帖子内容(HTML)")
    content_json: Optional[str] = Field(None, description="Tiptap JSON格式内容")
    post_type: Optional[str] = Field(None, description="内容类型: image/video/text/long")
    video_url: Optional[str] = Field(None, description="视频文件URL")
    video_thumbnail: Optional[str] = Field(None, description="视频封面URL")
    category_id: Optional[int] = Field(None, description="分类ID")
    tag_names: Optional[List[str]] = Field(None, description="标签名称列表")
    is_private: Optional[bool] = Field(None, description="是否私密")
    diary_date: Optional[str] = Field(None, description="日记日期(YYYY-MM-DD)")
    mood: Optional[str] = Field(None, description="心情标签")
    is_anonymous: Optional[bool] = Field(None, description="是否匿名")
    city: Optional[str] = Field(None, description="发布时所在城市")


class PostAuthor(BaseModel):
    id: int
    username: str
    avatar: Optional[str] = None
    is_doctor: bool = Field(False, description="是否认证医生")

    class Config:
        from_attributes = True


class Post(PostBase):
    id: int
    author: PostAuthor
    category: Category
    images: List[PostImage]
    audios: List[PostAudio] = []
    attachments: List[PostAttachment] = []
    tags: List[Tag] = []
    content_preview: Optional[str] = None
    read_count: int = 0
    is_private: bool = False
    diary_date: Optional[str] = None
    mood: Optional[str] = None
    is_anonymous: bool = False
    like_count: int = Field(..., description="点赞数")
    comment_count: int = Field(..., description="评论数")
    is_liked: bool = Field(..., description="当前用户是否点赞")
    is_bookmarked: bool = Field(False, description="当前用户是否收藏")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    total: int = Field(..., description="总帖子数")
    items: List[Post] = Field(..., description="帖子列表")


class PostCommentBase(BaseModel):
    content: str = Field(..., description="评论内容")


class PostCommentCreate(PostCommentBase):
    pass


class PostCommentAuthor(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class PostComment(PostCommentBase):
    id: int
    author: PostCommentAuthor
    post_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PostCommentListResponse(BaseModel):
    total: int = Field(..., description="总评论数")
    items: List[PostComment] = Field(..., description="评论列表")


class LikeResponse(BaseModel):
    liked: bool = Field(..., description="是否已点赞")
    like_count: int = Field(..., description="当前点赞数")


class ImageUploadResponse(BaseModel):
    image_url: str = Field(..., description="图片URL")


class AudioUploadResponse(BaseModel):
    audio_url: str = Field(..., description="音频URL")
    duration: int = Field(0, description="时长(秒)")
    file_size: int = Field(0, description="文件大小(字节)")


class FileUploadResponse(BaseModel):
    file_url: str = Field(..., description="文件URL")
    file_name: str = Field(..., description="原始文件名")
    file_size: int = Field(0, description="文件大小(字节)")
    file_type: str = Field("", description="MIME类型")


# ── Collections ──


class CollectionCreate(BaseModel):
    name: str = Field(..., max_length=50)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_public: bool = False


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_public: Optional[bool] = None


class CollectionItemAdd(BaseModel):
    post_id: int
    note: Optional[str] = None


class CollectionItemResponse(BaseModel):
    id: int
    post_id: int
    post: Post
    note: Optional[str] = None
    sort_order: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class CollectionItemListResponse(BaseModel):
    total: int
    items: List[CollectionItemResponse]


class CollectionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_public: bool = False
    share_slug: Optional[str] = None
    item_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionListResponse(BaseModel):
    items: List[CollectionResponse]


class BookmarkResponse(BaseModel):
    bookmarked: bool
    post_id: int


# ── Post Versions ──


class PostVersionResponse(BaseModel):
    id: int
    post_id: int
    editor: PostAuthor
    title: str
    content: Optional[str] = None
    content_json: Optional[str] = None
    edit_summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PostVersionListResponse(BaseModel):
    total: int
    items: List[PostVersionResponse]


class MedicalReportFileResponse(BaseModel):
    id: int
    file_url: str
    file_name: str
    file_size: int
    file_type: Optional[str] = None
    order: int

    class Config:
        from_attributes = True


class MedicalReportResponse(BaseModel):
    id: int
    title: str
    tags: Optional[str] = None
    files: List[MedicalReportFileResponse] = []
    interpretation_json: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MedicalReportListResponse(BaseModel):
    total: int
    items: List[MedicalReportResponse]


class MedicalReportCreate(BaseModel):
    title: str
    tags: Optional[str] = None


class MedicalReportUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[str] = None
