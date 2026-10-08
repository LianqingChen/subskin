<script setup lang="ts">
/**
 * SkinReportViewPage — 白斑变化报告（网页版）
 *
 * 对比报告（2026-08 重构）：分层封面 + 前后对比（日期可切换，置顶）+ VASI 趋势 + 客观变化摘要。
 * 不再生成时间轴堆叠图/变化最明显/AI 长文与建议——只呈现客观数据与图片。
 * 周报/月报（report_type=weekly/monthly）：封面拼图 + 部位总览 + 分部位前后对比卡片 + 多序列趋势。
 * 操作栏支持：导出PDF / 生成海报 / 发布到分享 / 复制链接。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])
import { getSkinReport, deleteSkinReport, shareReportToCommunity, getPairCompare } from '@/api/skin_report'
import type {
  SkinReport,
  SiteSection,
  TrendChartWithSeries,
  TimelineFrame,
  PairAlign,
  PairMetrics,
} from '@/api/skin_report'
import SkinReportPoster from '@/components/diary/SkinReportPoster.vue'
import HealthReportSections from '@/components/report/HealthReportSections.vue'
import ComparisonViews from '@/components/report/ComparisonViews.vue'
import PairDateSwitcher from '@/components/report/PairDateSwitcher.vue'
import { exportElementToPdf } from '@/utils/report-pdf'
import { toProtectedFileUrl } from '@/utils/file-url'
import { useToast } from '@/composables/useToast'
import { copyTextToClipboard } from '@/utils/clipboard'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const report = ref<SkinReport | null>(null)
const loading = ref(true)
const error = ref('')
const reportRef = ref<HTMLElement>()
const chartRef = ref<HTMLElement>()
const showPoster = ref(false)
const exporting = ref(false)
const sharing = ref(false)
let chartInstance: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setTimeout> | null = null

const isPeriodic = computed(
  () => report.value?.report_type === 'weekly' || report.value?.report_type === 'monthly',
)
const isSynthesis = computed(() => report.value?.report_type === 'synthesis')
const isComparison = computed(() => !isPeriodic.value && !isSynthesis.value)
const periodicSites = computed<SiteSection[]>(() => report.value?.metrics?.sites ?? [])
const narrativeSections = computed(() => report.value?.metrics?.narrative_sections ?? [])
const coverUrl = computed(() =>
  report.value?.cover_composite_url ? protectedUrl(report.value.cover_composite_url) : '',
)

// ── 前后对比：日期切换状态（默认最早 vs 最晚） ──
const frames = computed<TimelineFrame[]>(() => report.value?.metrics?.timeline_frames ?? [])
const beforeIdx = ref(0)
const afterIdx = ref(0)
const activeAlign = ref<PairAlign | null>(null)
const activeMetrics = ref<PairMetrics | null>(null)
const activeBeforeUrl = ref('')
const activeAfterUrl = ref('')
const activeBeforeDate = ref('')
const activeAfterDate = ref('')
const pairLoading = ref(false)
let suppressPairWatch = true
let pairSwitchTimer: ReturnType<typeof setTimeout> | null = null

function setDefaultPair() {
  const m = report.value?.metrics
  if (!m || !isComparison.value) return
  suppressPairWatch = true
  beforeIdx.value = 0
  afterIdx.value = Math.max(frames.value.length - 1, 1)
  activeAlign.value = m.pair_align ?? null
  activeMetrics.value = m.pair_metrics ?? null
  activeBeforeUrl.value = protectedUrl(m.first?.image_url)
  activeAfterUrl.value = protectedUrl(m.last?.image_url)
  activeBeforeDate.value = m.first?.date ?? ''
  activeAfterDate.value = m.last?.date ?? ''
  nextTick(() => {
    suppressPairWatch = false
  })
}

async function switchPair() {
  if (!report.value || !isComparison.value) return
  const fs = frames.value
  const a = beforeIdx.value
  const b = afterIdx.value
  if (!fs.length || a === b || a >= fs.length || b >= fs.length) return
  pairLoading.value = true
  try {
    const { data } = await getPairCompare(report.value.id, a, b)
    activeMetrics.value = data.pair_metrics
    activeAlign.value = data.pair_align
    const first = data.first ?? fs[a]
    const last = data.last ?? fs[b]
    activeBeforeUrl.value = protectedUrl(first?.image_url)
    activeAfterUrl.value = protectedUrl(last?.image_url)
    activeBeforeDate.value = first?.date ?? ''
    activeAfterDate.value = last?.date ?? ''
  } catch {
    toast.show('这组照片对比计算失败，请稍后重试', 'error')
  } finally {
    pairLoading.value = false
  }
}

watch([beforeIdx, afterIdx], () => {
  if (suppressPairWatch || !isComparison.value) return
  if (pairSwitchTimer) clearTimeout(pairSwitchTimer)
  pairSwitchTimer = setTimeout(() => switchPair(), 60)
})

/** 封面客观指标 chips（对比报告） */
function coverChips() {
  const m = report.value?.metrics
  if (!m || !isComparison.value) return []
  const good = 'rc-chip--good'
  const bad = 'rc-chip--bad'
  const flat = 'rc-chip--flat'
  const chips: { icon: string; text: string; cls: string }[] = []
  const trend = trendStyle(m.trend)
  chips.push({ icon: trend.icon, text: trend.label, cls: trend.bg })
  const pm = m.pair_metrics
  if (pm?.comparison_status === 'measured' && !pm.duplicate) {
    if (pm.size_change_percent != null) {
      const shrink = pm.size_change_percent < 0
      chips.push({
        icon: shrink ? 'ri-zoom-out-line' : 'ri-zoom-in-line',
        text: `面积 ${shrink ? '' : '+'}${pm.size_change_percent}%`,
        cls: shrink ? good : bad,
      })
    }
    if (pm.melanin_score_a != null && pm.melanin_score_b != null) {
      const up = (pm.melanin_change ?? 0) > 0
      chips.push({ icon: 'ri-drop-line', text: `复色指数 ${pm.melanin_score_a}→${pm.melanin_score_b}`, cls: up ? good : flat })
    }
  }
  if (m.has_vasi && m.vasi_change != null) {
    chips.push({
      icon: 'ri-line-chart-line',
      text: `VASI ${m.vasi_change > 0 ? '+' : ''}${m.vasi_change}`,
      cls: m.vasi_change < 0 ? good : m.vasi_change > 0 ? bad : flat,
    })
  }
  return chips
}

