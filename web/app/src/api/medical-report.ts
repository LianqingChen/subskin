import apiClient from './client'

/** Convert backend-relative file_url to the authenticated serving URL.
 *  Optionally appends access_token query param for auth (the API
 *  requires Bearer auth, which new tabs can't send via header). */
export function getFileServeUrl(fileUrl: string, accessToken?: string | null): string {
  const base = fileUrl.replace(/^\/uploads\//, '/api/files/serve/')
  return accessToken ? `${base}?access_token=${encodeURIComponent(accessToken)}` : base
}

/** Build the HTML viewer URL for a file.
 *  Works in all browsers including WeChat — renders PDF pages as images or shows images directly. */
export function getFileViewUrl(fileId: number, accessToken?: string | null): string {
  const base = `/api/files/view/${fileId}`
  return accessToken ? `${base}?access_token=${encodeURIComponent(accessToken)}` : base
}

export interface MedicalReportFile {
  id: number
  file_url: string
  file_name: string
  file_size: number
  file_type: string | null
  order: number
}

export interface ExtractedPatientInfo {
  name: string | null
  gender: string | null
  age: number | null
  exam_date: string | null
  confidence: number
}

export interface MedicalReport {
  id: number
  title: string
  tags: string | null
  files: MedicalReportFile[]
  interpretation_json: InterpretationResult | null
  created_at: string
  updated_at: string | null
  patient_profile_id: number | null
  extracted_patient_info_json: ExtractedPatientInfo | null
}

export interface InterpretationResult {
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  summary: string
  parsed_indicators: ParsedIndicator[]
  abnormal_items: AbnormalItem[]
  sections?: ReportSection[]  // New: per-section breakdown with traffic lights
  recommendations: Recommendation[]
  disclaimer: string
  schema_version: string
  parser_version: string
  llm_model: string
  generated_at: string
  extracted_patient_info?: ExtractedPatientInfo
}

export interface ReportSection {
  section_name: string
  risk: 'red' | 'yellow' | 'green'
  indicator_count: number
  abnormal_count: number
  section_summary: string
  indicators: SectionIndicator[]
  abnormal_items: AbnormalItem[]
  _expanded?: boolean  // UI state
}

export interface SectionIndicator {
  name: string
  value: string
  unit: string
  ref_range: string
  status: 'normal' | 'high' | 'low' | 'critical'
}

export interface ParsedIndicator {
  indicator_name: string
  value: string
  status: 'normal' | 'high' | 'low'
  ref_range: string
  canonical_name?: string
  unit_family?: string
}

export interface SourceIndicator {
  indicator_name: string
  value: string
  ref_range: string
}

export interface AbnormalItem {
  indicator_name: string
  value: string
  status: 'high' | 'low' | 'critical'
  interpretation: string
  possible_causes: string[]
  suggestions: string[]
  source_indicators: SourceIndicator[]
  source_text_excerpt: string
  confidence: number
}

export interface Recommendation {
  content: string
}

export interface MedicalReportListResponse {
  total: number
  items: MedicalReport[]
}

export interface ComparisonResult {
  reports: ComparisonReportMeta[]
  indicators: ComparisonIndicator[]
  summary: ComparisonSummary
  overall_assessment: OverallAssessment
}

export interface ComparisonReportMeta {
  id: number
  date: string
  title: string
}

export interface ComparisonIndicator {
  canonical_name: string
  display_name: string
  unit: string
  ref_range: string
  values: IndicatorValue[]
  change_category: 'newly_abnormal' | 'resolved_abnormal' | 'persistent_abnormal' | 'large_delta' | 'unchanged_stable' | 'not_measured'
  delta: number
  trend: 'improving' | 'stable' | 'worsening'
  trend_interpretation: string
}

export interface IndicatorValue {
  report_id: number
  date: string
  value: number
  status: 'normal' | 'high' | 'low' | 'critical'
}

export interface ComparisonSummary {
  total_indicators: number
  comparable: number
  newly_abnormal: number
  resolved: number
  persistent_abnormal: number
  unchanged: number
  not_measured: number
}

export interface OverallAssessment {
  trend: 'improving' | 'stable' | 'worsening'
  summary: string
  highlights: string[]
  concerns: string[]
  recommendations: string[]
}

export const medicalReportApi = {
  async list(limit = 20, offset = 0): Promise<MedicalReportListResponse> {
    const { data } = await apiClient.get('/medical-reports/', { params: { limit, offset } })
    return data
  },

  async get(reportId: number): Promise<MedicalReport> {
    const { data } = await apiClient.get(`/medical-reports/${reportId}`)
    return data
  },

  async create(title: string, tags: string | null, files: File[]): Promise<MedicalReport> {
    const formData = new FormData()
    formData.append('title', title)
    if (tags) formData.append('tags', tags)
    files.forEach((file) => {
      formData.append('files', file)
    })
    const { data } = await apiClient.post('/medical-reports/', formData)
    return data
  },

  async delete(reportId: number): Promise<void> {
    await apiClient.delete(`/medical-reports/${reportId}`)
  },

  async interpret(reportId: number, age?: number, gender?: string): Promise<InterpretationResult> {
    const formData = new FormData()
    if (age) formData.append('user_age', String(age))
    if (gender) formData.append('user_gender', gender)
    const { data } = await apiClient.post(`/medical-reports/${reportId}/interpret`, formData)
    return data
  },

  async getInterpretation(reportId: number): Promise<{ interpreted: boolean } & Partial<InterpretationResult>> {
    const { data } = await apiClient.get(`/medical-reports/${reportId}/interpretation`)
    return data
  },

  async linkProfile(reportId: number, patientProfileId: number): Promise<MedicalReport> {
    const { data } = await apiClient.post(`/medical-reports/${reportId}/link-profile`, {
      patient_profile_id: patientProfileId
    })
    return data
  },

  async compare(reportIds: number[]): Promise<ComparisonResult> {
    const { data } = await apiClient.post('/medical-reports/compare', {
      report_ids: reportIds
    })
    return data
  },
}
