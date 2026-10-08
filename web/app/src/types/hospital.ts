/**
 * 就医经验（/hospitals）模块类型。
 *
 * HospitalView 是统一视图模型：既承载后端 `/api/hospitals` 返回的目录条目，
 * 也承载离线兜底的静态目录（data/hospitals.ts），两者在 useHospitalRegistry 中归一。
 */

/** 评价对象：医院 / 医生 / 治疗方案 / 治疗经历 */
export type ReviewTarget = 'hospital' | 'doctor' | 'treatment' | 'experience'

/** 统一 6 维就医体验档位（v3 唯一评分体系，不含任何疗效/医术维度） */
export type ExperienceLevel = 'satisfied' | 'neutral' | 'unsatisfied' | 'na'

/** 单个维度的档位计数分布（含「没体验过」档，用于抑制刷分） */
export interface DimensionDistribution {
  dimension: string
  total: number
  satisfied: number
  neutral: number
  unsatisfied: number
  na: number
}

export interface HospitalStats {
  reviewCount: number
  ratingCount: number
  /** 旧版平均分：v3 起不再用于任何 UI 展示与排序（保留字段以兼容历史数据） */
  ratingAvg: number | null
  doctorCount: number
  treatmentCount: number
  /** 各评价对象类型的条数：hospital / doctor / treatment / experience */
  targets: Record<string, number>
  /** 病友常提到的中性标签聚合（只做展示，不做排名） */
  topTags: { tag: string; count: number }[]
  /** 6 维体验提及分布（替代平均分：计数型，无可被截图当作「医院得分」的数字） */
  dimensionDistribution: DimensionDistribution[]
}

export const EMPTY_STATS: HospitalStats = {
  reviewCount: 0, ratingCount: 0, ratingAvg: null, doctorCount: 0, treatmentCount: 0,
  targets: {}, topTags: [], dimensionDistribution: [],
}

/** 评价排序：最新 / 最有用 */
export type ReviewSort = 'recent' | 'helpful'

/** 凭证图（费用单/挂号单/处方/检查单）—— 明确禁止病情照片 */
export interface HospitalReviewImage {
  url: string
  label: string
}

export const REVIEW_IMAGE_LABELS = ['费用单', '挂号单', '处方', '检查单'] as const
export const MAX_REVIEW_IMAGES = 3

/** 完整分享门槛：结构化信息 ≥2 项 */
export const COMPLETE_DETAIL_SCORE = 2

export interface HospitalView {
  /** 稳定标识（跨后端/离线一致）：官方条目用 slug，病友补充条目用 `c-<id>` */
  key: string
  /** 后端主键；离线兜底时为 null（此时不能发布评价） */
  id: number | null
  slug: string
  name: string
  province: string
  city: string
  district: string
  address: string
  department: string
  kind: string
  features: string[]
  summary: string
  source: string
  checkedAt: string
  /** official=平台按官方来源收录；community=病友补充（前端必须标注待核实） */
  origin: 'official' | 'community'
  lat: number | null
  lng: number | null
  stats: HospitalStats
}

/** 第一步「选择医院」的筛选条件（省份 → 城市 → 区县/具体地址 + 关键词） */
export interface HospitalFilterState {
  query: string
  province: string
  city: string
  district: string
  feature: string
  onlyMarked: boolean
  onlyReviewed: boolean
}

/** 静态兜底目录的原始条目（data/hospitals.ts） */
export interface Hospital {
  id: string
  name: string
  province: string
  city: string
  district?: string
  address?: string
  department: string
  kind: '综合医院' | '皮肤病专科'
  features: string[]
  summary: string
  source: string
  checkedAt: string
  lat?: number
  lng?: number
}

