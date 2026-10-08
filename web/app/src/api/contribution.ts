import apiClient from './client'

/** 分用途数据授权与自报事实（图像数据库专项）。后端：/api/data-consents、/api/self-report */

export type GrantState = 'active' | 'withdrawn' | 'expired'
export type GrantScope = 'future_only' | 'all_records' | 'selected'

export interface DataGrant {
  id: number
  purpose: string
  title: string
  scope: GrantScope
  project_id: string | null
  text_version: string
  state: GrantState
  created_at: string
  expires_at: string | null
  withdrawal_status: string | null
}

export interface ConsentStatus {
  active: Record<string, boolean>
  grants_enabled: boolean
}

export interface MicroQuestion {
  id: string
  text: string
  options: { value: string; label: string }[]
  multi: boolean
  scope: 'body_site' | 'user'
  version: string
}

export type MicroTrigger = 'record_saved' | 'compare_viewed' | 'checklist'

export async function fetchConsentStatus(): Promise<ConsentStatus> {
  return (await apiClient.get('/data-consents/status')).data
}

export async function fetchGrants(): Promise<DataGrant[]> {
  return (await apiClient.get('/data-consents')).data
}

export async function createGrant(body: {
  purpose: string
  scope: GrantScope
  text_version: string
  source?: string
}): Promise<DataGrant> {
  return (await apiClient.post('/data-consents', { platform: 'web', ...body })).data
}

export async function withdrawGrant(id: number): Promise<DataGrant> {
  return (await apiClient.post(`/data-consents/${id}/withdraw`)).data
}

export async function nextQuestions(
  trigger: MicroTrigger,
  bodySite: string | null,
  sessionId: string,
): Promise<MicroQuestion[]> {
  const res = await apiClient.post('/self-report/next', {
    trigger,
    body_site: bodySite || undefined,
    session_id: sessionId,
  })
  return res.data.questions
}

export async function answerQuestion(body: {
  question_id: string
  answer: string | string[]
  body_site?: string | null
  session_id?: string
}): Promise<void> {
  await apiClient.post('/self-report/answer', { ...body, body_site: body.body_site || undefined })
}

export async function dismissQuestion(body: {
  question_id: string
  body_site?: string | null
  session_id?: string
}): Promise<void> {
  await apiClient.post('/self-report/dismiss', { ...body, body_site: body.body_site || undefined })
}

/** 响应错误里的业务码（后端 detail.code）。 */
export function errorCode(e: unknown): string | null {
  const d = (e as { response?: { data?: { detail?: { code?: string } } } })?.response?.data?.detail
  return d && typeof d === 'object' ? d.code ?? null : null
}
