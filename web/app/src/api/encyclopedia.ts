/**
 * 白白百科 API 客户端
 */

import apiClient from './client'

export interface ArticleSummary {
  id: number
  slug: string
  title: string
  category: string
  icon?: string
  summary?: string
  view_count: number
  updated_at?: string
}

export interface CategoryTreeItem {
  category: string
  icon: string
  articles: ArticleSummary[]
}

export interface ArticleDetail {
  id: number
  slug: string
  title: string
  category: string
  icon?: string
  content: string
  summary?: string
  view_count: number
  updated_at?: string
  revision_count: number
}

export interface RevisionResponse {
  id: number
  article_id: number
  user_id: number
  title: string
  content: string
  change_summary?: string
  change_type: string
  status: string
  diff_preview?: string
  created_at: string
  upvotes: number
  downvotes: number
}

export interface CommentResponse {
  id: number
  article_id: number
  user_id: number
  parent_id?: number
  content: string
  username?: string
  is_approved: boolean
  created_at: string
  replies: CommentResponse[]
}

// ── Articles ──

export async function getEncyclopediaArticles(): Promise<CategoryTreeItem[]> {
  const { data } = await apiClient.get('/encyclopedia/articles')
  return data
}

export async function getEncyclopediaArticle(slug: string): Promise<ArticleDetail> {
  const { data } = await apiClient.get(`/encyclopedia/articles/${slug}`)
  return data
}

// ── Revisions ──

export async function submitRevision(
  slug: string,
  body: { title: string; content: string; change_summary: string }
): Promise<RevisionResponse> {
  const { data } = await apiClient.post(`/encyclopedia/articles/${slug}/revision`, body)
  return data
}

export async function getRevisions(
  slug: string,
  params?: { status?: string }
): Promise<RevisionResponse[]> {
  const { data } = await apiClient.get(`/encyclopedia/articles/${slug}/revisions`, { params })
  return data
}

export async function reviewRevision(
  revisionId: number,
  body: { action: 'approve' | 'reject'; comment?: string }
): Promise<{ status: string }> {
  const { data } = await apiClient.post(`/encyclopedia/revisions/${revisionId}/review`, body)
  return data
}

export async function rollbackRevision(
  revisionId: number
): Promise<{ status: string }> {
  const { data } = await apiClient.post(`/encyclopedia/revisions/${revisionId}/rollback`)
  return data
}

// ── Votes ──

export async function voteRevision(
  revisionId: number,
  body: { vote_type: 'up' | 'down'; comment?: string }
): Promise<{ upvotes: number; downvotes: number }> {
  const { data } = await apiClient.post(`/encyclopedia/revisions/${revisionId}/vote`, body)
  return data
}

// ── Comments ──

export async function getComments(slug: string): Promise<CommentResponse[]> {
  const { data } = await apiClient.get(`/encyclopedia/articles/${slug}/comments`)
  return data
}

export async function createComment(
  slug: string,
  body: { content: string; parent_id?: number }
): Promise<{ status: string; comment_id: number }> {
  const { data } = await apiClient.post(`/encyclopedia/articles/${slug}/comments`, body)
  return data
}
