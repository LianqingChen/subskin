/**
 * API client for image labeling admin endpoints.
 */

import request from './request'

// ── Types ──

export interface LabelItem {
  id: number
  image_url: string
  image_hash?: string
  body_site?: string
  ai_body_site?: string
  ai_is_vitiligo?: boolean
  ai_vitiligo_type?: string
  ai_area_percentage?: number
  ai_confidence?: number
  label_status: string
  training_eligible: boolean
  priority_score?: number
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
}

export interface TrainingDashboard {
  total_samples: number
  train_count: number
  val_count: number
  test_count: number
  pending_sync: number
  last_export_at: string | null
  model_versions: ModelVersion[]
}

export interface ModelVersion {
  version_tag: string
  metrics: Record<string, number>
  sample_count: number
  is_active: boolean
  created_at: string
}

// ── API calls ──

export function fetchLabelList(params: {
  limit?: number
  offset?: number
  label_status?: string
  sort_by?: string
  training_eligible?: boolean
}) {
  return request.get<{ total: number; items: LabelItem[] }>('/vasi/admin/image-labels', { params })
}

export function fetchLabelStats() {
  return request.get<LabelStats>('/vasi/admin/image-labels/stats')
}

export function fetchLabelDetail(id: number) {
  return request.get(`/vasi/admin/image-labels/${id}`)
}

export function fetchLabelAnnotations(id: number) {
  return request.get<{ annotations: any[] }>(`/vasi/admin/image-labels/${id}/annotations`)
}

export function submitLabel(id: number, payload: any) {
  return request.post(`/vasi/admin/image-labels/${id}/label`, payload)
}

export function fetchQueue(params?: { limit?: number; min_confidence?: number }) {
  return request.get<{ total: number; items: LabelItem[] }>('/vasi/admin/image-labels/queue', { params })
}

export function fetchTrainingDashboard() {
  return request.get<TrainingDashboard>('/vasi/admin/training/dashboard')
}

export function syncTrainingSamples() {
  return request.post<{ synced: number }>('/vasi/admin/training/sync-samples')
}

export function startWorkSession() {
  return request.post<{ session_id: number; started_at: string }>('/vasi/admin/labeling/sessions')
}

export function endWorkSession(sessionId: number) {
  return request.put(`/vasi/admin/labeling/sessions/${sessionId}`)
}
