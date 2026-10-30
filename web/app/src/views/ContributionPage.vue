<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useMainNav } from '@/composables/useMainNav'
import { useContributionOverview } from '@/composables/useContributionOverview'
import { useMyContributions } from '@/composables/useMyContributions'
import ContributionPersonal from '@/components/contribution/ContributionPersonal.vue'
import ContributionWaffle from '@/components/contribution/ContributionWaffle.vue'
import ContributionTrend from '@/components/contribution/ContributionTrend.vue'
import ContributionBodyChart from '@/components/contribution/ContributionBodyChart.vue'
import ContributionGrowth from '@/components/contribution/ContributionGrowth.vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
const { navItems } = useMainNav()
const title = computed(() => navItems.value.find(x => x.path === '/contribution')?.label ?? '')
const { overview, distribution, timeline, loading, overviewError, distributionError, timelineError, load } = useContributionOverview()
const mine = useMyContributions()
// 手机端月份图与部位图合为一组切换，平板/桌面并排
const chart = ref<'trend' | 'body'>('trend')
function retryCharts() { void load(); if (mine.summary.value) void mine.load() }
let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({ '@context': 'https://schema.org', '@type': 'CollectionPage', name: `${title.value} · 病友共同建设`, description: '查看个人贡献与病友共同积累的有效图片、采纳月份与部位分布。', url: `${location.origin}/contribution` })
  document.head.appendChild(schema)
})
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div class="page space-y-4 pb-6 pt-4 text-gray-900 dark:text-gray-100 md:space-y-5 md:pt-6">
    <h1 class="sr-only">{{ title }}</h1>

    <div class="grid gap-4 md:grid-cols-2">
      <ContributionPersonal :summary="mine.summary.value" :loading="mine.loading.value" :error="mine.error.value" @retry="mine.load" />
      <ContributionWaffle :overview="overview" :summary="mine.summary.value" :loading="loading" :error="overviewError" @retry="load" />
    </div>

    <section aria-label="采纳月份与部位分布">
      <div class="mb-3 grid grid-cols-2 rounded-xl bg-gray-100 p-1 dark:bg-gray-800 md:hidden" role="tablist" aria-label="切换图表">
        <button type="button" role="tab" class="min-h-10 rounded-lg text-sm" :class="chart === 'trend' ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" :aria-selected="chart === 'trend'" @click="chart = 'trend'">月份积累</button>
        <button type="button" role="tab" class="min-h-10 rounded-lg text-sm" :class="chart === 'body' ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" :aria-selected="chart === 'body'" @click="chart = 'body'">部位分布</button>
      </div>
      <div class="grid items-stretch gap-4 md:grid-cols-2">
        <ContributionTrend :class="chart !== 'trend' && 'max-md:hidden'" :timeline="timeline" :personal-timeline="mine.visuals.value?.timeline ?? null" :loading="loading" :error="timelineError" @retry="retryCharts" />
        <ContributionBodyChart :class="chart !== 'body' && 'max-md:hidden'" :distribution="distribution" :personal="mine.visuals.value" :loading="loading" :error="distributionError" :personal-error="mine.visualsError.value" @retry="retryCharts" />
      </div>
    </section>

    <ContributionGrowth :summary="mine.summary.value" :rules="overview?.rules ?? []" :levels="overview?.levels ?? []" :events="mine.events.value" :total-events="mine.totalEvents.value" :events-error="mine.eventsError.value" :loading-events="mine.loadingEvents.value" :sync-error="mine.syncError.value" @more="mine.moreEvents" @retry="mine.load" />

    <MedicalDisclaimer variant="footer" message="贡献图表呈现共同建设进度，部位颜色不表示病情严重度，统计不代表诊断、治疗效果或康复人数。" />
  </div>
</template>
