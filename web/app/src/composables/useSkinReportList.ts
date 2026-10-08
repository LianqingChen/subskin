/**
 * SkinReportListPage — 白斑变化报告列表
 * 顶部提供周报/月报快捷生成入口（基于可用性预览），列表按类型筛选。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSkinReports, getPeriodicPreview, createPeriodicReport } from '@/api/skin_report'
import type { SkinReportListItem, PeriodicPreviewItem } from '@/api/skin_report'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

export function useSkinReportList() {
const router = useRouter()
const toast = useToast()
const authStore = useAuthStore()
const reports = ref<SkinReportListItem[]>([])
const loading = ref(false)
const previews = ref<PeriodicPreviewItem[]>([])
const typeFilter = ref<'all' | 'comparison' | 'weekly' | 'monthly'>('all')
const generating = ref<Set<string>>(new Set())
let pollTimer: ReturnType<typeof setInterval> | null = null

// 访客也可能被小白管家引导到此页（报告属个人健康数据，需登录）；
// 未登录时显示登录引导，不发起会被 401 的请求
const isLoggedIn = computed(() => authStore.isLoggedIn)

const filteredReports = computed(() =>
  typeFilter.value === 'all'
    ? reports.value
    : reports.value.filter((r) => r.report_type === typeFilter.value),
)

const typeTabs = [
  { key: 'all', label: '全部' },
  { key: 'weekly', label: '周报' },
  { key: 'monthly', label: '月报' },
  { key: 'comparison', label: '对比报告' },
] as const

async function load() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const { data } = await getSkinReports({ limit: 50 })
    reports.value = data.items
  } catch {
    toast.show('加载报告失败', 'error')
  } finally {
    loading.value = false
  }
}

/** 暂停周报/月报生成（2026-10-01）：隐藏快捷卡，已生成的报告仍在列表里可看。恢复时改为 false。 */
const PERIODIC_PAUSED = true

async function loadPreviews() {
  if (PERIODIC_PAUSED || !isLoggedIn.value) return
  try {
    const { data } = await getPeriodicPreview()
    previews.value = data.items
  } catch {
    previews.value = []
  }
}

/** 生成周报/月报：后台异步，进入轮询直到状态不再是 generating */
async function generatePeriodic(item: PeriodicPreviewItem) {
  if (PERIODIC_PAUSED) return
  if (generating.value.has(item.label)) return
  generating.value.add(item.label)
  try {
    await createPeriodicReport({ period_type: item.period_type, anchor_date: item.period_start })
    toast.show('正在生成，约需 1-2 分钟', 'success')
    startPolling()
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '生成失败，请稍后重试'
    toast.show(msg, 'error')
    generating.value.delete(item.label)
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await load()
    await loadPreviews()
    const hasGenerating = reports.value.some((r) => r.status === 'generating')
    if (!hasGenerating) {
      stopPolling()
      generating.value.clear()
    }
  }, 6000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function previewBusy(item: PeriodicPreviewItem) {
  return (
    generating.value.has(item.label) ||
    item.existing_status === 'generating' ||
    reports.value.some(
      (r) => r.id === item.existing_report_id && r.status === 'generating',
    )
  )
}

function previewDone(item: PeriodicPreviewItem) {
  return !!item.existing_report_id && item.existing_status === 'completed'
}

/** 快捷卡点击：已有报告→查看；可生成→生成 */
function handleQuick(item: PeriodicPreviewItem) {
  if (previewDone(item) && item.existing_report_id) {
    router.push({ name: 'skin-report-view', params: { id: item.existing_report_id } })
    return
  }
  generatePeriodic(item)
}

function trendStyle(trend?: string) {
  if (trend === '好转')
    return { cls: 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300', icon: 'ri-arrow-down-line' }
  if (trend === '加重')
    return { cls: 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300', icon: 'ri-arrow-up-line' }
  if (trend === '稳定')
    return { cls: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300', icon: 'ri-subtract-line' }
  return { cls: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300', icon: 'ri-question-line' }
}

function typeLabel(t: string) {
  if (t === 'weekly') return '周报'
  if (t === 'monthly') return '月报'
  return '对比报告'
}

function fmtDate(d: string | null) {
  return d ? d.slice(0, 10) : ''
}

onMounted(() => {
  load()
  loadPreviews()
})

onUnmounted(stopPolling)

return { router, authStore, reports, loading, previews, typeFilter, isLoggedIn, filteredReports, typeTabs, previewBusy, previewDone, handleQuick, trendStyle, typeLabel, fmtDate }
}
