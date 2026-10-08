import apiClient from './client'

// ── Types ──

export interface ReportPoint {
  image_id: number
  date: string
  image_url?: string
  body_site: string | null
  has_vasi: boolean
  vasi_score: number | null
  area_percentage: number | null
  stage: string | null
  classification: string | null
  light_summary: string | null
  depigmentation_level: number | null
  quality?: string | null
}

export interface SkinReportMetrics {
  point_count: number
  has_vasi: boolean
  data_source: string
  date_span_days: number
  first: ReportPoint | null
  last: ReportPoint | null
  vasi_change?: number
  vasi_change_percent?: number
  area_change?: number
  trend: string
  // 首末图对配对识别（spot_compare）
  pair_metrics?: PairMetrics | null
  // 首末图对像素级配准产物（滑块/叠影/热力图）
  pair_align?: PairAlign | null
  // 图对引用（"pi:12" / "va:34"，与 timeline_frames 同序，日期切换用）
  refs?: string[]
  // 客观变化摘要（每条一句话，替代 AI 叙事/洞察/建议）
  change_summary?: string[]
  // 变化最大图对（旧报告遗留字段，新版不再生成）
  max_change_pair?: {
    first: ReportPoint
    last: ReportPoint
    first_image_url?: string
    last_image_url?: string
    pair_metrics: PairMetrics | null
    align?: PairAlign | null
  } | null
  // 时间轴帧（日期切换器的数据源；timeline_stack_url 为旧报告遗留）
  timeline_frames?: TimelineFrame[]
  timeline_stack_url?: string | null
  // 周报/月报字段
  period_days?: number
  sites_summary?: SitesSummary
  melanin_sites?: string[]
  site_count?: number
  sites?: SiteSection[]
  headline?: string
  diary_count?: number
  treatment_count?: number
  // 综合健康报告新增字段
  mood?: MoodSummary
  exam?: ExamSummary
  qa?: QaSummary
  narrative_sections?: NarrativeSection[]
  // 历史报告对比（synthesis）来源
  sources?: SynthesisSource[]
}

/** 时间轴帧（日期切换器的数据源） */
export interface TimelineFrame {
  image_id: number
  date: string
  image_url?: string
  quality?: string | null
}

/** 图对像素级配准产物（photo_align，v2 掩膜差分） */
export interface HeatmapClasses {
  repigmented_px: number
  expanded_px: number
  analysis_px: number
}

export interface TrendChartData {
  dates: string[]
  vasi_scores: (number | null)[]
  area_percentages: (number | null)[]
}

/** 周报/月报多序列趋势数据 */
export interface TrendSeries {
  body_site: string
  body_site_label: string
  dates: string[]
  vasi_scores: (number | null)[]
  area_percentages: (number | null)[]
  melanin_scores: (number | null)[]
}

export interface TrendChartWithSeries {
  series: TrendSeries[]
}

/** 配对识别 merged 指标（spot_compare） */
export interface PairMetrics {
  measurement_version?: string
  comparison_status?: 'measured' | 'not_comparable' | 'legacy'
  reasons?: string[]
  change_interval_percent?: number[] | null
  color_reason?: string | null
  melanin_score_a: number | null
  melanin_score_b: number | null
  melanin_change: number | null
  melanin_signals: {
    follicular_repigmentation?: number | null
    island_repigmentation?: number | null
    edge_inward?: boolean | null
    note?: string | null
  }
  size_change_percent: number | null
  color_change: string | null
  border_change: string | null
  trend: string
  trend_en: string
  confidence: number | null
  summary: string | null
  capture_note: string | null
  low_confidence: boolean
  duplicate?: boolean
}

/** 图对像素级配准产物（photo_align） */
export interface PairAlign {
  aligned: boolean
  inlier_count: number | null
  scale: number | null
  note: string | null
  aligned_after_url?: string | null
  heatmap_url?: string | null
  classes?: HeatmapClasses | null
}

/** 周报/月报的单部位区块 */
export interface SiteSection {
  body_site: string
  body_site_label: string
  photo_count_in_period: number
  has_baseline: boolean
  first: { ref: string; date: string; has_vasi: boolean; vasi_score: number | null } | null
  last: { ref: string; date: string; has_vasi: boolean; vasi_score: number | null } | null
  first_image_url?: string
  last_image_url?: string
  pair_metrics: PairMetrics | null
  vasi_change: number | null
  trend: string
  trend_source: string | null
  vasi_points: { date: string; vasi_score: number | null; area_percentage: number | null }[]
}

export interface SitesSummary {
  improving: number
  stable: number
  worsening: number
  pending: number
  total: number
}

/** 综合健康报告：心情与互动摘要 */
export interface MoodSummary {
  post_count: number
  like_received: number
  comment_received: number
  mood_positive: number
  mood_neutral: number
  mood_negative: number
  mood_label: string
  top_content?: string[]
  comfort_line?: string
  mood_trend?: string
}

/** 综合健康报告：体检摘要 */
export interface ExamAbnormalItem {
  indicator: string
  value: string
  status: string
  interpretation: string
}

export interface ExamSummary {
  report_count: number
  risk_counts: { low: number; medium: number; high: number; critical: number }
  risk_label: string
  abnormal_items: ExamAbnormalItem[]
  relevant_indicators: string[]
  summaries: string[]
}

/** 综合健康报告：AI 问答摘要 */
export interface QaSummary {
  question_count: number
  topics: string[]
}

/** 综合健康报告：分段叙事章节 */
export interface NarrativeSection {
  kind: 'skin' | 'mood' | 'exam' | 'social' | 'qa'
  title: string
  body: string
}

