<script setup lang="ts">
import { formatPrice, type CareItem, type CareTopic } from '@/data/care-catalog'
import { trackClick } from '@/composables/useTracking'
defineProps<{ item: CareItem; topic: CareTopic }>()
</script>

<template>
  <article class="flex h-full flex-col overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
    <router-link :to="`/care/${item.id}`" class="group flex h-full flex-col text-gray-900 no-underline focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-gray-100" :data-track-id="`care_card_${item.id}`" @click="trackClick('care_card_open', item.name, { item: item.id, topic: topic.id })">
      <div class="relative flex aspect-square flex-col items-center justify-center gap-3 bg-gray-50 dark:bg-gray-900/50">
        <i :class="topic.icon" class="text-5xl text-primary-600 transition-transform motion-safe:group-hover:scale-105 dark:text-primary-300" aria-hidden="true"></i>
        <span class="text-[11px] text-gray-400 dark:text-gray-500">品类示意 · 非商品实拍</span>
        <span v-if="item.status === 'planned'" class="absolute left-2 top-2 rounded bg-gray-200 px-2 py-1 text-[11px] text-gray-700 dark:bg-gray-700 dark:text-gray-200">筹备中</span>
        <span v-else-if="item.buyUrl" class="absolute left-2 top-2 rounded bg-primary-50 px-2 py-1 text-[11px] text-primary-700 dark:bg-primary-900 dark:text-primary-200">推广</span>
      </div>
      <div class="flex flex-1 flex-col p-3">
        <p class="text-[11px] text-gray-500 dark:text-gray-400">{{ topic.title }}</p>
        <h3 class="mt-1 min-h-10 text-sm font-semibold leading-5">{{ item.name }}</h3>
        <p v-if="item.spec" class="mt-1 text-xs text-gray-500 dark:text-gray-400">{{ item.spec }}</p>
        <p v-if="topic.id === 'nutrition'" class="mt-1 text-xs text-amber-800 dark:text-amber-200">先检查，遵医嘱</p>
        <p class="mt-auto pt-3 text-sm font-medium" :class="item.price === undefined ? 'text-gray-600 dark:text-gray-300' : 'text-primary-700 dark:text-primary-300'">{{ item.price !== undefined ? formatPrice(item) : item.status === 'planned' ? '暂未发售' : '选购参考' }}</p>
        <span class="mt-2 flex min-h-11 items-center justify-between border-t border-gray-100 pt-2 text-xs text-primary-700 dark:border-gray-700 dark:text-primary-300">查看详情<i class="ri-arrow-right-s-line text-lg" aria-hidden="true"></i></span>
      </div>
    </router-link>
  </article>
</template>
