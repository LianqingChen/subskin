<template>
  <div class="flex flex-col gap-5 p-4 md:p-6 max-w-6xl mx-auto w-full">
    <!-- North Star: 累计注册用户数（去重） -->
    <div class="card p-5 relative overflow-hidden">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-xs font-semibold text-primary-700 dark:text-primary-300 bg-primary-50 dark:bg-primary-900/30 px-2.5 py-0.5 rounded-full"><i class="ri-star-line mr-1"></i>北极星指标</span>
        <span v-if="overview.new_users_today > 0" class="text-xs text-primary-600 dark:text-primary-400">今日 +{{ overview.new_users_today }}</span>
      </div>
      <div class="text-4xl font-extrabold text-gray-900 dark:text-white tracking-tight">{{ overview.total_users }}</div>
      <div class="text-sm text-gray-500  mt-0.5">注册用户数</div>
      <div ref="northStarChartRef" class="h-28 mt-2"></div>
    </div>

    <!-- Overview Cards (3 compact) -->
    <div class="grid grid-cols-3 gap-3">
      <div class="card p-4 border-l-4 border-l-primary-500">
        <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ overview.today_uv }}</div>
        <div class="text-xs text-gray-500  mt-0.5">今日UV</div>
      </div>
      <div class="card p-4 border-l-4 border-l-primary-400">
        <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ overview.today_pv }}</div>
        <div class="text-xs text-gray-500  mt-0.5">今日PV</div>
      </div>
      <div class="card p-4 border-l-4 border-l-amber-500">
        <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ overview.today_active_users }}</div>
        <div class="text-xs text-gray-500  mt-0.5">今日活跃</div>
      </div>
    </div>

    <!-- UV/PV Trend -->
    <div class="card p-5">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-gray-700">UV/PV趋势</h3>
        <div class="flex bg-gray-100 rounded-lg p-0.5">
          <button @click="trendPeriod = '7d'" :class="toggleClass(trendPeriod === '7d')">7天</button>
          <button @click="trendPeriod = '30d'" :class="toggleClass(trendPeriod === '30d')">30天</button>
        </div>
      </div>
      <div ref="trendChartRef" class="w-full h-56 md:h-72"></div>
    </div>

    <!-- Funnel -->
    <div class="card p-5">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-gray-700">转化漏斗</h3>
        <div class="flex bg-gray-100 rounded-lg p-0.5">
          <button @click="funnelPeriod = '7d'" :class="toggleClass(funnelPeriod === '7d')">7天</button>
          <button @click="funnelPeriod = '30d'" :class="toggleClass(funnelPeriod === '30d')">30天</button>
        </div>
      </div>
      <div ref="funnelChartRef" class="w-full h-48"></div>
    </div>

    <!-- Feature Usage -->
    <div class="card p-5">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-gray-700">功能使用 (UV)</h3>
        <div class="flex bg-gray-100 rounded-lg p-0.5">
          <button @click="featurePeriod = '7d'" :class="toggleClass(featurePeriod === '7d')">7天</button>
          <button @click="featurePeriod = '30d'" :class="toggleClass(featurePeriod === '30d')">30天</button>
        </div>
      </div>
      <div ref="featureChartRef" class="w-full h-48"></div>
    </div>

    <!-- 用户动线Top10 -->
    <div class="card p-5">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-gray-700">用户动线Top10</h3>
        <div class="flex items-center gap-3">
          <span class="text-xs text-gray-400">共 {{ journeyData?.total_sessions ?? 0 }} 个会话</span>
          <div class="flex bg-gray-100 rounded-lg p-0.5">
            <button @click="journeyPeriod = '7d'" :class="toggleClass(journeyPeriod === '7d')">7天</button>
            <button @click="journeyPeriod = '30d'" :class="toggleClass(journeyPeriod === '30d')">30天</button>
          </div>
        </div>
      </div>
      <div v-if="journeyData?.top_paths?.length" class="space-y-1">
        <div v-for="(p, idx) in journeyData.top_paths.slice(0, 10)" :key="p.path"
          class="flex items-center gap-2 text-xs py-1.5 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
          <span class="w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-bold shrink-0"
            :class="idx < 3 ? 'bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300' : 'bg-gray-100 text-gray-500 '">
            {{ idx + 1 }}
          </span>
          <span class="truncate flex-1 text-gray-600 ">{{ p.path }}</span>
          <span class="font-medium text-gray-900 shrink-0">{{ p.count }}次</span>
        </div>
      </div>
      <div v-else class="text-xs text-gray-400 text-center py-6">暂无动线数据</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { analyticsApi } from '@/api/analytics'
