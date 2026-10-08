/** Shared editor gate: denominator is skin, never skin ∪ lesion. Matches backend. */
export interface MaskMeasurement {
  areaPercentage: number | null
  skinPixels: number
  lesionPixels: number
  outsidePixels: number
  reason: string
}
export function measureMaskPixels(skin: Uint8ClampedArray, lesion: Uint8ClampedArray): MaskMeasurement {
  const result: MaskMeasurement = { areaPercentage: null, skinPixels: 0, lesionPixels: 0, outsidePixels: 0, reason: '' }
  if (!skin.length || skin.length !== lesion.length || skin.length % 4) {
    return { ...result, reason: '标注尺寸不一致，请重新核对' }
  }
  let inside = 0
  for (let i = 3; i < skin.length; i += 4) {
    const inSkin = (skin[i] ?? 0) > 32
    const inLesion = (lesion[i] ?? 0) > 32
    if (inSkin) result.skinPixels++
    if (inLesion) { result.lesionPixels++; if (inSkin) inside++; else result.outsidePixels++ }
  }
  if (!result.skinPixels) result.reason = '请先标出可见皮肤范围'
  else if (result.outsidePixels > Math.max(4, Math.floor(result.lesionPixels * .02))) result.reason = '浅色范围超出皮肤范围，请先修正'
  else result.areaPercentage = Math.round(inside / result.skinPixels * 10000) / 100
  return result
}