async function load(showLoading = true) {
  if (showLoading) loading.value = true
  error.value = ''
  try {
    const id = Number(route.params.id)
    const { data } = await getSkinReport(id)
    report.value = data
    setDefaultPair()
    await nextTick()
    initChart()
    // 后台生成中：轮询直到完成/失败
    if (data.status === 'generating') {
      pollTimer = setTimeout(() => load(false), 5000)
    }
  } catch {
    error.value = '报告加载失败或不存在'
  } finally {
    loading.value = false
  }
}

function initChart() {
  if (!chartRef.value || !report.value?.trend_chart) return
  const tc = report.value.trend_chart

  // 周报/月报：多序列（每部位一条 VASI 曲线）
  if ('series' in tc && Array.isArray((tc as TrendChartWithSeries).series)) {
    const usable = (tc as TrendChartWithSeries).series.filter(
      (s) => s.vasi_scores.some((v) => v != null),
    )
    if (!usable.length) return
    chartInstance?.dispose()
    chartInstance = echarts.init(chartRef.value)
    chartInstance.setOption({
      grid: { left: 44, right: 18, top: 38, bottom: 38 },
      tooltip: { trigger: 'axis' },
      legend: {
        top: 0,
        textStyle: { color: '#64748b', fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8,
      },
      xAxis: {
        type: 'category',
        data: [...new Set(usable.flatMap((s) => s.dates.map((d) => d.slice(5))))],
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: 'VASI',
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      series: usable.map((s, idx) => ({
        name: s.body_site_label,
        type: 'line' as const,
        data: s.dates.map((d, i) => [d.slice(5), s.vasi_scores[i]]),
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { width: 3 },
        itemStyle: {},
        color: ['#0d9488', '#f59e0b', '#6366f1', '#ec4899'][idx % 4],
      })),
    })
    return
  }

  // 对比报告：单序列（旧格式）
  if (!('vasi_scores' in tc) || !tc.vasi_scores.some((v) => v != null)) return
  chartInstance?.dispose()
  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption({
    grid: { left: 44, right: 18, top: 24, bottom: 38 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: tc.dates.map((d) => d.slice(5)),
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'VASI',
      nameTextStyle: { color: '#94a3b8', fontSize: 11 },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [
      {
        name: 'VASI',
        type: 'line',
        data: tc.vasi_scores,
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 3, color: '#0d9488' },
        itemStyle: { color: '#0d9488' },
        areaStyle: { color: 'rgba(13,148,136,0.12)' },
      },
    ],
  })
}

function handleResize() {
  chartInstance?.resize()
}

function trendStyle(trend: string) {
  if (trend === '好转')
    return { bg: 'bg-primary-50 text-primary-700 border-primary-200', icon: 'ri-arrow-down-line', label: '好转' }
  if (trend === '加重')
    return { bg: 'bg-rose-50 text-rose-700 border-rose-200', icon: 'ri-arrow-up-line', label: '加重' }
  if (trend === '稳定')
    return { bg: 'bg-amber-50 text-amber-700 border-amber-200', icon: 'ri-subtract-line', label: '稳定' }
  return { bg: 'bg-slate-50 text-slate-600 border-slate-200', icon: 'ri-question-line', label: trend }
}

/** 部位卡片指标徽章：VASI 数值优先，spot_compare 指标仅在置信度足够时展示 */
function siteBadges(s: SiteSection) {
  const badges: { icon: string; text: string; cls: string }[] = []
  const pm = s.pair_metrics

  if (s.vasi_change != null) {
    badges.push({
      icon: 'ri-line-chart-line',
      text: `VASI ${s.vasi_change > 0 ? '+' : ''}${s.vasi_change}`,
      cls: s.vasi_change < 0 ? 'ps-badge--good' : s.vasi_change > 0 ? 'ps-badge--bad' : 'ps-badge--flat',
    })
  }
  if (pm?.comparison_status === 'measured' && !pm.low_confidence && !pm.duplicate) {
    if (pm.melanin_score_b != null) {
      const up = (pm.melanin_change ?? 0) > 0
      badges.push({
        icon: 'ri-drop-line',
        text: `复色指数 ${pm.melanin_score_a ?? '—'}→${pm.melanin_score_b}`,
        cls: up ? 'ps-badge--good' : 'ps-badge--flat',
      })
    }
    if (pm.size_change_percent != null) {
      const shrink = pm.size_change_percent < 0
      badges.push({
        icon: shrink ? 'ri-zoom-out-line' : 'ri-zoom-in-line',
        text: `面积 ${shrink ? '' : '+'}${pm.size_change_percent}%`,
        cls: shrink ? 'ps-badge--good' : 'ps-badge--bad',
      })
    }
    if (pm.melanin_signals?.edge_inward) {
      badges.push({ icon: 'ri-shrink-line', text: '边缘内收', cls: 'ps-badge--good' })
    }
    if ((pm.melanin_signals?.follicular_repigmentation ?? 0) >= 2) {
      badges.push({ icon: 'ri-sparkling-line', text: '点状复色明显', cls: 'ps-badge--good' })
    }
  } else if (pm?.comparison_status === 'measured' && !pm.duplicate) {
    badges.push({ icon: 'ri-error-warning-line', text: '此次无法可靠比较', cls: 'ps-badge--flat' })
  }
  return badges
}

function fmtDate(d: string | null) {
  return d ? d.slice(0, 10) : ''
}

function protectedUrl(url?: string | null) {
  if (!url) return ''
  return toProtectedFileUrl(url) || url
}

async function exportPdf() {
  if (!reportRef.value || !report.value) return
  exporting.value = true
  try {
    await exportElementToPdf(reportRef.value, `SubSkin-${report.value.title}.pdf`)
    toast.show('PDF 已生成', 'success')
  } catch {
    toast.show('PDF 生成失败', 'error')
  } finally {
    exporting.value = false
  }
}

// 分享前二次确认：明确告知将把病情摘要公开发布到分享社区
function confirmShareToCommunity(): Promise<boolean> {
  return new Promise((resolve) => {
    const el = document.createElement('div')
    el.innerHTML = `
      <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 px-4" role="dialog" aria-modal="true">
        <div class="card dark:bg-gray-800 w-full max-w-md p-5 shadow-xl">
          <div class="mb-3 flex items-center gap-2">
            <i class="ri-shield-keyhole-line text-lg text-primary-600 dark:text-primary-400"></i>
            <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">确认分享到社区？</h3>
          </div>
          <p class="text-sm leading-6 text-gray-600 dark:text-gray-300">
            将在分享社区创建一篇<strong>公开帖子</strong>，包含这份白斑变化报告的
            标题、叙述摘要与报告链接。原始照片与分析明细不会公开。
            发布后你可随时在社区删除该帖。
          </p>
          <div class="mt-4 flex justify-end gap-2">
            <button data-act="cancel" class="btn-ghost px-4 py-2 text-sm">取消</button>
            <button data-act="ok" class="btn-primary px-4 py-2 text-sm">确认分享</button>
          </div>
        </div>
      </div>`
    document.body.appendChild(el)
    el.querySelector('[data-act="cancel"]')!.addEventListener('click', () => { el.remove(); resolve(false) })
    el.querySelector('[data-act="ok"]')!.addEventListener('click', () => { el.remove(); resolve(true) })
    el.addEventListener('click', (ev) => { if (ev.target === el.firstElementChild) { el.remove(); resolve(false) } })
  })
}

async function shareToCommunity() {
  if (!report.value) return
  const ok = await confirmShareToCommunity()
  if (!ok) return
  sharing.value = true
  try {
    const { data } = await shareReportToCommunity(report.value.id)
    toast.show('已发布到分享', 'success')
    report.value.is_public = true
    report.value.post_id = data.post_id
  } catch (e: any) {
    toast.show(e.response?.data?.detail || '分享失败', 'error')
  } finally {
    sharing.value = false
  }
}

async function copyLink() {
  if (!report.value?.share_token) return
  const url = `${location.origin}/share/report/${report.value.share_token}`
  try {
    if (await copyTextToClipboard(url)) {
      toast.show('链接已复制', 'success')
      return
    }
    throw new Error('copy failed')
  } catch {
    toast.show('复制失败，请手动复制', 'error')
  }
}

const confirmDeleteVisible = ref(false)

function handleDelete() {
  if (!report.value) return
  confirmDeleteVisible.value = true
}

async function onConfirmDelete() {
  confirmDeleteVisible.value = false
  if (!report.value) return
  try {
    await deleteSkinReport(report.value.id)
    toast.show('已删除', 'success')
    router.push({ name: 'assessment' })
  } catch {
    toast.show('删除失败', 'error')
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<template>
  <div class="report-page">
  <ConfirmDialog
    :visible="confirmDeleteVisible"
    title="删除确认"
    message="确定删除这份报告吗？删除后不可恢复。"
    confirm-text="删除"
    @confirm="onConfirmDelete"
    @cancel="confirmDeleteVisible = false"
  />

    <!-- Header -->
    <header class="report-header">
      <div class="report-header__inner">
        <button class="report-back" @click="router.back()">
          <i class="ri-arrow-left-s-line"></i>
        </button>
        <h1 class="report-header__title">白斑变化报告</h1>
        <button class="report-back" @click="handleDelete">
          <i class="ri-delete-bin-line"></i>
        </button>
      </div>
    </header>

    <main class="report-main">
      <div v-if="loading" class="report-loading">
        <i class="ri-loader-4-line report-spin"></i>
        <p>报告加载中...</p>
      </div>

      <div v-else-if="error" class="report-error">
        <i class="ri-file-damage-line"></i>
        <p>{{ error }}</p>
      </div>

      <template v-else-if="report">
        <!-- 后台生成中 -->
        <div v-if="report.status === 'generating'" class="report-loading">
          <i class="ri-loader-4-line report-spin"></i>
          <p>AI 正在分析你的白斑照片（约 1-2 分钟）…</p>
          <p class="report-loading__sub">页面会自动刷新，也可以稍后回来查看</p>
        </div>

        <div v-else-if="report.status === 'failed'" class="report-error">
          <i class="ri-file-damage-line"></i>
          <p>{{ report.error_message || '报告生成失败，请稍后重试' }}</p>
        </div>

        <!-- 报告文档区（固定浅色，确保 PDF 可读） -->
        <div v-else ref="reportRef" class="report-doc">
          <!-- 封面（对比报告：分层标题，简短有层次） -->
          <div class="report-cover">
            <div class="report-cover__brand">
              <i class="ri-leaf-line"></i>
              <span>SubSkin</span>
            </div>
            <template v-if="isComparison">
              <span class="report-cover__badge">
                <i class="ri-git-compare-line"></i> 对比报告
              </span>
              <h2 class="report-cover__headline">{{ report.body_site_label }}白斑变化报告</h2>
              <p class="report-cover__meta">
                {{ fmtDate(report.period_start) }} ~ {{ fmtDate(report.period_end) }}
                <template v-if="report.metrics"> · {{ report.metrics.point_count }} 次记录 · 跨 {{ report.metrics.date_span_days }} 天</template>
              </p>
              <div v-if="coverChips().length" class="report-cover__chips">
                <span v-for="(c, i) in coverChips()" :key="i" class="rc-chip" :class="c.cls">
                  <i :class="c.icon"></i> {{ c.text }}
                </span>
              </div>
            </template>
            <template v-else>
              <h2 v-if="(isPeriodic || isSynthesis) && report.metrics?.headline" class="report-cover__headline">
                {{ report.metrics.headline }}
              </h2>
              <h2 v-else class="report-cover__headline">{{ report.title }}</h2>
              <div class="report-cover__meta-row">
                <p class="report-cover__meta">
                  {{ isSynthesis ? '历史报告对比' : '多部位汇总' }} ·
                  {{ fmtDate(report.period_start) }} ~ {{ fmtDate(report.period_end) }}
                </p>
                <div
                  v-if="report.metrics"
                  class="report-cover__trend"
                  :class="trendStyle(report.metrics.trend).bg"
                >
                  <i :class="trendStyle(report.metrics.trend).icon"></i>
                  <span>{{ trendStyle(report.metrics.trend).label }}</span>
                </div>
              </div>
            </template>
          </div>

          <!-- 封面拼图（周报/月报） -->
          <img v-if="isPeriodic && coverUrl" :src="coverUrl" alt="白斑前后对比拼图" class="report-coverimg" />

          <!-- 前后对比（对比报告核心，置顶）：日期可切换 + 热力图 + 变化要点 -->
          <div v-if="isComparison && activeBeforeUrl && activeAfterUrl" class="report-section report-compare">
            <h3 class="report-section__title"><i class="ri-git-compare-line"></i> 前后对比</h3>
            <PairDateSwitcher
              v-if="frames.length > 2"
              :frames="frames"
              v-model:before-index="beforeIdx"
              v-model:after-index="afterIdx"
              :disabled="pairLoading"
            />
            <div class="report-compare__stage">
              <div v-if="pairLoading" class="report-compare__loading">
                <i class="ri-loader-4-line report-spin"></i>
                <span>AI 正在对比这两张照片…</span>
              </div>
              <ComparisonViews
                :before-url="activeBeforeUrl"
                :after-url="activeAfterUrl"
                :align="activeAlign"
                :metrics="activeMetrics"
                :before-label="activeBeforeDate"
                :after-label="activeAfterDate"
              />
            </div>
            <p v-if="frames.length > 2" class="ps-note">
              <i class="ri-information-line"></i>
              默认对比最早与最晚两张，点击上方日期可切换查看任意两次记录的对比
            </p>
          </div>

          <!-- 历史报告对比：来源报告 -->
          <div v-if="isSynthesis && report.metrics?.sources?.length" class="report-section">
            <h3 class="report-section__title"><i class="ri-file-list-3-line"></i> 来源报告</h3>
            <div class="src-list">
              <div v-for="s in report.metrics.sources" :key="s.report_id" class="src-item">
                <img
                  v-if="protectedUrl(s.cover_composite_url)"
                  :src="protectedUrl(s.cover_composite_url)"
                  alt="来源报告封面"
                  loading="lazy"
                />
                <i v-else class="ri-file-chart-line src-item__ph"></i>
                <div class="src-item__body">
                  <span class="src-item__title">{{ s.headline || s.title }}</span>
                  <span class="src-item__meta">{{ s.period }}</span>
                </div>
                <span v-if="s.trend" class="src-item__trend" :class="trendStyle(s.trend).bg">
                  <i :class="trendStyle(s.trend).icon"></i> {{ s.trend }}
                </span>
              </div>
            </div>
          </div>

          <!-- 周报/月报：部位总览 -->
          <div v-if="isPeriodic && report.metrics?.sites_summary" class="report-section">
            <h3 class="report-section__title"><i class="ri-body-scan-line"></i> 部位总览</h3>
            <div class="ps-overview">
              <div class="ps-overview__item ps-overview__item--good">
                <i class="ri-arrow-down-line"></i>
                <span>{{ report.metrics.sites_summary.improving }}</span>
                <em>好转</em>
              </div>
              <div class="ps-overview__item ps-overview__item--flat">
                <i class="ri-subtract-line"></i>
                <span>{{ report.metrics.sites_summary.stable }}</span>
                <em>稳定</em>
              </div>
              <div class="ps-overview__item ps-overview__item--bad">
                <i class="ri-arrow-up-line"></i>
                <span>{{ report.metrics.sites_summary.worsening }}</span>
                <em>需关注</em>
              </div>
              <div class="ps-overview__item">
                <i class="ri-camera-line"></i>
                <span>{{ report.metrics.period_days }}</span>
                <em>天周期</em>
              </div>
            </div>
            <div v-if="report.metrics.melanin_sites?.length" class="ps-melanin">
              <i class="ri-sparkling-line"></i>
              复色进行中：{{ report.metrics.melanin_sites.join('、') }}
            </div>
          </div>

          <!-- 周报/月报：分部位对比卡片 -->
          <div v-for="s in periodicSites" :key="s.body_site" class="report-section">
            <div class="ps-site-head">
              <h3 class="report-section__title ps-site-head__title">
                <i class="ri-focus-3-line"></i> {{ s.body_site_label }}
              </h3>
              <span class="ps-site-head__trend" :class="trendStyle(s.trend).bg">
                <i :class="trendStyle(s.trend).icon"></i> {{ s.trend }}
              </span>
            </div>
            <div v-if="siteBadges(s).length" class="ps-badges">
              <span v-for="(b, bi) in siteBadges(s)" :key="bi" class="ps-badge" :class="b.cls">
                <i :class="b.icon"></i> {{ b.text }}
              </span>
            </div>
            <div v-if="s.first_image_url && s.last_image_url" class="ps-split">
              <figure class="ps-split__item">
                <img
                  :src="protectedUrl(s.first_image_url)"
                  :alt="`${s.body_site_label} 之前`"
                  loading="lazy"
                />
                <figcaption>之前 · {{ fmtDate(s.first?.date ?? null) }}</figcaption>
              </figure>
              <figure class="ps-split__item">
                <img
                  :src="protectedUrl(s.last_image_url)"
                  :alt="`${s.body_site_label} 之后`"
                  loading="lazy"
                />
                <figcaption>之后 · {{ fmtDate(s.last?.date ?? null) }}</figcaption>
              </figure>
            </div>
            <p v-if="s.pair_metrics?.summary" class="ps-summary">{{ s.pair_metrics.summary }}</p>
            <p v-if="s.pair_metrics?.capture_note" class="ps-note">
              <i class="ri-information-line"></i> {{ s.pair_metrics.capture_note }}
            </p>
            <p v-if="s.pair_metrics?.low_confidence" class="ps-note ps-note--warn">
              <i class="ri-error-warning-line"></i>
              本次对比置信度较低（拍摄条件差异），建议同角度、同光线下拍摄以提升精度
            </p>
          </div>

          <!-- 综合健康报告：心情/体检/问答/概览 -->
          <HealthReportSections v-if="isPeriodic" :metrics="report.metrics" />

          <!-- VASI 趋势（客观数值曲线） -->
          <div v-if="report.metrics?.has_vasi" class="report-section">
            <h3 class="report-section__title"><i class="ri-line-chart-line"></i> VASI 趋势</h3>
            <div ref="chartRef" class="report-chart"></div>
          </div>

          <!-- 变化摘要（对比报告：客观事实，每条一句话，不做解读） -->
          <div v-if="isComparison && report.metrics?.change_summary?.length" class="report-section">
            <h3 class="report-section__title"><i class="ri-file-list-3-line"></i> 变化摘要</h3>
            <ul class="report-facts">
              <li v-for="(line, i) in report.metrics.change_summary" :key="i">
                <i class="ri-checkbox-circle-line"></i>
                <span>{{ line }}</span>
              </li>
            </ul>
          </div>

          <!-- AI 分析 / 洞察 / 建议：仅周报月报与历史报告对比保留（对比报告不再生成长文） -->
          <template v-if="!isComparison">
            <div v-if="narrativeSections.length" class="report-section">
              <h3 class="report-section__title"><i class="ri-sparkling-2-line"></i> AI 分析</h3>
              <div v-for="(sec, si) in narrativeSections" :key="si" class="report-narrative__section">
                <h4 class="report-narrative__title">{{ sec.title }}</h4>
                <p class="report-narrative">{{ sec.body }}</p>
              </div>
            </div>
            <div v-else-if="report.narrative" class="report-section">
              <h3 class="report-section__title"><i class="ri-sparkling-2-line"></i> AI 分析</h3>
              <p class="report-narrative">{{ report.narrative }}</p>
            </div>

            <div v-if="report.insights?.length" class="report-section">
              <h3 class="report-section__title"><i class="ri-lightbulb-line"></i> 关键洞察</h3>
              <ul class="report-list">
                <li v-for="(ins, i) in report.insights" :key="'ins-' + i">
                  <i class="ri-checkbox-circle-line"></i>
                  <span>{{ ins }}</span>
                </li>
              </ul>
            </div>

            <div v-if="report.recommendations?.length" class="report-section">
              <h3 class="report-section__title"><i class="ri-thumb-up-line"></i> 建议</h3>
              <ul class="report-list report-list--rec">
                <li v-for="(rec, i) in report.recommendations" :key="'rec-' + i">
                  <i class="ri-arrow-right-s-line"></i>
                  <span>{{ rec }}</span>
                </li>
              </ul>
            </div>
          </template>

          <!-- 免责声明 -->
          <div class="report-disclaimer">
            <i class="ri-error-warning-line"></i>
            <span v-if="isComparison">本报告为照片的客观比对结果，仅供参考，不构成医疗建议；如有疑问请咨询专业医生。</span>
            <span v-else>本报告由 AI 基于你的记录生成，仅供参考，不构成医疗诊断建议。如有疑问请咨询专业医生。</span>
          </div>
        </div>

        <!-- 操作栏 -->
        <div
          v-if="report.status === 'completed'"
          class="report-actions"
        >
          <button class="r-action" :disabled="exporting" @click="exportPdf">
            <i :class="exporting ? 'ri-loader-4-line report-spin' : 'ri-file-download-line'"></i>
            <span>PDF</span>
          </button>
          <button class="r-action" @click="showPoster = true">
            <i class="ri-image-2-line"></i>
            <span>海报</span>
          </button>
          <button class="r-action r-action--primary" :disabled="sharing" @click="shareToCommunity">
            <i :class="sharing ? 'ri-loader-4-line report-spin' : 'ri-team-line'"></i>
            <span>{{ report.is_public ? '已分享' : '分享' }}</span>
          </button>
          <button class="r-action" @click="copyLink">
            <i class="ri-link"></i>
            <span>链接</span>
          </button>
        </div>
      </template>
    </main>

    <!-- 海报弹层 -->
    <SkinReportPoster :visible="showPoster" :report="report" @close="showPoster = false" />
  </div>
</template>

<style scoped>
.report-page {
  min-height: 0;
  min-height: 0;
  background: #f5f7fa;
  padding-bottom: 90px;
}

.report-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(245, 247, 250, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #e2e8f0;
}

html.dark .report-page {
  background: #0f172a;
}

html.dark .report-header {
  background: rgba(15, 23, 42, 0.85);
  border-color: #1e293b;
}

.report-header__inner {
  max-width: 896px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  height: 48px;
}

.report-back {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #475569;
  font-size: 22px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

html.dark .report-back {
  color: #cbd5e1;
}

.report-header__title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

html.dark .report-header__title {
  color: #f1f5f9;
}

.report-main {
  max-width: 896px;
  margin: 0 auto;
  padding: 16px;
}

.report-loading,
.report-error {
  text-align: center;
  padding: 64px 24px;
  color: #94a3b8;
}

.report-loading i,
.report-error i {
  font-size: 40px;
  display: block;
  margin-bottom: 12px;
}

.report-spin {
  animation: r-spin 1s linear infinite;
}

@keyframes r-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 报告文档区：固定浅色 */
.report-doc {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
  color: #1e293b;
}

.report-cover {
  background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
  color: white;
  padding: 14px 16px;
}

.report-cover__brand {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  opacity: 0.85;
  margin-bottom: 6px;
}

.report-cover__brand i {
  font-size: 14px;
}

.report-cover__meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.report-cover__meta {
  font-size: 12px;
  opacity: 0.9;
  margin: 0;
}

.report-cover__trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid;
  flex-shrink: 0;
}

.report-section {
  padding: 20px 24px;
  border-top: 1px solid #f1f5f9;
}

.report-section__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #0f766e;
  margin-bottom: 14px;
}

.report-section__title i {
  font-size: 18px;
}

.report-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

@media (min-width: 640px) {
  .report-metrics {
    grid-template-columns: repeat(4, 1fr);
  }
}

.report-metric {
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px;
  text-align: center;
}

.report-metric__label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.report-metric__value {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.report-source-note {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  font-size: 12px;
  color: #d97706;
}

.report-chart {
  width: 100%;
  height: 220px;
}

.report-compare-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.report-narrative {
  font-size: 15px;
  line-height: 1.8;
  color: #334155;
  white-space: pre-wrap;
}

.report-narrative__section {
  margin-bottom: 16px;
}

.report-narrative__section:last-child {
  margin-bottom: 0;
}

.report-narrative__title {
  font-size: 14px;
  font-weight: 700;
  color: #0f766e;
  margin-bottom: 6px;
}

.report-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.report-list li i {
  color: #0d9488;
  font-size: 16px;
  margin-top: 2px;
  flex-shrink: 0;
}

.report-list--rec li i {
  color: #94a3b8;
}

.report-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 14px 24px;
  background: #fefce8;
  color: #92400e;
  font-size: 12px;
  line-height: 1.6;
}

.report-disclaimer i {
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

.report-loading__sub {
  font-size: 12px;
  margin-top: 4px;
}

/* ── 封面拼图（周报/月报） ── */
.report-cover__headline {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.35;
  margin-bottom: 8px;
}

.report-coverimg {
  display: block;
  width: 100%;
}

/* ── 对比报告封面：分层标题 ── */
.report-cover__badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.2);
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 8px;
}

.report-cover__badge i {
  font-size: 12px;
}

.report-cover__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.rc-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.92);
  color: #0f172a;
}