import type { OverviewData, FunnelStep, FeatureUsageData, RegistrationTrendItem, UserJourneyData } from '@/api/analytics'

const loading = ref(false)
const trendPeriod = ref<'7d' | '30d'>('7d')
const funnelPeriod = ref<'7d' | '30d'>('7d')
const featurePeriod = ref<'7d' | '30d'>('7d')
const journeyPeriod = ref<'7d' | '30d'>('7d')

const overview = ref<OverviewData>({ total_users: 0, today_uv: 0, today_pv: 0, new_users_today: 0, today_active_users: 0 })
const trendItems = ref<Array<{ date: string; uv: number; pv: number; new_users: number }>>([])
const funnelSteps = ref<FunnelStep[]>([])
const features = ref<FeatureUsageData[]>([])
const registrationTrend = ref<RegistrationTrendItem[]>([])
const journeyData = ref<UserJourneyData | null>(null)

const trendChartRef = ref<HTMLElement | null>(null)
const featureChartRef = ref<HTMLElement | null>(null)
const funnelChartRef = ref<HTMLElement | null>(null)
const northStarChartRef = ref<HTMLElement | null>(null)

let trendChart: echarts.ECharts | null = null
let featureChart: echarts.ECharts | null = null
let funnelChart: echarts.ECharts | null = null
let northStarChart: echarts.ECharts | null = null

const CHART_COLORS = {
  primary: '#26A69A',
  primaryLight: '#5EC4BA',
  secondary: '#A5D6A7',
  secondaryLight: '#C8E6C9',
  warning: '#FFB74D',
  danger: '#ef4444',
}

const isDark = () => document.documentElement.classList.contains('dark')
const getTextColor = () => isDark() ? '#9ca3af' : '#6b7280'
const getSplitLineColor = () => isDark() ? '#374151' : '#e5e7eb'
const tooltipTheme = () => ({
  backgroundColor: isDark() ? '#1f2937' : '#ffffff',
  borderColor: isDark() ? '#374151' : '#e5e7eb',
  textStyle: { color: isDark() ? '#f3f4f6' : '#111827' }
})
const toggleClass = (active: boolean) => [
  'px-2.5 py-1 text-xs rounded-md transition-colors',
  active ? 'bg-white  text-primary-600 dark:text-primary-400 shadow-sm' : 'text-gray-500 '
]

const initCharts = () => {
  if (trendChartRef.value) trendChart = echarts.init(trendChartRef.value)
  if (featureChartRef.value) featureChart = echarts.init(featureChartRef.value)
  if (funnelChartRef.value) funnelChart = echarts.init(funnelChartRef.value)
  if (northStarChartRef.value) northStarChart = echarts.init(northStarChartRef.value)
  updateAllCharts()
}

