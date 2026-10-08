import type { PhotoMeasurement, ObservationContext } from '@/types/assessment'
import apiClient from './client'

export interface ContourRegion {
  label: string
  polygon: number[][]
  area_percent?: number
}

export interface SuspectedLesion {
  label: string
  center: [number, number]
  estimated_size_percent: number
  confidence: number
}

export interface ReferenceObject {
  type: string
  bbox: [number, number, number, number]
  known_size_mm?: number
}

export interface VasiAssessmentResponse {
  record_status?: string
  measurement?: PhotoMeasurement | null
  observation?: ObservationContext | null
  id: number
  user_id: number
  image_url: string
  vasi_score: number
  body_site: string
  area_percentage: number
  classification: string
  stage: string
  contours: ContourRegion[]
  assessment_date: string
  created_at: string
  precision_level?: string
  precise_available?: boolean
  confidence?: number
  final_vasi_score?: number | null
  final_area_percentage?: number | null
  is_user_corrected?: boolean
  depigmentation_level?: number | null
  reference_objects?: ReferenceObject[] | null
  skin_fitzpatrick?: string | null
  skin_layer_data_url?: string | null
  lesion_layer_data_url?: string | null
  assessment_source?: string | null
  suspected_lesions?: SuspectedLesion[] | null
  skin_region_ratio?: number | null
  visual_features?: VisualFeatures | null
  // 全自动识别自循环
  auto_finalized?: boolean
  consensus?: {
    verdict?: string
    iou?: number | null
    sam_pixels?: number | null
    patient_pixels?: number | null
    verified_candidates?: Array<Record<string, unknown>>
  } | null
  patient_model_version?: string | null
}

export interface VisualFeatureDimension {
  level?: string
  texture?: string
  pattern?: string
  description: string
}

export interface VisualFeatures {
  visibility: VisualFeatureDimension
  color: VisualFeatureDimension
  border: VisualFeatureDimension
  shape: VisualFeatureDimension
  surface: VisualFeatureDimension
  distribution: VisualFeatureDimension
  similarity_note: string
  recommendation: string
}

export interface VasiHistoryItem {
  measurement?: PhotoMeasurement | null
  observation?: ObservationContext | null
  id: number
  image_url: string
  vasi_score: number
  body_site: string
  area_percentage: number
  classification?: string
  stage: string
  assessment_date: string
  final_vasi_score?: number | null
  final_area_percentage?: number | null
  is_user_corrected?: boolean
}

export interface VasiHistoryResponse {
  total: number
  items: VasiHistoryItem[]
}

export interface VasiTrendDataPoint {
  date: string
  vasi_score: number
  stage: string
}

export interface VasiTrendSummary {
  first_score: number | null
  last_score: number | null
  change: number | null
  change_percent: number | null
  trend: string
}

export interface VasiTrendResponse {
  body_site: string
  period: { start: string; end: string }
  data: VasiTrendDataPoint[]
  summary: VasiTrendSummary
}

export interface QualityCheckResult {
  overall: string
  blur_score: number
  blur_ok: boolean
  skin_ratio: number
  skin_ok: boolean
  brightness_mean: number
  lighting_ok: boolean
  resolution: [number, number]
  size_ok: boolean
  suggestions: string[]
}

