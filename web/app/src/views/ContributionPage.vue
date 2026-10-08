<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useMainNav } from '@/composables/useMainNav'
import { useContributionOverview } from '@/composables/useContributionOverview'
import { useMyContributions } from '@/composables/useMyContributions'
import ContributionPersonal from '@/components/contribution/ContributionPersonal.vue'
import ContributionGrowth from '@/components/contribution/ContributionGrowth.vue'
import ContributionCommunity from '@/components/contribution/ContributionCommunity.vue'
import ContributionMatrix from '@/components/contribution/ContributionMatrix.vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
const { navItems } = useMainNav()
const title = computed(() => navItems.value.find(x => x.path === '/contribution')?.label ?? '')
const { overview, distribution, loading, overviewError, distributionError, load } = useContributionOverview()
const mine = useMyContributions()
const sections = [{ id: 'my-contribution', label: '我的贡献' }, { id: 'contribution-growth', label: '贡献成长' }, { id: 'community-results', label: '共建成果' }]
function jump(id: string) { document.getElementById(id)?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }) }
let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({ '@context': 'https://schema.org', '@type': 'CollectionPage', name: `${title.value} · 病友共同建设`, description: '查看个人贡献、共建积分与病友共同建设的数据成果。', url: `${location.origin}/contribution` })
  document.head.appendChild(schema)
})
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div class="page space-y-7 pb-8 pt-5 text-gray-900 dark:text-gray-100 md:space-y-9 md:pt-7">
    <header class="relative overflow-hidden rounded-3xl border border-primary-100 bg-gradient-to-br from-primary-50 via-white to-primary-50/60 p-6 dark:border-primary-900 dark:from-primary-900 dark:via-gray-900 dark:to-gray-950 md:p-8">
      <div class="pointer-events-none absolute -right-8 -top-10 h-48 w-48 rounded-full border-[28px] border-primary-100 dark:border-primary-800" aria-hidden="true"></div>
      <div class="relative max-w-2xl"><p class="flex items-center gap-2 text-xs font-medium tracking-widest text-primary-700 dark:text-primary-300"><i class="ri-hand-heart-line text-lg" aria-hidden="true"></i>{{ title }} · 每个人的一份</p><h1 class="mt-4 text-2xl font-bold leading-snug tracking-tight md:text-3xl">每一份记录，<br class="sm:hidden" />汇成更多病友的参考</h1><p class="mt-3 text-sm leading-7 text-gray-500 dark:text-gray-400">从认真记录自己，到为同行的人添一份力量。<br class="hidden sm:block" />我们一起，让白斑数据库更完整，让每一份贡献被看见。</p></div>
      <nav class="relative mt-5 flex flex-wrap gap-2" aria-label="同行页面内容"><button v-for="section in sections" :key="section.id" type="button" class="inline-flex min-h-11 items-center gap-2 rounded-full border border-primary-100 bg-white/80 px-4 text-xs text-primary-700 transition-colors hover:bg-primary-50 dark:border-primary-800 dark:bg-gray-900/50 dark:text-primary-300" @click="jump(section.id)">{{ section.label }}<i class="ri-arrow-down-line" aria-hidden="true"></i></button></nav>
    </header>
    <ContributionPersonal :summary="mine.summary.value" :loading="mine.loading.value" :error="mine.error.value" @retry="mine.load" />
    <ContributionGrowth :summary="mine.summary.value" :rules="overview?.rules ?? []" :levels="overview?.levels ?? []" :events="mine.events.value" :total-events="mine.totalEvents.value" :events-error="mine.eventsError.value" :loading-events="mine.loadingEvents.value" :sync-error="mine.syncError.value" @more="mine.moreEvents" @retry="mine.load" />
    <ContributionCommunity :overview="overview" :loading="loading" :error="overviewError" @retry="load" />
    <ContributionMatrix :distribution="distribution" :loading="loading" :error="distributionError" @retry="load" />
    <aside class="flex flex-col gap-4 rounded-2xl bg-primary-50 p-5 dark:bg-primary-900/20 sm:flex-row sm:items-center sm:justify-between"><div><p class="text-base font-medium text-primary-800 dark:text-primary-200">下一份贡献，从一次认真记录开始</p><p class="mt-2 text-xs leading-6 text-primary-700 dark:text-primary-300">选择你愿意记录的部位，核对自己知道的信息。持续记录，比无意义地重复拍照更有价值。</p></div><router-link to="/assessment" class="btn-primary inline-flex min-h-11 shrink-0 items-center justify-center gap-2 px-5 text-sm">去记录<i class="ri-arrow-right-line" aria-hidden="true"></i></router-link></aside>
    <MedicalDisclaimer variant="footer" message="贡献统计用于呈现共同建设进度，不代表诊断、治疗效果或康复人数。具体诊疗请遵医嘱。" />
  </div>
</template>