export interface HospitalReview {
  id: number
  hospitalId: number
  hospitalName: string
  hospitalCity: string
  target: ReviewTarget
  doctorName: string
  doctorTitle: string
  doctorDepartment: string
  treatmentName: string
  treatmentDetail: string
  visitMonth: string
  duration: string
  cost: string
  outcome: string
  /** 旧版 1-5 星评分：仅作者本人可见（公开层不再输出，避免被当作医院得分） */
  ratings: Record<string, number>
  /** 统一 6 维体验档位 */
  experienceScores: Record<string, ExperienceLevel>
  tags: string[]
  /** 凭证图原图：仅作者本人可见 */
  images: HospitalReviewImage[]
  /** 公开层只给徽标（如「费用单」），不回可访问 URL */
  credentialLabels: string[]
  content: string
  moderationStatus: 'approved' | 'flagged' | 'restricted' | 'blocked' | string
  /** 受限/驳回原因：仅作者本人可见 */
  restrictedReason: string | null
  helpfulCount: number
  isHelpful: boolean
  detailScore: number
  authorName: string
  authorAvatar: string
  isMine: boolean
  createdAt: string
}

export interface HospitalReviewPayload {
  target: ReviewTarget
  doctorName?: string
  doctorTitle?: string
  doctorDepartment?: string
  treatmentName?: string
  treatmentDetail?: string
  visitMonth?: string
  duration?: string
  cost?: string
  outcome?: string
  ratings?: Record<string, number>
  experienceScores?: Record<string, ExperienceLevel>
  tags?: string[]
  content: string
  images?: HospitalReviewImage[]
  imagesConfirmed?: boolean
  confirmPii?: boolean
  /** PIPL 第 28/29 条：就医体验属敏感个人信息，必须显式单独同意 */
  healthConsent?: boolean
  /** 发布前冷静确认（命中情绪化/结论性表述时必须） */
  riskAck?: boolean
}

export interface HospitalCreatePayload {
  name: string
  province: string
  city: string
  district?: string
  address?: string
  department?: string
  kind?: string
  source?: string
  note?: string
  confirmNoPii?: boolean
}

export interface HospitalReviewPublishResult {
  review: HospitalReview
  piiRedacted: boolean
  claimsFlagged: string[]
  message: string
  /** 风控档位：safe / watch / restricted / high */
  riskLevel: 'safe' | 'watch' | 'restricted' | 'high' | string
  riskScore: number
  riskCategories: string[]
  /** 给作者的改写建议（命中风险规则时） */
  authorHints: string[]
  /** 是否处于聚合冷处理（内容已公开，暂不计入标签聚合与维度分布） */
  aggregatePending: boolean
}

/** 举报原因码（与后端 REPORT_REASON_CODES 一致） */
export type ReviewReportReason = 'fake' | 'abuse' | 'privacy' | 'ad' | 'promotion' | 'other'

/** 申诉人身份 */
export type AppealClaimantType = 'hospital' | 'doctor' | 'author' | 'other'

export interface HospitalReviewAppealPayload {
  reviewId: number
  claimantType: AppealClaimantType
  claimantName: string
  contact: string
  reason: string
  evidenceUrls?: string[]
}

export interface HospitalReviewAppeal {
  id: number
  reviewId: number
  claimantType: AppealClaimantType
  claimantName: string
  status: 'pending' | 'accepted' | 'rejected' | string
  resolution: string | null
  resolvedAction: string | null
  dueAt: string | null
  createdAt: string | null
  overdue: boolean
}

// ── 本机记录（想去/去过标记、经历草稿、补充纠错草稿） ──

export type HospitalMark = 'want' | 'visited'

export interface HospitalReviewDraft {
  hospitalId: string
  month: string
  duration: string
  cost: string
  outcome: string
  ratings: Record<string, string>
  tags: string[]
  text: string
  savedAt: string
}

export interface HospitalSuggestion {
  name: string
  city: string
  source: string
  note: string
}

export interface HospitalNotebook {
  marks: Record<string, HospitalMark>
  reviews: Record<string, HospitalReviewDraft>
  suggestion?: HospitalSuggestion
}
