import apiClient from './client'

export interface ImageLabelAnnotation {
  source: string
  region_index: number
  body_site?: string
  is_vitiligo?: boolean
  vitiligo_type?: string
  vitiligo_stage?: string
  area_percentage?: number
  depigmentation_level?: number
  region_contour?: string
  region_bbox?: string
  mask_data?: string
  skin_mask_data?: string
  confidence?: number
  notes?: string
}

export interface ImageLabelDetail {
  id: number
  assessment_id?: number
  original_user_id?: number
  image_url: string
  image_key?: string
  image_hash?: string
  is_user_deleted: boolean
  is_face_detected: boolean
  is_face_blurred: boolean
  is_phi_removed: boolean

  ai_body_site?: string
  ai_is_vitiligo?: boolean
  ai_vitiligo_type?: string
  ai_vitiligo_stage?: string
  ai_area_percentage?: number
  ai_vasi_score?: number
  ai_confidence?: number

  user_body_site?: string
  user_is_vitiligo?: boolean
  user_vitiligo_type?: string
  user_area_percentage?: number
  user_vasi_score?: number
  user_depigmentation_level?: number
  user_notes?: string

  admin_body_site?: string
  admin_is_vitiligo?: boolean
  admin_vitiligo_type?: string
  admin_vitiligo_stage?: string
  admin_area_percentage?: number
  admin_vasi_score?: number
  admin_depigmentation_level?: number
  admin_notes?: string
  labeled_by?: number
  labeled_at?: string

  label_status: string
  training_eligible: boolean
  training_set_split?: string

  annotated_image_path?: string
  annotated_image_url?: string
  annotated_layers_path?: string

  annotations: ImageLabelAnnotation[]

  created_at?: string
  updated_at?: string
}

export interface ImageLabelListItem {
  id: number
  assessment_id?: number
  image_url: string
  image_hash?: string
  body_site?: string
  ai_is_vitiligo?: boolean
  ai_vitiligo_type?: string
  ai_area_percentage?: number
  admin_is_vitiligo?: boolean
  admin_vitiligo_type?: string
  admin_area_percentage?: number
  label_status: string
  is_user_deleted: boolean
  training_eligible: boolean
  created_at?: string
  labeled_at?: string
}

export interface LabelStats {
  total: number
  pending: number
  labeled: number
  skipped: number
  rejected: number
  training_ready: number
  user_deleted: number
}

export interface LabelChoices {
  body_sites: string[]
  vitiligo_types: string[]
  stages: string[]
  label_statuses: string[]
  training_splits: string[]
}

export function getImageProxyUrl(labelId: number): string {
  const token = (typeof window !== 'undefined') ? window.localStorage.getItem('subskin_token') : null
  const baseURL = apiClient.defaults.baseURL || ''
  return `${baseURL}/vasi/admin/image-labels/${labelId}/image?access_token=${token || ''}`
}

export const imageLabelApi = {
  async list(params?: {
    limit?: number
    offset?: number
    label_status?: string
    is_vitiligo?: boolean
    body_site?: string
    training_eligible?: boolean
    is_user_deleted?: boolean
  }): Promise<{ total: number; items: ImageLabelListItem[] }> {
    const { data } = await apiClient.get('/vasi/admin/image-labels', { params })
    return data
  },

  async stats(): Promise<LabelStats> {
    const { data } = await apiClient.get('/vasi/admin/image-labels/stats')
    return data
  },

  async getDetail(labelId: number): Promise<ImageLabelDetail> {
    const { data } = await apiClient.get(`/vasi/admin/image-labels/${labelId}`)
    return data
  },

  async submitLabel(labelId: number, payload: {
    body_site?: string
    is_vitiligo?: boolean
    vitiligo_type?: string
    vitiligo_stage?: string
    area_percentage?: number
    vasi_score?: number
    depigmentation_level?: number
    notes?: string
    training_eligible?: boolean
    annotations?: ImageLabelAnnotation[]
  }): Promise<{ status: string; label_id: number; changes: number }> {
    const { data } = await apiClient.post(`/vasi/admin/image-labels/${labelId}/label`, payload)
    return data
  },

  async batchUpdateStatus(ids: number[], labelStatus: string, trainingEligible?: boolean): Promise<{ status: string; updated: number }> {
    const { data } = await apiClient.post('/vasi/admin/image-labels/batch-status', {
      ids,
      label_status: labelStatus,
      training_eligible: trainingEligible,
    })
    return data
  },

  async syncAssessments(): Promise<{ status: string; created: number; skipped: number; total_assessments: number }> {
    const { data } = await apiClient.post('/vasi/admin/image-labels/sync-assessments')
    return data
  },

  async exportTraining(params?: {
    split_ratio?: string
    include_ai?: boolean
    include_user?: boolean
    only_admin_labeled?: boolean
  }): Promise<{
    total_count: number
    train_count: number
    val_count: number
    test_count: number
    export_url?: string
  }> {
    const { data } = await apiClient.post('/vasi/admin/image-labels/training-export', params)
    return data
  },

  async getChoices(): Promise<LabelChoices> {
    const { data } = await apiClient.get('/vasi/admin/image-labels/choices')
    return data
  },

  async getHistory(labelId: number): Promise<{
    label_id: number
    history: Array<{
      id: number
      operator_id: number
      action: string
      field_name?: string
      old_value?: string
      new_value?: string
      created_at?: string
    }>
  }> {
    const { data } = await apiClient.get(`/vasi/admin/image-labels/${labelId}/history`)
    return data
  },

  async aiPretrain(labelId: number): Promise<AiPretrainResponse> {
    const { data } = await apiClient.post(`/vasi/admin/image-labels/${labelId}/ai-pretrain`)
    return data
  },
}

export interface AiPretrainResponse {
  contours: Array<{
    polygon: number[][]
    body_site?: string
    area_percentage?: number
    confidence?: number
    [key: string]: any
  }>
  body_site?: string
  is_vitiligo?: boolean
  vitiligo_type?: string
  vitiligo_stage?: string
  area_percentage?: number
  vasi_score?: number
  depigmentation_level?: number
  confidence?: number
  lesion_layer_data_url?: string | null
  skin_layer_data_url?: string | null
  suspected_lesions?: Array<Record<string, any>> | null
  source?: string | null
  duration_ms?: number
}