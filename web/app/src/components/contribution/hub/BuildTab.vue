<script setup lang="ts">
import { ref } from 'vue'
import { useMyContributions } from '@/composables/useMyContributions'
import ContributionPersonal from '@/components/contribution/ContributionPersonal.vue'
import ContributionWaffle from '@/components/contribution/ContributionWaffle.vue'
import ContributionTrend from '@/components/contribution/ContributionTrend.vue'
import ContributionBodyChart from '@/components/contribution/ContributionBodyChart.vue'
import ContributionGrowth from '@/components/contribution/ContributionGrowth.vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import type { ContributionDistribution, ContributionOverview, ContributionTimeline } from '@/types/contribution'

// 共建栏目 = 原「同行」页内容；总览数据由页面统一加载后传入（与顶部里程碑共用，避免重复请求）
const props = defineProps<{
  overview: ContributionOverview | null; distribution: ContributionDistribution | null; timeline: ContributionTimeline | null
  loading: boolean; overviewError: boolean; distributionError: boolean; timelineError: boolean
}>()
const emit = defineEmits<{ reload: [] }>()
const mine = useMyContributions()
// 手机端月份图与部位图合为一组切换，平板/桌面并排
const chart = ref<'trend' | 'body'>('trend')
function retryCharts() { emit('reload'); if (mine.summary.value) void mine.load() }
</script>

<template>
  <div class="space-y-4 md:space-y-5">
    <div class="grid gap-4 md:grid-cols-2">
      <ContributionPersonal :summary="mine.summary.value" :loading="mine.loading.value" :error="mine.error.value" @retry="mine.load" />
      <ContributionWaffle :overview="props.overview" :summary="mine.summary.value" :loading="props.loading" :error="props.overviewError" @retry="emit('reload')" />
    </div>

    <section aria-label="采纳月份与部位分布">
      <div class="mb-3 grid grid-cols-2 rounded-xl bg-gray-100 p-1 dark:bg-gray-800 md:hidden" role="tablist" aria-label="切换图表">
        <button type="button" role="tab" class="min-h-10 rounded-lg text-sm" :class="chart === 'trend' ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" :aria-selected="chart === 'trend'" @click="chart = 'trend'">月份积累</button>
        <button type="button" role="tab" class="min-h-10 rounded-lg text-sm" :class="chart === 'body' ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" :aria-selected="chart === 'body'" @click="chart = 'body'">部位分布</button>
      </div>
      <div class="grid items-stretch gap-4 md:grid-cols-2">
        <ContributionTrend :class="chart !== 'trend' && 'max-md:hidden'" :timeline="props.timeline" :personal-timeline="mine.visuals.value?.timeline ?? null" :loading="props.loading" :error="props.timelineError" @retry="retryCharts" />
        <ContributionBodyChart :class="chart !== 'body' && 'max-md:hidden'" :distribution="props.distribution" :personal="mine.visuals.value" :loading="props.loading" :error="props.distributionError" :personal-error="mine.visualsError.value" @retry="retryCharts" />
      </div>
    </section>

    <ContributionGrowth :summary="mine.summary.value" :rules="props.overview?.rules ?? []" :levels="props.overview?.levels ?? []" :events="mine.events.value" :total-events="mine.totalEvents.value" :events-error="mine.eventsError.value" :loading-events="mine.loadingEvents.value" :sync-error="mine.syncError.value" @more="mine.moreEvents" @retry="mine.load" />

    <MedicalDisclaimer variant="footer" message="贡献图表呈现共同建设进度，部位颜色不表示病情严重度，统计不代表诊断、治疗效果或康复人数。" />
  </div>
</template>
