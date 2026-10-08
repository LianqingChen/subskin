<script setup lang="ts">
import type { ContributionDistribution } from '@/types/contribution'
defineProps<{ distribution: ContributionDistribution | null }>()
</script>

<template>
  <details v-if="distribution" class="card p-5 dark:bg-gray-800">
    <summary class="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3"><span class="font-medium">更多覆盖维度</span><span class="text-xs text-gray-500 dark:text-gray-400">部位 × 分型 × 拍摄条件<i class="ri-arrow-down-s-line ml-2" aria-hidden="true"></i></span></summary>
    <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-gray-400">{{ distribution.types.note }} 医生确认数据具备后，再展示部位与分型的热力矩阵；缺失字段保留未知。</p>
    <ul class="mt-4 flex flex-wrap gap-2"><li v-for="dimension in distribution.dimensions" :key="dimension.name" class="rounded-full bg-gray-50 px-3 py-2 text-xs text-gray-600 dark:bg-gray-900 dark:text-gray-300"><i :class="dimension.status === 'available' ? 'ri-checkbox-circle-line' : 'ri-time-line'" class="mr-1" aria-hidden="true"></i>{{ dimension.name }} · {{ dimension.status === 'available' ? '已有分布' : '待补充' }}</li></ul>
    <p class="mt-4 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ distribution.coverage.note }}。正常皮肤与相似疾病独立归入对照样本。</p>
  </details>
</template>
