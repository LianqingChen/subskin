/**
 * useVasiHistory — 评估历史管理
 *
 * 职责：历史加载、分页、筛选、选择模式、滑动删除、批量操作
 * 拆分自 useVasiAssessment.ts（637行 → 本文件约200行）
 */
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { vasiApi } from '@/api/vasi'
import type { VasiHistoryItem } from '@/api/vasi'

export function useVasiHistory() {
  const authStore = useAuthStore()
  const toast = useToast()

  // ── State ──
  const recentAssessments = ref<Array<{
    id: number
    date: string
    bodySite: string
    vasiScore: number
    areaPercentage: number
    stage: string
    classification?: string
  }>>([])

  const loadingHistory = ref(false)
  const historyPage = ref(1)
  const historyPageSize = ref(10)
  const historyTotal = ref(0)
  const historyTotalPages = computed(() =>
    historyPageSize.value > 0 ? Math.max(1, Math.ceil(historyTotal.value / historyPageSize.value)) : 1,
  )

  const currentBodySiteFilter = ref<string | null>(null)

  // ── Selection mode ──
  const selectMode = ref(false)
  const selectedIds = ref<Set<number>>(new Set())

  // ── Swipe-to-delete ──
  const swipedId = ref<number | null>(null)
  const deletingIds = ref<Set<number>>(new Set())
  const touchStartX = ref(0)

  // ── API ──
  async function loadHistory(reset = true, bodySite?: string) {
    if (!authStore.isLoggedIn) return
    if (reset) {
      loadingHistory.value = true
      historyPage.value = 1
      currentBodySiteFilter.value = bodySite ?? null
    }
    try {
      const limit = historyPageSize.value
      const offset = reset ? 0 : (historyPage.value - 1) * historyPageSize.value
      const res = await vasiApi.getHistory(limit, offset, currentBodySiteFilter.value || undefined)
      const items = res.items.map((item: VasiHistoryItem) => ({
        id: item.id,
        date: item.assessment_date.split('T')[0],
        bodySite: item.body_site,
        vasiScore: item.final_vasi_score ?? item.vasi_score,
        areaPercentage: item.final_area_percentage ?? item.area_percentage,
        stage: item.stage,
        classification: item.classification,
      }))
      recentAssessments.value = items
      historyTotal.value = typeof res.total === 'number' ? res.total : items.length
      selectMode.value = false
      selectedIds.value.clear()
    } catch (err) {
      console.error('Failed to load VASI history:', err)
    } finally {
      loadingHistory.value = false
    }
  }

  async function goToPage(page: number) {
    const total = historyTotalPages.value
    const next = Math.min(Math.max(1, Math.floor(page)), total)
    if (next === historyPage.value && recentAssessments.value.length > 0) return
    historyPage.value = next
    await loadHistory(false)
  }

  async function setPageSize(size: number) {
    const allowed = [10, 20, 50, 100]
    const n = allowed.includes(size) ? size : 10
    if (n === historyPageSize.value) return
    historyPageSize.value = n
    historyPage.value = 1
    await loadHistory(true)
  }

  // ── Selection ──
  function toggleSelectMode() {
    selectMode.value = !selectMode.value
    if (!selectMode.value) selectedIds.value.clear()
  }

  function toggleSelect(id: number) {
    if (selectedIds.value.has(id)) selectedIds.value.delete(id)
    else selectedIds.value.add(id)
  }

  // ── Swipe ──
  function isSwiped(id: number) { return swipedId.value === id }

  function onTouchStart(e: TouchEvent) {
    if (selectMode.value) return
    touchStartX.value = e.touches[0].clientX
  }

  function onTouchEnd(e: TouchEvent, id: number) {
    if (selectMode.value) return
    const deltaX = e.changedTouches[0].clientX - touchStartX.value
    if (deltaX < -50) swipedId.value = id
    else if (deltaX > 30) swipedId.value = null
  }

  // ── Delete ──
  async function deleteSingle(id: number) {
    if (deletingIds.value.has(id)) return
    deletingIds.value.add(id)
    try {
      await vasiApi.deleteAssessment(id)
      recentAssessments.value = recentAssessments.value.filter(r => r.id !== id)
      historyTotal.value = Math.max(0, historyTotal.value - 1)
      swipedId.value = null
      toast.success('已删除')
      if (recentAssessments.value.length === 0 && historyPage.value > 1) {
        await goToPage(historyPage.value - 1)
      }
    } catch {
      toast.error('删除失败')
    } finally {
      deletingIds.value.delete(id)
    }
  }

  async function deleteSelected() {
    if (selectedIds.value.size === 0) return
    const count = selectedIds.value.size
    deletingIds.value = new Set(selectedIds.value)
    try {
      await vasiApi.deleteAssessmentsBatch([...selectedIds.value])
      recentAssessments.value = recentAssessments.value.filter(r => !selectedIds.value.has(r.id))
      historyTotal.value = Math.max(0, historyTotal.value - count)
      toast.success(`已删除 ${count} 条记录`)
      selectMode.value = false
      selectedIds.value.clear()
      if (recentAssessments.value.length === 0 && historyPage.value > 1) {
        await goToPage(historyPage.value - 1)
      }
    } catch {
      toast.error('批量删除失败')
    } finally {
      deletingIds.value.clear()
    }
  }

  // Sparkline helper
  const sparklineData = computed(() => {
    const items = recentAssessments.value
    if (items.length < 2) return null
    return items.slice(0, 7).reverse().map(r => r.vasiScore)
  })

  return {
    // State
    recentAssessments, loadingHistory,
    historyPage, historyPageSize, historyTotal, historyTotalPages,
    selectMode, selectedIds,
    swipedId, deletingIds,
    sparklineData,
    // Methods
    loadHistory, goToPage, setPageSize,
    toggleSelectMode, toggleSelect,
    isSwiped, onTouchStart, onTouchEnd,
    deleteSingle, deleteSelected,
  }
}
