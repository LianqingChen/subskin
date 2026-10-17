<script setup lang="ts">
import { computed, ref } from 'vue'
import { compactContributionCount } from '@/utils/contribution-charts'
import type { ContributionTimeline } from '@/types/contribution'
const props = defineProps<{ timeline: ContributionTimeline | null; personalTimeline: ContributionTimeline | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const selectedMonth = ref('')
const data = computed(() => props.personalTimeline ?? props.timeline)
const personalOnly = computed(() => !!props.personalTimeline && (data.value?.status === 'suppressed' || data.value?.periods.some(p => p.others === null)))
const values = computed(() => data.value?.periods.map(p => ({ ...p, value: personalOnly.value ? p.mine : p.total })) ?? [])
const maximum = computed(() => Math.max(1, ...values.value.map(p => p.value ?? 0)))
const hasData = computed(() => values.value.some(p => (p.value ?? 0) > 0))
const selectedPeriod = computed(() => values.value.find(p => p.month === selectedMonth.value))
const accessible = computed(() => values.value.map(p => `${p.month}：${p.value === null ? '暂不公开' : `${p.value}张`}`).join('；'))
const until = computed(() => data.value ? new Date(data.value.updated_at).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric' }) : '')
function select(month: string) { selectedMonth.value = selectedMonth.value === month ? '' : month }
</script>

<template>
  <section id="contribution-trend" class="card flex min-w-0 flex-col p-4 dark:bg-gray-800 sm:p-5" aria-labelledby="trend-title">
    <div class="mb-3 flex items-center justify-between gap-2"><h2 id="trend-title" class="text-base font-semibold">月份积累</h2><span v-if="until" class="text-xs text-gray-500 dark:text-gray-400">近 6 个月 · 截至 {{ until }}</span></div>
    <div v-if="loading" role="status" class="h-52 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-700"><span class="sr-only">正在加载增长图</span></div>
    <div v-else-if="error && !personalTimeline" role="alert" class="py-6 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">月份统计加载失败</p><button type="button" class="btn-ghost mt-2 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else-if="data">
      <template v-if="hasData">
        <p class="text-xs text-gray-500 dark:text-gray-400">{{ personalOnly ? '我的有效图片' : '有效图片' }} · 按采纳月份（张）</p>
        <div class="trend-bars mt-3" role="group" :aria-label="accessible">
          <button v-for="period in values" :key="period.month" type="button" class="trend-hit" :aria-pressed="selectedMonth === period.month" :aria-label="`${period.month}，${period.value ?? '未公开'}张`" @click="select(period.month)">
            <span class="trend-value">{{ compactContributionCount(period.value ?? 0) }}</span>
            <span class="trend-bar" :class="{ 'trend-personal-only': personalOnly, 'trend-selected': selectedMonth === period.month }" :style="{ height: `${Math.max(2, (period.value ?? 0) / maximum * 120)}px` }"><span v-if="!personalOnly && period.mine !== null && (period.total ?? 0) > 0" class="trend-mine" :style="{ height: `${period.mine / (period.total ?? 1) * 100}%` }"></span></span>
            <span class="trend-month">{{ Number(period.month.slice(5)) }}月</span>
          </button>
        </div>
        <p class="mt-2 min-h-5 text-xs text-gray-500 dark:text-gray-400" aria-live="polite"><template v-if="selectedPeriod">{{ selectedPeriod.month }} · {{ personalOnly ? '我的' : '有效图片' }} {{ selectedPeriod.value }} 张<span v-if="!personalOnly && selectedPeriod.mine !== null">，我的 {{ selectedPeriod.mine }} 张</span></template><template v-else>点柱子查看当月明细</template></p>
        <div class="mt-2 flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400"><span v-if="personalTimeline" class="inline-flex items-center gap-1.5"><b class="trend-key trend-mine"></b>我的贡献</span><span v-if="!personalOnly" class="inline-flex items-center gap-1.5"><b class="trend-key trend-bar"></b>{{ personalTimeline ? '其他贡献者' : '大家的贡献' }}</span><span v-if="personalOnly">公共分布暂不公开</span></div>
      </template>
      <p v-else class="flex items-center gap-2 rounded-xl bg-gray-50 px-3 py-3 text-xs text-gray-500 dark:bg-gray-900 dark:text-gray-400" role="status"><i class="ri-bar-chart-2-line text-base text-primary-600 dark:text-primary-400" aria-hidden="true"></i>{{ data.status === 'suppressed' && !personalTimeline ? '月份分布暂不公开' : '采纳记录正在积累' }}</p>
      <details class="mt-1 text-xs text-gray-500 dark:text-gray-400"><summary class="min-h-10 cursor-pointer py-2.5">统计口径</summary><p class="leading-5">{{ data.note }}</p><p v-if="data.own_unknown_dates" class="mt-1.5 leading-5">我的采纳日期待补充 {{ data.own_unknown_dates.value }} 张；展示月份之前 {{ data.own_earlier?.value ?? 0 }} 张。</p><p v-if="data.unknown_dates.value !== null" class="mt-1.5 leading-5">采纳日期待补充 {{ data.unknown_dates.value }} 张；展示月份之前 {{ data.earlier.value ?? '未公开' }} 张。</p></details>
    </template>
  </section>
</template>

<style scoped>
.trend-bars { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:6px; align-items:end; }
.trend-hit { display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:164px; min-width:0; border-radius:8px; }
.trend-hit:focus-visible { outline:2px solid var(--color-primary-500); outline-offset:2px; }
.trend-value,.trend-month { font-size:11px; font-variant-numeric:tabular-nums; color:var(--color-text-secondary); }
.trend-value { margin-bottom:4px; }
.trend-month { margin-top:6px; white-space:nowrap; }
.trend-bar { position:relative; display:block; width:min(100%,32px); background:var(--color-primary-200); border-radius:4px 4px 0 0; overflow:hidden; }
.trend-selected { outline:2px solid var(--color-primary-600); outline-offset:1px; }
.trend-mine { display:block; position:absolute; bottom:0; left:0; width:100%; background:var(--color-primary-700); }
.trend-key { position:static; display:inline-block; height:10px; width:10px; border-radius:2px; }
.trend-personal-only { background:var(--color-primary-700); }
:global(html.dark .trend-bar) { background:var(--color-primary-600); }
:global(html.dark .trend-mine) ,:global(html.dark .trend-personal-only) { background:var(--color-primary-300); }
</style>
