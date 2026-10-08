<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDiscoveryFeed } from '@/composables/useDiscoveryFeed'
import { useDiscoverySearch } from '@/composables/useDiscoverySearch'
import CreatePostSheet from '@/components/community/CreatePostSheet.vue'
import CityPicker from '@/components/community/CityPicker.vue'
import FeedWaterfall from '@/components/community/FeedWaterfall.vue'
import SortDropdown from '@/components/community/SortDropdown.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const showCreateSheet = ref(false)
const showCityPicker = ref(false)
const { geo, posts, loading, loadError, loadingMore, activeFeedType, activeSort, activeTag, searchQuery, loadMoreSentinel, hasMore, retryLoad, handleLikeClick, handleFollowChange } = useDiscoveryFeed()
const { showSearch, searchInputRef, tagSuggestions, showSuggestions, onSearchInput, handleSearch, clearSearch, selectTagSuggestion, onSearchBlur, toggleSearch } = useDiscoverySearch(searchQuery, retryLoad)
const FEED_TYPES = [{ key: 'follow', label: '关注' }, { key: 'recommend', label: '推荐' }] as const
const SORT_OPTIONS = [
  { key: 'hot', label: '综合' }, { key: 'newest', label: '最新' },
  { key: 'views', label: '最多浏览' }, { key: 'likes', label: '最多点赞' },
  { key: 'bookmarks', label: '最多收藏' }, { key: 'shares', label: '最多转发' },
] as const
function selectCity() {
  activeTag.value = null
  if (activeFeedType.value === 'local' && geo.city.value) showCityPicker.value = true
  else { activeFeedType.value = 'local'; if (!geo.city.value) showCityPicker.value = true }
}
function handleCityPick(city: { name: string; lat: number; lng: number }) {
  showCityPicker.value = false
  geo.city.value = city.name; geo.lat.value = city.lat; geo.lng.value = city.lng
  geo.setManualCity(city.name)
}
function createPost() {
  if (authStore.isLoggedIn) showCreateSheet.value = true
  else authStore.showLoginModal = true
}
onMounted(() => {
  if (route.query.create && authStore.isLoggedIn) {
    showCreateSheet.value = true
    void router.replace({ query: { ...route.query, create: undefined } })
  }
})
</script>

