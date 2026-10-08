<script setup lang="ts">
import { computed } from 'vue'
import type { ContributionMetric } from '@/types/contribution'
const props = defineProps<{ label: string; icon: string; metric: ContributionMetric; secondary?: string }>()
const value = computed(() => props.metric.status === 'available' && props.metric.value !== null
  ? props.metric.value.toLocaleString('zh-CN') : props.metric.status === 'suppressed' ? '暂不公开' : '待统计')
</script>

<template>
  <details class="group min-w-0 rounded-2xl border border-gray-100 bg-white/70 p-4 dark:border-gray-700 dark:bg-gray-800/70">
    <summary class="cursor-pointer list-none rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
      <span class="flex min-h-11 items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span><i :class="icon" class="mr-1.5 text-base text-primary-600 dark:text-primary-400" aria-hidden="true"></i>{{ label }}</span>
        <i class="ri-information-line" aria-hidden="true"></i>
      </span>
      <span class="mt-1 block font-semibold tabular-nums text-gray-900 dark:text-gray-100" :class="metric.status === 'available' ? 'text-3xl' : 'text-lg'">
        {{ value }}<span v-if="metric.status === 'available'" class="ml-1 text-xs font-normal text-gray-400">{{ metric.unit }}</span>
      </span>
      <span v-if="secondary" class="mt-2 block text-[11px] leading-5 text-gray-500 dark:text-gray-400">{{ secondary }}</span>
    </summary>
    <p class="mt-3 border-t border-gray-100 pt-3 text-xs leading-6 text-gray-500 dark:border-gray-700 dark:text-gray-400">{{ metric.note }}</p>
  </details>
</template>