.rc-chip i {
  font-size: 13px;
}

.rc-chip--good {
  background: #ecfdf5;
  color: #047857;
}

.rc-chip--bad {
  background: #fef2f2;
  color: #b91c1c;
}

.rc-chip--flat {
  background: #f1f5f9;
  color: #475569;
}

/* ── 前后对比（置顶区块） ── */
.report-compare__stage {
  position: relative;
}

.report-compare__loading {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.82);
  backdrop-filter: blur(2px);
  color: #0f766e;
  font-size: 13px;
  font-weight: 500;
}

html.dark .report-compare__loading {
  background: rgba(15, 23, 42, 0.82);
  color: #5eead4;
}

.report-compare__loading i {
  font-size: 26px;
}

/* ── 客观变化摘要 ── */
.report-facts {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-facts li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.report-facts li i {
  color: #0d9488;
  font-size: 16px;
  margin-top: 2px;
  flex-shrink: 0;
}

/* ── 周报/月报部位总览 ── */
.ps-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.ps-overview__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px 8px;
}

.ps-overview__item i {
  font-size: 18px;
  color: #94a3b8;
}

.ps-overview__item--good i {
  color: #059669;
}

.ps-overview__item--bad i {
  color: #dc2626;
}

.ps-overview__item--flat i {
  color: #d97706;
}

