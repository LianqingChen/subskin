import request from './request'
import type {
  LabelingChoices, LabelingProgress, SubmitPayload, TaskDetail, TaskFilters, TaskList, TaskStats, UploadResult,
} from '@/types/labeling'

const BASE = '/vasi/admin/labeling'

export async function fetchChoices(): Promise<LabelingChoices> {
  return (await request.get<LabelingChoices>(`${BASE}/choices`)).data
}
export async function fetchStats(): Promise<TaskStats> {
  return (await request.get<TaskStats>(`${BASE}/stats`)).data
}
export async function fetchProgress(): Promise<LabelingProgress> {
  return (await request.get<LabelingProgress>(`${BASE}/progress`)).data
}
export async function fetchTasks(filters: TaskFilters, limit = 20, offset = 0): Promise<TaskList> {
  const params: Record<string, unknown> = { ...filters, limit, offset }
  Object.keys(params).forEach((k) => { if (params[k] === null || params[k] === undefined || params[k] === false) delete params[k] })
  return (await request.get<TaskList>(`${BASE}/tasks`, { params })).data
}
export async function fetchTask(id: number): Promise<TaskDetail> {
  return (await request.get<TaskDetail>(`${BASE}/tasks/${id}`)).data
}
/** 图片只通过 Authorization 头获取（不把令牌放进 URL）。 */
export async function fetchTaskImage(id: number, size: 'full' | 'thumb' = 'full'): Promise<Blob> {
  return (await request.get<Blob>(`${BASE}/tasks/${id}/image`, { params: { size }, responseType: 'blob' })).data
}
export async function fetchSubmissionLabels(taskId: number, submissionId: number): Promise<string> {
  return (await request.get<{ labels: string }>(`${BASE}/tasks/${taskId}/submissions/${submissionId}/labels`)).data.labels
}
export async function submitLabels(id: number, payload: SubmitPayload): Promise<{ submission_id: number; status: string }> {
  return (await request.post(`${BASE}/tasks/${id}/submissions`, payload)).data
}
export async function approveSubmission(id: number, note = ''): Promise<{ review_mode: string }> {
  return (await request.post(`${BASE}/submissions/${id}/approve`, { note })).data
}
export async function returnSubmission(id: number, note: string): Promise<void> {
  await request.post(`${BASE}/submissions/${id}/return`, { note })
}
export async function setTaskStatus(id: number, status: 'skipped' | 'rejected' | 'pending', reasons: string[] = []): Promise<void> {
  await request.post(`${BASE}/tasks/${id}/status`, { status, reasons })
}
export async function setBenchmark(id: number, benchmark: boolean): Promise<{ status: string }> {
  return (await request.post(`${BASE}/tasks/${id}/benchmark`, { benchmark })).data
}
export async function snapEdges(id: number, labels: string): Promise<string> {
  return (await request.post<{ labels: string }>(`${BASE}/tasks/${id}/snap`, { labels })).data.labels
}
export async function redraft(id: number): Promise<{ labels: string; source: string | null }> {
  return (await request.post(`${BASE}/tasks/${id}/redraft`)).data
}
export async function syncDiary(): Promise<{ synced: number } & TaskStats> {
  return (await request.post(`${BASE}/sync`)).data
}
export async function uploadPhotos(files: File[], sourceNote: string, subjectRef: string, rightsConfirmed: boolean): Promise<UploadResult> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  form.append('source_note', sourceNote)
  if (subjectRef) form.append('subject_ref', subjectRef)
  form.append('rights_confirmed', String(rightsConfirmed))
  return (await request.post<UploadResult>(`${BASE}/uploads`, form)).data
}
export async function importLegacy(rightsConfirmed: boolean): Promise<{ imported: number[]; failed: { id: number; reason: string }[] }> {
  return (await request.post(`${BASE}/legacy/import`, { rights_confirmed: rightsConfirmed })).data
}

/** 统一错误文案：优先后端 detail。 */
export function errorText(cause: unknown, fallback: string): string {
  const detail = (cause as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' && detail ? detail : fallback
}
