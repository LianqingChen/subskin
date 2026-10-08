export interface AlignmentTransform { scale: number; rotation: number; x: number; y: number }
export interface ManualComparisonAlignment extends AlignmentTransform {
  version: 'manual-similarity-v1'
  reference_id: number
  moving_id: number
  confirmed: true
}
export interface ImageDimensions { width: number; height: number }
