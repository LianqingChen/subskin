/**
 * 五类类别图：与 ml/rgb_segmentation 完全一致的像素值。
 * 0 背景 · 1 正常皮肤 · 2 白斑(脱色) · 3 遮挡 · 4 不可判读 · 255 未标（训练忽略）
 * 传输格式：PNG data URL；上行用 RGBA 画布（R 通道=类别、A=255），下行为 L 灰度 PNG。
 */

export const UNKNOWN = 255
export type ClassValue = 0 | 1 | 2 | 3 | 4 | 255

export interface ClassDef { value: ClassValue; label: string; key: string; color: [number, number, number] | null; hint: string }

export const CLASSES: ClassDef[] = [
  { value: 1, label: '正常皮肤', key: '1', color: [59, 130, 246], hint: '目标部位内颜色正常的皮肤' },
  { value: 2, label: '白斑', key: '2', color: [236, 72, 153], hint: '比周围明显更白、边界可辨认' },
  { value: 3, label: '遮挡', key: '3', color: [245, 158, 11], hint: '头发、手指、饰品、眼/眉等非皮肤器官' },
  { value: 4, label: '不可判读', key: '4', color: [139, 92, 246], hint: '过曝、强反光、模糊处' },
  { value: 0, label: '背景', key: '5', color: [100, 116, 139], hint: '衣物、墙面等非皮肤' },
  { value: 255, label: '未标', key: '0', color: null, hint: '拿不准的过渡带留空，训练时忽略' },
]

export const CLASS_BY_VALUE = new Map(CLASSES.map((c) => [c.value, c]))

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('无法解码标注图层'))
    img.src = src
  })
}

export async function decodeClassMap(dataUrl: string, width: number, height: number): Promise<Uint8Array> {
  const img = await loadImage(dataUrl)
  if (img.naturalWidth !== width || img.naturalHeight !== height) throw new Error('标注图层与照片尺寸不一致')
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('浏览器不支持画布')
  ctx.drawImage(img, 0, 0)
  const rgba = ctx.getImageData(0, 0, width, height).data
  const out = new Uint8Array(width * height)
  for (let i = 0; i < out.length; i++) out[i] = rgba[i * 4]
  return out
}

export function encodeClassMap(map: Uint8Array, width: number, height: number): string {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('浏览器不支持画布')
  const image = ctx.createImageData(width, height)
  for (let i = 0; i < map.length; i++) {
    const o = i * 4
    image.data[o] = image.data[o + 1] = image.data[o + 2] = map[i]
    image.data[o + 3] = 255
  }
  ctx.putImageData(image, 0, 0)
  return canvas.toDataURL('image/png')
}

export function paintOverlay(map: Uint8Array, target: ImageData, alpha: number) {
  const a = Math.round(alpha * 255)
  const lut = new Uint8Array(256 * 4)
  for (const c of CLASSES) {
    if (!c.color) continue
    lut.set([...c.color, c.value === 0 ? Math.round(a * 0.5) : a], c.value * 4)
  }
  const data = target.data
  for (let i = 0; i < map.length; i++) {
    const o = map[i] * 4
    const d = i * 4
    data[d] = lut[o]; data[d + 1] = lut[o + 1]; data[d + 2] = lut[o + 2]; data[d + 3] = lut[o + 3]
  }
}

export function paintDisc(map: Uint8Array, width: number, height: number, cx: number, cy: number, radius: number, value: number) {
  const r2 = radius * radius
  const x0 = Math.max(0, Math.floor(cx - radius)); const x1 = Math.min(width - 1, Math.ceil(cx + radius))
  const y0 = Math.max(0, Math.floor(cy - radius)); const y1 = Math.min(height - 1, Math.ceil(cy + radius))
  for (let y = y0; y <= y1; y++) {
    const dy = y + 0.5 - cy
    for (let x = x0; x <= x1; x++) {
      const dx = x + 0.5 - cx
      if (dx * dx + dy * dy <= r2) map[y * width + x] = value
    }
  }
}

export function paintLine(map: Uint8Array, width: number, height: number, from: [number, number], to: [number, number], radius: number, value: number) {
  const dist = Math.hypot(to[0] - from[0], to[1] - from[1])
  const steps = Math.max(1, Math.ceil(dist / Math.max(1, radius / 2)))
  for (let s = 0; s <= steps; s++) {
    const t = s / steps
    paintDisc(map, width, height, from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t, radius, value)
  }
}

/** 4 连通区域生长：same=同类连通（填充），或按照片颜色容差（魔棒）。返回被选中的像素索引。 */
export function growRegion(
  map: Uint8Array, width: number, height: number, x: number, y: number,
  rgb: Uint8ClampedArray | null, tolerance: number, limit = width * height,
): Int32Array {
  const start = y * width + x
  const seedClass = map[start]
  const seen = new Uint8Array(width * height)
  const out = new Int32Array(limit)
  let count = 0
  const stack = [start]
  seen[start] = 1
  const sr = rgb ? rgb[start * 4] : 0; const sg = rgb ? rgb[start * 4 + 1] : 0; const sb = rgb ? rgb[start * 4 + 2] : 0
  const tol2 = tolerance * tolerance
  while (stack.length && count < limit) {
    const p = stack.pop() as number
    out[count++] = p
    const px = p % width
    const neighbours = [px > 0 ? p - 1 : -1, px < width - 1 ? p + 1 : -1, p - width, p + width]
    for (const n of neighbours) {
      if (n < 0 || n >= map.length || seen[n]) continue
      seen[n] = 1
      if (rgb) {
        const dr = rgb[n * 4] - sr; const dg = rgb[n * 4 + 1] - sg; const db = rgb[n * 4 + 2] - sb
        if (dr * dr + dg * dg + db * db > tol2) continue
      } else if (map[n] !== seedClass) continue
      stack.push(n)
    }
  }
  return out.subarray(0, count)
}

export interface MapStats { counts: Record<number, number>; lesionRatio: number | null; labeledFraction: number }

export function mapStats(map: Uint8Array): MapStats {
  const counts: Record<number, number> = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 255: 0 }
  for (let i = 0; i < map.length; i++) counts[map[i]] = (counts[map[i]] ?? 0) + 1
  const skin = counts[1] + counts[2]
  return {
    counts,
    lesionRatio: skin ? Math.round((counts[2] / skin) * 10000) / 100 : null,
    labeledFraction: map.length ? 1 - counts[255] / map.length : 0,
  }
}
