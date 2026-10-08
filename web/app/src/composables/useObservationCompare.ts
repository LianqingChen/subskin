import { ref, watch, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { vasiApi } from '@/api/vasi'
import type { VasiAssessmentResponse } from '@/api/vasi'
import type { AlignmentTransform } from '@/types/comparison-alignment'
import { bindManualAlignment } from '@/utils/comparison-alignment'
import { createComparisonReport, getComparisonCapabilities } from '@/api/skin_report'
import { assessmentError } from '@/utils/assessment-errors'
import { BODY_SITES } from '@/constants/bodySites'
export function useObservationCompare() {
  const auth = useAuthStore()
  const items = ref<VasiAssessmentResponse[]>([])
  const loading = ref(false), generating = ref(false), error = ref('')
  let generation = 0
  const siteId = (value: string) => Object.values(BODY_SITES).find(site => site.id === value || site.label === value || (site.id === 'neck' && value === '颈部'))?.id
  async function load(ids: number[], bodySite?: string) {
    const current = ++generation, owner = auth.user?.id
    loading.value = true; error.value = ''; items.value = []
    try {
      if (ids.length !== 2 || new Set(ids).size !== 2) { error.value = '请选择两次白斑记录'; return }
      const records = await Promise.all(ids.map(id => vasiApi.getAssessment(id)))
      if (current !== generation || !auth.isLoggedIn || auth.user?.id !== owner) return
      const site = siteId(records[0].body_site)
      if (!site || records.some(record => siteId(record.body_site) !== site) || (bodySite && site !== bodySite)) { error.value = '请选择同一身体部位的两次记录'; return }
      items.value = records.sort((a, b) => a.assessment_date.localeCompare(b.assessment_date))
    } catch (e) { if (current === generation) error.value = assessmentError(e, '请选择两条可以访问的白斑记录') }
    finally { if (current === generation) loading.value = false }
  }
  async function generate(alignment?: AlignmentTransform | null): Promise<number | null> {
    if (generating.value || loading.value || items.value.length !== 2) return null
    const current = generation, owner = auth.user?.id
    generating.value = true; error.value = ''
    const selected = items.value.map(i => i.id)
    try {
      if (alignment) {
        const capabilities = await getComparisonCapabilities()
        if (!capabilities.manual_alignment || capabilities.version !== 'manual-similarity-v1') throw new Error('手动对齐分析尚未启用')
      }
      if (current !== generation || !auth.isLoggedIn || auth.user?.id !== owner) return null
      const { data } = await createComparisonReport({ vasi_ids: selected, manual_alignment: alignment ? bindManualAlignment(alignment, selected[0], selected[1]) : undefined })
      return current === generation && auth.isLoggedIn && auth.user?.id === owner ? data.id : null
    }
    catch (e) { error.value = assessmentError(e, '对比暂时无法生成，请重试'); return null }
    finally { generating.value = false }
  }
  watch(() => [auth.user?.id, auth.isLoggedIn], () => { generation++; items.value = []; error.value = ''; loading.value = false })
  onBeforeUnmount(() => { generation++ })
  return { items, loading, generating, error, load, generate }
}
