<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { medicalReportApi } from '@/api/medical-report'
import type {
  ComparisonChangeType,
  ComparisonIndicator,
  ComparisonResult,
  IndicatorValue,
} from '@/api/medical-report'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const loadError = ref('')
const compareData = ref<ComparisonResult | null>(null)
const activeFilter = ref<'all' | 'abnormal' | 'improving' | 'worsening'>('all')

const reportIds = computed(() => {
  const idsParam = route.query.ids as string | undefined
  if (!idsParam) return []
  return idsParam
    .split(',')
    .map((id) => Number(id))
    .filter((id) => Number.isInteger(id) && id > 0)
})

const reportColumns = computed(() => compareData.value?.report_summaries ?? [])

interface DisplayIndicator extends ComparisonIndicator {
  _expanded?: boolean
  deltaText: string
  trend: 'improving' | 'stable' | 'worsening'
  interpretation: string
}

const displayIndicators = computed<DisplayIndicator[]>(() => {
  const changes = compareData.value?.narrative.key_changes ?? []
  return (compareData.value?.aligned_indicators ?? []).map((indicator) => {
    const measured = indicator.values.filter((value) => value.measured && value.numeric_value != null)
    let deltaText = '—'
    if (measured.length >= 2) {
      const delta = measured[measured.length - 1].numeric_value! - measured[0].numeric_value!
      deltaText = `${delta > 0 ? '+' : ''}${Number(delta.toFixed(2))}`
    }

    return {
      ...indicator,
      deltaText,
      trend: trendOf(indicator.change_type),
      interpretation:
        changes.find((change) => {
          const name = change.indicator_name || ''
          return name === indicator.display_name || name === indicator.canonical_name
        })?.interpretation || defaultInterpretation(indicator),
    }
  })
})

const filteredIndicators = computed(() =>
  displayIndicators.value.filter((indicator) => {
    if (activeFilter.value === 'all') return true
    if (activeFilter.value === 'abnormal') {
      return indicator.values.some((value) => isAbnormal(value))
    }
    return indicator.trend === activeFilter.value
  }),
)

const counts = computed(() => {
  const summary = compareData.value?.change_summary
  return {
    improving: summary?.resolved_abnormal ?? 0,
    worsening: (summary?.newly_abnormal ?? 0) + (summary?.persistent_abnormal ?? 0),
    stable: (summary?.unchanged_stable ?? 0) + (summary?.large_delta ?? 0),
    attentionNeeded: (summary?.newly_abnormal ?? 0) + (summary?.persistent_abnormal ?? 0),
  }
})

const overallTrend = computed<'improving' | 'stable' | 'worsening'>(() => {
  if (counts.value.improving > counts.value.worsening && counts.value.improving > 0) return 'improving'
  if (counts.value.worsening > counts.value.improving && counts.value.worsening > 0) return 'worsening'
  return 'stable'
})

const recommendations = computed(() =>
  compareData.value?.narrative.recommendations?.map((item) => item.content).filter(Boolean) ?? [],
)
const keyChanges = computed(() => compareData.value?.narrative.key_changes ?? [])

async function loadComparison() {
  loadError.value = ''
  compareData.value = null
  if (reportIds.value.length < 2) {
    loading.value = false
    return
  }

  loading.value = true
  try {
    compareData.value = await medicalReportApi.compare(reportIds.value)
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    loadError.value = typeof detail === 'string' ? detail : '无法加载对比数据，请稍后重试'
  } finally {
    loading.value = false
  }
}

function valueFor(indicator: ComparisonIndicator, reportId: number): IndicatorValue | undefined {
  return indicator.values.find((value) => value.report_id === reportId)
}

function displayValue(value: IndicatorValue | undefined): string {
  if (!value?.measured) return '未测量'
  return value.value || '—'
}

function isAbnormal(value: IndicatorValue | undefined): boolean {
  return !!value?.measured && ['high', 'low', 'critical'].includes(value.status)
}

