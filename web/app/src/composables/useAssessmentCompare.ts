/**
 * useAssessmentCompare — 历史评估多选 → 生成 AI 对比报告
 *
 * 职责：校验选中评估（数量/同部位）、调用对比报告接口、跳转报告详情页轮询。
 * 快速对比（2 条即时滑块对比）走 vasi-compare 路由，不经本 composable。
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { createComparisonReport } from '@/api/skin_report'

export interface HistoryItem {
  id: number
  date: string
  bodySite: string
  vasiScore: number
  areaPercentage: number
  stage: string
  classification?: string
}

/** 对比报告最多纳入的评估条数（与照片对比上限对齐） */
export const MAX_COMPARE_ITEMS = 2

export function useAssessmentCompare() {
  const router = useRouter()
  const toast = useToast()
  const generating = ref(false)

  /** 选中项是否跨部位（跨部位无法直接生成对比报告） */
  function hasMixedSites(items: HistoryItem[]) {
    return new Set(items.map((i) => i.bodySite).filter(Boolean)).size > 1
  }

  const canGenerate = (count: number) => count >= 2 && count <= MAX_COMPARE_ITEMS

  async function generateReport(selected: HistoryItem[]) {
    if (generating.value) return
    if (!canGenerate(selected.length)) {
      toast.warning('请选择两条同部位记录')
      return
    }
    if (hasMixedSites(selected)) {
      toast.warning('已选评估包含多个部位，请选择同一部位进行对比')
      return
    }
    generating.value = true
    try {
      const { data } = await createComparisonReport({
        vasi_ids: selected.map((i) => i.id),
      })
      toast.show('已开始生成，约需 1-2 分钟', 'success')
      router.push({ name: 'skin-report-view', params: { id: data.id } })
    } catch (e: any) {
      toast.show(e?.response?.data?.detail || '生成失败，请重试', 'error')
    } finally {
      generating.value = false
    }
  }

  return {
    generating,
    hasMixedSites,
    canGenerate,
    generateReport,
  }
}