export interface SkinReport {
  id: number
  report_type: string
  title: string
  period_start: string | null
  period_end: string | null
  body_site: string | null
  body_site_label: string
  narrative: string | null
  metrics: SkinReportMetrics | null
  insights: string[]
  recommendations: string[]
  trend_chart: TrendChartData | TrendChartWithSeries | null
  status: string
  error_message?: string | null
  is_public: boolean
  share_token: string | null
  created_at: string
  source_data?: any
  post_id?: number
  cover_composite_url?: string | null
  has_cover?: boolean
}

export interface SkinReportListItem {
  id: number
  report_type: string
  title: string
  period_start: string | null
  period_end: string | null
  body_site: string | null
  body_site_label: string
  status: string
  is_public: boolean
  share_token: string | null
  created_at: string
  trend?: string
  has_vasi?: boolean
  headline?: string
  sites_summary?: SitesSummary
  has_cover?: boolean
  cover_composite_url?: string | null
  exam_count?: number
  exam_risk?: string
  qa_count?: number
  mood_label?: string
  post_count?: number
}

export interface PeriodicPreviewItem {
  period_type: 'weekly' | 'monthly'
  label: string
  period_start: string
  period_end: string
  photo_count: number
  site_count: number
  exam_count?: number
  qa_count?: number
  post_count?: number
  can_generate: boolean
  existing_report_id: number | null
  existing_status: string | null
}

// ── API Functions ──

/** 对比照片条目（直接上传用） */
export interface ComparisonPhotoInput {
  image_url: string
  body_site?: string | null
  capture_date?: string | null
}

/** 生成白斑变化对比报告（image_ids 照片 / vasi_ids 历史评估，二选一） */
export function createComparisonReport(data: {
  image_ids?: number[]
  vasi_ids?: number[]
  body_site?: string
  profile_id?: number
}) {
  return apiClient.post<SkinReport>('/skin-reports/comparison', data)
}

/** 保存白斑对比照片（存为私有日记帖，供对比报告选择） */
export function saveComparisonPhotos(photos: ComparisonPhotoInput[]) {
  return apiClient.post<{ status: string; post_id: number; image_ids: number[] }>(
    '/skin-reports/comparison-photos',
    { photos },
  )
}

/** 编辑白斑照片元数据（部位/拍摄日期） */
export function updatePhotoMeta(
  imageId: number,
  data: { body_site?: string | null; capture_date?: string | null },
) {
  return apiClient.patch<{
    status: string
    id: number
    body_site: string | null
    capture_date: string | null
  }>(`/skin-reports/photos/${imageId}`, data)
}

/** 删除白斑照片（仅所有者） */
export function deletePhoto(imageId: number) {
  return apiClient.delete<{ status: string; deleted_id: number }>(
    `/skin-reports/photos/${imageId}`,
  )
}

/** 调整白斑照片顺序（image_ids 按新顺序排列） */
export function reorderPhotos(imageIds: number[]) {
  return apiClient.put<{ status: string }>('/skin-reports/photos/reorder', {
    image_ids: imageIds,
  })
}

/** 历史报告对比：来源报告摘要 */
export interface SynthesisSource {
  report_id: number
  title: string
  period: string
  report_type: string
  headline?: string | null
  trend?: string | null
  narrative?: string | null
  cover_composite_url?: string | null
  site_count?: number | null
  mood_label?: string | null
  exam_risk?: string | null
  qa_count?: number | null
}

/** 基于多份历史报告提炼对比，生成新的对比报告 */
export function synthesizeReports(reportIds: number[]) {
  return apiClient.post<SkinReport>('/skin-reports/synthesize', { report_ids: reportIds })
}

/** 生成白斑周报/月报（后台异步，返回 generating 状态报告） */
export function createPeriodicReport(data: {
  period_type: 'weekly' | 'monthly'
  anchor_date?: string
  body_sites?: string[]
  profile_id?: number
  force?: boolean
}) {
  return apiClient.post<SkinReport>('/skin-reports/periodic', data)
}

/** 周报/月报快捷生成可用性预览 */
export function getPeriodicPreview() {
  return apiClient.get<{ items: PeriodicPreviewItem[] }>('/skin-reports/periodic/preview')
}

/** 获取我的报告列表 */
export function getSkinReports(params?: {
  limit?: number
  offset?: number
  report_type?: string
  body_site?: string
}) {
  return apiClient.get<{ total: number; items: SkinReportListItem[] }>('/skin-reports/', {
    params,
  })
}

/** 获取报告详情 */
export function getSkinReport(id: number) {
  return apiClient.get<SkinReport>(`/skin-reports/${id}`)
}

/** 任意图对按需对比结果（日期切换器） */
export interface PairCompareResult {
  first: TimelineFrame | null
  last: TimelineFrame | null
  pair_metrics: PairMetrics | null
  pair_align: PairAlign | null
}

/** 按需对比报告内任选两张照片（首次计算需数秒，服务端有缓存与频控） */
export function getPairCompare(reportId: number, indexA: number, indexB: number) {
  return apiClient.get<PairCompareResult>(`/skin-reports/${reportId}/pair-compare`, {
    params: { index_a: indexA, index_b: indexB },
    timeout: 120000,
  })
}

/** 公开访问报告（无需登录） */
export function getSharedReport(token: string) {
  return apiClient.get<SkinReport>(`/skin-reports/shared/${token}`)
}

/** 删除报告 */
export function deleteSkinReport(id: number) {
  return apiClient.delete(`/skin-reports/${id}`)
}

/** 发布报告到分享 */
export function shareReportToCommunity(id: number, isAnonymous = false) {
  return apiClient.post<{ status: string; post_id: number; share_url: string }>(
    `/skin-reports/${id}/share-to-community`,
    { is_anonymous: isAnonymous },
  )
}