function getStatusColor(value: IndicatorValue | undefined): string {
  if (!value?.measured) return 'text-gray-400 dark:text-gray-500'
  if (value.status === 'normal') return 'text-green-600 dark:text-green-400'
  if (['high', 'low', 'critical'].includes(value.status)) return 'text-red-600 dark:text-red-400'
  return 'text-gray-600 dark:text-gray-300'
}

function trendOf(changeType: ComparisonChangeType): 'improving' | 'stable' | 'worsening' {
  if (changeType === 'resolved_abnormal') return 'improving'
  if (changeType === 'newly_abnormal' || changeType === 'persistent_abnormal') return 'worsening'
  return 'stable'
}

function defaultInterpretation(indicator: ComparisonIndicator): string {
  if (indicator.change_type === 'resolved_abnormal') return '该指标由异常恢复到参考范围。'
  if (indicator.change_type === 'newly_abnormal') return '该指标在最新报告中超出参考范围，建议结合医生意见复查。'
  if (indicator.change_type === 'persistent_abnormal') return '该指标在两次报告中均异常，建议持续关注。'
  if (indicator.change_type === 'large_delta') return '该指标虽未标记异常，但变化幅度较大，可结合报告原文核对。'
  if (indicator.change_type === 'not_measured') return '该指标缺少可比较的测量值。'
  return '该指标保持稳定。'
}

function getTrendIcon(trend: 'improving' | 'stable' | 'worsening'): string {
  if (trend === 'improving') return 'ri-trending-up-line text-green-500'
  if (trend === 'worsening') return 'ri-trending-down-line text-red-500'
  return 'ri-subtract-line text-gray-400'
}

function getTrendLabel(trend: 'improving' | 'stable' | 'worsening'): string {
  if (trend === 'improving') return '改善'
  if (trend === 'worsening') return '需关注'
  return '稳定'
}

function getChangeLabel(change: ComparisonChangeType | string): string {
  const labels: Record<string, string> = {
    newly_abnormal: '新异常',
    resolved_abnormal: '异常恢复',
    persistent_abnormal: '持续异常',
    large_delta: '明显变化',
    unchanged_stable: '稳定',
    not_measured: '未测量',
  }
  return labels[change] || '稳定'
}

function getDeltaColor(trend: 'improving' | 'stable' | 'worsening'): string {
  if (trend === 'improving') return 'text-green-600 dark:text-green-400'
  if (trend === 'worsening') return 'text-red-600 dark:text-red-400'
  return 'text-gray-500 dark:text-gray-400'
}

onMounted(loadComparison)
</script>

