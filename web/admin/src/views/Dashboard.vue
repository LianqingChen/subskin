<template>
  <div>
    <!-- 顶部统计卡片 -->
    <n-grid :cols="isMobile ? 2 : 4" :x-gap="isMobile ? 8 : 16" :y-gap="isMobile ? 8 : 16"
            responsive="screen">
      <n-gi :span="isMobile ? 2 : 1">
        <n-card size="small" class="stat-card">
          <n-statistic label="今日 DAU" :value="overview.today_active_users ?? 0">
            <template #prefix>
              <i class="ri-user-star-line stat-icon" style="color: #6366f1;" />
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi :span="isMobile ? 2 : 1">
        <n-card size="small" class="stat-card">
          <n-statistic label="总用户数" :value="overview.total_users ?? 0">
            <template #prefix>
              <i class="ri-team-line stat-icon" style="color: #10b981;" />
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi :span="isMobile ? 2 : 1">
        <n-card size="small" class="stat-card">
          <n-statistic label="总帖子数" :value="overview.total_posts ?? 0">
            <template #prefix>
              <i class="ri-article-line stat-icon" style="color: #f59e0b;" />
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi :span="isMobile ? 2 : 1">
        <n-card size="small" class="stat-card">
          <n-statistic label="VASI 评估次数" :value="overview.vasi_count ?? 0">
            <template #prefix>
              <i class="ri-health-book-line stat-icon" style="color: #ef4444;" />
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- 趋势图表 -->
    <n-card title="趋势图表" style="margin-top: 24px" class="chart-card">
      <template #header-extra>
        <n-radio-group v-model:value="trendDays" size="small" @update:value="fetchTrend">
          <n-radio-button :value="7">7 天</n-radio-button>
          <n-radio-button :value="14">14 天</n-radio-button>
          <n-radio-button :value="30">30 天</n-radio-button>
        </n-radio-group>
      </template>
      <div ref="trendChartRef" :style="{ height: isMobile ? '260px' : '400px' }" />
    </n-card>

    <!-- 页面访问排行 & 功能使用统计 -->
    <n-grid :cols="isMobile ? 1 : 2" :x-gap="16" :y-gap="16" style="margin-top: 24px" responsive="screen">
      <n-gi>
        <n-card title="页面访问排行" class="table-card">
          <n-data-table
            :columns="pageViewColumns"
            :data="pageViews"
            :bordered="false"
            :single-line="false"
            size="small"
            :loading="pageViewsLoading"
            max-height="400px"
          />
          <n-empty v-if="!pageViewsLoading && pageViews.length === 0" description="暂无数据" size="small" style="margin-top: 16px;" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card title="功能使用统计" class="table-card">
          <n-data-table
            :columns="featureUsageColumns"
            :data="featureUsage"
            :bordered="false"
            :single-line="false"
            size="small"
            :loading="featureUsageLoading"
            max-height="400px"
          />
          <n-empty v-if="!featureUsageLoading && featureUsage.length === 0" description="暂无数据" size="small" style="margin-top: 16px;" />
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import request from '@/api/request'
import {
  NGrid,
  NGi,
  NCard,
  NStatistic,
  NRadioGroup,
  NRadioButton,
  NDataTable,
  NEmpty,
  useMessage,
} from 'naive-ui'

const message = useMessage()

const isMobile = ref(false)
function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

// ── Types ──
interface OverviewData {
  total_users?: number
  today_uv?: number
  today_pv?: number
  new_users_today?: number
  today_active_users?: number
  total_posts?: number
  vasi_count?: number
}

interface TrendItem {
  date: string
  uv: number
  pv: number
  new_users: number
}

interface TrendData {
  days: number
  items: TrendItem[]
}

interface PageViewItem {
  page: string
  path: string
  count: number
  uv: number
}

interface FeatureUsageItem {
  name: string
  uv: number
  pv: number
}

// ── State ──
const overview = ref<OverviewData>({})
const trendDays = ref<number>(30)
const trendItems = ref<TrendItem[]>([])
const pageViews = ref<PageViewItem[]>([])
const pageViewsLoading = ref(false)
const featureUsage = ref<FeatureUsageItem[]>([])
const featureUsageLoading = ref(false)
const loading = ref(false)

const trendChartRef = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null

// ── Table columns ──
const pageViewColumns = computed(() => {
  const cols: any[] = [
    { title: '页面', key: 'page', ellipsis: { tooltip: true } },
  ]
  if (!isMobile.value) {
    cols.push({ title: '路径', key: 'path', ellipsis: { tooltip: true } })
  }
  cols.push(
    { title: '访问量', key: 'count', width: 80, sorter: (a: PageViewItem, b: PageViewItem) => a.count - b.count },
    { title: 'UV', key: 'uv', width: 70, sorter: (a: PageViewItem, b: PageViewItem) => a.uv - b.uv },
  )
  return cols
})

const featureUsageColumns = computed(() => [
  { title: '功能', key: 'name', ellipsis: { tooltip: true } },
  { title: 'UV', key: 'uv', width: 80, sorter: (a: FeatureUsageItem, b: FeatureUsageItem) => a.uv - b.uv },
  { title: 'PV', key: 'pv', width: 80, sorter: (a: FeatureUsageItem, b: FeatureUsageItem) => a.pv - b.pv },
])

// ── Charts ──
const initTrendChart = () => {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value, 'dark', {
    renderer: 'canvas',
  })
  updateTrendChart()
}

