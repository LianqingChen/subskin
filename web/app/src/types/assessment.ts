export interface RefinementEvidence {
  version: string
  status: string
  measurement_eligible?: boolean
  unresolved_region_count?: number
  lesion_regions_total?: number
}
export interface AnnotationReference {
  job_id?: string
  mask_revision?: string
  source?: string
  refine?: RefinementEvidence
  proposal_layer_data_url?: string | null
  protocol: string
  review_state: 'pending' | 'user_reviewed'
  uncertain_layer_data_url?: string | null
  excluded_layer_data_url?: string | null
  uncertain_pixels?: number
  uncertain_percentage?: number
  region_count?: number
}
export interface PhotoMeasurement {
  annotation?: AnnotationReference
  version: string
  status: 'measured' | 'partial' | 'unavailable' | 'legacy'
  scope: string
  area_percentage: number | null
  area_cm2?: number | null
  clinical_vasi?: number | null
  clinical_vasi_valid: boolean
  touches_frame?: boolean
  region_count?: number | null
  regions?: { id: number; pixels: number; centroid: number[]; bbox_pixels: number[]; location: string }[] | null
  region_details_truncated?: boolean
  lesion_pixels?: number
  skin_pixels?: number
  extent?: { width_pixels: number; height_pixels: number; mask_width: number; mask_height: number }
  mask_revision?: string
  reasons: string[]
  color?: { relative_lightness: number; delta_e76: number; calibrated: boolean } | null
  border?: { perimeter_pixels: number; status: string } | null
}
export interface ObservationContext {
  id?: string
  label?: string
  view?: string
  intent?: 'discovery' | 'tracking'
  capture_date?: string
  date_confirmed?: boolean
  baseline_id?: number | null
  background?: string
  calibration?: { points: number[][]; length_mm: number; same_plane: boolean }
}
export interface AssessmentResult {
  id: number
  imageUrl: string | null
  vasiScore: number
  bodySite: string
  areaPercentage: number
  classification: string
  stage: string
  confidence?: number
  measurement?: PhotoMeasurement | null
  observation?: ObservationContext | null
}
