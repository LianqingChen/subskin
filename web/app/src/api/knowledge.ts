import apiClient from './client'

export type KnowledgeStatus = 'draft' | 'editor_reviewed' | 'medical_reviewed' | 'published' | 'retired' | string
export type EvidenceLevel = 'A' | 'B' | 'C' | 'D' | 'E'

export interface KnowledgeTopic { key: string; label: string }
export interface KnowledgeCardSummary {
  slug: string; topic: string; title: string; summary: string; evidence_level: EvidenceLevel | null
  source_count: number; reviewed_at: string | null; ai_assisted: boolean; status: KnowledgeStatus
}
export interface KnowledgeSource {
  type: 'pmid' | 'doi' | 'nct' | 'guideline' | 'url'; ref: string; title: string; url: string
  year: number | null; evidence_level: EvidenceLevel | null
}
export interface KnowledgeCard extends KnowledgeCardSummary {
  body_md: string; sources: KnowledgeSource[]; next_review_at: string | null; related: string[]; disclaimer: string
}
export interface KnowledgeCardList { topics: KnowledgeTopic[]; items: KnowledgeCardSummary[] }

export interface PipelineRegion { region: string; status: string; date: string | null }
export interface PipelineItem {
  key: string; drug_zh: string; drug_en: string; mechanism: string; route: string; sponsor: string; phase: string
  regions: PipelineRegion[]; latest_event: string; event_date: string | null
  sources: { label: string; url: string }[]; checked_at: string | null; status: KnowledgeStatus
}
export interface KnowledgePipeline { updated_at: string | null; items: PipelineItem[] }

export interface DigestItem {
  key: string; title_zh: string; title_en: string; one_liner: string; why_it_matters: string; limitations: string
  study_type: string; sample_size: number | string | null; is_preprint: boolean; published_on: string | null
  journal: string; url: string; pmid: string | null; status: KnowledgeStatus
}
export interface KnowledgeDigests { items: DigestItem[] }

export interface ResearchPurpose {
  purpose: string; title: string; description: string; open: boolean
  active: { value: number | null; status: 'available' | 'unavailable' | 'suppressed'; note: string }
}
export interface ResearchProject { key?: string; title?: string; name?: string; institution?: string; summary?: string; status?: string }
export interface KnowledgeResearch { purposes: ResearchPurpose[]; projects: ResearchProject[]; note: string }

/** preview=1 仅对管理员生效（后端也会校验），非管理员不传该参数 */
const previewParams = (preview?: boolean) => (preview ? { preview: 1 } : {})

export async function getKnowledgeCards(topic = '', preview = false): Promise<KnowledgeCardList> {
  return (await apiClient.get('/knowledge/cards', { params: { ...(topic ? { topic } : {}), ...previewParams(preview) } })).data
}
export async function getKnowledgeCard(slug: string, preview = false): Promise<KnowledgeCard> {
  return (await apiClient.get(`/knowledge/cards/${encodeURIComponent(slug)}`, { params: previewParams(preview) })).data
}
export async function getKnowledgePipeline(preview = false): Promise<KnowledgePipeline> {
  return (await apiClient.get('/knowledge/pipeline', { params: previewParams(preview) })).data
}
export async function getKnowledgeDigests(limit = 10, preview = false): Promise<KnowledgeDigests> {
  return (await apiClient.get('/knowledge/digests', { params: { limit, ...previewParams(preview) } })).data
}
export async function getKnowledgeResearch(): Promise<KnowledgeResearch> {
  return (await apiClient.get('/knowledge/research')).data
}
