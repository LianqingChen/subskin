<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useMainNav } from '@/composables/useMainNav'
import { useContributionOverview } from '@/composables/useContributionOverview'
import { useMyContributions } from '@/composables/useMyContributions'
import ContributionPersonal from '@/components/contribution/ContributionPersonal.vue'
import ContributionWaffle from '@/components/contribution/ContributionWaffle.vue'
import ContributionTrend from '@/components/contribution/ContributionTrend.vue'
import ContributionBodyChart from '@/components/contribution/ContributionBodyChart.vue'
import ContributionGrowth from '@/components/contribution/ContributionGrowth.vue'
import ContributionCoverage from '@/components/contribution/ContributionCoverage.vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
const { navItems } = useMainNav()
const title = computed(() => navItems.value.find(x => x.path === '/contribution')?.label ?? '')
const { overview, distribution, timeline, loading, overviewError, distributionError, timelineError, load } = useContributionOverview()
const mine = useMyContributions()
const sections = [{ id: 'my-contribution', label: '我的贡献' }, { id: 'community-results', label: '共同成果' }, { id: 'body-distribution', label: '数据覆盖' }]
function jump(id: string) { document.getElementById(id)?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }) }
function retryCharts() { void load(); if (mine.summary.value) void mine.load() }
let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({ '@context': 'https://schema.org', '@type': 'CollectionPage', name: `${title.value} · 病友共同建设`, description: '通过贡献成长环、图片积累图、采纳月份图和部位图查看个人与病友共同建设的成果。', url: `${location.origin}/contribution` })
  document.head.appendChild(schema)
})
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div class="page space-y-5 pb-8 pt-5 text-gray-900 dark:text-gray-100 md:space-y-6 md:pt-7">
    <section aria-label="个人与共同成果" class="space-y-5">
      <header><p class="flex items-center gap-2 text-xs font-medium text-primary-700 dark:text-primary-300"><i class="ri-hand-heart-line text-base" aria-hidden="true"></i>{{ title }} · 每个人的一份</p><h1 class="mt-2 text-2xl font-bold leading-snug tracking-tight md:text-3xl">我的一份，大家的力量</h1><p class="mt-2 text-sm leading-7 text-gray-500 dark:text-gray-400">每一次认真记录，都让共同的参考更完整。</p><nav class="mt-3 flex flex-wrap gap-2" :aria-label="`${title}页面内容`"><button v-for="section in sections" :key="section.id" type="button" class="inline-flex min-h-11 items-center gap-2 rounded-full border border-gray-200 bg-white px-4 text-xs text-primary-700 dark:border-gray-700 dark:bg-gray-800 dark:text-primary-300" @click="jump(section.id)">{{ section.label }}<i class="ri-arrow-down-line" aria-hidden="true"></i></button></nav></header>
      <div class="grid gap-4 md:grid-cols-2"><ContributionPersonal :summary="mine.summary.value" :loading="mine.loading.value" :error="mine.error.value" @retry="mine.load" /><ContributionWaffle :overview="overview" :summary="mine.summary.value" :loading="loading" :error="overviewError" @retry="load" /></div>
    </section>
    <section aria-label="增长与部位分布" class="grid items-stretch gap-4 md:grid-cols-2"><ContributionTrend :timeline="timeline" :personal-timeline="mine.visuals.value?.timeline ?? null" :loading="loading" :error="timelineError" @retry="retryCharts" /><ContributionBodyChart :distribution="distribution" :personal="mine.visuals.value" :loading="loading" :error="distributionError" :personal-error="mine.visualsError.value" @retry="retryCharts" /></section>
    <section aria-label="贡献足迹与继续同行" class="space-y-4"><ContributionGrowth :summary="mine.summary.value" :rules="overview?.rules ?? []" :levels="overview?.levels ?? []" :events="mine.events.value" :total-events="mine.totalEvents.value" :events-error="mine.eventsError.value" :loading-events="mine.loadingEvents.value" :sync-error="mine.syncError.value" @more="mine.moreEvents" @retry="mine.load" /><ContributionCoverage :distribution="distribution" /><aside class="flex flex-col gap-3 rounded-2xl bg-primary-50 p-5 dark:bg-primary-900 sm:flex-row sm:items-center sm:justify-between"><div><p class="text-base font-medium text-primary-800 dark:text-primary-200">下一份贡献，补上下一块拼图</p><p class="mt-2 text-xs leading-6 text-primary-700 dark:text-primary-300">选择愿意记录的部位，核对自己知道的信息，在合适的随访时间持续记录。</p></div><router-link to="/assessment" class="btn-primary inline-flex min-h-11 shrink-0 items-center justify-center gap-2 px-5 text-sm">继续认真记录<i class="ri-arrow-right-line" aria-hidden="true"></i></router-link></aside><MedicalDisclaimer variant="footer" message="贡献图表呈现共同建设进度，部位颜色不表示病情严重度，统计不代表诊断、治疗效果或康复人数。" /></section>
  </div>
</template>
