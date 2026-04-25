<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { useGeolocation } from '@/composables/useGeolocation'
import type { Post, Category, PostTag } from '@/types'
import LoginModal from '@/components/common/LoginModal.vue'
import CreatePostSheet from '@/components/community/CreatePostSheet.vue'
import FeedWaterfall from '@/components/community/FeedWaterfall.vue'

const authStore = useAuthStore()
const showLoginModal = ref(false)
const showCreateSheet = ref(false)
const loading = ref(false)
const posts = ref<Post[]>([])
const totalPosts = ref(0)
const pageSize = 20
const loadingMore = ref(false)
const hasMore = computed(() => posts.value.length < totalPosts.value)
const loadMoreSentinel = ref<HTMLElement | null>(null)
const categories = ref<Category[]>([])
const publicPostsLoaded = ref(0)
const searchQuery = ref('')
const isSearching = ref(false)
const activeFeedType = ref<'follow' | 'recommend' | 'local'>('recommend')
const activeTag = ref<string | null>(null)
const tagSuggestions = ref<PostTag[]>([])
const showSuggestions = ref(false)
const tagSearchMode = ref(false)
const showCityPicker = ref(false)
const manualCity = ref('')
const showSearch = ref(false)
const searchInputRef = ref<HTMLInputElement | null>(null)
let suggestTimer: ReturnType<typeof setTimeout> | null = null

const geo = useGeolocation()

let scrollObserver: IntersectionObserver | null = null

function setupScrollObserver() {
  if (scrollObserver) scrollObserver.disconnect()
  scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !loadingMore.value) {
        loadMore()
      }
    },
    { rootMargin: '300px' }
  )
  const el = loadMoreSentinel.value
  if (el) scrollObserver.observe(el)
}

onUnmounted(() => {
  if (scrollObserver) scrollObserver.disconnect()
})

function mergePosts(...lists: Post[][]): Post[] {
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



async function loadPosts(offset = 0, append = false) {
  const params: { limit: number; offset: number; feed_type?: string; tag?: string; city?: string } = {
    limit: pageSize,
    offset,
  }

  // 映射前端标签到后端 feed_type
  if (activeFeedType.value === 'follow') {
    params.feed_type = 'following'
  } else if (activeFeedType.value === 'local') {
    params.feed_type = 'local'
    // 同城需要城市参数
    const userCity = geo.city.value || await geo.requestCity()
    if (userCity) {
      params.city = userCity
    } else {
      // 无法获取位置，显示空状态
    }
  } else {
    params.feed_type = 'recommend'
  }
  if (activeTag.value) {
    params.tag = activeTag.value
  }
  if (searchQuery.value.trim()) {
    params.tag = searchQuery.value.trim()
  }

  const shouldLoadMyDiaries =
    offset === 0 && authStore.isLoggedIn && activeFeedType.value === 'recommend' && !activeTag.value && !searchQuery.value.trim()

  const [postRes, diaryRes] = await Promise.all([
    communityApi.getPosts(params),
    shouldLoadMyDiaries ? communityApi.getMyDiaries(pageSize, 0) : Promise.resolve({ total: 0, items: [] as Post[] }),
  ])

  publicPostsLoaded.value = offset + postRes.items.length

  const mergedPosts = append
    ? mergePosts(posts.value, postRes.items)
    : mergePosts(postRes.items, diaryRes.items)

  posts.value = mergedPosts

  const privateDiaryCount = offset === 0
    ? diaryRes.items.filter(post => post.is_private).length
    : posts.value.filter(post => post.is_private).length

  totalPosts.value = Math.max(postRes.total + privateDiaryCount, posts.value.length)
}

let isInitialMount = true

onMounted(async () => {
  loading.value = true
  try {
    const catRes = await communityApi.getCategories()
    categories.value = catRes
    await loadPosts()
  } catch {
    posts.value = getFallbackPosts()
    totalPosts.value = posts.value.length
  } finally {
    loading.value = false
    isInitialMount = false
  }
})

watch(loadMoreSentinel, () => {
  setupScrollObserver()
})

watch(activeFeedType, async (newType, oldType) => {
  if (isInitialMount) return
  loading.value = true
  try {
    await loadPosts()
  } catch {
    // keep current posts
  } finally {
    loading.value = false
  }
})

watch(activeTag, async () => {
  if (isInitialMount) return
  loading.value = true
  try {
    await loadPosts()
  } catch {
    // keep current posts
  } finally {
    loading.value = false
  }
})

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    await loadPosts(publicPostsLoaded.value, true)
  } catch (err) {
    console.error('Failed to load more posts:', err)
  } finally {
    loadingMore.value = false
  }
}

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    isSearching.value = false
    tagSearchMode.value = false
    loading.value = true
    try { await loadPosts() } catch {} finally { loading.value = false }
    return
  }
  isSearching.value = true
  tagSearchMode.value = true
  // 标签搜索：传给后端作为 tag 参数搜索
  loading.value = true
  try {
    const params: { limit: number; offset: number; tag?: string } = {
      limit: pageSize,
      offset: 0,
      tag: searchQuery.value.trim(),
    }
    const res = await communityApi.getPosts(params)
    posts.value = res.items
    totalPosts.value = res.total
  } catch {
    // keep current
  } finally {
    loading.value = false
  }
}

