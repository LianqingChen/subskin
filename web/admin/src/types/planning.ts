export interface ArchiveDocument {
  id: string
  path: string
  title: string
  summary: string
  date: string | null
  updated_at: string
  size: number
  category: string
  topic: string
  source: string
  topic_title?: string
  related_count?: number
}
export interface ArchiveDetail extends ArchiveDocument {
  content: string
  related: ArchiveDocument[]
}
export interface ArchiveOption { value: string; label: string; count: number }
export interface ArchiveList {
  items: ArchiveDocument[]
  total: number
  page: number
  page_size: number
  stats: { documents: number; topics: number; updated_at: string | null }
  categories: ArchiveOption[]
  sources: ArchiveOption[]
  months: ArchiveOption[]
  warnings: { path: string; message: string }[]
}
export interface ArchiveFilters { q: string; category: string; source: string; month: string; page: number }
export const archiveCategories: Record<string, string> = {
  research: '研究分析', design: '设计方案', plan: '任务计划',
  progress: '发现与进度', review: '验收审查', deployment: '部署记录',
}
