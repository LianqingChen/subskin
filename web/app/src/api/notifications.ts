import apiClient from './client'

export interface NotificationItem {
  id: number
  type: string
  title: string
  body: string | null
  ref_type: string | null
  ref_id: number | null
  is_read: boolean
  actor: { id: number; username: string; avatar_url: string } | null
  created_at: string
}

export interface NotificationList {
  items: NotificationItem[]
  total: number
  unread_count: number
}

export const notificationApi = {
  async list(unreadOnly = false, limit = 20, offset = 0): Promise<NotificationList> {
    const { data } = await apiClient.get('/notifications', {
      params: { unread_only: unreadOnly, limit, offset },
    })
    return data
  },

  async getUnreadCount(): Promise<{ unread_count: number }> {
    const { data } = await apiClient.get('/notifications/unread-count')
    return data
  },

  async markRead(notificationId: number): Promise<void> {
    await apiClient.post(`/notifications/${notificationId}/read`)
  },

  async markAllRead(): Promise<void> {
    await apiClient.post('/notifications/read-all')
  },
}