function clearSearch() {
  searchQuery.value = ''
  isSearching.value = false
  loading.value = true
  loadPosts().finally(() => { loading.value = false })
}

function handleTagClick(tagName: string) {
  activeTag.value = tagName
  searchQuery.value = ''
  isSearching.value = false
}

function setManualCity() {
  const city = manualCity.value.trim()
  if (!city) return
  showCityPicker.value = false
  geo.city.value = city
  loadPosts()
}

async function handleLikeClick(postId: number) {
  if (!authStore.isLoggedIn) {
    showLoginModal.value = true
    return
  }
  try {
    const res = await communityApi.toggleLike(postId)
    const post = posts.value.find(p => p.id === postId)
    if (post) {
      post.is_liked = res.liked
      post.like_count = res.like_count
    }
  } catch (err) {
    console.error('Failed to toggle like:', err)
  }
}

async function handleBookmarkClick(postId: number) {
  if (!authStore.isLoggedIn) {
    showLoginModal.value = true
    return
  }
  try {
    const res = await communityApi.toggleBookmark(postId)
    const post = posts.value.find(p => p.id === postId)
    if (post) {
      post.is_bookmarked = res.bookmarked
    }
  } catch (err) {
    console.error('Failed to toggle bookmark:', err)
  }
}

async function fetchTagSuggestions(query: string) {
  if (!query.trim()) {
    tagSuggestions.value = []
    showSuggestions.value = false
    return
  }
  try {
    const tags = await communityApi.getTags({ q: query.trim(), limit: 6 })
    tagSuggestions.value = tags
    showSuggestions.value = tags.length > 0
  } catch {
    tagSuggestions.value = []
    showSuggestions.value = false
  }
}

function onSearchInput() {
  if (suggestTimer) clearTimeout(suggestTimer)
  suggestTimer = setTimeout(() => fetchTagSuggestions(searchQuery.value), 200)
}

function selectTagSuggestion(tag: PostTag) {
  searchQuery.value = tag.name
  showSuggestions.value = false
  tagSuggestions.value = []
  handleSearch()
}

function onSearchBlur() {
  setTimeout(() => { showSuggestions.value = false }, 200)
}

function toggleSearch() {
  showSearch.value = !showSearch.value
  if (showSearch.value) {
    nextTick(() => {
      searchInputRef.value?.focus()
    })
  }
}



