import { onBeforeUnmount, ref } from 'vue'
import type { RGBSelector } from '@/api/rgb-segmentation'
import { RGBTaskError } from '@/api/rgb-segmentation'
import { assessmentError } from '@/utils/assessment-errors'
import { useToast } from '@/composables/useToast'
import { paintMask, readMask } from '@/utils/lesionMaskTools'

export function useRemoteMaskSelection(options: {
  selector: () => RGBSelector | undefined
  skin: () => HTMLCanvasElement | null
  lesion: () => HTMLCanvasElement | null
  changed: () => void
}) {
  const pending = ref(false)
  const toast = useToast()
  let controller: AbortController | null = null
  async function select(x: number, y: number) {
    const selector = options.selector(), skin = options.skin(), lesion = options.lesion()
    if (!selector || !skin || !lesion || pending.value) return
    controller = new AbortController()
    const signal = controller.signal
    const skinBefore = skin.toDataURL('image/png'), lesionBefore = lesion.toDataURL('image/png')
    pending.value = true
    try {
      const dataUrl = await selector({ x: (Math.min(skin.width - 1, Math.max(0, Math.round(x))) + .5) / skin.width, y: (Math.min(skin.height - 1, Math.max(0, Math.round(y))) + .5) / skin.height, skinMask: skinBefore, signal })
      if (signal.aborted) return
      const image = await new Promise<HTMLImageElement>((resolve, reject) => {
        const element = new Image(); element.onload = () => resolve(element); element.onerror = reject; element.src = dataUrl
      })
      if (signal.aborted || options.skin() !== skin || options.lesion() !== lesion) return
      if (skin.toDataURL('image/png') !== skinBefore || lesion.toDataURL('image/png') !== lesionBefore) {
        toast.warning('标注已变化，请重新点选'); return
      }
      if (image.naturalWidth !== skin.width || image.naturalHeight !== skin.height) throw new RGBTaskError('REVISION_CONFLICT')
      const canvas = document.createElement('canvas'); canvas.width = skin.width; canvas.height = skin.height
      const ctx = canvas.getContext('2d'), target = lesion.getContext('2d')
      if (!ctx || !target) return
      ctx.drawImage(image, 0, 0)
      const mask = readMask(canvas), allowed = readMask(skin)
      for (let i = 0; i < mask.length; i++) mask[i] = mask[i] && allowed[i] ? 1 : 0
      paintMask(target, mask, skin.width, skin.height, '#00aa64')
      options.changed()
    } catch (error) {
      if (!signal.aborted) toast.warning(error instanceof RGBTaskError ? error.message : assessmentError(error, '交互分割暂未完成，可使用画笔调整'))
    } finally { pending.value = false }
  }
  onBeforeUnmount(() => controller?.abort())
  return { pending, select }
}
