<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { useGeolocation } from '@/composables/useGeolocation'
import type { Post, Category, PostTag } from '@/types'
import CreatePostSheet from '@/components/community/CreatePostSheet.vue'
import CityPicker from '@/components/community/CityPicker.vue'
import FeedWaterfall from '@/components/community/FeedWaterfall.vue'
import DiaryCalendar from '@/components/community/DiaryCalendar.vue'
import type { DiaryCalendarEntry } from '@/api/community'

const authStore = useAuthStore()
const router = useRouter()
const showCreateSheet = ref(false)
const loading = ref(false)
const posts = ref<Post[]>([])
const totalPosts = ref(0)
const pageSize = 20
const MAX_RENDERED_POSTS = 150 // Cap DOM nodes for performance
const loadingMore = ref(false)
// Cursor-based pagination: the backend returns next_cursor, which we echo back
// as `after` on the next page. This is stable under inserts/deletes (offset-
// based pagination skips/duplicates items when the feed changes between pages).
const nextCursor = ref<string | null>(null)
const hasMore = computed(() => !!nextCursor.value || posts.value.length < totalPosts.value)
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
const showSearch = ref(false)
const showDiaryCalendar = ref(false)
const searchInputRef = ref<HTMLInputElement | null>(null)
let suggestTimer: ReturnType<typeof setTimeout> | null = null

const geo = useGeolocation()
let previousCityForLocal: string | null = null

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
  const params: { limit: number; offset: number; feed_type?: string; tag?: string; city?: string; after?: string | null } = {
    limit: pageSize,
    offset,
  }
  // Use the cursor for append (load-more) requests; the initial load resets
  // the cursor so a fresh feed starts from the top.
  if (append && nextCursor.value) {
    params.after = nextCursor.value
    // offset is retained for the recommendation-service fallback path but the
    // cursor takes precedence server-side when present.
    params.offset = offset
  } else if (!append) {
    nextCursor.value = null
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
    shouldLoadMyDiaries ? communityApi.getMyDiaries(pageSize, 0) : Promise.resolve({ total: 0, items: [] as Post[], next_cursor: null }),
  ])

  // Track the cursor returned by the backend for the next load-more page.
  nextCursor.value = postRes.next_cursor ?? null
  publicPostsLoaded.value = offset + postRes.items.length

  const mergedPosts = append
    ? mergePosts(posts.value, postRes.items)
    : mergePosts(postRes.items, diaryRes.items)

  posts.value = mergedPosts.slice(0, MAX_RENDERED_POSTS)

  const privateDiaryCount = offset === 0
    ? diaryRes.items.filter(post => post.is_private).length
    : posts.value.filter(post => post.is_private).length

  totalPosts.value = Math.max(postRes.total + privateDiaryCount, posts.value.length)
}

let isInitialMount = true

