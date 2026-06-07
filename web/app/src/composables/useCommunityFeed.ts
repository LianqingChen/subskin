import { ref, computed } from 'vue'
import { communityApi } from '@/api/community'
import type { Post } from '@/types'

export function mergePosts(...lists: Post[][]): Post[] {
  const merged = new Map<number, Post>()
  for (const list of lists) {
    for (const post of list) {
      merged.set(post.id, post)
    }
  }
  return Array.from(merged.values()).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )
}

interface LoadParams {
  feedType: 'follow' | 'recommend' | 'local'
  tag?: string | null
  searchQuery?: string
  city?: string
  lat?: number | null
  lng?: number | null
  offset?: number
  append?: boolean
  includeDiaries?: boolean
}

export function useCommunityFeed() {
  const posts = ref<Post[]>([])
  const total = ref(0)
  const loading = ref(false)
  const loadingMore = ref(false)
  const publicLoaded = ref(0)
  const pageSize = 20
  const hasMore = computed(() => posts.value.length < total.value)

  async function loadPosts(p: LoadParams) {
    const apiParams: any = {
      limit: pageSize,
      offset: p.offset ?? 0,
    }

    if (p.feedType === 'follow') {
      apiParams.feed_type = 'following'
    } else if (p.feedType === 'local') {
      apiParams.feed_type = 'local'
      if (p.city) {
        apiParams.city = p.city
        if (p.lat != null && p.lng != null) {
          apiParams.user_lat = p.lat
          apiParams.user_lng = p.lng
        }
      }
    } else {
      apiParams.feed_type = 'recommend'
    }

    if (p.tag) apiParams.tag = p.tag
    if (p.searchQuery?.trim()) apiParams.tag = p.searchQuery.trim()

    const shouldLoadDiaries = p.includeDiaries && !p.offset

    const [postRes, diaryRes] = await Promise.all([
      communityApi.getPosts(apiParams),
      shouldLoadDiaries
        ? communityApi.getMyDiaries(pageSize, 0)
        : Promise.resolve({ total: 0, items: [] as Post[] }),
    ])

    publicLoaded.value = (p.offset ?? 0) + postRes.items.length

    const mergedPosts = p.append
      ? mergePosts(posts.value, postRes.items)
      : mergePosts(postRes.items, diaryRes.items)

    posts.value = mergedPosts

    const privateDiaryCount = !p.offset
      ? diaryRes.items.filter((post: Post) => post.is_private).length
      : mergedPosts.filter((post: Post) => post.is_private).length

    total.value = Math.max(postRes.total + privateDiaryCount, mergedPosts.length)

    return { postRes, diaryRes }
  }

  return {
    posts, total, loading, loadingMore, publicLoaded, pageSize, hasMore, loadPosts,
  }
}
