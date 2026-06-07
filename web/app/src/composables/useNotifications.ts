import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { moderationApi } from '@/api/moderation'
import type { NotificationItem } from '@/api/moderation'

const unreadCount = ref(0)
const notifications = ref<NotificationItem[]>([])
const notificationTotal = ref(0)
const loading = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchUnreadCount() {
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) {
    unreadCount.value = 0
    return
  }
  try {
    const res = await moderationApi.getUnreadCount()
    unreadCount.value = res.unread_count
  } catch {
  }
}

async function fetchNotifications(limit = 20, offset = 0) {
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) return
  loading.value = true
  try {
    const res = await moderationApi.getNotifications({ limit, offset })
    notifications.value = res.items
    notificationTotal.value = res.total
  } catch {
  } finally {
    loading.value = false
  }
}

async function markRead(notificationId: number) {
  try {
    await moderationApi.markNotificationRead(notificationId)
    const n = notifications.value.find(n => n.id === notificationId)
    if (n && !n.is_read) {
      n.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  } catch {
  }
}

function startPolling(intervalMs = 60000) {
  stopPolling()
  fetchUnreadCount()
  pollTimer = setInterval(fetchUnreadCount, intervalMs)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

export function useNotifications() {
  const authStore = useAuthStore()

  onMounted(() => {
    if (authStore.isLoggedIn) {
      startPolling()
    }
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    unreadCount,
    notifications,
    notificationTotal,
    loading,
    fetchNotifications,
    markRead,
    fetchUnreadCount,
    startPolling,
  }
}
