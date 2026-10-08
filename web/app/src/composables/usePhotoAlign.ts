/**
 * usePhotoAlign — 照片白斑对比的「按部位锚点自动对齐」。
 *
 * 调用后端 MediaPipe 关键点接口（面部=瞳距 / 手部=掌宽 / 躯干四肢=肩宽），
 * 拿到每张照片的缩放/旋转/锚点参数后，在前端用 canvas 按相似变换重绘：
 *   1. 以参考照片的锚点中点为锚；
 *   2. 按锚点距离比例缩放（同一部位同样大小）；
 *   3. 旋转使锚点连线与参考照片同角度（同高同点）。
 * 重绘画布统一使用参考照片的尺寸，两张图逐像素对齐，滑块对比才真正对得上。
 *
 * 上传前把照片最长边压缩到 1600px（对齐只需几何参数，展示画布本身最多 1400px），
 * 减少移动端上行流量与后端耗时；服务端不落盘、仅返回数值参数。
 */
import { ref } from 'vue'
import { alignPhotos } from '@/api/vasi'
import type { PhotoAlignItem, PhotoAlignResult } from '@/api/vasi'

const MAX_UPLOAD_SIDE = 1600
const MAX_CANVAS_SIDE = 1400

/** 压缩照片用于上传（EXIF 方向已由 createImageBitmap 转正，与后端检测一致） */
async function downscaleForUpload(file: File): Promise<Blob | null> {
  try {
    const bmp = await createImageBitmap(file)
    const s = Math.min(1, MAX_UPLOAD_SIDE / Math.max(bmp.width, bmp.height))
    if (s >= 1) {
      bmp.close?.()
      return file
    }
    const cw = Math.max(1, Math.round(bmp.width * s))
    const ch = Math.max(1, Math.round(bmp.height * s))
    const cv = document.createElement('canvas')
    cv.width = cw
    cv.height = ch
    const ctx = cv.getContext('2d')
    if (!ctx) {
      bmp.close?.()
      return null
    }
    ctx.drawImage(bmp, 0, 0, cw, ch)
    bmp.close?.()
    return await new Promise<Blob | null>((resolve) => cv.toBlob((b) => resolve(b), 'image/jpeg', 0.9))
  } catch {
    return null
  }
}

/** 按对齐参数把照片重绘到参考画布（锚点重合 + 锚距比例缩放 + 锚线旋转） */
async function drawAligned(file: File, res: PhotoAlignResult, item: PhotoAlignItem): Promise<string | null> {
  const canvas = res.canvas
  if (!canvas) return null
  try {
    const bmp = await createImageBitmap(file)
    const k = Math.min(1, MAX_CANVAS_SIDE / Math.max(canvas.width, canvas.height))
    const cw = Math.round(canvas.width * k)
    const ch = Math.round(canvas.height * k)
    const cv = document.createElement('canvas')
    cv.width = cw
    cv.height = ch
    const ctx = cv.getContext('2d')
    if (!ctx) {
      bmp.close?.()
      return null
    }
    ctx.imageSmoothingQuality = 'high'
    // 相似变换：参考锚点 → 旋转（锚线对齐参考角度）→ 锚距比例缩放 → 照片锚点
    ctx.translate(canvas.anchor_mid[0] * k, canvas.anchor_mid[1] * k)
    ctx.rotate(((item.rotate_deg ?? 0) * Math.PI) / 180)
    const s = (item.scale ?? 1) * k
    ctx.scale(s, s)
    ctx.translate(-(item.anchor_mid?.[0] ?? 0), -(item.anchor_mid?.[1] ?? 0))
    ctx.drawImage(bmp, 0, 0, item.width ?? bmp.width, item.height ?? bmp.height)
    bmp.close?.()
    return cv.toDataURL('image/jpeg', 0.92)
  } catch {
    return null
  }
}

export function usePhotoAlign() {
  const status = ref<'idle' | 'aligning' | 'done' | 'failed'>('idle')
  const note = ref('')
  const kind = ref<'face' | 'hand' | 'pose' | null>(null)
  let runId = 0

  /**
   * 对齐一组照片（按传入顺序，index 与 files 下标对应）。
   * @returns Map<fileIndex, dataURL>；失败/部分失败返回已成功部分，status/note 记录状态
   */
  async function align(files: File[], bodySite?: string): Promise<Map<number, string>> {
    const id = ++runId
    status.value = 'aligning'
    note.value = ''
    const map = new Map<number, string>()
    if (files.length < 2) {
      status.value = 'idle'
      return map
    }
    try {
      const blobs = await Promise.all(files.map(downscaleForUpload))
      if (blobs.some((b) => !b)) {
        if (id !== runId) return map
        status.value = 'failed'
        note.value = '照片预处理失败，未自动对齐'
        return map
      }
      const res = await alignPhotos(blobs as Blob[], bodySite || undefined)
      if (id !== runId) return map
      if (res.ok) {
        kind.value = res.kind ?? null
        for (const item of res.items) {
          if (!item.found || !files[item.index]) continue
          const url = await drawAligned(files[item.index], res, item)
          if (url) map.set(item.index, url)
        }
      }
      if (id !== runId) return map
      if (!res.ok) {
        status.value = 'failed'
        note.value = res.note || '未检测到同一部位特征，未自动对齐'
      } else if (map.size < files.length) {
        status.value = 'done'
        note.value = '部分照片未检测到同一部位特征，已按原样展示'
      } else {
        status.value = 'done'
        note.value = ''
      }
      return map
    } catch {
      if (id !== runId) return map
      status.value = 'failed'
      note.value = '自动对齐失败，可手动调整'
      return map
    }
  }

  function reset() {
    runId++
    status.value = 'idle'
    note.value = ''
    kind.value = null
  }

  return { status, note, kind, align, reset }
}