const updateNorthStarChart = () => {
  if (!northStarChart) return
  const data = registrationTrend.value
  if (!data.length) return

  northStarChart.setOption({
    grid: { top: 10, right: 10, bottom: 20, left: 35, containLabel: false },
    xAxis: { type: 'category', show: false, data: data.map(d => d.date) },
    yAxis: [
      { type: 'value', show: false },
      { type: 'value', show: false },
    ],
    tooltip: {
      trigger: 'axis',
      ...tooltipTheme(),
      formatter: (params: any) => {
        const cum = params.find((p: any) => p.seriesName === '累计用户')
        const daily = params.find((p: any) => p.seriesName === '当日新注册')
        let s = params[0]?.name || ''
        if (cum) s += `<br/>${cum.marker} 累计: ${cum.value}`
        if (daily) s += `<br/>${daily.marker} 当日新注册: ${daily.value}`
        return s
      }
    },
    series: [
      {
        name: '累计用户',
        type: 'line',
        yAxisIndex: 0,
        data: data.map(d => d.cumulative_users),
        smooth: true,
        symbol: 'none',
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(16, 185, 129, 0.35)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0.02)' }
          ])
        },
        lineStyle: { color: '#10b981', width: 2 },
      },
      {
        name: '当日新注册',
        type: 'bar',
        yAxisIndex: 1,
        data: data.map(d => d.new_users),
        barMaxWidth: 12,
        itemStyle: { color: 'rgba(59, 130, 246, 0.6)', borderRadius: [2, 2, 0, 0] },
      }
    ]
  })
}

const updateTrendChart = () => {
  if (!trendChart) return
  const textColor = getTextColor()
  const splitLineColor = getSplitLineColor()
  const items = trendItems.value
  const dates = items.map(i => i.date.slice(5))

  trendChart.setOption({
    tooltip: { trigger: 'axis', ...tooltipTheme() },
    legend: { data: ['UV', 'PV'], textStyle: { color: textColor }, bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: dates, axisLabel: { color: textColor }, axisLine: { lineStyle: { color: splitLineColor } } },
    yAxis: [
      {
        type: 'value', name: 'UV', nameTextStyle: { color: CHART_COLORS.primary, fontSize: 11 },
        axisLabel: { color: CHART_COLORS.primary },
        splitLine: { lineStyle: { color: splitLineColor, type: 'dashed' } },
      },
      {
        type: 'value', name: 'PV', nameTextStyle: { color: CHART_COLORS.secondary, fontSize: 11 },
        axisLabel: { color: CHART_COLORS.secondary },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'UV', type: 'line', yAxisIndex: 0, smooth: true, data: items.map(i => i.uv),
        itemStyle: { color: CHART_COLORS.primary },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: CHART_COLORS.primaryLight }, { offset: 1, color: 'rgba(59,130,246,0.05)' }]) }
      },
      {
        name: 'PV', type: 'line', yAxisIndex: 1, smooth: true, data: items.map(i => i.pv),
        itemStyle: { color: CHART_COLORS.secondary },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: CHART_COLORS.secondaryLight }, { offset: 1, color: 'rgba(16,185,129,0.05)' }]) }
      }
    ]
  })
}

const updateFeatureChart = () => {
  if (!featureChart) return
  const textColor = getTextColor()
  const splitLineColor = getSplitLineColor()
  const sorted = [...features.value].sort((a, b) => a.uv - b.uv)

  featureChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipTheme() },
    grid: { left: '3%', right: '12%', bottom: '3%', top: '5%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: textColor }, splitLine: { lineStyle: { color: splitLineColor, type: 'dashed' } } },
    yAxis: { type: 'category', data: sorted.map(f => f.name), axisLabel: { color: textColor, fontSize: 11 }, axisLine: { lineStyle: { color: splitLineColor } } },
    series: [{
      name: 'UV', type: 'bar', data: sorted.map(f => f.uv),
      itemStyle: { color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [{ offset: 0, color: CHART_COLORS.primary }, { offset: 1, color: CHART_COLORS.primaryLight }]), borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: textColor, fontSize: 11 }
    }]
  })
}

