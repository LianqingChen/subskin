import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { useGeolocation } from '@/composables/useGeolocation'
import type { Post } from '@/types'

export function useDiscoveryFeed() {
  const auth = useAuthStore()
  const geo = useGeolocation()
  const posts = ref<Post[]>([])
  const loading = ref(false)
  const loadError = ref(false)
  const loadingMore = ref(false)
  const activeFeedType = ref<'follow' | 'recommend' | 'local'>('recommend')
  const activeSort = ref('hot')
  const activeTag = ref<string | null>(null)
  const searchQuery = ref('')
  const loadMoreSentinel = ref<HTMLElement | null>(null)
  const nextCursor = ref<string | null>(null)
  const totalPosts = ref(0)
  const publicPostsLoaded = ref(0)
  const hasMore = computed(() => posts.value.length < 150 && (!!nextCursor.value || posts.value.length < totalPosts.value))
  let initial = true
  let generation = 0
  let observer: IntersectionObserver | null = null
  function observe() {
    observer?.disconnect()
    if (!loadMoreSentinel.value) return
    observer = new IntersectionObserver(entries => {
      if (entries[0]?.isIntersecting && !loading.value) void loadMore()
    }, { rootMargin: '300px' })
    observer.observe(loadMoreSentinel.value)
  }
  async function loadPosts(append = false) {
    const current = append ? generation : ++generation
    const offset = append ? publicPostsLoaded.value : 0
    const tag = searchQuery.value.trim() || activeTag.value || undefined
    const feedType = activeFeedType.value === 'follow' ? 'following' : activeFeedType.value === 'local' ? 'local' : 'recommend'
    const city = feedType === 'local' ? geo.city.value || await geo.requestCity() : undefined
    if (current !== generation) return
    const params = { limit: 20, offset, feed_type: feedType, sort: activeSort.value, tag, city: city || undefined, after: append ? nextCursor.value : undefined }
    const ownDiaries = !append && auth.isLoggedIn && feedType === 'recommend' && !tag
    const [publicResult, diaries] = await Promise.all([
      communityApi.getPosts(params),
      ownDiaries ? communityApi.getMyDiaries(20, 0) : Promise.resolve({ items: [] as Post[] }),
    ])
    if (current !== generation) return
    // Keep server order; later copies refresh counters without shifting the first position.
    const merged = new Map<number, Post>()
    for (const post of [...(append ? posts.value : []), ...publicResult.items, ...diaries.items]) merged.set(post.id, post)
    posts.value = Array.from(merged.values()).slice(0, 150)
    nextCursor.value = publicResult.next_cursor ?? null
    publicPostsLoaded.value = offset + publicResult.items.length
    const privateCount = posts.value.filter(post => post.is_private).length
    totalPosts.value = Math.max(publicResult.total + privateCount, posts.value.length)
    loadError.value = false
  }
  async function retryLoad() {
    const current = generation + 1
    loading.value = true
    loadError.value = false
    try { await loadPosts() }
    catch (error) {
      if (current === generation) { console.error('Failed to load discovery:', error); loadError.value = true }
    }
    finally { if (current === generation) loading.value = false }
  }
  async function loadMore() {
    if (loading.value || loadingMore.value || !hasMore.value) return
    loadingMore.value = true
    try { await loadPosts(true) }
    catch (error) { console.error('Failed to load more discovery:', error) }
    finally { loadingMore.value = false }
  }
  async function handleLikeClick(postId: number) {
    if (!auth.isLoggedIn) { auth.showLoginModal = true; return }
    try {
      const result = await communityApi.toggleLike(postId)
      const post = posts.value.find(p => p.id === postId)
      if (post) { post.is_liked = result.liked; post.like_count = result.like_count }
    } catch (error) { console.error('Failed to toggle like:', error) }
  }
  function handleFollowChange(followed: boolean, userId: number) {
    for (const post of posts.value) if (post.author.id === userId) post.author.is_followed = followed
  }
  watch([activeFeedType, activeSort, activeTag], () => { if (!initial) void retryLoad() })
  watch(geo.city, (city, previous) => {
    if (!initial && activeFeedType.value === 'local' && city && city !== previous) void retryLoad()
  })
  watch(() => auth.user?.id, () => {
    generation++
    posts.value = []
    if (!initial) void retryLoad()
  })
  watch(loadMoreSentinel, observe)
  onMounted(async () => { geo.preloadCity(); await retryLoad(); initial = false })
  onActivated(() => {
    observe()
    if (!initial && !searchQuery.value.trim()) void loadPosts().catch(error => console.error('Discovery refresh failed; keeping current content:', error))
  })
  onDeactivated(() => { observer?.disconnect() })
  onUnmounted(() => { generation++; observer?.disconnect() })
  return { geo, posts, loading, loadError, loadingMore, activeFeedType, activeSort, activeTag, searchQuery, loadMoreSentinel, hasMore, retryLoad, loadMore, handleLikeClick, handleFollowChange }
}
