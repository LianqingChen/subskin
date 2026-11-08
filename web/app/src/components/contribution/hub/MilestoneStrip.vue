<script setup lang="ts">
import { computed } from 'vue'
import type { ContributionOverview } from '@/types/contribution'
const props = defineProps<{ overview: ContributionOverview | null; loading: boolean; error: boolean }>()
// 只展示真实数据；不足或未公开时诚实说明，加载失败则整条隐藏
const images = computed(() => props.overview?.images.status === 'available' && (props.overview.images.value ?? 0) > 0 ? props.overview.images.value : null)
const contributors = computed(() => props.overview?.contributors.status === 'available' && (props.overview.contributors.value ?? 0) > 0 ? props.overview.contributors.value : null)
</script>

<template>
  <div v-if="loading" class="h-11 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" role="status"><span class="sr-only">正在加载共同里程碑</span></div>
  <section v-else-if="overview && !error" aria-label="共同里程碑" class="flex min-h-11 items-center gap-2 rounded-xl border border-primary-100 bg-primary-50 px-3 py-2 text-sm text-primary-800 dark:border-primary-900 dark:bg-primary-900/20 dark:text-primary-300">
    <i class="ri-flag-2-line shrink-0 text-base" aria-hidden="true"></i>
    <span class="shrink-0 font-medium">共同里程碑</span>
    <span class="min-w-0 truncate text-primary-700 dark:text-primary-300">
      <template v-if="images !== null">社区已采纳图片 <b class="tabular-nums">{{ images.toLocaleString('zh-CN') }}</b> 张<template v-if="contributors !== null"> · <b class="tabular-nums">{{ contributors.toLocaleString('zh-CN') }}</b> 位贡献者</template></template>
      <template v-else>正在积累，满 5 人后公开</template>
    </span>
  </section>
</template>
