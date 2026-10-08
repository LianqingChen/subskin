// 打标模块共享类型 — 供工作区、蒙层编辑器、多白斑管理等组件使用

export interface AdminAnnotationItem {
  source: 'ai' | 'admin'
  region_index: number
  body_site: string | null
  is_vitiligo: boolean | null
  vitiligo_type: string | null
  vitiligo_stage: string | null
  area_percentage: number | null
  depigmentation_level: number | null
  region_contour: string | null  // JSON string
  region_bbox: string | null  // JSON string
  mask_data: string | null  // PNG data URL
  skin_mask_data?: string | null  // skin mask PNG
  confidence: number | null
  notes: string | null
}

export interface LabelingSubmitPayload {
  body_site: string | null
  is_vitiligo: boolean | null
  vitiligo_type: string | null
  vitiligo_stage: string | null
  area_percentage: number | null
  vasi_score: number | null
  depigmentation_level: number | null
  notes: string | null
  training_eligible: boolean | null
  annotations: AdminAnnotationItem[]
  annotated_image?: string | null  // composite: original photo + brush overlays baked in
}
