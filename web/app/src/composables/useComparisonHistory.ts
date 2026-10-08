/**
 * useComparisonHistory — 对比报告历史管理
 *
 * 职责：加载「对比报告」列表（report_type=comparison）、分页、部位筛选。
 * 默认：未选部位 = 全量历史；后台按 created_at 倒序；每页默认 5 条。
 */
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { getSkinReports } from '@/api/skin_report'
import type { SkinReportListItem } from '@/api/skin_report'

export function useComparisonHistory() {
  const authStore = useAuthStore()
  const toast = useToast()

  // ── State ──
  const reports = ref<SkinReportListItem[]>([])
  const loading = ref(false)
  const page = ref(1)
  /** 默认每页 5 条 */
  const pageSize = ref(5)
  const total = ref(0)
  const totalPages = computed(() =>
    pageSize.value > 0 ? Math.max(1, Math.ceil(total.value / pageSize.value)) : 1,
  )
  /** 当前部位筛选（null = 全量历史） */
  const currentBodySiteFilter = ref<string | null>(null)

  async function load(reset = true, bodySite?: string) {
    if (!authStore.isLoggedIn) return
    if (reset) {
      loading.value = true
      page.value = 1
      currentBodySiteFilter.value = bodySite ?? null
    }
    try {
      const offset = reset ? 0 : (page.value - 1) * pageSize.value
      const { data } = await getSkinReports({
        limit: pageSize.value,
        offset,
        report_type: 'comparison',
        body_site: currentBodySiteFilter.value || undefined,
      })
      reports.value = data.items
      total.value = typeof data.total === 'number' ? data.total : data.items.length
    } catch (err) {
      console.error('Failed to load comparison report history:', err)
      toast.show('对比报告历史加载失败，请重试', 'error')
    } finally {
      loading.value = false
    }
  }

  async function goToPage(p: number) {
    const next = Math.min(Math.max(1, Math.floor(p)), totalPages.value)
    if (next === page.value && reports.value.length > 0) return
    page.value = next
    await load(false)
  }

  async function setPageSize(size: number) {
    const allowed = [5, 10, 20, 50]
    const n = allowed.includes(size) ? size : 5
    if (n === pageSize.value) return
    pageSize.value = n
    page.value = 1
    await load(true)
  }

  return {
    // State
    reports, loading,
    page, pageSize, total, totalPages,
    currentBodySiteFilter,
    // Methods
    load, goToPage, setPageSize,
  }
}