export const vasiApi = {
  async assess(image: File, bodySite: string, precision: string = 'quick', options: { hasReferenceCard?: boolean; observation?: ObservationContext } = {}): Promise<VasiAssessmentResponse> {
    const capability = await apiClient.get<{ protocol: string }>('/vasi/annotation-protocol')
    if (capability.data.protocol !== 'skin-outline-v1') throw new Error('annotation-protocol-unavailable')
    const formData = new FormData()
    formData.append('annotation_protocol', 'skin-outline-v1')
    formData.append('image', image)
    formData.append('body_site', bodySite)
    formData.append('precision', precision)
    if (options.hasReferenceCard) formData.append('has_reference', 'true')
    const context = options.observation
    if (context) {
      formData.append('intent', context.intent || 'discovery')
      formData.append('observation_label', context.label || '')
      formData.append('view', context.view || '')
      formData.append('background', context.background || '')
      if (context.calibration) formData.append('calibration', JSON.stringify(context.calibration))
      if (context.capture_date) formData.append('capture_date', context.capture_date)
      if (context.baseline_id) formData.append('baseline_id', String(context.baseline_id))
    }
    const { data } = await apiClient.post('/vasi/assess', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // VLM 视觉分析实测 ~76-115s（token-plan 端点），须留足余量；
      // 与 nginx proxy_read_timeout 300s 对齐，避免前端先于后端超时。
      timeout: 300000,
    })
    return data
  },

  async getHistory(limit = 20, offset = 0, bodySite?: string): Promise<VasiHistoryResponse> {
    const params: Record<string, string | number> = { limit, offset }
    if (bodySite) params.body_site = bodySite
    const { data } = await apiClient.get('/vasi/history', { params })
    return data
  },

  async getAssessment(assessmentId: number): Promise<VasiAssessmentResponse> {
    const { data } = await apiClient.get(`/vasi/assess/${assessmentId}`)
    return data
  },

  async getTrend(bodySite?: string, days = 30): Promise<VasiTrendResponse> {
    const params: Record<string, string | number> = { days }
    if (bodySite) params.body_site = bodySite
    const { data } = await apiClient.get('/vasi/trend', { params })
    return data
  },

  async submitContour(assessmentId: number, contours: ContourRegion[], maskImage: string | null = null): Promise<{
    status: string; assessment_id: number; ai_contour_count: number; user_contour_count: number;
    diff_summary: { match: boolean; iou?: number; avg_point_distance?: number; modified: boolean };
    measurement?: PhotoMeasurement; final_area_percentage?: number; final_vasi_score?: number
  }> {
    const body: Record<string, unknown> = { contours }
    if (maskImage) body.mask_image = maskImage
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/contour`, body)
    return data
  },

  async submitTwoLayerMask(assessmentId: number, skinMaskImage: string, lesionMaskImage: string, uncertaintyReviewed = false): Promise<{
    status: string; assessment_id: number;
    diff_summary: { match: boolean; iou?: number; avg_point_distance?: number; modified: boolean };
    measurement?: PhotoMeasurement; final_area_percentage?: number; final_vasi_score?: number
  }> {
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/contour`, { contours: [], skin_mask_image: skinMaskImage, lesion_mask_image: lesionMaskImage, uncertainty_reviewed: uncertaintyReviewed })
    return data
  },

  async deleteAssessment(assessmentId: number): Promise<void> {
    await apiClient.delete(`/vasi/assess/${assessmentId}`)
  },

  async deleteAssessmentsBatch(ids: number[]): Promise<{ deleted: number }> {
    const { data } = await apiClient.delete('/vasi/assess/batch', { data: { ids } })
    return data
  },

  async checkPhotoQuality(image: File): Promise<QualityCheckResult> {
    const formData = new FormData()
    formData.append('image', image)
    const { data } = await apiClient.post('/vasi/check-photo-quality', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    })
    return data
  },

  async preparePromptable(image: File | Blob, cacheKey: string): Promise<{
    status: string; cache_key: string; width: number; height: number; cached: boolean; encode_time_s?: number
  }> {
    const formData = new FormData()
    formData.append('image', image)
    formData.append('cache_key', cacheKey)
    const { data } = await apiClient.post('/vasi/promptable/prepare', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    return data
  },

  async clickPromptable(cacheKey: string, points: Array<{ x: number; y: number; label?: number }>): Promise<{
    mask_polygon: number[][]; mask_b64_png: string; score: number; area_pixels: number;
    area_percent_in_image: number; width: number; height: number
  }> {
    const { data } = await apiClient.post('/vasi/promptable/click', {
      cache_key: cacheKey,
      points: points.map(p => ({ x: p.x, y: p.y, label: p.label ?? 1 })),
    }, { timeout: 15000 })
    return data
  },

  async refineCircle(cacheKey: string, circle: { center_x: number; center_y: number; radius_x: number; radius_y: number }): Promise<{
    mask_polygon: number[][]; mask_b64_png: string; score: number; confidence: number;
    area_pixels: number; area_percent_in_image: number; width: number; height: number
  }> {
    const { data } = await apiClient.post('/vasi/promptable/refine-circle', {
      cache_key: cacheKey,
      circle,
    }, { timeout: 15000 })
    return data
  },

  async finalizeAssessment(assessmentId: number): Promise<{ status: string; message: string }> {
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/finalize`)
    return data
  },

  async abandonAssessment(assessmentId: number): Promise<{ status: string }> {
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/abandon`)
    return data
  },

  /** 白斑病灶轨迹（每处白斑的身份与面积变化，统一画布 IoU 匹配） */
  async getTracks(assessmentId: number): Promise<{
    assessment_id: number
    tracks: Record<string, Array<{
      photo_ref: string
      photo_date: string | null
      area_canvas_px: number | null
      area_normalized: number | null
      status: string
      source: string | null
      confidence: number | null
    }>>
  }> {
    const { data } = await apiClient.get(`/vasi/assess/${assessmentId}/tracks`)
    return data
  },

  /** 白斑识别自学习状态（患者模型/样本数/自动终审率） */
  async getSelfLearningStatus(): Promise<{
    patient_models: Array<{
      body_site: string
      version: string | null
      training_source: string | null
      sample_count: number
      shadow_dice: number | null
      trained_at: string | null
    }>
    stats: {
      recent_assessments: number
      auto_finalized: number
      auto_finalize_rate: number | null
      user_corrected: number
    }
    note: string
  }> {
    const { data } = await apiClient.get('/vasi/self-learning/status')
    return data
  },
}

