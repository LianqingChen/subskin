/** Display palette never changes the binary masks used for measurement. */
export const MASK_PALETTE = { skin: [147, 197, 253], lesion: [249, 168, 212], opacity: 0.4 } as const
export type PhotoMaskTool = 'skin' | 'lesion' | 'eraser' | 'refine'
export interface PhotoMasks { width: number; height: number; skin: Uint8Array; lesion: Uint8Array }
export function alphaMask(rgba: Uint8ClampedArray): Uint8Array {
  return Uint8Array.from({ length: rgba.length / 4 }, (_, i) => rgba[i * 4 + 3] > 32 ? 1 : 0)
}
export function combineCandidates(skin: Uint8Array, lesion: Uint8Array, candidate: Uint8Array): Uint8Array {
  return Uint8Array.from(skin, (value, i) => value && (lesion[i] || candidate[i]) ? 1 : 0)
}
export function overlayPixels(masks: PhotoMasks): Uint8ClampedArray {
  const out = new Uint8ClampedArray(masks.width * masks.height * 4)
  for (let i = 0; i < masks.skin.length; i++) {
    if (!masks.skin[i]) continue
    const color = masks.lesion[i] ? MASK_PALETTE.lesion : MASK_PALETTE.skin
    const offset = i * 4
    out[offset] = color[0]; out[offset + 1] = color[1]; out[offset + 2] = color[2]; out[offset + 3] = Math.round(255 * MASK_PALETTE.opacity)
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
  }
}
