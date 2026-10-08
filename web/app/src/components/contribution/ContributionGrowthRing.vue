<script setup lang="ts">
import { computed } from 'vue'
import { compactContributionCount } from '@/utils/contribution-charts'
import type { MyContributions } from '@/types/contribution'
const props = defineProps<{ membership: MyContributions['membership'] }>()
const circumference = 2 * Math.PI * 48
const progress = computed(() => Math.min(100, Math.max(0, props.membership.progress)))
</script>

<template>
  <div class="relative h-28 w-28 shrink-0" role="progressbar" aria-label="贡献等级升级进度" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100" :aria-valuetext="`${membership.points}积分，${membership.current.name}，距下一等级${membership.remaining}分`">
    <svg class="h-full w-full -rotate-90" viewBox="0 0 112 112" aria-hidden="true">
      <circle cx="56" cy="56" r="48" fill="none" stroke="currentColor" stroke-width="8" class="text-gray-100 dark:text-gray-700" />
      <circle v-if="progress > 0" cx="56" cy="56" r="48" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" :stroke-dasharray="circumference" :stroke-dashoffset="circumference * (1 - progress / 100)" class="text-primary-600 dark:text-primary-400" />
    </svg>
    <div class="absolute inset-0 flex flex-col items-center justify-center"><span class="text-2xl font-semibold tabular-nums">{{ compactContributionCount(membership.points) }}</span><span class="mt-1 text-[11px] text-gray-500 dark:text-gray-400">同行积分</span></div>
  </div>
</template>
