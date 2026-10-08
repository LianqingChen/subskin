import request from './request'
import type { ArchiveDetail, ArchiveFilters, ArchiveList } from '@/types/planning'

export async function fetchArchive(filters: ArchiveFilters, refresh = false): Promise<ArchiveList> {
  const { data } = await request.get<ArchiveList>('/admin/planning', { params: { ...filters, refresh } })
  return data
}
export async function fetchArchiveDocument(id: string): Promise<ArchiveDetail> {
  const { data } = await request.get<ArchiveDetail>('/admin/planning/document', { params: { id } })
  return data
}
export async function resolveArchiveDocument(path: string): Promise<string> {
  const { data } = await request.get<{ id: string }>('/admin/planning/resolve', { params: { path } })
  return data.id
}
