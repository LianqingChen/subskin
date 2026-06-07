/**
 * Shared composable for post like / bookmark actions.
 * Eliminates duplicate logic in CommunityPage and PostDetailPage.
 */
import { useAuthStore } from '@/stores/auth'
import { communityApi } from '@/api/community'
import type { Post } from '@/types'

export function usePostActions() {
  const authStore = useAuthStore()

  async function toggleLike(post: Post): Promise<{ liked: boolean; likeCount: number } | null> {
    if (!authStore.isLoggedIn) {
      authStore.showLoginModal = true
      return null
    }
    try {
      const res = await communityApi.toggleLike(post.id)
      return { liked: res.liked, likeCount: res.like_count }
    } catch {
      return null
    }
  }

  async function toggleBookmark(post: Post): Promise<{ bookmarked: boolean } | null> {
    if (!authStore.isLoggedIn) {
      authStore.showLoginModal = true
      return null
    }
    try {
      const res = await communityApi.toggleBookmark(post.id)
      return { bookmarked: res.bookmarked }
    } catch {
      return null
    }
  }

  return { toggleLike, toggleBookmark }
}
