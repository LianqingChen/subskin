import request from './request'

export interface SiteStorage { available: boolean; database_bytes: number | null; wal_bytes: number | null }
export interface EmbedResult { embedded_count: number; failed_count: number; total: number }
export async function getSiteStorage(): Promise<SiteStorage> {
  const { data } = await request.get<SiteStorage>('/admin/site/status')
  return data
}
export async function triggerSiteEmbedding(): Promise<EmbedResult> {
  const { data } = await request.post<{ status: string; result: EmbedResult }>('/admin/embed-batch')
  if (data.status !== 'ok') throw new Error('向量化任务未完成')
  return data.result
}
