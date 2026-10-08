import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { createComparisonReport, getComparisonCapabilities, getSkinReport } from '@/api/skin_report'
import { toProtectedFileUrl } from '@/utils/file-url'
import { bindManualAlignment } from '@/utils/comparison-alignment'
import { assessmentError } from '@/utils/assessment-errors'
import type { AlignmentTransform } from '@/types/comparison-alignment'
interface SourcePair { kind: 'va' | 'pi'; reference: number; moving: number; referenceUrl: string; movingUrl: string }
export function useReportReanalysis(props: { beforeUrl: string; afterUrl: string; beforeLabel?: string; afterLabel?: string }) {
  const route = useRoute(), router = useRouter(), auth = useAuthStore()
  const reportId = computed(() => route.name === 'skin-report-view' ? Number(route.params.id) : 0)
  const available = computed(() => auth.isLoggedIn && Number.isSafeInteger(reportId.value) && reportId.value > 0)
  const pair = ref<SourcePair | null>(null), loading = ref(false), busy = ref(false), error = ref('')
  let generation = 0
  function canonical(source: string): string {
    const value = toProtectedFileUrl(source)
    if (value.startsWith('data:') || value.startsWith('blob:')) return value
    try { const url = new URL(value, window.location.origin); url.searchParams.delete('access_token'); url.hash = ''; return url.href }
    catch { return value }
  }
  function reset() { generation++; pair.value = null; loading.value = false; busy.value = false; error.value = '' }
  async function load() {
    reset()
    if (!available.value) return
    const current = generation, owner = auth.user?.id
    loading.value = true
    try {
      const { data } = await getSkinReport(reportId.value)
      if (current !== generation || auth.user?.id !== owner || !auth.isLoggedIn) return
      const metrics = data.metrics, frames = metrics?.timeline_frames?.length ? metrics.timeline_frames : [metrics?.first, metrics?.last].filter(frame => !!frame)
      const refs = metrics?.refs || []
      const find = (url: string, label: string | undefined, fallback: number) => {
        const matches = frames.map((frame, index) => frame && canonical(frame.image_url || '') === canonical(url) && (!label || frame.date.slice(0, 10) === label.slice(0, 10)) ? index : -1).filter(index => index >= 0)
        return matches.length === 1 ? matches[0] : frames.length === 2 && matches.includes(fallback) ? fallback : -1
      }
      const a = find(props.beforeUrl, props.beforeLabel, 0), b = find(props.afterUrl, props.afterLabel, frames.length - 1)
      const reference = /^(va|pi):(\d+)$/.exec(refs[a] || ''), moving = /^(va|pi):(\d+)$/.exec(refs[b] || '')
      if (a === b || !reference || !moving || reference[1] !== moving[1] || Number(reference[2]) === Number(moving[2])) throw new Error('missing pair references')
      const referenceId = Number(reference[2]), movingId = Number(moving[2])
      if (![referenceId, movingId].every(id => Number.isSafeInteger(id) && id > 0)) throw new Error('invalid source ids')
      const referenceUrl = frames[a]?.image_url, movingUrl = frames[b]?.image_url
      if (!referenceUrl || !movingUrl) throw new Error('missing source images')
      pair.value = { kind: reference[1] as 'va' | 'pi', reference: referenceId, moving: movingId, referenceUrl, movingUrl }
    } catch { if (current === generation) error.value = '这份报告的来源暂不可用，请返回白斑对比重新选择两张照片或记录' }
    finally { if (current === generation) loading.value = false }
  }
  async function generate(alignment: AlignmentTransform | null) {
    const selected = pair.value, owner = auth.user?.id, current = generation
    if (!selected || busy.value || !available.value) return
    busy.value = true; error.value = ''
    try {
      if (alignment) {
        const capabilities = await getComparisonCapabilities()
        if (!capabilities.manual_alignment || capabilities.version !== 'manual-similarity-v1') throw new Error('manual unavailable')
      }
      if (current !== generation || auth.user?.id !== owner || !auth.isLoggedIn) return
      const ids = [selected.reference, selected.moving]
      const { data } = await createComparisonReport({ ...(selected.kind === 'va' ? { vasi_ids: ids } : { image_ids: ids }), manual_alignment: alignment ? bindManualAlignment(alignment, selected.reference, selected.moving) : undefined })
      if (current === generation && auth.user?.id === owner && auth.isLoggedIn) await router.push({ name: 'skin-report-view', params: { id: data.id } })
    } catch (cause) { if (current === generation) error.value = assessmentError(cause, '暂时无法重新分析，请稍后重试') }
    finally { if (current === generation) busy.value = false }
  }
  watch(() => [reportId.value, auth.user?.id, auth.isLoggedIn, props.beforeUrl, props.afterUrl, props.beforeLabel, props.afterLabel], reset)
  onBeforeUnmount(reset)
  return { available, pair, loading, busy, error, load, reset, generate }
}
