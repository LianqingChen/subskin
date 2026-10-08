import { alphaMask, binaryPixels, combineCandidates, MASK_PALETTE, type PhotoMasks } from './photo-mask'
export interface PhotoMaskSources { image: string; skin?: string | null; lesion?: string | null; candidate?: string | null }
export interface LoadedPhotoMasks { image: HTMLImageElement; masks: PhotoMasks }
function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const timer = setTimeout(() => { img.onload = null; img.onerror = null; reject(new Error('照片加载超时，请重试')) }, 15000)
    img.onload = () => { clearTimeout(timer); resolve(img) }
    img.onerror = () => { clearTimeout(timer); reject(new Error('照片或涂层加载失败，请重试')) }
    img.crossOrigin = 'anonymous'
    img.src = url
  })
}
function canvas(width: number, height: number): HTMLCanvasElement {
  const el = document.createElement('canvas'); el.width = width; el.height = height; return el
}
function context(el: HTMLCanvasElement): CanvasRenderingContext2D {
  const ctx = el.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('画布暂不可用，请重试')
  return ctx
}
export async function loadPhotoMasks(sources: PhotoMaskSources): Promise<LoadedPhotoMasks> {
  const [image, skinImage, lesionImage, candidateImage] = await Promise.all([loadImage(sources.image), ...[sources.skin, sources.lesion, sources.candidate].map(url => url ? loadImage(url) : null)])
  if (!image) throw new Error('照片加载失败')
  const scale = Math.min(1, 1024 / Math.max(image.naturalWidth, image.naturalHeight))
  const width = Math.round(image.naturalWidth * scale), height = Math.round(image.naturalHeight * scale)
  const work = canvas(width, height), ctx = context(work)
  const read = (layer: HTMLImageElement | null): Uint8Array => {
    if (!layer) return new Uint8Array(width * height)
    if (Math.abs(layer.naturalWidth / layer.naturalHeight - width / height) > 0.02) throw new Error('涂层与照片不匹配，请重新加载')
    ctx.clearRect(0, 0, width, height); ctx.imageSmoothingEnabled = false; ctx.drawImage(layer, 0, 0, width, height)
    return alphaMask(ctx.getImageData(0, 0, width, height).data)
  }
  const skin = read(skinImage), lesion = combineCandidates(skin, read(lesionImage), read(candidateImage))
  return { image, masks: { width, height, skin, lesion } }
}
interface PaintBounds { x: number; y: number; width: number; height: number }
const renderBuffers = new WeakMap<HTMLCanvasElement, { state: LoadedPhotoMasks; overlay: HTMLCanvasElement; pixels: ImageData }>()
export function renderPhotoMasks(target: HTMLCanvasElement, state: LoadedPhotoMasks, dirty?: PaintBounds): void {
  const { width, height, skin, lesion } = state.masks
  if (target.width !== width) target.width = width
  if (target.height !== height) target.height = height
  let buffer = renderBuffers.get(target)
  if (!buffer || buffer.state !== state) {
    buffer = { state, overlay: canvas(width, height), pixels: new ImageData(width, height) }
    renderBuffers.set(target, buffer); dirty = undefined
  }
  const area = dirty || { x: 0, y: 0, width, height }, pixels = buffer.pixels.data
  for (let y = area.y; y < area.y + area.height; y++) for (let x = area.x; x < area.x + area.width; x++) {
    const i = y * width + x, offset = i * 4, color = lesion[i] ? MASK_PALETTE.lesion : MASK_PALETTE.skin
    pixels[offset] = color[0]; pixels[offset + 1] = color[1]; pixels[offset + 2] = color[2]
    pixels[offset + 3] = skin[i] ? Math.round(255 * MASK_PALETTE.opacity) : 0
  }
  context(buffer.overlay).putImageData(buffer.pixels, 0, 0, area.x, area.y, area.width, area.height)
  const ctx = context(target)
  ctx.save(); ctx.beginPath(); ctx.rect(area.x, area.y, area.width, area.height); ctx.clip()
  ctx.clearRect(area.x, area.y, area.width, area.height)
  ctx.drawImage(state.image, 0, 0, width, height); ctx.drawImage(buffer.overlay, 0, 0); ctx.restore()
}
export function exportPhotoMasks(state: LoadedPhotoMasks): { skinMaskDataUrl: string; lesionMaskDataUrl: string } {
  const { width, height, skin, lesion } = state.masks
  const target = canvas(width, height), ctx = context(target)
  const encode = (mask: Uint8Array) => { ctx.putImageData(new ImageData(binaryPixels(mask), width, height), 0, 0); return target.toDataURL('image/png') }
  return { skinMaskDataUrl: encode(skin), lesionMaskDataUrl: encode(lesion) }
}

/** 上次确认的白斑范围 → 仅描边的琥珀色图。只做参考显示，不参与测量与导出。 */
export async function referenceOutlineUrl(url: string): Promise<string> {
  const image = await loadImage(url)
  const scale = Math.min(1, 1024 / Math.max(image.naturalWidth, image.naturalHeight))
  const width = Math.round(image.naturalWidth * scale), height = Math.round(image.naturalHeight * scale)
  const work = canvas(width, height), ctx = context(work)
  ctx.drawImage(image, 0, 0, width, height)
  const mask = alphaMask(ctx.getImageData(0, 0, width, height).data)
  const out = new ImageData(width, height)
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = y * width + x
    if (!mask[i]) continue
    const edge = x === 0 || y === 0 || x === width - 1 || y === height - 1 || !mask[i - 1] || !mask[i + 1] || !mask[i - width] || !mask[i + width]
    if (!edge) continue
    const o = i * 4
    out.data[o] = 245; out.data[o + 1] = 158; out.data[o + 2] = 11; out.data[o + 3] = 230
  }
  ctx.putImageData(out, 0, 0)
  return work.toDataURL('image/png')
}
