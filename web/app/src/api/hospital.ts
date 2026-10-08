import apiClient from './client'
import type {
  AppealClaimantType,
  DimensionDistribution,
  ExperienceLevel,
  HospitalCreatePayload,
  HospitalReviewAppeal,
  HospitalReviewAppealPayload,
  HospitalReview,
  HospitalReviewPayload,
  HospitalReviewPublishResult,
  HospitalStats,
  HospitalView,
  ReviewReportReason,
  ReviewSort,
  ReviewTarget,
} from '@/types/hospital'

/** 后端 `/api/hospitals` 响应（snake_case） */
interface ApiHospital {
  id: number
  slug: string
  name: string
  province: string
  city: string
  district?: string | null
  address?: string | null
  department?: string | null
  kind?: string | null
  features?: string[] | null
  summary?: string | null
  source?: string | null
  checked_at?: string | null
  origin?: string | null
  status?: string | null
  lat?: number | null
  lng?: number | null
  stats?: {
    review_count?: number
    rating_count?: number
    rating_avg?: number | null
    doctor_review_count?: number
    treatment_review_count?: number
    targets?: Record<string, number> | null
    top_tags?: { tag: string; count: number }[] | null
    dimension_distribution?: {
      dimension?: string | null
      total?: number | null
      satisfied?: number | null
      neutral?: number | null
      unsatisfied?: number | null
      na?: number | null
    }[] | null
  } | null
}

interface ApiReview {
  id: number
  hospital_id: number
  hospital_name?: string | null
  hospital_city?: string | null
  target: string
  doctor_name?: string | null
  doctor_title?: string | null
  doctor_department?: string | null
  treatment_name?: string | null
  treatment_detail?: string | null
  visit_month?: string | null
  duration?: string | null
  cost?: string | null
  outcome?: string | null
  ratings?: Record<string, number> | null
  experience_scores?: Record<string, string> | null
  tags?: string[] | null
  images?: { url?: string | null; label?: string | null }[] | null
  credential_labels?: string[] | null
  content: string
  moderation_status?: string | null
  restricted_reason?: string | null
  helpful_count?: number | null
  is_helpful?: boolean | null
  detail_score?: number | null
  author?: { username?: string | null; avatar_url?: string | null } | null
  is_mine?: boolean
  created_at?: string | null
}

export interface HospitalListResponse {
  total: number
  items: ApiHospital[]
}

export interface HospitalReviewListResponse {
  total: number
  items: ApiReview[]
  summary: ApiHospital['stats']
}

export function toStats(raw: ApiHospital['stats']): HospitalStats {
  return {
    reviewCount: Number(raw?.review_count ?? 0),
    ratingCount: Number(raw?.rating_count ?? 0),
    ratingAvg: raw?.rating_avg == null ? null : Number(raw.rating_avg),
    doctorCount: Number(raw?.doctor_review_count ?? 0),
    treatmentCount: Number(raw?.treatment_review_count ?? 0),
    targets: raw?.targets ?? {},
    topTags: (raw?.top_tags ?? []).map(item => ({ tag: String(item.tag), count: Number(item.count) })),
    dimensionDistribution: (raw?.dimension_distribution ?? []).map(toDistribution),
  }
}

function toDistribution(raw: {
  dimension?: string | null; total?: number | null; satisfied?: number | null
  neutral?: number | null; unsatisfied?: number | null; na?: number | null
}): DimensionDistribution {
  return {
    dimension: String(raw.dimension ?? ''),
    total: Number(raw.total ?? 0),
    satisfied: Number(raw.satisfied ?? 0),
    neutral: Number(raw.neutral ?? 0),
    unsatisfied: Number(raw.unsatisfied ?? 0),
    na: Number(raw.na ?? 0),
  }
}

export function toHospitalView(raw: ApiHospital): HospitalView {
  return {
    key: raw.origin === 'community' ? `c-${raw.id}` : raw.slug,
    id: raw.id,
    slug: raw.slug,
    name: raw.name,
    province: raw.province,
    city: raw.city,
    district: raw.district ?? '',
    address: raw.address ?? '',
    department: raw.department ?? '',
    kind: raw.kind ?? '',
    features: raw.features ?? [],
    summary: raw.summary ?? '',
    source: raw.source ?? '',
    checkedAt: raw.checked_at ?? '',
    origin: raw.origin === 'community' ? 'community' : 'official',
    lat: raw.lat ?? null,
    lng: raw.lng ?? null,
    stats: toStats(raw.stats),
  }
}

