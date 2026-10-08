import { loadPhotoMasks, renderPhotoMasks } from '@/utils/photo-mask-canvas'
import { toProtectedFileUrl } from '@/utils/file-url'
function png(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('图片生成失败')), 'image/png'))
}
/** Same binary masks and display palette as the editor. Original photo stays unmodified. */
export async function journalShareImages(image: string, skin: string, lesion: string, poster: Blob): Promise<Blob[]> {
  const state = await loadPhotoMasks({ image: toProtectedFileUrl(image), skin: toProtectedFileUrl(skin), lesion: toProtectedFileUrl(lesion) })
  const canvas = document.createElement('canvas'); renderPhotoMasks(canvas, state)
  const annotated = await png(canvas)
  canvas.width = state.image.naturalWidth; canvas.height = state.image.naturalHeight
  const ctx = canvas.getContext('2d'); if (!ctx) throw new Error('图片生成失败')
  ctx.drawImage(state.image, 0, 0)
  const original = await png(canvas)
  return [poster, annotated, original]
}
