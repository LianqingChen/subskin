import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { vasiApi, type VasiHistoryItem } from '@/api/vasi'

export interface AssessmentRecord {
  id: number
  date: string
  bodySite: string
  vasiScore: number
  areaPercentage: number
  stage: string
  classification?: string
}

export interface AssessmentStats {
  latestScore: string
  improvement: string
  trend: string
  totalAssessments: number
}

export function useAssessmentHistory() {
  const authStore = useAuthStore()
  const toast = useToast()

  const loading = ref(false)
  const assessments = ref<AssessmentRecord[]>([])
  const selectMode = ref(false)
  const selectedIds = ref<Set<number>>(new Set())
  const swipedId = ref<number | null>(null)
  const deletingIds = ref<Set<number>>(new Set())

  const stats = computed<AssessmentStats>(() => {
    const items = assessments.value
    if (!items.length) return { latestScore: '-', improvement: '-', trend: '暂无数据', totalAssessments: 0 }

    const latest = items[0]?.vasiScore ?? '-'
    let improvement = '-'
    let trend = '首次评估'

    if (items.length >= 2) {
      const first = items[items.length - 1]?.vasiScore
      const last = items[0]?.vasiScore
      if (first != null && last != null && first > 0) {
        const diff = ((first - last) / first) * 100
        improvement = Math.abs(parseFloat(diff.toFixed(1))).toString()
        trend = diff > 0 ? '改善中' : diff < 0 ? '需关注' : '首次评估'
      }
    }

    return { latestScore: String(latest), improvement, trend, totalAssessments: items.length }
  })

  async function load() {
    if (!authStore.isLoggedIn) return
    loading.value = true
    try {
      const res = await vasiApi.getHistory(20, 0)
      assessments.value = res.items.map((item: VasiHistoryItem) => ({
        id: item.id,
        date: item.assessment_date.split('T')[0],
        bodySite: item.body_site,
        vasiScore: item.final_vasi_score ?? item.vasi_score,
        areaPercentage: item.final_area_percentage ?? item.area_percentage,
        stage: item.stage,
        classification: item.classification,
      }))
      selectMode.value = false
      selectedIds.value.clear()
    } catch (err) {
      console.error('Failed to load VASI history:', err)
    } finally {
      loading.value = false
    }
  }

  function toggleSelectMode() {
    selectMode.value = !selectMode.value
    if (!selectMode.value) selectedIds.value.clear()
  }

  function toggleSelect(id: number) {
    if (selectedIds.value.has(id)) selectedIds.value.delete(id)
    else selectedIds.value.add(id)
  }

  function isSwiped(id: number) { return swipedId.value === id }

  function handleTouchStart(e: TouchEvent, touchStartX: { value: number }) {
    if (selectMode.value) return
    touchStartX.value = e.touches[0].clientX
  }

  function handleTouchEnd(e: TouchEvent, id: number, touchStartX: { value: number }) {
    if (selectMode.value) return
    const deltaX = e.changedTouches[0].clientX - touchStartX.value
    if (deltaX < -50) swipedId.value = id
    else if (deltaX > 30) swipedId.value = null
  }

  async function deleteSingle(id: number) {
    if (deletingIds.value.has(id)) return
    deletingIds.value.add(id)
    try {
      await vasiApi.deleteAssessment(id)
      assessments.value = assessments.value.filter(r => r.id !== id)
      swipedId.value = null
      toast.success('已删除')
    } catch {
      toast.error('删除失败')
    } finally {
      deletingIds.value.delete(id)
    }
  }

  async function deleteSelected() {
    if (selectedIds.value.size === 0) return
    deletingIds.value = new Set(selectedIds.value)
    try {
      await vasiApi.deleteAssessmentsBatch([...selectedIds.value])
      assessments.value = assessments.value.filter(r => !selectedIds.value.has(r.id))
      toast.success(`已删除 ${selectedIds.value.size} 条记录`)
      selectMode.value = false
      selectedIds.value.clear()
    } catch {
      toast.error('批量删除失败')
    } finally {
      deletingIds.value = new Set()
    }
  }

  return {
    assessments, loading, stats, selectMode, selectedIds, swipedId, deletingIds,
    load, toggleSelectMode, toggleSelect, isSwiped,
    handleTouchStart, handleTouchEnd, deleteSingle, deleteSelected,
  }
}