.ps-overview__item span {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.ps-overview__item em {
  font-style: normal;
  font-size: 11px;
  color: #94a3b8;
}

.ps-melanin {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 10px 12px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 10px;
  font-size: 13px;
  color: #047857;
}

.ps-melanin i {
  font-size: 16px;
}

/* ── 分部位卡片 ── */
.ps-site-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.ps-site-head__title {
  margin-bottom: 0;
}

.ps-site-head__trend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid;
  flex-shrink: 0;
}

.ps-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

/* 并排对比（照片未做像素级对齐，并排展示更直观） */
.ps-split {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.ps-split__item {
  margin: 0;
}

.ps-split__item img {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 10px;
  background: #e2e8f0;
}

.ps-split__item figcaption {
  margin-top: 6px;
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
}

/* 历史报告对比：来源报告列表 */
.src-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.src-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px;
}

.src-item img {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  background: #e2e8f0;
}

.src-item__ph {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: #e2e8f0;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.src-item__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.src-item__title {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.src-item__meta {
  font-size: 11px;
  color: #94a3b8;
}

.src-item__trend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  flex-shrink: 0;
}

.ps-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.ps-badge i {
  font-size: 13px;
}

.ps-badge--good {
  background: #ecfdf5;
  color: #047857;
}

.ps-badge--bad {
  background: #fef2f2;
  color: #b91c1c;
}

.ps-badge--flat {
  background: #f1f5f9;
  color: #475569;
}

.ps-summary {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.7;
  color: #334155;
}

.ps-note {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: #94a3b8;
}

.ps-note i {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 2px;
}

.ps-note--warn {
  color: #b45309;
}

/* 操作栏 */
.report-actions {
  max-width: 896px;
  margin: 16px auto 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 0 16px;
}

.r-action {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 4px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: white;
  color: #475569;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

html.dark .r-action {
  background: #1e293b;
  border-color: #334155;
  color: #cbd5e1;
}

.r-action i {
  font-size: 20px;
}

.r-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.r-action--primary {
  background: #0f766e;
  border-color: #0f766e;
  color: white;
}

html.dark .r-action--primary {
  background: #0f766e;
  border-color: #0f766e;
  color: white;
}
</style>
