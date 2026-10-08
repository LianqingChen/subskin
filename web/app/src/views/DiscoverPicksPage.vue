<script setup lang="ts">
/** 发现 · 种草：按主体浏览好物笔记（为什么值得看、怎么挑），点进商品详情再决定是否加购。 */
import { computed, ref } from 'vue'
import { CARE_TOPICS, TOPIC_TINT, formatPrice } from '@/data/care-catalog'
import { useCareCart } from '@/composables/useCareCart'
import { trackClick } from '@/composables/useTracking'

const active = ref('all')
const cart = useCareCart()
const tabs = [{ id: 'all', title: '全部' }, ...CARE_TOPICS.map(t => ({ id: t.id, title: t.title }))]
const notes = computed(() => CARE_TOPICS
  .filter(topic => active.value === 'all' || topic.id === active.value)
  .flatMap(topic => topic.items.map(item => ({ item, topic }))))
</script>

<template>
  <div class="page pb-10 pt-3 text-gray-900 dark:text-gray-100 md:pt-5">
    <router-link to="/community" class="-ml-1 inline-flex min-h-10 items-center gap-1 text-sm text-gray-500 no-underline hover:text-gray-800 dark:text-gray-400"><i class="ri-arrow-left-s-line" aria-hidden="true"></i>返回发现</router-link>
    <header class="mt-1">
      <p class="text-xs font-semibold tracking-widest text-primary-700 dark:text-primary-300">发现 · 种草</p>
      <h1 class="page-title mt-1">值得看看的日常好物</h1>
      <p class="page-subtitle leading-6">旧版选购笔记保留供查阅；统一选购入口已在调养，清单仅保存在此设备。</p>
    </header>
    <nav aria-label="种草分类" class="sticky top-14 z-20 -mx-4 mt-3 flex gap-2 overflow-x-auto bg-gray-50 px-4 py-2 no-scrollbar dark:bg-gray-950 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <button v-for="tab in tabs" :key="tab.id" type="button" class="min-h-[40px] shrink-0 whitespace-nowrap rounded-full px-4 text-sm font-medium transition-colors" :aria-pressed="active === tab.id" :class="active === tab.id ? 'bg-primary-600 text-white' : 'border border-gray-200 bg-white text-gray-600 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300'" @click="active = tab.id">{{ tab.title }}</button>
    </nav>
    <ul class="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:gap-4 xl:grid-cols-4">
      <li v-for="{ item, topic } in notes" :key="item.id" class="flex flex-col overflow-hidden rounded-2xl border border-gray-200/80 bg-white transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800">
        <router-link :to="`/care/${item.id}`" class="block no-underline" @click="trackClick('picks_card_open', item.name, { item: item.id, topic: topic.id })">
          <div class="flex aspect-[16/10] items-center justify-center bg-gradient-to-br text-4xl lg:text-5xl" :class="TOPIC_TINT[topic.id]"><i :class="topic.icon" aria-hidden="true"></i></div>
          <div class="px-3 pt-2">
            <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ item.name }}</h2>
            <p class="mt-1 line-clamp-2 text-xs leading-5 text-gray-600 dark:text-gray-300">{{ item.why }}</p>
            <p v-if="item.pick[0]" class="mt-1 flex gap-1 text-xs leading-5 text-gray-500 dark:text-gray-400"><i class="ri-lightbulb-line mt-0.5 shrink-0" aria-hidden="true"></i><span>{{ item.pick[0] }}</span></p>
          </div>
        </router-link>
        <div class="mt-auto flex items-center justify-between px-3 pb-3 pt-2">
          <span class="min-w-0 truncate text-xs text-gray-500 dark:text-gray-400">{{ topic.title }} · {{ formatPrice(item) }}</span>
           <button type="button" class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-600 text-white hover:bg-primary-700" :aria-label="`${item.name}加入清单`" @click="cart.add(item.id)"><i class="ri-shopping-bag-3-line" aria-hidden="true"></i></button>
        </div>
      </li>
    </ul>
  </div>
</template>