export interface FeedbackPrompt {
  should_ask: boolean
  confidence: number
  title: string
  question: string
  options: string[]
  reason: string
}

export const vasiFeedbackApi = {
  async getPrompt(assessmentId: number): Promise<FeedbackPrompt> {
    const { data } = await apiClient.get(`/vasi/assess/${assessmentId}/feedback/prompt`)
    return data
  },

  async submitRating(assessmentId: number, rating: number, comment?: string, issues?: string[]): Promise<{ status: string; message: string }> {
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/feedback/rating`, { rating, comment, issues })
    return data
  },

  async submitActiveQuery(assessmentId: number, selectedOption: string, comment?: string): Promise<{ status: string; message: string }> {
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/feedback/active-query`, { selected_option: selectedOption, comment })
    return data
  },

  async recordStay(assessmentId: number, durationSeconds: number): Promise<{ status: string }> {
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/feedback/stay`, { duration_seconds: durationSeconds })
    return data
  },

  async recordShare(assessmentId: number): Promise<{ status: string }> {
    const { data } = await apiClient.post(`/vasi/assess/${assessmentId}/feedback/share`)
    return data
  },
}

// ── 照片对齐（按部位锚点：面部=瞳距 / 手部=掌宽 / 躯干四肢=肩宽，滑块对比用）──

export interface PhotoAlignItem {
  index: number
  found: boolean
  kind?: 'face' | 'hand' | 'pose'
  anchor_a?: [number, number]
  anchor_b?: [number, number]
  anchor_mid?: [number, number]
  anchor_dist?: number
  scale?: number
  rotate_deg?: number
  width?: number
  height?: number
}

export interface PhotoAlignResult {
  ok: boolean
  note?: string
  ref_index?: number
  kind?: 'face' | 'hand' | 'pose'
  canvas?: {
    width: number
    height: number
    anchor_mid: [number, number]
    angle_deg: number
    anchor_dist: number
  }
  items: PhotoAlignItem[]
}

/** 请求后端计算多张照片的对齐参数（服务端不落盘，仅返回数值参数） */
export async function alignPhotos(files: Blob[], bodySite?: string): Promise<PhotoAlignResult> {
  const formData = new FormData()
  files.forEach((b, i) => formData.append('files', b, `photo${i}.jpg`))
  if (bodySite) formData.append('body_site', bodySite)
  const { data } = await apiClient.post('/vasi/photo-align', formData, { timeout: 60000 })
  return data
}
