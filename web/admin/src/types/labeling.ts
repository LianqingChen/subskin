/** 五类打标工作台（/admin/labeling/*）的数据契约，与后端 services/labeling 一一对应。 */

export type TaskStatus = 'pending' | 'in_review' | 'returned' | 'gold' | 'rejected' | 'skipped'
export type TaskOrigin = 'diary' | 'admin_upload' | 'legacy_import'
export type PrefillSource = 'none' | 'ai' | 'user' | 'previous'
export type SubmissionStatus = 'submitted' | 'approved' | 'returned' | 'superseded'
export type Tristate = 'yes' | 'no' | 'unknown'

export interface Agreement { lesion_dice: number | null; skin_dice: number | null }

export interface SubmissionStats {
  pixels: Record<string, number>
  labeled_fraction: number
  lesion_ratio: number | null
  has_lesion: boolean
  vs_ai: Agreement | null
  vs_user: Agreement | null
  user_revision: string | null
}

export interface LabelAttributes {
  quality_issues: string[]
  shot_type: string
  imaging: string
  lighting: string
  monk_skin_tone: number | null
  body_site: string | null
  signs: Record<string, Tristate>
  escalate: boolean
  notes: string
}

export interface SubmissionSummary {
  id: number
  revision: string
  status: SubmissionStatus
  author_id: number
  author: string | null
  reviewer: string | null
  review_mode: 'dual' | 'single_review' | null
  review_note: string | null
  prefill_source: PrefillSource
  blind: boolean
  duration_ms: number | null
  attributes: Partial<LabelAttributes>
  stats: Partial<SubmissionStats>
  created_at: string | null
  reviewed_at: string | null
}

export interface GoldInfo {
  revision: string
  approved_by: number
  approved_at: string
  review_mode?: 'dual' | 'single_review'
  submission_id?: number
  author_id?: number
}

export interface TaskSummary {
  id: number
  origin: TaskOrigin
  status: TaskStatus
  benchmark: boolean
  body_site: string | null
  body_site_label: string | null
  body_group: string
  created_at: string | null
  capture_date: string | null
  user_ratio: number | null
  lesion_ratio: number | null
  priority: number | null
  latest: SubmissionSummary | null
  gold: GoldInfo | null
  rejection: { status: string; reasons?: string[]; at: string } | null
  escalate: boolean
  user_revision_newer: boolean
  external: ExternalAttribution | null
}

/** 公开授权来源的署名（PMC 开放获取 / Wikimedia Commons）。 */
export interface ExternalAttribution {
  source: 'pmc_oa' | 'wikimedia_commons'
  license?: string
  license_url?: string
  share_alike?: boolean
  citation?: string
  doi?: string
  pmcid?: string
  figure?: string
  caption?: string
  artist?: string
  url?: string
}

export interface TaskFilters {
  status: 'all' | 'open' | 'review' | TaskStatus
  origin?: TaskOrigin | null
  group?: string | null
  benchmark?: boolean | null
  escalate?: boolean
  mine?: boolean
  external?: 'any' | 'pmc_oa' | 'wikimedia_commons' | null
  sort?: 'queue' | 'newest'
}

export interface TaskList { total: number; items: TaskSummary[]; ids: number[] }

export interface TaskStats {
  counts: Record<TaskStatus, number>
  total: number
  hidden_unconsented: number
  legacy: number
}

export interface TaskDetail {
  task: TaskSummary
  image: { width: number; height: number }
  blind: boolean
  layers: { ai: string | null; user: string | null; user_revision: string | null; latest: string | null }
  submissions: SubmissionSummary[]
  consent: { required: boolean; allowed: boolean }
  provenance: { origin: string; source_note?: string; subject_ref?: string | null } | null
}

export interface BodySiteEntry { code: string; label: string; group: string; side: string; legacy?: boolean }

export interface LabelingChoices {
  guideline_version: string
  quality_issues: string[]
  reject_reasons: string[]
  shot_types: string[]
  imaging: string[]
  lighting: string[]
  signs: string[]
  body_sites: { groups: Record<string, string>; sites: BodySiteEntry[] }
}

export interface SubmitPayload {
  labels: string
  attributes: LabelAttributes
  prefill_source: PrefillSource
  duration_ms: number | null
}

export interface UploadResult { created: number[]; skipped: { name: string; reason: string }[] }

export interface AnnotatorRow {
  author_id: number
  author: string | null
  submitted: number
  approved: number
  returned: number
  minutes_per_image: number | null
}

export interface LabelingProgress {
  window_days: number
  annotators: AnnotatorRow[]
  awaiting_review: number
  draft_quality: { vs_ai_lesion_dice: number | null; vs_ai_skin_dice: number | null; vs_user_lesion_dice: number | null }
  inter_annotator: { pairs: number; lesion_dice: number | null; skin_dice: number | null }
  gold: {
    total: number
    negatives: number
    benchmark: number
    subjects_estimate: number
    coverage: Record<string, Record<string, number>>
  }
  gate: { min_test_images: number; min_test_subjects: number; min_dice: number; min_skin_dice: number }
}

/** 中文显示名（与后端取值一一对应）。 */
export const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: '待标注', in_review: '待复核', returned: '已退回', gold: '金标准', rejected: '不可用', skipped: '已跳过',
}
export const ORIGIN_LABEL: Record<TaskOrigin, string> = {
  diary: '日记', admin_upload: '后台上传', legacy_import: '旧版转入',
}
export const PREFILL_LABEL: Record<PrefillSource, string> = {
  none: '盲标', ai: 'AI 初稿', user: '用户日记版', previous: '上一版本',
}
export const REASON_LABEL: Record<string, string> = {
  blur: '模糊', exposure: '曝光异常', glare: '反光', occlusion: '遮挡', angle: '角度过斜',
  site_mismatch: '部位存疑', identifiable: '含可识别信息', out_of_scope: '超出范围（黏膜/隐私部位）',
  not_skin: '不是皮肤照片', duplicate: '重复图片', other: '其他',
}
export const GROUP_LABEL: Record<string, string> = {
  head: '头颈', torso: '躯干', arm: '上肢', hand: '手', leg: '下肢', foot: '足', other: '其他', unknown: '未知',
}
