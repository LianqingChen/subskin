/**
 * useQuickPhotoCompare — 相册照片快速对比
 *
 * 职责：两张相册照片的本地滑块对比（不上传），以及一键转 AI 对比报告
 * （上传 → 存为私有对比照片 → 生成 comparison 报告 → 返回报告 id）。
 */
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { AlignmentTransform } from '@/types/comparison-alignment'
import { bindManualAlignment } from '@/utils/comparison-alignment'
import { BODY_SITES } from '@/constants/bodySites'
import { communityApi } from '@/api/community'
import { createComparisonReport, saveComparisonPhotos, getComparisonCapabilities } from '@/api/skin_report'

// One-shot in-memory handoff for the home gallery's multi-selection.
let pendingPhotos: File[] = []
export function queueComparisonPhotos(files: File[]) {
  pendingPhotos = []
  if (files.length !== 2) throw new Error('白斑对比请选择两张照片')
  pendingPhotos = [...files]
}
export function takeComparisonPhotos(): File[] { const files = pendingPhotos; pendingPhotos = []; return files }

export function useQuickPhotoCompare() {
  const generating = ref(false), auth = useAuthStore()

  /** 两张照片生成 AI 对比报告，返回报告 id
   *  @param photos 按拍摄日期升序的照片（file + date），随照片一并保存
   *  @param bodySite 测评页选中的身体部位，照片默认按此打标
   */
  async function generateReport(
    photos: Array<{ file: File; date: string }>,
    bodySite?: string,
    alignment?: AlignmentTransform | null,
  ): Promise<number> {
    if (generating.value) throw new Error('busy')
    if (photos.length !== 2 || !Object.values(BODY_SITES).some(site => site.id === bodySite)) throw new Error('请选择同一部位的两张照片')
    const owner = auth.user?.id
    const checkOwner = () => { if (!auth.isLoggedIn || auth.user?.id !== owner) throw new Error('会话已变化，请重新选择照片') }
    checkOwner()
    generating.value = true
    try {
      if (alignment) {
        const capabilities = await getComparisonCapabilities()
        if (!capabilities.manual_alignment || capabilities.version !== 'manual-similarity-v1') throw new Error('手动对齐分析尚未启用')
      }
      checkOwner()
      const urls: string[] = []
      for (const p of photos) {
        checkOwner()
        const up = await communityApi.uploadImage(p.file)
        checkOwner()
        urls.push(up.image_url)
      }
      const saved = await saveComparisonPhotos(
        urls.map((u, i) => ({
          image_url: u,
          body_site: bodySite || null,
          capture_date: photos[i].date,
        })),
      )
      checkOwner()
      const ids = saved.data.image_ids
      if (ids.length !== 2) throw new Error('照片尚未保存完整，请重试')
      const { data } = await createComparisonReport({ image_ids: ids, manual_alignment: alignment ? bindManualAlignment(alignment, ids[0], ids[1]) : undefined })
      checkOwner()
      return data.id
    } finally {
      generating.value = false
    }
  }

  return { generating, generateReport }
}
