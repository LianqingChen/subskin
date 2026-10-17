/** Display palette never changes the binary masks used for measurement. */
export const MASK_PALETTE = { skin: [147, 197, 253], lesion: [249, 168, 212], uncertain: [240, 143, 0], opacity: 0.4 } as const
export type PhotoMaskTool = 'skin' | 'lesion' | 'eraser' | 'refine' | 'remove'
export interface PhotoMasks { width: number; height: number; skin: Uint8Array; lesion: Uint8Array; uncertain?: Uint8Array }
export function alphaMask(rgba: Uint8ClampedArray): Uint8Array {
  return Uint8Array.from({ length: rgba.length / 4 }, (_, i) => rgba[i * 4 + 3] > 32 ? 1 : 0)
}
export function combineCandidates(skin: Uint8Array, lesion: Uint8Array, candidate: Uint8Array): Uint8Array {
  return Uint8Array.from(skin, (value, i) => value && (lesion[i] || candidate[i]) ? 1 : 0)
}
/** Keep confirmed lesion separate. Candidates stay uncertain until the user adopts them. */
export function separateCandidates(skin: Uint8Array, lesion: Uint8Array, candidate: Uint8Array): { lesion: Uint8Array; uncertain: Uint8Array } {
  const next = new Uint8Array(lesion.length), uncertain = new Uint8Array(lesion.length)
  for (let i = 0; i < skin.length; i++) {
    if (!skin[i]) continue
    if (lesion[i]) next[i] = 1
    else if (candidate[i]) uncertain[i] = 1
  }
  return { lesion: next, uncertain }
}
export function adoptUncertain(m: PhotoMasks): void {
  const u = m.uncertain
  if (!u) return
  for (let i = 0; i < m.lesion.length; i++) {
    if (u[i] && m.skin[i]) m.lesion[i] = 1
    u[i] = 0
  }
}
export function discardUncertain(m: PhotoMasks): void {
  m.uncertain?.fill(0)
}
/** Tap-to-remove: clear the 8-connected lesion (or candidate) region under the point. Skin is kept. */
export function removeRegionAt(m: PhotoMasks, x: number, y: number): number {
  const px = Math.floor(x), py = Math.floor(y)
  if (px < 0 || py < 0 || px >= m.width || py >= m.height) return 0
  const start = py * m.width + px
  const layer = m.lesion[start] ? m.lesion : m.uncertain?.[start] ? m.uncertain : null
  if (!layer) return 0
  const stack = [start]
  let removed = 0
  layer[start] = 0
  while (stack.length) {
    const i = stack.pop() as number
    removed++
    const cx = i % m.width, cy = (i - cx) / m.width
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const nx = cx + dx, ny = cy + dy
      if (nx < 0 || ny < 0 || nx >= m.width || ny >= m.height) continue
      const j = ny * m.width + nx
      if (layer[j]) { layer[j] = 0; stack.push(j) }
    }
  }
  return removed
}
export function replaceLayer(m: PhotoMasks, layer: 'lesion' | 'uncertain', incoming: Uint8Array): void {
  const dest = layer === 'lesion' ? m.lesion : (m.uncertain || (m.uncertain = new Uint8Array(m.lesion.length)))
  for (let i = 0; i < dest.length; i++) {
    const on = incoming[i] && m.skin[i] ? 1 : 0
    if (layer === 'uncertain') dest[i] = on && !m.lesion[i] ? 1 : 0
    else { dest[i] = on; if (m.uncertain && on) m.uncertain[i] = 0 }
  }
}
export function overlayPixels(masks: PhotoMasks): Uint8ClampedArray {
  const out = new Uint8ClampedArray(masks.width * masks.height * 4)
  const uncertain = masks.uncertain
  for (let i = 0; i < masks.skin.length; i++) {
    if (!masks.skin[i]) continue
    const amber = !masks.lesion[i] && !!uncertain?.[i]
    const color = masks.lesion[i] ? MASK_PALETTE.lesion : amber ? MASK_PALETTE.uncertain : MASK_PALETTE.skin
    const offset = i * 4
    out[offset] = color[0]; out[offset + 1] = color[1]; out[offset + 2] = color[2]
    out[offset + 3] = amber ? 140 : Math.round(255 * MASK_PALETTE.opacity)
  }
  return out
}
export function binaryPixels(mask: Uint8Array): Uint8ClampedArray {
  const out = new Uint8ClampedArray(mask.length * 4)
  for (let i = 0; i < mask.length; i++) if (mask[i]) {
    const offset = i * 4
    out[offset] = 255; out[offset + 1] = 255; out[offset + 2] = 255; out[offset + 3] = 255
  }
  return out
}
/** Skin stores total skin. Visible normal skin = skin minus lesion; brushes replace the visible class. */
export function paintPhotoMasks(m: PhotoMasks, layer: 'skin' | 'lesion', erase: boolean, from: [number, number], to: [number, number], radius: number): void {
  const dx = to[0] - from[0], dy = to[1] - from[1], length = dx * dx + dy * dy
  const x0 = Math.max(0, Math.floor(Math.min(from[0], to[0]) - radius)), x1 = Math.min(m.width - 1, Math.ceil(Math.max(from[0], to[0]) + radius))
  const y0 = Math.max(0, Math.floor(Math.min(from[1], to[1]) - radius)), y1 = Math.min(m.height - 1, Math.ceil(Math.max(from[1], to[1]) + radius))
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    const t = length ? Math.max(0, Math.min(1, ((x - from[0]) * dx + (y - from[1]) * dy) / length)) : 0
    if ((x - from[0] - t * dx) ** 2 + (y - from[1] - t * dy) ** 2 > radius ** 2) continue
    const i = y * m.width + x
    if (layer === 'skin') { m.skin[i] = erase ? 0 : 1; m.lesion[i] = 0 }
    else { m.lesion[i] = erase ? 0 : 1; if (!erase) m.skin[i] = 1 }
    if (m.uncertain) m.uncertain[i] = 0
  }
}
