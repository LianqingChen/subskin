<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProductCard from '@/components/care/ProductCard.vue'
import { useCareCatalog } from '@/composables/useCareCatalog'
import { trackClick } from '@/composables/useTracking'

const route = useRoute()
const router = useRouter()
const { active, query, sort, categories, items, activeTitle, reset } = useCareCatalog()
const collapsed = ref(false)
const searchInput = ref<HTMLInputElement>()
function submitSearch() {
  query.value = query.value.trim()
  searchInput.value?.blur()
}
function select(id: string) {
  active.value = id
  void router.replace({ hash: id === 'all' ? '' : `#${id}` })
  if (id !== 'all') trackClick('care_category_open', categories.find(c => c.id === id)?.title, { topic: id })
}
function clearFilters() { reset(); void router.replace({ hash: '' }) }
watch(() => route.hash, hash => {
  const id = hash.replace(/^#/, '')
  active.value = categories.some(c => c.id === id) ? id : 'all'
}, { immediate: true })
let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({ '@context': 'https://schema.org', '@type': 'CollectionPage', name: '调养 · 日常用品选购参考', description: '防晒、食材、营养、餐具与记录工具的选购参考，不构成医疗建议。', url: `${location.origin}/care` })
  document.head.appendChild(schema)
})
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div class="page pb-8 pt-4 text-gray-900 dark:text-gray-100 md:pt-6">
    <header class="space-y-3">
      <h1 class="sr-only">调养</h1>
      <form role="search" aria-label="搜索调养用品" class="flex min-w-0 items-center gap-2" @submit.prevent="submitSearch">
        <div class="relative min-w-0 flex-1">
          <label for="care-search" class="sr-only">搜索用品</label>
          <i class="ri-search-line pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" aria-hidden="true"></i>
          <input id="care-search" ref="searchInput" v-model="query" type="search" enterkeyhint="search" placeholder="搜索用品，如防晒、黑芝麻" class="h-12 w-full min-w-0 rounded-xl border border-gray-200 bg-white pl-10 pr-4 text-sm outline-none transition-colors focus:border-primary-400 focus:ring-2 focus:ring-primary-100 dark:border-gray-700 dark:bg-gray-800 dark:focus:ring-primary-900" />
        </div>
        <button type="submit" class="btn-primary h-12 shrink-0 rounded-xl px-4 text-sm focus-visible:ring-2 focus-visible:ring-primary-500">搜索</button>
      </form>
      <p role="note" class="text-xs leading-5 text-gray-500 dark:text-gray-400">目前提供选购参考，尚未接入购买；清单仅存此设备，站内不收款。</p>
    </header>

    <div class="mt-4 flex flex-col gap-4 lg:flex-row lg:gap-6">
      <aside class="min-w-0 shrink-0 lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:self-start" :class="collapsed ? 'lg:w-12' : 'lg:w-52'">
        <div class="hidden items-center justify-between pb-2 lg:flex">
          <span v-if="!collapsed" class="text-xs font-medium text-gray-500 dark:text-gray-400">用品分类</span>
          <button type="button" class="flex h-11 w-11 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-gray-400 dark:hover:bg-gray-800" :aria-label="collapsed ? '展开分类' : '收起分类'" :aria-expanded="!collapsed" @click="collapsed = !collapsed">
            <i :class="collapsed ? 'ri-arrow-right-s-line' : 'ri-arrow-left-s-line'" class="text-lg" aria-hidden="true"></i>
          </button>
        </div>
        <nav aria-label="商品分类" class="no-scrollbar flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:overflow-y-auto">
          <button v-for="cat in categories" :key="cat.id" type="button" class="flex min-h-11 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-3 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 lg:w-full" :aria-pressed="active === cat.id" :aria-label="`${cat.title}，${cat.count} 项`" :title="cat.title" :class="active === cat.id ? 'bg-primary-50 font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'" @click="select(cat.id)">
            <i :class="cat.icon" class="shrink-0 text-lg" aria-hidden="true"></i>
            <span :class="collapsed ? 'lg:hidden' : ''">{{ cat.title }}</span>
            <span class="ml-auto hidden text-xs tabular-nums opacity-70" :class="collapsed ? '' : 'lg:block'">{{ cat.count }}</span>
          </button>
        </nav>
      </aside>

      <section class="min-w-0 flex-1" aria-labelledby="care-results-title">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-x-2 gap-y-1 border-b border-gray-200 pb-3 dark:border-gray-700">
          <h2 id="care-results-title" class="text-sm font-semibold">{{ activeTitle }} <span class="ml-1 text-xs font-normal text-gray-500 dark:text-gray-400" aria-live="polite">{{ items.length }} 项</span></h2>
          <div class="flex items-center gap-2">
            <button v-if="active !== 'all' || query || sort !== 'default'" type="button" class="min-h-11 text-xs text-primary-700 dark:text-primary-300" @click="clearFilters">清除筛选</button>
            <label for="care-sort" class="sr-only">商品排序</label>
            <select id="care-sort" v-model="sort" class="min-h-11 max-w-full rounded-lg border border-gray-200 bg-white px-2 text-xs text-gray-600 focus:ring-2 focus:ring-primary-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300">
              <option value="default">默认排序</option><option value="name">名称排序</option>
            </select>
          </div>
        </div>
        <div v-if="items.length" class="grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4 2xl:grid-cols-4">
          <ProductCard v-for="{ item, topic } in items" :key="item.id" :item="item" :topic="topic" />
        </div>
        <div v-else class="py-16 text-center">
          <i class="ri-search-line text-3xl text-gray-400" aria-hidden="true"></i>
          <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">没有找到相关用品</p>
          <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">试试其他关键词，或清除分类条件。</p>
          <button type="button" class="btn-ghost mt-3 min-h-11 text-sm" @click="clearFilters">清除筛选</button>
        </div>
        <footer class="mt-6 border-t border-gray-200 pt-4 text-xs leading-6 text-gray-500 dark:border-gray-700 dark:text-gray-400">
          食品和用品不是治疗手段，不能替代药物和光疗。营养补充先检查、遵医嘱。本文不构成医疗建议。
        </footer>
      </section>
    </div>
  </div>
</template>