const TARGETS: ReviewTarget[] = ['hospital', 'doctor', 'treatment', 'experience']

export function toReview(raw: ApiReview): HospitalReview {
  return {
    id: raw.id,
    hospitalId: raw.hospital_id,
    hospitalName: raw.hospital_name ?? '',
    hospitalCity: raw.hospital_city ?? '',
    target: (TARGETS.includes(raw.target as ReviewTarget) ? raw.target : 'hospital') as ReviewTarget,
    doctorName: raw.doctor_name ?? '',
    doctorTitle: raw.doctor_title ?? '',
    doctorDepartment: raw.doctor_department ?? '',
    treatmentName: raw.treatment_name ?? '',
    treatmentDetail: raw.treatment_detail ?? '',
    visitMonth: raw.visit_month ?? '',
    duration: raw.duration ?? '',
    cost: raw.cost ?? '',
    outcome: raw.outcome ?? '',
    ratings: raw.ratings ?? {},
    experienceScores: (raw.experience_scores ?? {}) as Record<string, ExperienceLevel>,
    tags: raw.tags ?? [],
    images: (raw.images ?? [])
      .filter(item => Boolean(item?.url))
      .map(item => ({ url: String(item.url), label: String(item.label ?? '凭证') })),
    credentialLabels: (raw.credential_labels ?? []).map(label => String(label)),
    content: raw.content,
    moderationStatus: raw.moderation_status ?? 'approved',
    restrictedReason: raw.restricted_reason ?? null,
    helpfulCount: Number(raw.helpful_count ?? 0),
    isHelpful: Boolean(raw.is_helpful),
    detailScore: Number(raw.detail_score ?? 0),
    authorName: raw.author?.username ?? '病友',
    authorAvatar: raw.author?.avatar_url ?? '',
    isMine: Boolean(raw.is_mine),
    createdAt: raw.created_at ?? '',
  }
}

export async function fetchHospitals(params: { province?: string; city?: string; q?: string } = {}) {
  const { data } = await apiClient.get<HospitalListResponse>('/hospitals', { params })
  return { total: data.total, items: data.items.map(toHospitalView) }
}

export async function fetchHospital(ident: string | number) {
  const { data } = await apiClient.get<ApiHospital>(`/hospitals/${ident}`)
  return toHospitalView(data)
}

export async function createHospital(payload: HospitalCreatePayload) {
  const { data } = await apiClient.post<ApiHospital>('/hospitals', {
    name: payload.name,
    province: payload.province,
    city: payload.city,
    district: payload.district || null,
    address: payload.address || null,
    department: payload.department || null,
    kind: payload.kind || null,
    source: payload.source || null,
    note: payload.note || null,
    confirm_no_pii: Boolean(payload.confirmNoPii),
  })
  return toHospitalView(data)
}

export async function fetchHospitalReviews(
  ident: string | number | null,
  params: { target?: ReviewTarget | ''; limit?: number; offset?: number; sort?: ReviewSort } = {},
) {
  const { data } = await apiClient.get<HospitalReviewListResponse>(ident === null ? '/hospitals/reviews/feed' : `/hospitals/${ident}/reviews`, {
    params: {
      target: params.target || undefined,
      sort: params.sort || 'recent',
      limit: params.limit ?? 20,
      offset: params.offset ?? 0,
    },
  })
  return { total: data.total, items: data.items.map(toReview), summary: toStats(data.summary) }
}

/** 上传评价凭证图（费用单/挂号单/处方/检查单），返回可访问 URL */
export async function uploadReviewImage(file: File) {
  const form = new FormData()
  form.append('image', file)
  const { data } = await apiClient.post<{ url: string }>('/hospitals/reviews/images', form)
  return data.url
}