function getFallbackPosts(): Post[] {
  return [
    { id: 1, title: '308准分子激光3个月心得分享', content: '从去年11月开始做308，每周2次，3个月下来面部的白斑明显缩小了...', content_json: null, post_type: 'long' as const, content_preview: null, video_url: null, video_thumbnail: null, category_id: 1, author: { id: 1, username: '小王', avatar: null, is_doctor: false }, category: { id: 1, name: '治疗分享', description: null, icon: '💊', post_count: 0 }, images: [], audios: [], attachments: [], tags: [], is_private: false, diary_date: null, mood: null, is_anonymous: false, like_count: 89, comment_count: 23, is_liked: false, is_bookmarked: false, created_at: new Date(Date.now() - 2 * 86400000).toISOString(), updated_at: new Date(Date.now() - 2 * 86400000).toISOString() },
    { id: 2, title: '他克莫司软膏使用体验记录', content: '用了2个月他克莫司，手部有一点色素恢复，但不是很明显...', content_json: null, post_type: 'long' as const, content_preview: null, video_url: null, video_thumbnail: null, category_id: 2, author: { id: 2, username: '李姐', avatar: null, is_doctor: false }, category: { id: 2, name: '心理支持', description: null, icon: '💝', post_count: 0 }, images: [], audios: [], attachments: [], tags: [], is_private: false, diary_date: null, mood: null, is_anonymous: false, like_count: 56, comment_count: 12, is_liked: false, is_bookmarked: false, created_at: new Date(Date.now() - 5 * 86400000).toISOString(), updated_at: new Date(Date.now() - 5 * 86400000).toISOString() },
    { id: 3, title: '3年白癜风心路历程', content: '刚确诊的时候真的很害怕，但现在回想起来其实没什么...', content_json: null, post_type: 'text' as const, content_preview: null, video_url: null, video_thumbnail: null, category_id: 2, author: { id: 3, username: '张哥', avatar: null, is_doctor: false }, category: { id: 2, name: '心理支持', description: null, icon: '💝', post_count: 0 }, images: [], audios: [], attachments: [], tags: [], is_private: false, diary_date: null, mood: null, is_anonymous: false, like_count: 128, comment_count: 34, is_liked: false, is_bookmarked: false, created_at: new Date(Date.now() - 7 * 86400000).toISOString(), updated_at: new Date(Date.now() - 7 * 86400000).toISOString() },
    { id: 4, title: '协和医院皮肤科就诊体验', content: '昨天去了协和挂了专家号，医生很有耐心，给我做了详细检查...', content_json: null, post_type: 'long' as const, content_preview: null, video_url: null, video_thumbnail: null, category_id: 5, author: { id: 4, username: '陈姐', avatar: null, is_doctor: false }, category: { id: 5, name: '诊断咨询', description: null, icon: '🔬', post_count: 0 }, images: [], audios: [], attachments: [], tags: [], is_private: false, diary_date: null, mood: null, is_anonymous: false, like_count: 67, comment_count: 28, is_liked: false, is_bookmarked: false, created_at: new Date(Date.now() - 3 * 86400000).toISOString(), updated_at: new Date(Date.now() - 3 * 86400000).toISOString() },
    { id: 5, title: '白癜风饮食忌口清单整理', content: '整理了常见的忌口食物和推荐食物，希望能帮到大家...', content_json: null, post_type: 'long' as const, content_preview: null, video_url: null, video_thumbnail: null, category_id: 4, author: { id: 5, username: '刘哥', avatar: null, is_doctor: false }, category: { id: 4, name: '日常饮食', description: null, icon: '🥗', post_count: 0 }, images: [], audios: [], attachments: [], tags: [], is_private: false, diary_date: null, mood: null, is_anonymous: false, like_count: 203, comment_count: 89, is_liked: false, is_bookmarked: false, created_at: new Date(Date.now() - 1 * 86400000).toISOString(), updated_at: new Date(Date.now() - 1 * 86400000).toISOString() },
    { id: 6, title: '遮盖小妙招分享！亲测有效', content: '分享一下我用的遮盖液和化妆技巧，夏天穿短袖也不怕了...', content_json: null, post_type: 'image' as const, content_preview: null, video_url: null, video_thumbnail: null, category_id: 3, author: { id: 6, username: '赵姐', avatar: null, is_doctor: false }, category: { id: 3, name: '护肤经验', description: null, icon: '🧴', post_count: 0 }, images: [], audios: [], attachments: [], tags: [], is_private: false, diary_date: null, mood: null, is_anonymous: false, like_count: 156, comment_count: 45, is_liked: false, is_bookmarked: false, created_at: new Date(Date.now() - 4 * 86400000).toISOString(), updated_at: new Date(Date.now() - 4 * 86400000).toISOString() },
  ]
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-3 py-3 space-y-3">
    <!-- Feed type tabs + search icon row -->
    <div class="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1">
      <button
        v-for="ft in [{ key: 'follow', label: '关注' }, { key: 'recommend', label: '推荐' }, { key: 'local', label: '同城' }]"
        :key="ft.key"
        class="flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap"
        :class="activeFeedType === ft.key && !activeTag
          ? 'bg-primary-500 text-white shadow-sm'
          : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'"
        @click="activeTag = null; activeFeedType = ft.key as any"
      >
        {{ ft.label }}
      </button>
      <!-- Loading indicator for geolocation -->
      <span v-if="activeFeedType === 'local' && geo.loading.value" class="text-xs text-gray-400 dark:text-gray-500 self-center ml-2">正在获取位置...</span>
      <!-- Active tag filter chip -->
      <button
        v-if="activeTag"
        class="flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-700"
        @click="activeTag = null"
      >
        #{{ activeTag }} ✕
      </button>
      <!-- Spacer to push search icon to right -->
      <div class="flex-1 min-w-0"></div>
      <!-- Search magnifier icon -->
      <button
        class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-gray-400 dark:text-gray-500 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        @click="toggleSearch"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </button>
    </div>

    <!-- Search overlay (animated expand/collapse) -->
    <div v-if="showSearch" class="relative transition-all duration-200">
      <div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-full px-4 py-2 gap-2">
        <svg class="w-4 h-4 text-gray-400 dark:text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          placeholder="搜索病友分享或标签..."
          class="flex-1 bg-transparent text-sm text-gray-700 dark:text-gray-300 placeholder-gray-400 dark:placeholder-gray-500 outline-none"
          @keydown.enter="handleSearch"
          @input="onSearchInput"
          @blur="onSearchBlur"
        />
        <button
          v-if="searchQuery"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          @click="clearSearch"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <!-- Tag autocomplete dropdown -->
      <div
        v-if="showSuggestions"
        class="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden z-50"
      >
        <button
          v-for="tag in tagSuggestions"
          :key="tag.id"
          class="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-left"
          @mousedown.prevent="selectTagSuggestion(tag)"
        >
          <svg class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
          </svg>
          <span>#{{ tag.name }}</span>
          <span class="ml-auto text-[11px] text-gray-400 dark:text-gray-500">{{ tag.usage_count }} 篇</span>
        </button>
      </div>
    </div>

    <!-- Waterfall Feed -->
    <main class="min-w-0">
      <!-- Loading skeleton -->
      <div v-if="loading" class="columns-2 sm:columns-3 lg:columns-4 gap-2.5">
        <div v-for="i in 6" :key="i" class="break-inside-avoid mb-2.5 rounded-xl overflow-hidden bg-white dark:bg-gray-800 animate-pulse">
          <div class="aspect-[3/4] bg-gray-200 dark:bg-gray-700"></div>
          <div class="px-2.5 pt-2 pb-2 space-y-2">
            <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-4/5"></div>
            <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-3/5"></div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="posts.length === 0" class="text-center py-16 space-y-3">
        <template v-if="activeFeedType === 'local' && geo.error.value && !geo.loading.value">
          <div class="text-4xl">📍</div>
          <p class="text-gray-400 dark:text-gray-500 text-sm">{{ geo.error.value }}</p>
          <button class="btn-primary text-sm" @click="showCityPicker = true">手动选择城市</button>
        </template>
        <template v-else-if="activeFeedType === 'local' && geo.city.value">
          <div class="text-4xl">🏙️</div>
          <p class="text-gray-400 dark:text-gray-500 text-sm">暂无 {{ geo.city.value }} 的同城分享</p>
        </template>
        <template v-else>
          <div class="text-4xl">📝</div>
          <p class="text-gray-400 dark:text-gray-500 text-sm">暂无分享，成为第一个分享的人吧</p>
          <button v-if="authStore.isLoggedIn" class="btn-primary text-sm" @click="showCreateSheet = true">✏️ 发布分享</button>
        </template>
      </div>

      <!-- Waterfall feed with type-aware cards -->
      <FeedWaterfall v-else :posts="posts" @tag-click="handleTagClick" @like-click="handleLikeClick" @bookmark-click="handleBookmarkClick" />

      <!-- Load more sentinel -->
      <div v-if="hasMore" ref="loadMoreSentinel" class="text-center py-4">
        <span v-if="loadingMore" class="text-sm text-gray-400 dark:text-gray-500">加载中...</span>
      </div>
      <div v-else-if="!loading && posts.length > 0" class="text-center py-4 text-sm text-gray-400 dark:text-gray-500">
        — 已经到底了 —
      </div>
    </main>

    <!-- Login prompt for non-logged-in users -->
    <div v-if="!authStore.isLoggedIn" class="card dark:bg-gray-800 p-5 text-center mt-4">
      <p class="text-gray-500 dark:text-gray-400 text-sm mb-3">登录后可以发布分享和评论</p>
      <button class="btn-primary text-sm" @click="showLoginModal = true">立即登录</button>
    </div>

    <!-- Medical disclaimer -->
    <div class="text-center text-[10px] text-gray-400 dark:text-gray-500 py-2">
      ⚠️ 本平台不构成医疗建议，分享内容仅供参考
    </div>
  </div>

  <!-- FAB: Create Post -->
  <button
    v-if="authStore.isLoggedIn"
    class="fixed right-5 w-12 h-12 bg-primary-500 hover:bg-primary-600 text-white rounded-full shadow-lg flex items-center justify-center z-30 transition-all duration-200 hover:scale-110 active:scale-95"
    :style="{ bottom: 'calc(5rem + env(safe-area-inset-bottom, 0px))' }"
    @click="showCreateSheet = true"
    data-track-id="community_fab_create"
  >
    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
    </svg>
  </button>

  <!-- For non-logged-in users, show login prompt on FAB tap -->
  <button
    v-else
    class="fixed right-5 w-12 h-12 bg-primary-500 hover:bg-primary-600 text-white rounded-full shadow-lg flex items-center justify-center z-30 transition-all duration-200 hover:scale-110 active:scale-95"
    :style="{ bottom: 'calc(5rem + env(safe-area-inset-bottom, 0px))' }"
    @click="showLoginModal = true"
    data-track-id="community_fab_login"
  >
    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
    </svg>
  </button>

  <CreatePostSheet v-model="showCreateSheet" />

  <LoginModal v-if="showLoginModal" @close="showLoginModal = false" />

  <!-- Manual city picker modal -->
  <Teleport to="body">
    <div v-if="showCityPicker" class="fixed inset-0 bg-black/50 z-[110] flex items-center justify-center" @click.self="showCityPicker = false">
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-sm w-full mx-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">选择城市</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">输入你所在的城市名称，查看同城分享</p>
        <input
          v-model="manualCity"
          type="text"
          placeholder="例如：北京、上海、广州..."
          class="w-full bg-gray-100 dark:bg-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 placeholder-gray-400 dark:placeholder-gray-500 outline-none mb-4"
          @keydown.enter="setManualCity"
        />
        <div class="flex gap-3 justify-end">
          <button class="btn-ghost px-4 py-2" @click="showCityPicker = false">取消</button>
          <button class="btn-primary px-4 py-2" :disabled="!manualCity.trim()" @click="setManualCity">确认</button>
        </div>
      </div>
    </div>
  </Teleport></template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
