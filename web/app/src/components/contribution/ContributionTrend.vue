<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { compactContributionCount } from '@/utils/contribution-charts'
import type { ContributionTimeline } from '@/types/contribution'
const props = defineProps<{ timeline: ContributionTimeline | null; personalTimeline: ContributionTimeline | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const pointerQuery = window.matchMedia('(pointer: coarse)')
const coarsePointer = ref(pointerQuery.matches)
const selectedMonth = ref('')
function pointerChanged(event: MediaQueryListEvent) { coarsePointer.value = event.matches }
pointerQuery.addEventListener?.('change', pointerChanged)
onBeforeUnmount(() => pointerQuery.removeEventListener?.('change', pointerChanged))
const data = computed(() => props.personalTimeline ?? props.timeline)
const personalOnly = computed(() => !!props.personalTimeline && (data.value?.status === 'suppressed' || data.value?.periods.some(p => p.others === null)))
const values = computed(() => data.value?.periods.map(p => ({ ...p, value: personalOnly.value ? p.mine : p.total })) ?? [])
const maximum = computed(() => Math.max(1, ...values.value.map(p => p.value ?? 0)))
const hasData = computed(() => values.value.some(p => (p.value ?? 0) > 0))
const selectedPeriod = computed(() => values.value.find(p => p.month === selectedMonth.value))
const accessible = computed(() => values.value.map(p => `${p.month}：${p.value === null ? '暂不公开' : `${p.value}张`}`).join('；'))
const until = computed(() => data.value ? new Date(data.value.updated_at).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '')
</script>

<template>
  <section id="contribution-trend" class="card flex min-w-0 scroll-mt-24 flex-col p-5 dark:bg-gray-800 sm:p-6" aria-labelledby="trend-title">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 id="trend-title" class="text-lg font-semibold">合力如何积累</h2><span class="text-xs text-gray-500 dark:text-gray-400">近六个月 · 截至 {{ until }}</span></div>
    <div v-if="loading" role="status" class="h-60 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-700"><span class="sr-only">正在加载增长图</span></div>
    <div v-else-if="error && !personalTimeline" role="alert" class="py-8 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">月份统计加载失败</p><button type="button" class="btn-ghost mt-3 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else-if="data">
      <p class="text-xs text-gray-500 dark:text-gray-400">{{ personalOnly ? '我的有效图片 · 采纳月份分布（张）' : '当前有效图片 · 采纳月份分布（张）' }}</p>
      <div v-if="hasData" class="trend-plot mt-4" role="group" :aria-label="accessible"><div class="trend-scale" aria-hidden="true"><span>{{ compactContributionCount(maximum) }}</span><span>0</span></div><div class="trend-bars"><component :is="coarsePointer ? 'div' : 'details'" v-for="period in values" :key="period.month" class="trend-column"><component :is="coarsePointer ? 'div' : 'summary'" class="trend-hit" :aria-label="`${period.month}，${period.value}张，${coarsePointer ? '在下方选择月份查看明细' : '点按查看详情'}`" :title="`${period.month} · ${personalOnly ? '我的' : '有效图片'} ${period.value} 张${!personalOnly && period.mine !== null ? `，我的 ${period.mine} 张` : ''}`"><span class="trend-value">{{ compactContributionCount(period.value ?? 0) }}</span><span class="trend-bar" :class="{ 'trend-personal-only': personalOnly }" :style="{ height: `${(period.value ?? 0) / maximum * 130}px` }"><span v-if="!personalOnly && period.mine !== null && (period.total ?? 0) > 0" class="trend-mine" :style="{ height: `${period.mine / (period.total ?? 1) * 100}%` }"></span></span><span class="trend-month"><span class="hidden sm:inline">{{ period.month.slice(2).replace('-', '.') }}</span><span class="sm:hidden">{{ period.month.slice(5) }}月</span></span></component><p v-if="!coarsePointer" class="mt-2 text-center text-[11px] leading-5 text-gray-500 dark:text-gray-400">{{ period.month }}<br />{{ personalOnly ? '我的' : '有效图片' }} {{ period.value }} 张<span v-if="!personalOnly && period.mine !== null"><br />我的 {{ period.mine }} 张</span></p></component></div></div>
      <div v-else class="mt-4 rounded-xl bg-gray-50 px-4 py-9 text-center dark:bg-gray-900"><i class="ri-bar-chart-2-line text-3xl text-primary-600 dark:text-primary-400" aria-hidden="true"></i><p class="mt-3 text-sm text-gray-500 dark:text-gray-400">{{ data.status === 'suppressed' && !personalTimeline ? '月份分布暂不公开' : '有据可查的采纳记录正在积累' }}</p><p class="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ data.status === 'suppressed' && !personalTimeline ? '小样本月份和可反推的余量一并隐藏。' : '没有采纳日志的资料，不用上传或补记积分日期代替。' }}</p></div>
      <div v-if="hasData && coarsePointer" class="mt-4"><label for="contribution-month-detail" class="mr-2 text-xs text-gray-500 dark:text-gray-400">月份明细</label><select id="contribution-month-detail" v-model="selectedMonth" class="min-h-11 rounded-xl border border-gray-200 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-900"><option value="">选择月份</option><option v-for="period in values" :key="period.month" :value="period.month">{{ period.month }}</option></select><p v-if="selectedPeriod" class="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400" aria-live="polite">{{ selectedPeriod.month }} · {{ personalOnly ? '我的' : '有效图片' }} {{ selectedPeriod.value }} 张<span v-if="!personalOnly && selectedPeriod.mine !== null">，我的 {{ selectedPeriod.mine }} 张</span></p></div>
      <div v-if="hasData" class="mt-4 flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400"><span v-if="personalTimeline" class="inline-flex items-center gap-2"><b class="trend-key trend-mine"></b>我的贡献</span><span v-if="!personalOnly" class="inline-flex items-center gap-2"><b class="trend-key trend-bar"></b>{{ personalTimeline ? '其他贡献者' : '大家的贡献' }}</span></div>
      <p v-if="personalOnly" class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">公共分布或小样本组合暂不公开，这里单独展示本人贡献。</p>
      <details class="mt-3 text-xs text-gray-500 dark:text-gray-400"><summary class="min-h-11 cursor-pointer">日期与统计说明</summary><p class="leading-6">{{ data.note }}</p><p v-if="data.own_unknown_dates" class="mt-2 leading-6">我的采纳日期待补充：{{ data.own_unknown_dates.value }} 张；我在展示月份之前的有效图片：{{ data.own_earlier?.value ?? 0 }} 张。</p><p v-if="data.unknown_dates.value !== null" class="mt-2 leading-6">采纳日期待补充：{{ data.unknown_dates.value }} 张；在展示月份之前：{{ data.earlier.value ?? '未公开' }} 张。</p></details>
    </template>
  </section>
</template>

<style scoped>
.trend-plot { display:flex; gap:8px; min-height:178px; }
.trend-scale { display:flex; flex-direction:column; justify-content:space-between; padding-bottom:24px; padding-top:18px; min-width:26px; font-size:11px; color:var(--color-text-secondary); }
.trend-bars { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:8px; flex:1; min-width:0; align-items:start; }
.trend-column { min-width:0; }
.trend-hit { display:flex; align-items:center; justify-content:flex-end; flex-direction:column; height:180px; min-height:44px; list-style:none; cursor:pointer; }
.trend-value,.trend-month { font-size:11px; font-variant-numeric:tabular-nums; }
.trend-value { margin-bottom:5px; }
.trend-month { margin-top:8px; white-space:nowrap; }
.trend-bar { position:relative; display:block; width:min(100%,36px); background:var(--color-primary-200); border-radius:4px 4px 0 0; overflow:hidden; }
.trend-mine { display:block; position:absolute; bottom:0; left:0; width:100%; background:var(--color-primary-700); }
.trend-key { position:static; display:inline-block; height:10px; width:10px; border-radius:2px; }
.trend-personal-only { background:var(--color-primary-700); }
:global(html.dark .trend-bar) { background:var(--color-primary-600); }
:global(html.dark .trend-mine) ,:global(html.dark .trend-personal-only) { background:var(--color-primary-300); }
</style>
