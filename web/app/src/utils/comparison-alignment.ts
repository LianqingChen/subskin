import type { AlignmentTransform, ImageDimensions, ManualComparisonAlignment } from '@/types/comparison-alignment'
export function identityAlignment(): AlignmentTransform { return { scale: 1, rotation: 0, x: 0, y: 0 } }
/** Same center/fit contract as the backend, in reference-image pixel coordinates. */
export function alignmentMatrix(a: ImageDimensions, b: ImageDimensions, value: AlignmentTransform): number[] {
  const scale = Math.min(a.width / b.width, a.height / b.height) * value.scale
  const angle = value.rotation * Math.PI / 180, c = Math.cos(angle) * scale, s = Math.sin(angle) * scale
  return [c, s, -s, c, a.width * (.5 + value.x) - c * b.width / 2 + s * b.height / 2,
    a.height * (.5 + value.y) - s * b.width / 2 - c * b.height / 2]
}
export function bindManualAlignment(value: AlignmentTransform, referenceId: number, movingId: number): ManualComparisonAlignment {
  return { ...value, version: 'manual-similarity-v1', reference_id: referenceId, moving_id: movingId, confirmed: true }
}
