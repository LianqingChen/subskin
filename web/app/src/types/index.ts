export interface User {
  id: number
  uid: string | null
  username: string
  avatar_url: string | null
  email: string | null
  phone: string | null
  patient_relation?: string | null
  is_active: boolean
  is_admin: boolean
  is_doctor?: boolean
  is_verified?: boolean
  user_status?: string
  muted_until?: string | null
  created_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  timestamp: number
  isLoading?: boolean
  isSkeleton?: boolean
  thinkingStage?: string
  thinkingMessage?: string
  isVoice?: boolean
  attachments?: ChatAttachment[]
  actionCards?: ActionCard[]
}

// ── Chat Attachment & Action Card Types ──

export interface ChatAttachment {
  id: string
  type: 'image' | 'document'
  url: string
  name: string
  size: number
  mimeType: string
  thumbnailUrl?: string
}

export interface VASICard {
  type: 'vasi'
  vasiScore: number
  bodySite: string
  classification: string
  stage: string
  riskLevel: string
  areaPercentage: number
  imageUrl: string
  saved: boolean
}

export interface ReportFinding {
  name: string
  value: string
  reference: string
  status: string
  risk: string
  explanation: string
}

export interface ReportCard {
  type: 'report'
  title: string
  reportType: string
  riskLevel: string
  summary: string
  keyFindings: ReportFinding[]
  recommendations: string[]
  disclaimer: string
  fileUrl: string
  fileName: string
  saved: boolean
}

export interface DiaryCard {
  type: 'diary'
  title: string
  content: string
  date: string
  privacy: 'private' | 'public'
  saved: boolean
}

export type ActionCard = VASICard | ReportCard | DiaryCard

export interface Source {
  title: string
  url?: string
  snippet?: string
}

// ── Community Types (aligned with backend API) ──

export interface Category {
  id: number
  name: string
  description: string | null
  icon: string | null
  post_count: number
}

export interface PostAuthor {
  id: number
  username: string
  avatar: string | null
  is_doctor: boolean
  is_verified?: boolean
  is_followed?: boolean
}

export interface PostImage {
  id: number
  image_url: string
  order: number
}

export interface PostAudio {
  id: number
  audio_url: string
  duration: number
  file_size: number
  order: number
}

export interface PostAttachment {
  id: number
  file_url: string
  file_name: string
  file_size: number
  file_type: string
  order: number
}

export interface PostTag {
  id: number
  name: string
  usage_count: number
}

export interface Post {
  id: number
  title: string
  content: string
  content_json: string | null
  post_type?: 'image' | 'video' | 'text' | 'long'
  content_preview?: string | null
  video_url?: string | null
  video_thumbnail?: string | null
  category_id: number
  author: PostAuthor
  category: Category
  images: PostImage[]
  audios: PostAudio[]
  attachments: PostAttachment[]
  tags: PostTag[]
  is_private: boolean
  diary_date: string | null
  diary_type: string | null
  mood: string | null
  is_anonymous: boolean
  city?: string | null
  latitude?: number | null
  longitude?: number | null
  distance?: number | null
  like_count: number
  comment_count: number
  is_liked: boolean
  is_bookmarked: boolean
  moderation_status?: string
  created_at: string
  updated_at: string
}

export interface PostListResponse {
  total: number
  items: Post[]
  next_cursor?: string | null
}

export interface PostCommentAuthor {
  id: number
  username: string
}

export interface PostComment {
  id: number
  content: string
  author: PostCommentAuthor
  post_id: number
  created_at: string
  updated_at: string
}

export interface PostCommentListResponse {
  total: number
  items: PostComment[]
}

export interface LikeResponse {
  liked: boolean
  like_count: number
}

export interface ImageUploadResponse {
  image_url: string
}

export interface AudioUploadResponse {
  audio_url: string
  duration: number
  file_size: number
}

export interface FileUploadResponse {
  file_url: string
  file_name: string
  file_size: number
  file_type: string
}

// ── Request Types ──

export interface PostCreateRequest {
  title: string
  content: string
  content_json?: string
  post_type?: 'image' | 'video' | 'text' | 'long'
  category_id: number
  images?: string[]
  video_url?: string
  video_thumbnail?: string
  tag_names?: string[]
  is_private?: boolean
  diary_date?: string
  diary_type?: string
  mood?: string
  is_anonymous?: boolean
  city?: string | null
  latitude?: number | null
  longitude?: number | null
}

export interface PostUpdateRequest {
  title?: string
  content?: string
  content_json?: string
  post_type?: 'image' | 'video' | 'text' | 'long'
  category_id?: number
  tag_names?: string[]
  is_private?: boolean
  diary_date?: string
  diary_type?: string
  mood?: string
  is_anonymous?: boolean
  images?: string[]
  city?: string | null
  latitude?: number | null
  longitude?: number | null
}

export interface CommentCreateRequest {
  content: string
}

// ── Legacy string-based category (for frontend-only category labels) ──
// Backend uses Category{ id, name, icon } but we keep these for UI labels
// as fallback when API categories haven't loaded yet

export type PostCategory =
  | 'treatment'
  | 'medication'
  | 'hospital'
  | 'diet'
  | 'concealment'
  | 'emotional'
  | 'newly_diagnosed'

export const POST_CATEGORY_LABELS: Record<PostCategory, string> = {
  treatment: '治疗经验',
  medication: '药效分享',
  hospital: '医院评价',
  diet: '日常忌口',
  concealment: '遮盖妙招',
  emotional: '心情驿站',
  newly_diagnosed: '新确诊指南',
}

export const POST_CATEGORY_ICONS: Record<PostCategory, string> = {
  treatment: 'ri-hospital-line',
  medication: 'ri-capsule-line',
  hospital: 'ri-search-line',
  diet: 'ri-restaurant-line',
  concealment: 'ri-brush-line',
  emotional: 'ri-boxing-line',
  newly_diagnosed: 'ri-newspaper-line',
}

// ── Collections (Knowledge Base) ──

export interface Collection {
  id: number
  name: string
  description: string | null
  icon: string | null
  is_public: boolean
  share_slug: string | null
  item_count: number
  created_at: string
  updated_at: string
}

export interface CollectionItem {
  id: number
  post_id: number
  post: Post
  note: string | null
  sort_order: number
  created_at: string
}

export interface PostFallback extends Post {
  is_bookmarked: boolean
}

export interface CollectionCreateRequest {
  name: string
  description?: string
  icon?: string
  is_public?: boolean
}

export interface CollectionUpdateRequest {
  name?: string
  description?: string
  icon?: string
  is_public?: boolean
}

export interface BookmarkResponse {
  bookmarked: boolean
  post_id: number
}

export interface PostVersion {
  id: number
  post_id: number
  editor: PostAuthor
  title: string
  content: string | null
  content_json: string | null
  edit_summary: string | null
  created_at: string
}

export interface PostVersionListResponse {
  total: number
  items: PostVersion[]
}

// ── VASI Assessment Types ──

export interface VasiAssessment {
  id: number
  date: string
  bodySite: string
  vasiScore: number
  areaPercentage: number
  stage: string
  classification: string
}

export interface VasiStats {
  latestScore: number
  improvement: number
  totalAssessments: number
  trend: string
}

export interface PublicUserProfile {
  id: number
  username: string
  avatar_url: string | null
  is_doctor: boolean
  patient_relation: string | null
  post_count: number
  following_count: number
  follower_count: number
  is_followed: boolean
  created_at: string | null
}
