<script setup lang="ts">
/**
 * AssessmentStepper — 白斑测评 3 步进度指示器
 *
 * 拍照评估 → 标注确认 → 评估结果
 * 语义化进度条，替代原 header 内零散的圆点 + 文字标签。
 */
defineProps<{ current: number }>()

const steps = [
  { n: 1, label: '拍照评估' },
  { n: 2, label: '标注确认' },
  { n: 3, label: '评估结果' },
]

function circleClass(n: number, current: number): string {
  if (current >= n) return 'bg-primary-500 border-primary-500 text-white shadow-sm'
  return 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-600 text-gray-400 dark:text-gray-500'
}

function labelClass(n: number, current: number): string {
  if (current >= n) return 'text-gray-700 dark:text-gray-300 font-medium'
  return 'text-gray-400 dark:text-gray-500'
}
</script>

<template>
  <nav class="flex items-center w-full max-w-sm mx-auto" aria-label="评估进度">
    <template v-for="(s, i) in steps" :key="s.n">
      <div class="flex items-center gap-1.5 shrink-0">
        <div
          class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold border transition-colors"
          :class="circleClass(s.n, current)"
          :aria-current="current === s.n ? 'step' : undefined"
        >
          <i v-if="current > s.n" class="ri-check-line text-[10px]"></i>
          <span v-else>{{ s.n }}</span>
        </div>
        <span class="text-[11px] leading-none whitespace-nowrap transition-colors" :class="labelClass(s.n, current)">
          {{ s.label }}
        </span>
      </div>
      <div
        v-if="i < steps.length - 1"
        class="flex-1 h-px mx-1.5 rounded-full transition-colors"
        :class="current > s.n ? 'bg-primary-400' : 'bg-gray-200 dark:bg-gray-600'"
      ></div>
    </template>
  </nav>
</template>
