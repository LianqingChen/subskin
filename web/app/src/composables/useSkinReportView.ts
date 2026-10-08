import { ref, computed, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getSkinReport, deleteSkinReport, shareReportToCommunity, type SkinReport, type SiteSection } from '@/api/skin_report'
import { useSkinReportPair } from './useSkinReportPair'
import { useSkinReportChart } from './useSkinReportChart'
import { useToast } from './useToast'
import { protectedUrl, coverChips } from '@/utils/skin-report-presentation'
import { exportElementToPdf } from '@/utils/report-pdf'
import { copyTextToClipboard } from '@/utils/clipboard'
export function useSkinReportView() {
const route = useRoute(), router = useRouter(), toast = useToast(), auth = useAuthStore()
let loadRequest = 0
const report = ref<SkinReport | null>(null)
const loading = ref(true)
const error = ref('')
const reportRef = ref<HTMLElement>()
const showPoster = ref(false)
const exporting = ref(false)
const sharing = ref(false)
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

const pair = useSkinReportPair(report)
const { setDefaultPair } = pair
const { chartRef, initChart } = useSkinReportChart(report)
const chips = computed(() => {
  const current = report.value
  if (!current?.metrics || !isComparison.value) return []
  return coverChips({ ...current, metrics: { ...current.metrics, pair_metrics: pair.activeMetrics.value,
    trend: pair.activeMetrics.value?.trend || current.metrics.trend } })
})
const changeSummary = computed(() => pair.activeMetrics.value?.summary
  ? [pair.activeMetrics.value.summary] : report.value?.metrics?.change_summary || [])
async function load(showLoading = true) {
  if (pollTimer) clearTimeout(pollTimer)
  const request = ++loadRequest
  const owner = auth.user?.id
  if (showLoading) loading.value = true
  error.value = ''
  try {
    const id = Number(route.params.id)
    const { data } = await getSkinReport(id)
    if (request !== loadRequest || owner !== auth.user?.id) return
    report.value = data
    setDefaultPair()
    await nextTick()
    if (request !== loadRequest) return
    initChart()
    // 后台生成中：轮询直到完成/失败
    if (data.status === 'generating') {
      pollTimer = setTimeout(() => load(false), 5000)
    }
  } catch {
    if (request === loadRequest) error.value = '报告加载失败或不存在'
  } finally {
    if (request === loadRequest) loading.value = false
  }
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

// 分享前二次确认：明确告知将把病情摘要公开发布到发现社区
const confirmShareVisible = ref(false)
function requestShare() { confirmShareVisible.value = true }
async function shareToCommunity() {
  if (!report.value) return
  confirmShareVisible.value = false
  sharing.value = true
  try {
    const { data } = await shareReportToCommunity(report.value.id)
    toast.show('已发布到发现', 'success')
    report.value.is_public = true
    report.value.post_id = data.post_id
  } catch (e: unknown) {
    toast.show((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '分享失败', 'error')
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


watch(() => [route.params.id, auth.user?.id], () => { report.value = null; void load() }, { immediate: true })
onBeforeUnmount(() => { loadRequest++; if (pollTimer) clearTimeout(pollTimer) })
return { report, loading, error, reportRef, chartRef, showPoster, exporting, sharing, isPeriodic, isSynthesis,
  isComparison, periodicSites, narrativeSections, coverUrl, chips, changeSummary, load, exportPdf, requestShare,
  shareToCommunity, copyLink, confirmDeleteVisible, handleDelete, onConfirmDelete, confirmShareVisible, router, ...pair }
}
