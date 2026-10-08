import apiClient from './client'
import { isAxiosError } from 'axios'
import type { ObservationContext, PhotoMeasurement } from '@/types/assessment'

export interface RGBJob {
  id: string
  operation: 'assessment' | 'refine' | 'outline'
  state: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  stage: string
  assessment_id: number | null
  error_code: string | null
  result: { protocol: 'skin-seg-v2'; mask_revision: string; status: string } | null
}
export interface RGBSelection {
  x: number; y: number; skinMask: string; signal: AbortSignal
}
export type RGBSelector = (input: RGBSelection) => Promise<string>
const messages: Record<string, string> = {
  QUALITY_INFORMATION_LOST: '照片部分区域过曝、过暗或不清晰，请重拍',
  REGIONS_UNRESOLVED: '边界仍不可靠，请使用画笔调整',
  SKIN_UNVERIFIED: '请先核对蓝色皮肤范围，再点选浅色区域',
  MODEL_UNAVAILABLE: '交互分割暂不可用，可使用画笔调整',
  REVISION_CONFLICT: '标注已变化，请重新加载后调整',
  INVALID_IMAGE: '照片无法读取，请换一张原图',
  TIMEOUT: '分析超时，请重试当前照片',
  WORKER_RESTARTED: '分析服务已重新连接，请重试',
  CANCELLED: '分析已取消',
}
export class RGBTaskError extends Error {
  constructor(public code: string) { super(messages[code] || '图像分析暂未完成，请重试'); this.name = 'RGBTaskError' }
}
function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new RGBTaskError('CANCELLED')); return }
    const done = () => { signal.removeEventListener('abort', abort); resolve() }
    const timer = setTimeout(done, ms)
    const abort = () => { clearTimeout(timer); reject(new RGBTaskError('CANCELLED')) }
    signal.addEventListener('abort', abort, { once: true })
  })
}
async function poll(initial: RGBJob, signal: AbortSignal, progress?: (stage: string) => void, timeoutMs = 120000): Promise<RGBJob> {
  let job = initial
  const deadline = Date.now() + timeoutMs
  try {
    while (true) {
      if (signal.aborted) throw new RGBTaskError('CANCELLED')
      progress?.(job.stage)
      if (job.state === 'completed') return job
      if (job.state === 'failed' || job.state === 'cancelled') throw new RGBTaskError(job.error_code || 'CANCELLED')
      if (Date.now() >= deadline) throw new RGBTaskError('TIMEOUT')
      await wait(750, signal)
      job = (await apiClient.get<RGBJob>(`/vasi/segmentation-jobs/${job.id}`, { timeout: 15000, signal })).data
    }
  } finally {
    if (signal.aborted || job.state === 'queued' || job.state === 'running') {
      await apiClient.post(`/vasi/segmentation-jobs/${job.id}/cancel`, {}, { timeout: 10000 }).catch(() => undefined)
    }
  }
}
async function submitIdempotently<T>(url: string, body: FormData | object, key: string): Promise<T> {
  try { return (await apiClient.post<T>(url, body, { timeout: 30000 })).data }
  catch (error) {
    if (!isAxiosError(error) || error.response) throw error
    try { return (await apiClient.post<T>(url, body, { timeout: 30000 })).data }
    catch (retryError) {
      await apiClient.post(`/vasi/segmentation-requests/${key}/cancel`, {}, { timeout: 10000 }).catch(() => undefined)
      throw retryError
    }
  }
}
export const rgbApi = {
  async cancel(jobId: string): Promise<void> { await apiClient.post(`/vasi/segmentation-jobs/${jobId}/cancel`, {}, { timeout: 10000 }) },
  async assess(image: File, bodySite: string, context: ObservationContext | undefined, signal: AbortSignal, progress: (stage: string) => void): Promise<{ jobId: string; assessmentId: number }> {
    const capability = (await apiClient.get<{ protocol: string; worker_ready: boolean }>('/vasi/rgb-capabilities', { timeout: 15000 })).data
    if (signal.aborted) throw new RGBTaskError('CANCELLED')
    if (capability.protocol !== 'skin-seg-v2' || !capability.worker_ready) throw new RGBTaskError('SERVICE_UNAVAILABLE')
    const key = crypto.randomUUID()
    const body = new FormData()
    body.append('image', image); body.append('body_site', bodySite); body.append('idempotency_key', key)
    body.append('context', JSON.stringify(context || {}))
    const initial = await submitIdempotently<RGBJob>('/vasi/segmentation-jobs', body, key)
    const completed = await poll(initial, signal, progress)
    if (!completed.assessment_id) throw new RGBTaskError('SERVICE_UNAVAILABLE')
    return { jobId: completed.id, assessmentId: completed.assessment_id }
  },
  async review(jobId: string, revision: string, skin: string, lesion: string, acknowledged: boolean): Promise<{
    measurement: PhotoMeasurement; skin_layer_data_url?: string; lesion_layer_data_url?: string; final_area_percentage: number; final_vasi_score: number; diff_summary: { modified: boolean }
  }> {
    return (await apiClient.patch(`/vasi/segmentation-jobs/${jobId}/review`, {
      base_revision: revision, skin_mask: skin, lesion_mask: lesion, acknowledged,
    }, { timeout: 30000 })).data
  },
  async select(jobId: string, revision: string, input: RGBSelection): Promise<string> {
    const key = crypto.randomUUID()
    const initial = await submitIdempotently<RGBJob>(`/vasi/segmentation-jobs/${jobId}/refine`, {
      idempotency_key: key, base_revision: revision, skin_mask: input.skinMask,
      points: [{ x: input.x, y: input.y, label: 1 }],
    }, key)
    const completed = await poll(initial, input.signal)
    if (!completed.result) throw new RGBTaskError('REGIONS_UNRESOLVED')
    const response = await apiClient.get<{ mask_data_url: string }>(`/vasi/segmentation-jobs/${completed.id}/overlays/${completed.result.mask_revision}/lesion`, { timeout: 15000, signal: input.signal })
    return response.data.mask_data_url
  },
  async outline(jobId: string, revision: string, signal: AbortSignal): Promise<{ lesion: string; uncertain: string }> {
    const key = crypto.randomUUID()
    const initial = await submitIdempotently<RGBJob>(`/vasi/segmentation-jobs/${jobId}/outline`, {
      idempotency_key: key, base_revision: revision,
    }, key)
    const completed = await poll(initial, signal, undefined, 240000)
    if (!completed.result) throw new RGBTaskError('REGIONS_UNRESOLVED')
    const jobRevision = completed.result.mask_revision
    const overlay = (kind: string) => apiClient.get<{ mask_data_url: string }>(`/vasi/segmentation-jobs/${completed.id}/overlays/${jobRevision}/${kind}`, { timeout: 15000, signal }).then(response => response.data.mask_data_url)
    const [lesion, uncertain] = await Promise.all([overlay('lesion'), overlay('uncertain')])
    return { lesion, uncertain }
  },
}