/** 给评价点「有用」（再点一次取消） */
export async function toggleReviewHelpful(reviewId: number) {
  const { data } = await apiClient.post<{ review_id: number; helpful_count: number; is_helpful: boolean }>(
    `/hospitals/reviews/${reviewId}/helpful`,
  )
  return { helpfulCount: Number(data.helpful_count), isHelpful: Boolean(data.is_helpful) }
}

export async function publishHospitalReview(ident: string | number, payload: HospitalReviewPayload) {
  const { data } = await apiClient.post<{
    review: ApiReview
    pii_redacted: boolean
    claims_flagged: string[]
    message: string
    risk_level?: string
    risk_score?: number
    risk_categories?: string[]
    author_hints?: string[]
    aggregate_pending?: boolean
  }>(`/hospitals/${ident}/reviews`, {
    target: payload.target,
    doctor_name: payload.doctorName || null,
    doctor_title: payload.doctorTitle || null,
    doctor_department: payload.doctorDepartment || null,
    treatment_name: payload.treatmentName || null,
    treatment_detail: payload.treatmentDetail || null,
    visit_month: payload.visitMonth || null,
    duration: payload.duration || null,
    cost: payload.cost || null,
    outcome: payload.outcome || null,
    ratings: payload.ratings ?? {},
    tags: payload.tags ?? [],
    images: (payload.images ?? []).map(image => ({ url: image.url, label: image.label })),
    images_confirmed: Boolean(payload.imagesConfirmed),
    content: payload.content,
    confirm_pii: Boolean(payload.confirmPii),
    experience_scores: payload.experienceScores ?? {},
    health_consent: Boolean(payload.healthConsent),
    risk_ack: Boolean(payload.riskAck),
  })
  const result: HospitalReviewPublishResult = {
    review: toReview(data.review),
    piiRedacted: Boolean(data.pii_redacted),
    claimsFlagged: data.claims_flagged ?? [],
    message: data.message ?? '',
    riskLevel: data.risk_level ?? 'safe',
    riskScore: Number(data.risk_score ?? 0),
    riskCategories: data.risk_categories ?? [],
    authorHints: data.author_hints ?? [],
    aggregatePending: Boolean(data.aggregate_pending),
  }
  return result
}

/** 举报一条评价（一人一次，幂等） */
export async function reportHospitalReview(reviewId: number, reasonCode: ReviewReportReason, detail?: string) {
  const { data } = await apiClient.post<{ review_id: number; report_count: number; status: string }>(
    `/hospitals/reviews/${reviewId}/report`,
    { reason_code: reasonCode, detail: detail || null },
  )
  return { reviewId: Number(data.review_id), reportCount: Number(data.report_count), status: String(data.status) }
}

/** 提交评价申诉（无需登录：机构申诉不应被登录门槛挡住） */
export async function submitHospitalReviewAppeal(payload: HospitalReviewAppealPayload) {
  const { data } = await apiClient.post<{
    id: number; review_id: number; claimant_type: string; claimant_name: string
    status: string; resolution?: string | null; resolved_action?: string | null
    due_at?: string | null; created_at?: string | null; overdue?: boolean
  }>('/hospitals/reviews/appeals', {
    review_id: payload.reviewId,
    claimant_type: payload.claimantType,
    claimant_name: payload.claimantName,
    contact: payload.contact,
    reason: payload.reason,
    evidence_urls: payload.evidenceUrls ?? [],
  })
  const appeal: HospitalReviewAppeal = {
    id: Number(data.id),
    reviewId: Number(data.review_id),
    claimantType: data.claimant_type as AppealClaimantType,
    claimantName: String(data.claimant_name ?? ''),
    status: String(data.status ?? 'pending'),
    resolution: data.resolution ?? null,
    resolvedAction: data.resolved_action ?? null,
    dueAt: data.due_at ?? null,
    createdAt: data.created_at ?? null,
    overdue: Boolean(data.overdue),
  }
  return appeal
}

export async function deleteHospitalReview(reviewId: number) {
  await apiClient.delete(`/hospitals/reviews/${reviewId}`)
}

export async function fetchMyHospitalReviews() {
  const { data } = await apiClient.get<ApiReview[]>('/hospitals/reviews/mine')
  return data.map(toReview)
}
