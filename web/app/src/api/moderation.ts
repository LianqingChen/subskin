import apiClient from './client'

export interface ModerationItem {
  id: number
  post_id: number | null
  user_id: number
  content_type: string
  content_snapshot: string | null
  risk_level: string
  risk_categories: string[] | null
  auto_action: string
  ai_reason: string | null
  ai_confidence: number | null
  status: string
  reviewed_by: number | null
  reviewed_at: string | null
  review_note: string | null
  created_at: string
  author_username: string | null
  post_title: string | null
}

export interface ModerationListResponse {
  total: number
  items: ModerationItem[]
}

export interface ReviewRequest {
  action: string
  note?: string
  mute_hours?: number
  ban?: boolean
}

export interface ViolationLogItem {
  id: number
  user_id: number
  action: string
  duration_hours: number | null
  reason: string | null
  operated_by: number | null
  created_at: string
}

export interface UserProfileModeration {
  user_id: number
  username: string
  user_status: string
  violation_count: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  muted_until: string | null
  banned_at: string | null
  ban_reason: string | null
  recent_logs: ViolationLogItem[]
}

export interface NotificationItem {
  id: number
  type: string
  title: string
  content: string | null
  is_read: boolean
  related_id: number | null
  ref_type: string | null
  ref_id: number | null
  created_at: string
}

export interface NotificationListResponse {
  total: number
  items: NotificationItem[]
}

export interface UnreadCountResponse {
  unread_count: number
}

export interface UserActionParams {
  action: string
  hours?: number
  reason?: string
}

export const moderationApi = {
  getPending(params?: { risk_level?: string; limit?: number; offset?: number }) {
    return apiClient.get<ModerationListResponse>('/moderation/pending', { params }).then((r) => r.data)
  },

  review(moderationId: number, body: ReviewRequest) {
    return apiClient.post<{ status: string; action: string }>(`/moderation/${moderationId}/review`, body).then((r) => r.data)
  },

  getUserProfile(userId: number) {
    return apiClient.get<UserProfileModeration>(`/moderation/user/${userId}`).then((r) => r.data)
  },

  userAction(userId: number, params: UserActionParams) {
    return apiClient.post<{ status: string; action: string }>(`/moderation/user/${userId}/action`, null, { params }).then((r) => r.data)
  },

  getNotifications(params?: { limit?: number; offset?: number }) {
    return apiClient.get<NotificationListResponse>('/moderation/notifications', { params }).then((r) => r.data)
  },

  markNotificationRead(notificationId: number) {
    return apiClient.post<{ status: string }>(`/moderation/notifications/${notificationId}/read`).then((r) => r.data)
  },

  getUnreadCount() {
    return apiClient.get<UnreadCountResponse>('/moderation/notifications/unread-count').then((r) => r.data)
  },
}

export default moderationApi