onMounted(async () => {
  geo.preloadCity()
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

watch(activeFeedType, async () => {
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

watch(geo.city, async (newCity) => {
  if (isInitialMount) return
  if (activeFeedType.value !== 'local') return
  if (newCity === previousCityForLocal) return
  previousCityForLocal = newCity
  if (!newCity) return
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

function handleCityPick(city: { name: string; lat: number; lng: number }, _province: string) {
  showCityPicker.value = false
  geo.city.value = city.name
  geo.lat.value = city.lat
  geo.lng.value = city.lng
  geo.setManualCity(city.name)
}

async function handleLikeClick(postId: number) {
  if (!authStore.isLoggedIn) {
    authStore.showLoginModal = true
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

function handleFollowChange(followed: boolean, userId: number) {
  // Update is_followed on all posts by this author
  posts.value.forEach(p => {
    if (p.author.id === userId) {
      p.author.is_followed = followed
    }
  })
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
  return []
}

function onDiaryEntrySelect(entry: DiaryCalendarEntry) {
  showDiaryCalendar.value = false
  router.push(`/community/${entry.id}`)
}
</script>

<template>
  <div class="max-w-2xl mx-auto px-4 py-3 space-y-3 sm:px-5 sm:py-4 sm:space-y-4">
    <!-- Feed type tabs + search icon in one row -->
    <div class="flex items-center gap-2 sm:gap-2.5 overflow-x-auto no-scrollbar pb-1">
      <button
        v-for="ft in [{ key: 'follow', label: '关注' }, { key: 'recommend', label: '推荐' }]"
        :key="ft.key"
        class="flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap"
        :class="activeFeedType === ft.key && !activeTag
          ? 'bg-primary-500 text-white shadow-sm'
          : 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 hover:border-primary-300 dark:hover:border-primary-700 hover:text-primary-600 dark:hover:text-primary-400'"
        @click="activeTag = null; activeFeedType = ft.key as any"
      >
        {{ ft.label }}
      </button>
      <!-- Dynamic city tab -->
      <button
        class="flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap flex items-center gap-1"
        :class="activeFeedType === 'local' && !activeTag
          ? 'bg-primary-500 text-white shadow-sm'
          : 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 hover:border-primary-300 dark:hover:border-primary-700 hover:text-primary-600 dark:hover:text-primary-400'"
        @click="activeTag = null; if (activeFeedType === 'local' && geo.city.value) { showCityPicker = true } else { activeFeedType = 'local'; if (!geo.city.value) showCityPicker = true }"
      >
        <template v-if="geo.city.value">{{ geo.city.value }}</template>
        <template v-else-if="geo.loading.value">定位中...</template>
        <template v-else>同城</template>
        <i v-if="geo.city.value" class="ri-arrow-down-s-line text-xs"></i>
      </button>
      <!-- Active tag filter chip -->
      <button
        v-if="activeTag"
        class="flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors whitespace-nowrap bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-700"
        @click="activeTag = null"
      >
        #{{ activeTag }} ✕
      </button>
      <!-- Search icon — right next to tabs -->
      <button
        class="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-full text-gray-400 hover:text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-all"
        @click="toggleSearch"
      >
        <i class="ri-search-line text-lg"></i>
      </button>
      <!-- Diary calendar button -->
      <button
        v-if="authStore.isLoggedIn"
        class="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-full text-gray-400 hover:text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-all"
        @click="showDiaryCalendar = true"
        title="治疗日记日历"
      >
        <i class="ri-calendar-2-line text-lg"></i>
      </button>
    </div>

    <!-- Search bar — expands below tabs when toggled -->
    <div v-if="showSearch" class="relative animate-fade-in" style="animation-duration: 150ms;">
      <div class="flex items-center bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-xl px-3.5 py-2.5 gap-2 focus-within:border-primary-300 dark:focus-within:border-primary-700 transition-colors">
        <i class="ri-search-line text-gray-400 text-base flex-shrink-0"></i>
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          placeholder="搜索病友分享或标签..."
          class="flex-1 bg-transparent text-sm text-gray-700 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 outline-none min-w-0"
          @keydown.enter="handleSearch"
          @input="onSearchInput"
          @blur="onSearchBlur"
        />
        <button
          v-if="searchQuery"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex-shrink-0"
          @click="clearSearch"
        >
          <i class="ri-close-line text-lg"></i>
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
          class="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-left"
          @mousedown.prevent="selectTagSuggestion(tag)"
        >
          <i class="ri-price-tag-3-line text-gray-400 text-xs flex-shrink-0"></i>
          <span>#{{ tag.name }}</span>
          <span class="ml-auto text-[11px] text-gray-400">{{ tag.usage_count }} 篇</span>
        </button>
      </div>
    </div>

    <!-- Waterfall Feed -->
    <main class="min-w-0">
      <!-- Loading skeleton -->
      <div v-if="loading" class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div v-for="i in 6" :key="i" class="break-inside-avoid mb-2.5 rounded-xl overflow-hidden bg-white  animate-pulse">
          <div class="aspect-[3/4] bg-gray-200 "></div>
          <div class="px-2.5 pt-2 pb-2 space-y-2">
            <div class="h-3 bg-gray-200  rounded w-4/5"></div>
            <div class="h-3 bg-gray-200  rounded w-3/5"></div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="posts.length === 0" class="text-center py-16 space-y-3">
        <template v-if="activeFeedType === 'local' && !geo.city.value">
          <i class="ri-map-pin-line text-4xl text-gray-300"></i>
          <p class="text-gray-400  text-sm">{{ geo.error.value || '请选择城市查看同城分享' }}</p>
          <button class="btn-primary text-sm" @click="showCityPicker = true">选择城市</button>
        </template>
        <template v-else-if="activeFeedType === 'local' && geo.city.value">
          <i class="ri-building-line text-4xl text-gray-300"></i>
          <p class="text-gray-400  text-sm">暂无 {{ geo.city.value }} 的同城分享</p>
          <button class="btn-ghost text-sm" @click="showCityPicker = true">切换城市</button>
        </template>
        <template v-else>
          <div class="text-4xl">📝</div>
          <p class="text-gray-400  text-sm">暂无分享，成为第一个分享的人吧</p>
          <button v-if="authStore.isLoggedIn" class="btn-primary text-sm" @click="showCreateSheet = true">✏️ 发布分享</button>
        </template>
      </div>

      <!-- Waterfall feed with type-aware cards -->
      <FeedWaterfall v-else :posts="posts" @like-click="handleLikeClick" @follow-change="handleFollowChange" />

      <!-- Load more sentinel -->
      <div v-if="hasMore" ref="loadMoreSentinel" class="text-center py-4">
        <span v-if="loadingMore" class="text-sm text-gray-400 ">加载中...</span>
      </div>
      <div v-else-if="!loading && posts.length > 0" class="text-center py-4 text-sm text-gray-400 ">
        — 已经到底了 —
      </div>
    </main>

    <!-- Login prompt for non-logged-in users -->
    <div v-if="!authStore.isLoggedIn" class="card  p-5 text-center mt-4">
      <p class="text-gray-500  text-sm mb-3">登录后可以发布分享和评论</p>
      <button class="btn-primary text-sm" @click="authStore.showLoginModal = true">立即登录</button>
    </div>

    <!-- Medical disclaimer -->
    <div class="text-center text-[10px] text-gray-400  py-2">
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
    @click="authStore.showLoginModal = true"
    data-track-id="community_fab_login"
  >
    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
    </svg>
  </button>

  <CreatePostSheet v-model="showCreateSheet" />

  <CityPicker v-if="showCityPicker" @select="handleCityPick" @close="showCityPicker = false" />

  <DiaryCalendar :visible="showDiaryCalendar" @close="showDiaryCalendar = false" @select-entry="onDiaryEntrySelect" />
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
