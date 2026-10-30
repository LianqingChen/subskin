import request from './request'
import type { DatasetReport, TrainingStatus } from '@/types/training'

const BASE = '/vasi/admin/rgb-training'

export async function fetchTrainingStatus(): Promise<TrainingStatus> {
  return (await request.get<TrainingStatus>(`${BASE}/status`)).data
}
export async function exportDataset(): Promise<DatasetReport> {
  return (await request.post<DatasetReport>(`${BASE}/datasets`)).data
}
export async function startRun(datasetId: string, epochs: number): Promise<void> {
  await request.post(`${BASE}/runs`, { dataset_id: datasetId, epochs })
}
export async function cancelRun(runId: string): Promise<void> {
  await request.delete(`${BASE}/runs/${runId}`)
}
export async function registerRun(runId: string): Promise<void> {
  await request.post(`${BASE}/runs/${runId}/register`)
}
export async function disableRegistry(): Promise<void> {
  await request.post(`${BASE}/registry/disable`)
}
