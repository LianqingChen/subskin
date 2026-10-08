import apiClient from './client'

// ── Types ──

export interface DiaryImage {
  id: number
  image_url: string
  body_site: string | null
  capture_date: string | null
  visual_analysis: Record<string, any> | null
  analysis_status: string
  vasi_assessment_id: number | null
  order_index: number
}

export interface DiaryImageInput {
  image_url: string
  body_site?: string
  capture_date?: string
}

export interface DiaryEntry {
  id: number
  user_id?: number
  profile_id?: number | null
  raw_text: string
  input_type: string
  mood: string | null
  sleep_quality: string | null
  diet_notes: string | null
  medication_taken: string | null
  stress_level: number | null
  skin_condition: string | null
  treatment_events_json: string | null
  ai_summary: string | null
  ai_extracted_json: string | null
  entry_date: string
  created_at: string
  vasi_assessment_id: number | null
  is_public: boolean
  post_id: number | null
  images_count: number
  images: DiaryImage[]
}

export interface DiaryCreateRequest {
  raw_text: string
  input_type?: string
  entry_date?: string
  profile_id?: number
  vasi_assessment_id?: number
  images?: DiaryImageInput[]
}

export interface DiaryQuickRequest {
  mood?: string
  medication_taken?: string
  skin_condition?: string
  sleep_quality?: string
  stress_level?: number
  note?: string
}

export interface DiaryListResponse {
  items: DiaryEntry[]
  total: number
}

export interface CalendarDay {
  date: string
  count: number
  moods: string[]
  has_assessment: boolean
}

export interface CalendarResponse {
  year: number
  month: number
  days: CalendarDay[]
}

export interface DailyMood {
  date: string
  moods: string[]
}

export interface WeeklyReport {
  week_start: string
  week_end: string
  entry_count: number
  recorded_days: number
  mood_distribution: Record<string, number>
  sleep_distribution: Record<string, number>
  avg_stress_level: number | null
  vasi_count: number
  daily_moods: DailyMood[]
  ai_summary: string | null
  insights: string[]
  current_streak: number
  recorded_today: boolean
}

// ── API Functions ──

/** 创建日记（AI自动提取结构化信息） */
export function createDiaryEntry(data: DiaryCreateRequest) {
  return apiClient.post<DiaryEntry>('/diary/entries', data)
}

/** 快捷记录 */
export function createQuickEntry(data: DiaryQuickRequest) {
  return apiClient.post<DiaryEntry>('/diary/quick', data)
}

/** 获取日记列表 */
export function getDiaryEntries(params?: {
  limit?: number
  offset?: number
  start_date?: string
  end_date?: string
}) {
  return apiClient.get<DiaryListResponse>('/diary/entries', { params })
}

/** 获取单条日记 */
export function getDiaryEntry(id: number) {
  return apiClient.get<DiaryEntry>(`/diary/entries/${id}`)
}

/** 更新日记 */
export function updateDiaryEntry(id: number, data: Partial<DiaryEntry>) {
  return apiClient.put<DiaryEntry>(`/diary/entries/${id}`, data)
}

/** 删除日记 */
export function deleteDiaryEntry(id: number) {
  return apiClient.delete(`/diary/entries/${id}`)
}

/** 获取日历数据 */
export function getDiaryCalendar(year: number, month: number) {
  return apiClient.get<CalendarResponse>('/diary/calendar', {
    params: { year, month },
  })
}

/** 获取周报 */
export function getWeeklyReport() {
  return apiClient.get<WeeklyReport>('/diary/summary/weekly')
}

/** 获取统计概览 */
export function getDiaryStats() {
  return apiClient.get<{
    total_entries: number
    current_streak: number
    recorded_today: boolean
    week_count: number
  }>('/diary/stats')
}

/** 为日记追加图片（触发轻量视觉分析） */
export function addDiaryImages(entryId: number, images: DiaryImageInput[]) {
  return apiClient.post<DiaryEntry>(`/diary/entries/${entryId}/images`, { images })
}

/** 对日记图片触发深度白斑分析（VASI 分割管线） */
export function deepAnalyzeDiaryImage(imageId: number) {
  return apiClient.post<{ status: string; vasi_assessment_id: number }>(
    `/diary/images/${imageId}/deep-analyze`,
  )
}
