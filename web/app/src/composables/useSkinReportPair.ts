import { ref, computed, watch, nextTick, onBeforeUnmount, type Ref } from 'vue'
import { getPairCompare, type SkinReport, type TimelineFrame, type PairAlign, type PairMetrics } from '@/api/skin_report'
import { protectedUrl } from '@/utils/skin-report-presentation'
import { useToast } from '@/composables/useToast'
export function useSkinReportPair(report: Ref<SkinReport | null>) {
const toast = useToast()
const isComparison = computed(() => report.value?.report_type === 'comparison')
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
let pairRequest = 0
let pairSwitchTimer: ReturnType<typeof setTimeout> | null = null

function setDefaultPair() {
  const m = report.value?.metrics
  if (!m || !isComparison.value) return
  suppressPairWatch = true
  pairRequest++; pairLoading.value = false
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
  const request = ++pairRequest
  pairLoading.value = true
  try {
    const { data } = await getPairCompare(report.value.id, a, b)
    if (request !== pairRequest) return
    activeMetrics.value = data.pair_metrics
    activeAlign.value = data.pair_align
    const first = data.first ?? fs[a]
    const last = data.last ?? fs[b]
    activeBeforeUrl.value = protectedUrl(first?.image_url)
    activeAfterUrl.value = protectedUrl(last?.image_url)
    activeBeforeDate.value = first?.date ?? ''
    activeAfterDate.value = last?.date ?? ''
  } catch {
    if (request === pairRequest) {
      toast.show('这组照片对比计算失败，请稍后重试', 'error')
      suppressPairWatch = true
      beforeIdx.value = Math.max(0, fs.findIndex(frame => frame.date === activeBeforeDate.value && protectedUrl(frame.image_url) === activeBeforeUrl.value))
      afterIdx.value = Math.max(0, fs.findIndex(frame => frame.date === activeAfterDate.value && protectedUrl(frame.image_url) === activeAfterUrl.value))
      nextTick(() => { suppressPairWatch = false })
    }
  } finally {
    if (request === pairRequest) pairLoading.value = false
  }
}

watch([beforeIdx, afterIdx], () => {
  if (suppressPairWatch || !isComparison.value) return
  pairRequest++; pairLoading.value = true
  if (pairSwitchTimer) clearTimeout(pairSwitchTimer)
  pairSwitchTimer = setTimeout(() => switchPair(), 60)
})


onBeforeUnmount(() => { pairRequest++; if (pairSwitchTimer) clearTimeout(pairSwitchTimer) })
return { frames, beforeIdx, afterIdx, activeAlign, activeMetrics, activeBeforeUrl, activeAfterUrl,
  activeBeforeDate, activeAfterDate, pairLoading, setDefaultPair }
}