<template>
  <div class="flex-1 bg-gray-50 pb-8 dark:bg-gray-950 md:pb-10">
    <header class="sticky top-14 z-30 border-b border-gray-200/80 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div class="page flex min-h-[52px] items-center gap-2">
        <button
          type="button"
          class="flex min-h-[44px] min-w-[44px] items-center justify-center p-2 -ml-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          aria-label="返回报告"
          @click="router.push('/assessment?tab=report')"
        >
          <i class="ri-arrow-left-line text-xl" aria-hidden="true"></i>
        </button>
        <h1 class="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">体检报告对比</h1>
      </div>
    </header>

    <div class="page py-4 space-y-6 md:py-6">
      <div v-if="loading" class="text-center py-20 text-gray-400 dark:text-gray-500">
        <div class="text-4xl mb-4 animate-pulse"><i class="ri-scales-line" aria-hidden="true"></i></div>
        <p>正在生成对比分析...</p>
      </div>

      <div v-else-if="loadError || !compareData" class="text-center py-20 text-gray-400 dark:text-gray-500">
        <div class="text-4xl mb-4"><i class="ri-error-warning-line" aria-hidden="true"></i></div>
        <p class="text-gray-600 dark:text-gray-300">{{ loadError || '请至少选择两份已完成 AI 解读的报告' }}</p>
        <button type="button" class="mt-4 btn-primary px-6" @click="router.push('/assessment?tab=report')">
          返回体检报告
        </button>
      </div>

      <template v-else>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="card p-5 flex items-center gap-4">
            <div
              class="w-12 h-12 rounded-full flex items-center justify-center shrink-0"
              :class="{
                'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400': overallTrend === 'improving',
                'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400': overallTrend === 'worsening',
                'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300': overallTrend === 'stable',
              }"
            >
              <i class="text-2xl" :class="getTrendIcon(overallTrend).split(' ')[0]" aria-hidden="true"></i>
            </div>
            <div>
              <p class="text-sm text-gray-500 dark:text-gray-400 mb-1">总体趋势</p>
              <p class="text-lg font-bold text-gray-900 dark:text-gray-100">{{ getTrendLabel(overallTrend) }}</p>
            </div>
          </div>

          <div class="card p-5 flex flex-col justify-center">
            <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">指标变化统计</p>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm font-medium">
              <span class="text-green-600 dark:text-green-400">{{ counts.improving }}项改善</span>
              <span class="text-gray-300 dark:text-gray-600">|</span>
              <span class="text-red-600 dark:text-red-400">{{ counts.worsening }}项需关注</span>
              <span class="text-gray-300 dark:text-gray-600">|</span>
              <span class="text-gray-600 dark:text-gray-300">{{ counts.stable }}项稳定</span>
            </div>
          </div>

          <div class="card p-5 flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400 flex items-center justify-center shrink-0">
              <i class="ri-error-warning-fill text-2xl" aria-hidden="true"></i>
            </div>
            <div>
              <p class="text-sm text-gray-500 dark:text-gray-400 mb-1">重点提醒</p>
              <p class="text-lg font-bold text-gray-900 dark:text-gray-100">
                <span v-if="counts.attentionNeeded > 0" class="text-yellow-600 dark:text-yellow-400">{{ counts.attentionNeeded }}项需关注</span>
                <span v-else class="text-green-600 dark:text-green-400">无持续异常</span>
              </p>
            </div>
          </div>
        </div>

        <div class="card overflow-hidden">
          <div class="border-b border-gray-100 dark:border-gray-800 px-4 py-3 overflow-x-auto no-scrollbar flex gap-2">
            <button
              v-for="filter in [
                { key: 'all', label: '全部指标' },
                { key: 'abnormal', label: '异常项' },
                { key: 'improving', label: '改善项' },
                { key: 'worsening', label: '需关注' },
              ]"
              :key="filter.key"
              type="button"
              class="control-slim"
              :class="activeFilter === filter.key
                ? 'control-slim-active'
                : ''"
              @click="activeFilter = filter.key as typeof activeFilter"
            >
              {{ filter.label }}
            </button>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse min-w-[680px]">
              <thead>
                <tr class="bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <th class="p-4 font-medium">指标名称</th>
                  <th v-for="report in reportColumns" :key="report.report_id" class="p-4 font-medium">
                    <span class="block text-gray-700 dark:text-gray-200">{{ report.title }}</span>
                    <span class="block normal-case text-gray-400 dark:text-gray-500 font-normal">{{ report.date }}</span>
                  </th>
                  <th class="p-4 font-medium">变化</th>
                  <th class="p-4 font-medium">趋势</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
                <template v-for="(indicator, idx) in filteredIndicators" :key="indicator.canonical_name || `${indicator.display_name}-${idx}`">
                  <tr
                    class="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 cursor-pointer transition-colors"
                    tabindex="0"
                    @click="indicator._expanded = !indicator._expanded"
                    @keydown.enter="indicator._expanded = !indicator._expanded"
                    @keydown.space.prevent="indicator._expanded = !indicator._expanded"
                  >
                    <td class="p-4">
                      <div class="flex items-center gap-2">
                        <i
                          class="ri-arrow-right-s-line text-gray-400 transition-transform duration-200"
                          :class="{ 'rotate-90': indicator._expanded }"
                          aria-hidden="true"
                        ></i>
                        <span class="font-medium text-gray-800 dark:text-gray-100">{{ indicator.display_name }}</span>
                        <span class="hidden sm:inline text-xs text-gray-400 dark:text-gray-500">{{ getChangeLabel(indicator.change_type) }}</span>
                      </div>
                    </td>
                    <td
                      v-for="report in reportColumns"
                      :key="report.report_id"
                      class="p-4 text-sm"
                      :class="getStatusColor(valueFor(indicator, report.report_id))"
                    >
                      {{ displayValue(valueFor(indicator, report.report_id)) }}
                    </td>
                    <td class="p-4">
                      <span class="text-sm font-medium" :class="getDeltaColor(indicator.trend)">{{ indicator.deltaText }}</span>
                    </td>
                    <td class="p-4">
                      <div class="flex items-center gap-1.5">
                        <i :class="getTrendIcon(indicator.trend)" aria-hidden="true"></i>
                        <span class="text-sm text-gray-700 dark:text-gray-300">{{ getTrendLabel(indicator.trend) }}</span>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="indicator._expanded" class="bg-gray-50/50 dark:bg-gray-800/40">
                    <td :colspan="reportColumns.length + 3" class="p-4 pt-0">
                      <div class="ml-6 p-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-100 dark:border-gray-700 shadow-sm flex items-start gap-3">
                        <i class="ri-robot-line text-primary-500 text-lg mt-0.5" aria-hidden="true"></i>
                        <div>
                          <p class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">AI 趋势解读</p>
                          <p class="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{{ indicator.interpretation }}</p>
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
                <tr v-if="filteredIndicators.length === 0">
                  <td :colspan="reportColumns.length + 3" class="p-8 text-center text-gray-500 dark:text-gray-400 text-sm">
                    没有找到符合条件的指标
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card p-5 md:p-6">
          <div class="flex items-center gap-2 mb-4">
            <i class="ri-file-list-3-line text-xl text-gray-700 dark:text-gray-300" aria-hidden="true"></i>
            <h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">综合评估</h2>
          </div>
          <p class="text-gray-700 dark:text-gray-300 leading-relaxed mb-6 text-sm md:text-base">
            {{ compareData.narrative.summary }}
          </p>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div v-if="keyChanges.length" class="space-y-6">
              <div>
                <h3 class="text-sm font-semibold text-primary-700 dark:text-primary-300 mb-3 flex items-center gap-1.5">
                  <i class="ri-focus-2-line" aria-hidden="true"></i> 重点变化
                </h3>
                <ul class="space-y-2">
                  <li v-for="(item, idx) in keyChanges" :key="idx" class="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
                    <i class="ri-checkbox-circle-fill text-primary-500 mt-0.5 shrink-0" aria-hidden="true"></i>
                    <span>{{ item.indicator_name }}：{{ item.interpretation }}</span>
                  </li>
                </ul>
              </div>
            </div>

            <div v-if="recommendations.length" class="bg-primary-50 dark:bg-primary-900 rounded-xl p-5 border border-primary-100 dark:border-primary-900">
              <h3 class="text-sm font-semibold text-primary-700 dark:text-primary-300 mb-3 flex items-center gap-1.5">
                <i class="ri-lightbulb-line" aria-hidden="true"></i> 下一步建议
              </h3>
              <ul class="space-y-3">
                <li v-for="(item, idx) in recommendations" :key="idx" class="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <span class="w-5 h-5 rounded-full bg-primary-100 dark:bg-primary-900 text-primary-600 dark:text-primary-300 flex items-center justify-center text-xs font-medium shrink-0 mt-0.5">{{ idx + 1 }}</span>
                  <span class="leading-relaxed">{{ item }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
