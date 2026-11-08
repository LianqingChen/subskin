<script setup lang="ts">
import { computed } from 'vue'
import type { EvidenceLevel } from '@/api/knowledge'
const props = defineProps<{ level: EvidenceLevel | string | null | undefined }>()
const LABELS: Record<string, string> = { A: '指南/综述', B: '临床试验', C: '观察研究', D: '专家意见', E: '病友经验' }
const key = computed(() => String(props.level ?? '').toUpperCase())
const label = computed(() => LABELS[key.value] ?? '')
// A/B 实心，C/D 描边，E 虚线框；始终显示字母 + 文字，不只靠颜色
const tone = computed(() => {
  if (key.value === 'A') return 'border border-primary-700 bg-primary-700 text-white dark:border-primary-600 dark:bg-primary-600'
  if (key.value === 'B') return 'border border-primary-600 bg-primary-600 text-white dark:border-primary-700 dark:bg-primary-700'
  if (key.value === 'C') return 'border border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300'
  if (key.value === 'D') return 'border border-gray-500 text-gray-700 dark:border-gray-400 dark:text-gray-300'
  return 'border border-dashed border-gray-400 text-gray-600 dark:border-gray-500 dark:text-gray-300'
})
</script>

<template>
  <span v-if="label" class="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs font-medium" :class="tone" :title="`证据等级 ${key}：${label}`">
    <b class="tabular-nums">{{ key }}</b><span>{{ label }}</span>
  </span>
</template>
