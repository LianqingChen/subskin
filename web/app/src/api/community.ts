import apiClient from './client'
import type {
  Post,
  PostListResponse,
  PostCreateRequest,
  PostUpdateRequest,
  PostComment as PostCommentType,
  PostCommentListResponse,
  CommentCreateRequest,
  Category,
  LikeResponse,
  ImageUploadResponse,
  PostTag,
  AudioUploadResponse,
  FileUploadResponse,
  Collection,
  CollectionCreateRequest,
  CollectionUpdateRequest,
  BookmarkResponse,
  PostVersionListResponse,
} from '@/types'

export interface CommunityUserStats {
  post_count: number
  bookmark_count: number
  comment_count: number
}

export const communityApi = {
  async getCategories(): Promise<Category[]> {
    const { data } = await apiClient.get('/community/categories')
    return data
  },

  async getPosts(params?: { category_id?: number; tag?: string; post_type?: string; feed_type?: string; limit?: number; offset?: number }): Promise<PostListResponse> {
    const { data } = await apiClient.get('/community/posts', { params })
    return data
  },

  async getPost(postId: number): Promise<Post> {
    const { data } = await apiClient.get(`/community/posts/${postId}`)
    return data
  },

  // ── Diary ──

  async getMyDiaries(limit = 20, offset = 0): Promise<PostListResponse> {
    const { data } = await apiClient.get('/community/my-diaries', { params: { limit, offset } })
    return data
  },

  async createPost(payload: PostCreateRequest): Promise<Post> {
    const { data } = await apiClient.post('/community/posts', payload)
    return data
  },

  async updatePost(postId: number, payload: PostUpdateRequest): Promise<Post> {
    const { data } = await apiClient.put(`/community/posts/${postId}`, payload)
    return data
  },

  async shareDiaryToCommunity(postId: number): Promise<Post> {
    const { data } = await apiClient.put(`/community/posts/${postId}`, { is_private: false })
    return data
  },

  async deletePost(postId: number): Promise<void> {
    await apiClient.delete(`/community/posts/${postId}`)
  },

  async toggleLike(postId: number): Promise<LikeResponse> {
    const { data } = await apiClient.post(`/community/posts/${postId}/like`)
    return data
  },

  async toggleBookmark(postId: number): Promise<BookmarkResponse> {
    const { data } = await apiClient.post(`/community/posts/${postId}/bookmark`)
    return data
  },

  async getBookmarks(limit?: number, offset?: number): Promise<PostListResponse> {
    const { data } = await apiClient.get('/community/bookmarks', { params: { limit, offset } })
    return data
  },

  async getUserStats(): Promise<CommunityUserStats> {
    const { data } = await apiClient.get('/community/user-stats')
    return data
  },

  async getComments(postId: number, params?: { limit?: number; offset?: number }): Promise<PostCommentListResponse> {
    const { data } = await apiClient.get(`/community/posts/${postId}/comments`, { params })
    return data
  },

  async addComment(postId: number, payload: CommentCreateRequest): Promise<PostCommentType> {
    const { data } = await apiClient.post(`/community/posts/${postId}/comments`, payload)
    return data
  },

  async uploadImage(file: File): Promise<ImageUploadResponse> {
    const formData = new FormData()
    formData.append('image', file)
    const { data } = await apiClient.post('/community/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async uploadAudio(file: File): Promise<AudioUploadResponse> {
    const formData = new FormData()
    formData.append('audio', file)
    const { data } = await apiClient.post('/community/upload/audio', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async uploadFile(file: File): Promise<FileUploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post('/community/upload/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async getTags(params?: { q?: string; limit?: number }): Promise<PostTag[]> {
    const { data } = await apiClient.get('/community/tags', { params })
    return data
  },

  async getHotTags(limit?: number): Promise<PostTag[]> {
    const { data } = await apiClient.get('/community/tags/hot', { params: { limit } })
    return data
  },

  async updatePostTags(postId: number, tagNames: string[]): Promise<Post> {
    const { data } = await apiClient.put(`/community/posts/${postId}/tags`, { tag_names: tagNames })
    return data
  },

  async logInteraction(postId: number, actionType: string): Promise<void> {
    await apiClient.post(`/community/posts/${postId}/interact`, { action_type: actionType })
  },

  // ── Collections ──

  async createCollection(payload: CollectionCreateRequest): Promise<Collection> {
    const { data } = await apiClient.post('/community/collections', payload)
    return data
  },

  async getCollections(): Promise<{ items: Collection[] }> {
    const { data } = await apiClient.get('/community/collections')
    return data
  },

  async getCollection(collectionId: number): Promise<Collection> {
    const { data } = await apiClient.get(`/community/collections/${collectionId}`)
    return data
  },

  async getCollectionBySlug(slug: string): Promise<Collection> {
    const { data } = await apiClient.get(`/community/collections/slug/${slug}`)
    return data
  },

  async updateCollection(collectionId: number, payload: CollectionUpdateRequest): Promise<Collection> {
    const { data } = await apiClient.put(`/community/collections/${collectionId}`, payload)
    return data
  },

  async deleteCollection(collectionId: number): Promise<void> {
    await apiClient.delete(`/community/collections/${collectionId}`)
  },

  async addToCollection(collectionId: number, postId: number, note?: string): Promise<{ id: number; post_id: number; note: string | null }> {
    const { data } = await apiClient.post(`/community/collections/${collectionId}/items`, { post_id: postId, note })
    return data
  },

  async removeFromCollection(collectionId: number, postId: number): Promise<void> {
    await apiClient.delete(`/community/collections/${collectionId}/items/${postId}`)
  },

  async getCollectionItems(collectionId: number, limit?: number, offset?: number): Promise<{ total: number; items: any[] }> {
    const { data } = await apiClient.get(`/community/collections/${collectionId}/items`, { params: { limit, offset } })
    return data
  },

  // ── Post Versions ──

  async getPostVersions(postId: number, limit?: number, offset?: number): Promise<PostVersionListResponse> {
    const { data } = await apiClient.get(`/community/posts/${postId}/versions`, { params: { limit, offset } })
    return data
  },

  async checkClaims(title: string, content: string): Promise<{ has_claims: boolean; words: string[] }> {
    const { data } = await apiClient.post('/community/check-claims', { title, content })
    return data
  },

  // ── Social (follow/block/report) ──

  async followUser(userId: number): Promise<void> {
    await apiClient.post(`/community/follow/${userId}`)
  },

  async unfollowUser(userId: number): Promise<void> {
    await apiClient.delete(`/community/follow/${userId}`)
  },

  async getFollowing(): Promise<{ items: any[]; total: number }> {
    const { data } = await apiClient.get('/community/follow/following')
    return data
  },

  async getFollowers(): Promise<{ items: any[]; total: number }> {
    const { data } = await apiClient.get('/community/follow/followers')
    return data
  },

  async blockUser(userId: number): Promise<void> {
    await apiClient.post(`/community/block/${userId}`)
  },

  async unblockUser(userId: number): Promise<void> {
    await apiClient.delete(`/community/block/${userId}`)
  },

  async getBlockList(): Promise<{ items: any[]; total: number }> {
    const { data } = await apiClient.get('/community/block/list')
    return data
  },

  async reportUser(targetUserId: number, reason: string, postId?: number): Promise<void> {
    await apiClient.post('/community/report', { target_user_id: targetUserId, reason, post_id: postId })
  },
}
