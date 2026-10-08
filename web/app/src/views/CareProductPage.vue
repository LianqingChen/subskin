<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import ProductCard from '@/components/care/ProductCard.vue'
import CartButton from '@/components/care/CartButton.vue'
import CartSheet from '@/components/care/CartSheet.vue'
import CareProductActions from '@/components/care/CareProductActions.vue'
import { CARE_ITEM_INDEX, EVIDENCE, formatPrice } from '@/data/care-catalog'
import { trackClick } from '@/composables/useTracking'

const route = useRoute()
const found = computed(() => CARE_ITEM_INDEX[String(route.params.id)])
const related = computed(() => found.value ? found.value.topic.items.filter(item => item.id !== found.value.item.id).slice(0, 4) : [])
let schema: HTMLScriptElement | undefined
watch(found, info => {
  schema?.remove()
  if (!info) return
  trackClick('care_item_view', info.item.name, { item: info.item.id, topic: info.topic.id })
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({ '@context': 'https://schema.org', '@type': 'WebPage', name: `${info.item.name} · 选购参考`, description: info.item.why, url: `${location.origin}/care/${info.item.id}` })
  document.head.appendChild(schema)
}, { immediate: true })
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div v-if="found" class="page pb-40 pt-3 text-gray-900 dark:text-gray-100 md:pb-28 lg:pb-10">
    <header class="mb-4 flex items-center justify-between gap-3">
      <router-link :to="`/care#${found.topic.id}`" class="inline-flex min-h-11 items-center gap-1 text-sm text-gray-500 no-underline dark:text-gray-400"><i class="ri-arrow-left-s-line" aria-hidden="true"></i>返回调养</router-link><CartButton />
    </header>
    <div class="grid gap-6 lg:grid-cols-2 lg:items-start lg:gap-10">
      <div class="flex aspect-square max-h-[420px] flex-col items-center justify-center gap-4 rounded-2xl bg-gray-100 dark:bg-gray-800 lg:max-h-none">
        <i :class="found.topic.icon" class="text-8xl text-primary-600 dark:text-primary-300" aria-hidden="true"></i><span class="text-xs text-gray-500 dark:text-gray-400">品类示意 · 非商品实拍</span>
      </div>
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <router-link :to="`/care#${found.topic.id}`" class="inline-flex min-h-11 items-center text-gray-500 no-underline dark:text-gray-400">{{ found.topic.title }}</router-link>
          <span v-if="found.item.buyUrl" class="rounded bg-primary-50 px-2 py-1 text-primary-700 dark:bg-primary-900 dark:text-primary-300">推广</span>
          <span v-if="found.item.status === 'planned'" class="rounded bg-gray-100 px-2 py-1 text-gray-600 dark:bg-gray-700 dark:text-gray-300">筹备中</span>
        </div>
        <h1 class="text-2xl font-semibold">{{ found.item.name }}</h1>
        <p class="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{{ found.item.why }}</p>
        <p class="mt-4 text-xl font-semibold text-primary-700 dark:text-primary-300">{{ found.item.price !== undefined ? formatPrice(found.item) : found.item.status === 'planned' ? '暂未发售' : '选购参考' }}</p>
        <p v-if="found.item.spec" class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ found.item.spec }}</p>
        <p class="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">{{ found.item.buyUrl && found.item.status !== 'planned' ? '购买跳转商家页面，价格、库存与售后由商家提供。' : '尚未接入购买，可加入本机清单或查看选购要点。' }}</p>
        <section class="mt-5 rounded-xl bg-amber-50 p-4 dark:bg-amber-900/20" aria-labelledby="care-risk-title">
          <h2 id="care-risk-title" class="flex items-center gap-2 text-sm font-semibold text-amber-900 dark:text-amber-200"><i class="ri-information-line" aria-hidden="true"></i>使用前请注意</h2>
          <ul class="mt-2 space-y-2 text-xs leading-6 text-amber-900 dark:text-amber-200"><li v-for="line in found.topic.cautions" :key="line">{{ line }}</li></ul>
          <p v-if="found.topic.id === 'nutrition'" class="mt-2 text-xs font-medium text-amber-900 dark:text-amber-200">先检查，遵医嘱。不自行决定补充剂量。</p>
          <p class="mt-2 text-xs text-amber-900 dark:text-amber-200">本文不构成医疗建议。</p>
        </section>
        <CareProductActions class="mt-5 hidden lg:flex" :item="found.item" :topic="found.topic" />
      </div>
    </div>
    <section id="care-selection" class="mt-8 scroll-mt-20 border-t border-gray-200 pt-6 dark:border-gray-700" aria-labelledby="care-selection-title">
      <h2 id="care-selection-title" class="text-base font-semibold">选购要点</h2>
      <ul class="mt-3 space-y-2 text-sm leading-6 text-gray-600 dark:text-gray-300"><li v-for="tip in found.item.pick" :key="tip" class="flex gap-2"><i class="ri-check-line shrink-0 text-primary-600 dark:text-primary-300" aria-hidden="true"></i><span>{{ tip }}</span></li></ul>
      <details class="mt-5 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
        <summary class="min-h-11 cursor-pointer text-sm font-medium">护理做法的依据与使用说明</summary>
        <div class="mt-2 space-y-3 text-sm leading-7 text-gray-600 dark:text-gray-300">
          <span class="inline-flex items-center gap-1 rounded-lg bg-gray-100 px-2 py-1 text-xs dark:bg-gray-700"><i :class="EVIDENCE[found.topic.evidence].icon" aria-hidden="true"></i>{{ EVIDENCE[found.topic.evidence].label }}</span>
          <p class="text-xs">以上依据针对护理做法，不代表某件商品具有治疗效果。</p>
          <p>{{ found.topic.summary }}</p>
          <ul class="space-y-2"><li v-for="tip in found.topic.pickGuide" :key="tip">{{ tip }}</li></ul>
          <router-link :to="`/discover/science#${found.topic.id}`" class="inline-flex min-h-11 items-center text-sm text-primary-700 no-underline dark:text-primary-300">查看完整参考说明<i class="ri-arrow-right-s-line" aria-hidden="true"></i></router-link>
        </div>
      </details>
    </section>
    <section v-if="related.length" class="mt-8" aria-labelledby="care-related-title"><h2 id="care-related-title" class="mb-4 text-base font-semibold">同类用品</h2><div class="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4"><ProductCard v-for="item in related" :key="item.id" :item="item" :topic="found.topic" /></div></section>
    <div class="app-fixed-x fixed bottom-[calc(54px+env(safe-area-inset-bottom,0px))] z-40 border-t border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900 md:bottom-0 md:pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:hidden"><CareProductActions class="mx-auto max-w-6xl" :item="found.item" :topic="found.topic" /></div>
    <CartSheet />
  </div>
  <div v-else class="page py-20 text-center text-sm text-gray-500 dark:text-gray-400"><p>没有找到这件用品。</p><router-link to="/care" class="mt-3 inline-flex min-h-11 items-center text-primary-700 no-underline dark:text-primary-300">返回调养</router-link></div>
</template>
