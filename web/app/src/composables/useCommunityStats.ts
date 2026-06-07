import { reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { communityApi } from '@/api/community'

export interface CommunityStats {
  postCount: number
  bookmarkCount: number
  commentCount: number
}

export function useCommunityStats() {
  const authStore = useAuthStore()
  const stats = reactive<CommunityStats>({ postCount: 0, bookmarkCount: 0, commentCount: 0 })

  function reset() {
    stats.postCount = 0
    stats.bookmarkCount = 0
    stats.commentCount = 0
  }

  async function fetch() {
    if (!authStore.isLoggedIn) {
      reset()
      return
    }
    try {
      const data = await communityApi.getUserStats()
      stats.postCount = data.post_count
      stats.bookmarkCount = data.bookmark_count
      stats.commentCount = data.comment_count
    } catch {
      reset()
    }
  }

  return { stats, fetch, reset }
}