const updateFunnelChart = () => {
  if (!funnelChart) return
  const steps = funnelSteps.value

  funnelChart.setOption({
    tooltip: { trigger: 'item', formatter: (p: any) => { const step = steps[p.dataIndex]; const pct = step?.rate_from_prev != null ? ` (${(step.rate_from_prev * 100).toFixed(1)}%)` : ''; return `${p.name}: ${p.value}${pct}`; }, ...tooltipTheme() },
    series: [{
      type: 'funnel', left: '10%', top: 10, bottom: 10, width: '80%',
      min: 0, max: Math.max(...steps.map(s => s.count), 1), minSize: '0%', maxSize: '100%',
      sort: 'desc', gap: 2,
      label: { show: true, position: 'inside', formatter: '{b}: {c}', color: '#fff', fontSize: 11 },
      itemStyle: { borderColor: isDark() ? '#1f2937' : '#fff', borderWidth: 1 },
      data: steps.map(s => ({ name: s.name, value: s.count })),
      color: [CHART_COLORS.primary, CHART_COLORS.primaryLight, CHART_COLORS.secondary, CHART_COLORS.secondaryLight]
    }]
  })
}

const updateAllCharts = () => {
  updateNorthStarChart()
  updateTrendChart()
  updateFeatureChart()
  updateFunnelChart()
}

const handleResize = () => {
  trendChart?.resize()
  featureChart?.resize()
  funnelChart?.resize()
  northStarChart?.resize()
}

let observer: MutationObserver | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  initCharts()
  window.addEventListener('resize', handleResize)
  observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.attributeName === 'class') updateAllCharts()
    })
  })
  observer.observe(document.documentElement, { attributes: true })
  fetchDashboard()
  refreshTimer = setInterval(fetchDashboard, 3600000)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  observer?.disconnect()
  if (refreshTimer) clearInterval(refreshTimer)
  trendChart?.dispose()
  featureChart?.dispose()
  funnelChart?.dispose()
  northStarChart?.dispose()
})

watch(trendPeriod, () => fetchDashboard())

watch(funnelPeriod, async () => {
  const days = funnelPeriod.value === '7d' ? 7 : 30
  const data = await analyticsApi.funnel(days).catch(() => [])
  if (data) funnelSteps.value = data
  updateFunnelChart()
})

watch(featurePeriod, async () => {
  const days = featurePeriod.value === '7d' ? 7 : 30
  const data = await analyticsApi.featureUsage(days).catch(() => [])
  if (data) features.value = data
  updateFeatureChart()
})

watch(journeyPeriod, async () => {
  const days = journeyPeriod.value === '7d' ? 7 : 30
  const data = await analyticsApi.userJourneys(days, 50).catch(() => null)
  if (data) journeyData.value = data
})

const fetchDashboard = async () => {
  loading.value = true
  try {
    const trendDays = trendPeriod.value === '7d' ? 7 : 30
    const funnelDays = funnelPeriod.value === '7d' ? 7 : 30
    const featureDays = featurePeriod.value === '7d' ? 7 : 30
    const journeyDays = journeyPeriod.value === '7d' ? 7 : 30
    const [overviewData, trendData, funnelData, featureData, regTrendData, journeyResult] = await Promise.all([
      analyticsApi.overview().catch(() => null),
      analyticsApi.trend(trendDays).catch(() => null),
      analyticsApi.funnel(funnelDays).catch(() => []),
      analyticsApi.featureUsage(featureDays).catch(() => []),
      analyticsApi.registrationTrend(14).catch(() => []),
      analyticsApi.userJourneys(journeyDays, 50).catch(() => null),
    ])

    if (overviewData) overview.value = overviewData
    if (trendData?.items) trendItems.value = trendData.items
    if (funnelData) funnelSteps.value = funnelData
    if (featureData) features.value = featureData
    if (regTrendData) registrationTrend.value = regTrendData
    if (journeyResult) journeyData.value = journeyResult

    updateAllCharts()
  } finally {
    loading.value = false
  }
}

defineExpose({ refresh: fetchDashboard })
</script>