<template>
  <div class="page space-y-3 pb-8 pt-3 md:space-y-4 md:pt-5">
    <h1 class="sr-only">发现</h1>
    <header class="discovery-toolbar flex min-w-0 flex-nowrap items-center gap-1">
      <nav aria-label="发现内容筛选" class="discovery-tabs flex min-w-0 flex-1 items-center gap-1 overflow-x-auto whitespace-nowrap">
        <button v-for="ft in FEED_TYPES" :key="ft.key" type="button" class="min-h-11 shrink-0 rounded-lg px-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-primary-500" :aria-pressed="activeFeedType === ft.key && !activeTag" :class="activeFeedType === ft.key && !activeTag ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'" @click="activeTag = null; activeFeedType = ft.key">{{ ft.label }}</button>
        <button type="button" class="flex min-h-11 min-w-11 max-w-28 flex-1 items-center gap-1 rounded-lg px-2 text-sm font-medium focus-visible:ring-2 focus-visible:ring-primary-500" :title="geo.city.value || '同城'" :aria-pressed="activeFeedType === 'local'" :class="activeFeedType === 'local' ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'text-gray-600 dark:text-gray-400'" @click="selectCity">
          <span class="min-w-0 truncate">{{ geo.city.value || (geo.loading.value ? '定位中…' : '同城') }}</span><i v-if="geo.city.value" class="ri-arrow-down-s-line shrink-0" aria-hidden="true"></i>
        </button>
      </nav>
      <div class="flex shrink-0 items-center gap-1">
        <SortDropdown v-if="!activeTag && !searchQuery.trim()" v-model="activeSort" :options="SORT_OPTIONS" />
        <button type="button" class="flex h-11 w-11 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-gray-400 dark:hover:bg-gray-800" aria-label="搜索病友内容" :aria-expanded="showSearch" @click="toggleSearch"><i class="ri-search-line text-lg" aria-hidden="true"></i></button>
        <router-link to="/hospitals" class="hidden min-h-11 items-center px-2 text-xs text-gray-500 no-underline hover:text-primary-700 dark:text-gray-400 md:inline-flex" data-track-id="community_hospitals_entry">就医经验<i class="ri-arrow-right-s-line" aria-hidden="true"></i></router-link>
        <details class="relative md:hidden">
          <summary class="flex h-11 w-11 cursor-pointer list-none items-center justify-center rounded-lg text-gray-500 focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-gray-400" aria-label="更多发现入口"><i class="ri-more-2-line text-lg" aria-hidden="true"></i></summary>
          <nav aria-label="更多发现入口" class="absolute right-0 top-full z-30 w-36 rounded-xl border border-gray-200 bg-white p-1 shadow-lg dark:border-gray-700 dark:bg-gray-800"><router-link to="/hospitals" class="flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm text-gray-700 no-underline dark:text-gray-200" data-track-id="community_hospitals_entry"><i class="ri-hospital-line" aria-hidden="true"></i>就医经验</router-link></nav>
        </details>
      </div>
    </header>

    <section v-if="showSearch" aria-label="搜索病友内容" class="relative">
      <form class="flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 dark:border-gray-700 dark:bg-gray-800" @submit.prevent="handleSearch">
        <label for="discovery-search" class="sr-only">搜索病友分享或标签</label>
        <i class="ri-search-line text-gray-400" aria-hidden="true"></i>
        <input id="discovery-search" ref="searchInputRef" v-model="searchQuery" type="search" placeholder="搜索病友分享或标签" class="h-12 min-w-0 flex-1 bg-transparent text-sm text-gray-700 outline-none dark:text-gray-200" @input="onSearchInput" @blur="onSearchBlur" />
        <button v-if="searchQuery" type="button" class="flex h-11 w-11 items-center justify-center text-gray-500" aria-label="清除搜索" @click="clearSearch"><i class="ri-close-line" aria-hidden="true"></i></button>
      </form>
      <div v-if="showSuggestions" class="absolute inset-x-0 top-full z-30 mt-1 rounded-xl border border-gray-200 bg-white p-1 shadow-lg dark:border-gray-700 dark:bg-gray-800">
        <button v-for="tag in tagSuggestions" :key="tag.id" type="button" class="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-left text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-700" @mousedown.prevent @click="selectTagSuggestion(tag)"><span>#{{ tag.name }}</span><span class="ml-auto text-xs text-gray-500">{{ tag.usage_count }} 篇</span></button>
      </div>
    </section>

    <section aria-label="病友内容" class="min-w-0">
      <div v-if="loading" class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4" aria-label="正在加载病友内容">
        <div v-for="i in 6" :key="i" class="overflow-hidden rounded-xl bg-white motion-safe:animate-pulse dark:bg-gray-800"><div class="aspect-[3/4] bg-gray-200 dark:bg-gray-700"></div><div class="h-16"></div></div>
      </div>
      <div v-else-if="loadError" class="space-y-3 py-16 text-center"><i class="ri-error-warning-line text-4xl text-gray-400" aria-hidden="true"></i><p class="text-sm text-gray-500 dark:text-gray-400">加载失败，请检查网络后重试</p><button type="button" class="btn-primary min-h-11 text-sm" @click="retryLoad">重新加载</button></div>
      <div v-else-if="!posts.length" class="py-16 text-center">
        <template v-if="activeFeedType === 'local'"><p class="text-sm text-gray-500 dark:text-gray-400">{{ geo.city.value ? `暂无 ${geo.city.value} 的同城分享` : geo.error.value || '请选择城市查看同城分享' }}</p><button type="button" class="btn-ghost mt-3 min-h-11 text-sm" @click="showCityPicker = true">{{ geo.city.value ? '切换城市' : '选择城市' }}</button></template>
        <EmptyState v-else icon="ri-quill-pen-line" :title="searchQuery.trim() ? '没有找到相关分享，换个标签试试' : '暂无分享，成为第一个分享的人吧'" :action-label="authStore.isLoggedIn && !searchQuery.trim() ? '发布分享' : ''" @action="createPost" />
      </div>
      <FeedWaterfall v-else :posts="posts" @like-click="handleLikeClick" @follow-change="handleFollowChange" />
      <div v-if="hasMore && !loadError" ref="loadMoreSentinel" class="py-4 text-center"><span v-if="loadingMore" class="text-sm text-gray-500 dark:text-gray-400">加载中…</span></div>
      <p v-else-if="!loading && posts.length" class="py-4 text-center text-xs text-gray-500 dark:text-gray-400">— 已经到底了 —</p>
    </section>
    <div v-if="!authStore.isLoggedIn" class="mx-auto max-w-md py-4 text-center"><p class="mb-3 text-sm text-gray-500 dark:text-gray-400">登录后可以发布分享和评论</p><button type="button" class="btn-primary min-h-11 text-sm" @click="authStore.showLoginModal = true">立即登录</button></div>
  </div>
  <button type="button" class="community-fab fixed right-5 z-30 flex h-12 w-12 items-center justify-center rounded-full bg-primary-600 text-white shadow-lg hover:bg-primary-700 focus-visible:ring-2 focus-visible:ring-primary-400 lg:right-8 lg:h-14 lg:w-14" aria-label="发布分享" :data-track-id="authStore.isLoggedIn ? 'community_fab_create' : 'community_fab_login'" @click="createPost"><i class="ri-add-line text-2xl" aria-hidden="true"></i></button>
  <CreatePostSheet v-model="showCreateSheet" />
  <CityPicker v-if="showCityPicker" @select="handleCityPick" @close="showCityPicker = false" />
</template>

<style scoped>
.community-fab { bottom: calc(5rem + env(safe-area-inset-bottom, 0px)); }
@media (min-width: 768px) { .community-fab { bottom: 2rem; } }
summary::-webkit-details-marker { display: none; }
.discovery-tabs { scrollbar-width: none; }
.discovery-tabs::-webkit-scrollbar { display: none; }
.discovery-toolbar :deep(.control-slim) { min-height: 44px; }
</style>