const updateTrendChart = () => {
  if (!trendChart) return
  const items = trendItems.value
  const dates = items.map(i => i.date.slice(5))
  const mobile = isMobile.value

  trendChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(148, 163, 184, 0.2)',
      textStyle: { color: '#e2e8f0', fontSize: mobile ? 11 : 12 },
    },
    legend: {
      data: ['UV', 'PV', '新增用户'],
      textStyle: { color: '#94a3b8', fontSize: mobile ? 10 : 12 },
      bottom: 0,
      itemWidth: mobile ? 12 : 25,
      itemHeight: mobile ? 8 : 14,
    },
    grid: {
      left: mobile ? '1%' : '3%',
      right: mobile ? '2%' : '4%',
      bottom: mobile ? '14%' : '10%',
      top: mobile ? '8%' : '5%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: {
        color: '#94a3b8',
        fontSize: mobile ? 9 : 12,
        interval: mobile ? Math.ceil(dates.length / 5) : 'auto',
        rotate: mobile ? 30 : 0,
      },
      axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } },
    },
    yAxis: [
      {
        type: 'value',
        name: mobile ? '' : 'UV / 新增',
        nameTextStyle: { color: '#6366f1', fontSize: mobile ? 9 : 11 },
        axisLabel: { color: '#94a3b8', fontSize: mobile ? 9 : 12 },
        splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.1)', type: 'dashed' } },
      },
      {
        type: 'value',
        name: mobile ? '' : 'PV',
        nameTextStyle: { color: '#10b981', fontSize: mobile ? 9 : 11 },
        axisLabel: { color: '#94a3b8', fontSize: mobile ? 9 : 12 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'UV',
        type: 'line',
        yAxisIndex: 0,
        smooth: true,
        data: items.map(i => i.uv),
        itemStyle: { color: '#6366f1' },
        showSymbol: !mobile,
        areaStyle: mobile ? undefined : {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(99, 102, 241, 0.4)' },
            { offset: 1, color: 'rgba(99, 102, 241, 0.02)' },
          ]),
        },
      },
      {
        name: 'PV',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: items.map(i => i.pv),
        itemStyle: { color: '#10b981' },
        showSymbol: !mobile,
        areaStyle: mobile ? undefined : {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(16, 185, 129, 0.4)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0.02)' },
          ]),
        },
      },
      {
        name: '新增用户',
        type: 'line',
        yAxisIndex: 0,
        smooth: true,
        data: items.map(i => i.new_users),
        itemStyle: { color: '#f59e0b' },
        lineStyle: { width: 2, type: 'dashed' },
        showSymbol: false,
      },
    ],
  }, true)
}

const handleResize = () => {
  checkMobile()
  trendChart?.resize()
}

let chartResizeObserver: ResizeObserver | null = null

// ── Data fetching ──
const fetchOverview = async () => {
  try {
    const { data } = await request.get<OverviewData>('/analytics/overview')
    overview.value = data
  } catch (err) {
    message.error('获取总览数据失败')
  }
}

const fetchTrend = async () => {
  try {
    const { data } = await request.get<TrendData>('/analytics/trend', {
      params: { days: trendDays.value },
    })
    trendItems.value = data.items || []
    await nextTick()
    updateTrendChart()
  } catch (err) {
    message.error('获取趋势数据失败')
  }
}

const fetchPageViews = async () => {
  pageViewsLoading.value = true
  try {
    const { data } = await request.get<PageViewItem[]>('/analytics/page-views', {
      params: { days: 7 },
    })
    pageViews.value = Array.isArray(data) ? data : []
  } catch (err) {
    // Backend method may not exist; fail silently
    pageViews.value = []
  } finally {
    pageViewsLoading.value = false
  }
}

const fetchFeatureUsage = async () => {
  featureUsageLoading.value = true
  try {
    const { data } = await request.get<FeatureUsageItem[]>('/analytics/feature-usage', {
      params: { days: 7 },
    })
    featureUsage.value = Array.isArray(data) ? data : []
  } catch (err) {
    message.error('获取功能使用统计失败')
    featureUsage.value = []
  } finally {
    featureUsageLoading.value = false
  }
}

const fetchAll = async () => {
  loading.value = true
  await Promise.all([
    fetchOverview(),
    fetchTrend(),
    fetchPageViews(),
    fetchFeatureUsage(),
  ])
  loading.value = false
}

// ── Lifecycle ──
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', handleResize)
  initTrendChart()
  // Use ResizeObserver for more reliable chart resizing
  if (trendChartRef.value) {
    chartResizeObserver = new ResizeObserver(() => {
      trendChart?.resize()
    })
    chartResizeObserver.observe(trendChartRef.value)
  }
  fetchAll()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartResizeObserver?.disconnect()
  chartResizeObserver = null
  trendChart?.dispose()
})
</script>

<style scoped>
.stat-card {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
}
.stat-card :deep(.n-card__content) {
  padding: 16px;
}
.stat-icon {
  font-size: 20px;
  margin-right: 8px;
  vertical-align: middle;
}
.chart-card {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
}
.table-card {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

@media (max-width: 768px) {
  .stat-card :deep(.n-card__content) {
    padding: 10px;
  }
  .stat-card :deep(.n-statistic .n-statistic-value__content) {
    font-size: 20px;
  }
  .stat-icon {
    font-size: 16px;
  }
  .chart-card :deep(.n-card-header) {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>
