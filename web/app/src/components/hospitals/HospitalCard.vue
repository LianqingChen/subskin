<script setup lang="ts">
import type { HospitalMark, HospitalView } from '@/types/hospital'

/**
 * 目录卡片（降噪版）：主按钮「查看详情」整卡可点，想去/去过/对比为次级操作。
 * v3 合规：不出现任何平均分/星级，只显示评价条数。
 */
defineProps<{ hospital: HospitalView; mark?: HospitalMark; compared: boolean }>()
const emit = defineEmits<{ open: []; mark: [value: HospitalMark]; compare: []; locate: [] }>()
</script>

<template>
  <article class="relative rounded-xl border border-gray-200/80 bg-white p-4 transition-all hover:border-gray-300 hover:shadow-md hover:shadow-gray-200/60 dark:border-gray-800 dark:bg-gray-900 dark:hover:shadow-none">
    <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
      <span>{{ hospital.province }} · {{ hospital.city }}<template v-if="hospital.district"> · {{ hospital.district }}</template></span>
      <span v-if="hospital.kind">{{ hospital.kind }}</span>
      <span v-if="hospital.origin === 'community'" class="rounded-md bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">病友补充 · 待核实</span>
    </div>
    <h3 class="mt-1.5">
      <button class="min-h-11 text-left text-base font-semibold leading-6 text-gray-900 after:absolute after:inset-0 hover:text-primary-700 dark:text-gray-100" @click="emit('open')">{{ hospital.name }}</button>
    </h3>
    <p v-if="hospital.address" class="mt-1 flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
      <i class="ri-map-pin-line shrink-0 text-primary-600 dark:text-primary-400" />
      <span class="truncate">{{ hospital.address }}</span>
    </p>
    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{{ hospital.department || '科室待确认' }}</p>
    <div v-if="hospital.features.length" class="mt-2 flex flex-wrap gap-1.5">
      <span v-for="tag in hospital.features.slice(0, 3)" :key="tag" class="rounded-md bg-gray-100 px-2 py-1 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">{{ tag }}</span>
    </div>
    <p v-if="hospital.stats.reviewCount > 0" class="mt-2 text-xs text-gray-500 dark:text-gray-400">{{ hospital.stats.reviewCount }} 条病友评价</p>
    <div class="relative z-10 mt-3 flex flex-wrap items-center gap-1 border-t border-gray-100 pt-2 dark:border-gray-800">
      <button class="hospital-action font-medium text-primary-700 dark:text-primary-300" @click="emit('open')">查看详情<i class="ri-arrow-right-s-line" /></button>
      <button class="hospital-action" title="在地图上定位此医院地址" @click="emit('locate')"><i class="ri-map-pin-range-line" /> 地图</button>
      <button :aria-pressed="mark === 'want'" class="hospital-action" :class="{ 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300': mark === 'want' }" @click="emit('mark', 'want')"><i :class="mark === 'want' ? 'ri-bookmark-fill' : 'ri-bookmark-line'" /> 想去</button>
      <button :aria-pressed="mark === 'visited'" class="hospital-action" :class="{ 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300': mark === 'visited' }" @click="emit('mark', 'visited')"><i class="ri-map-pin-user-line" /> 去过</button>
      <button :aria-pressed="compared" class="hospital-action ml-auto" :class="{ 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300': compared }" @click="emit('compare')"><i :class="compared ? 'ri-checkbox-circle-fill' : 'ri-scales-3-line'" /> {{ compared ? '已加入' : '对比' }}</button>
    </div>
  </article>
</template>

<style scoped>
.hospital-action { @apply min-h-11 rounded-lg px-3 text-sm text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800; }
</style>
