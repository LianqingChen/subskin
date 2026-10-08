<script setup lang="ts">
import { useAnalysisCountdown } from '@/composables/useAnalysisCountdown'
const props = defineProps<{ active: boolean; stage: string }>()
const emit = defineEmits<{ cancel: [] }>()
const countdown = useAnalysisCountdown(() => props.active)
</script>
<template>
  <section aria-label="分析进度" class="flex min-h-[68px] items-center justify-between gap-2 rounded-xl bg-primary-50 p-3 text-primary-900 dark:bg-primary-900 dark:text-primary-100">
    <div class="min-w-0">
      <p class="text-sm font-semibold tabular-nums">{{ countdown.overdue.value ? '耗时较长' : `参考倒计时 ${countdown.remaining.value} 秒` }}</p>
      <p role="status" aria-live="polite" class="mt-1 text-xs"><i class="ri-loader-4-line mr-1 inline-block animate-spin" aria-hidden="true"></i>{{ countdown.overdue.value ? '仍在分析，可取消后重试' : stage }}</p>
    </div>
    <button type="button" class="flex min-h-[44px] shrink-0 items-center gap-1 rounded-lg border border-primary-200 bg-white/70 px-2.5 text-xs font-medium text-primary-700 transition-colors hover:bg-white active:bg-primary-100 dark:border-primary-700 dark:bg-gray-900/60 dark:text-primary-200" @click="emit('cancel')"><i class="ri-close-line text-base" aria-hidden="true"></i>取消分析</button>
  </section>
</template>
