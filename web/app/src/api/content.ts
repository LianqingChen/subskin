import apiClient from './client'

export interface DailyBriefingStat {
  source: string
  count: number
}

export interface DailyBriefing {
  date: string
  total: number
  stats: DailyBriefingStat[]
  summary: string
}

export interface DailyBriefingResponse {
  available: boolean
  briefing: DailyBriefing | null
}

export const contentApi = {
  async getDailyBriefing(): Promise<DailyBriefingResponse> {
    const { data } = await apiClient.get('/content/daily-briefing')
    return data
  },

  async getLatest(limit = 10): Promise<{ count: number; latest: unknown[] }> {
    const { data } = await apiClient.get('/content/latest', { params: { limit } })
    return data
  },

  async getTimeline(limit = 20): Promise<TimelineResponse> {
    const { data } = await apiClient.get('/content/timeline', { params: { limit } })
    return data
  },
}

export interface TimelineHighlight {
  id: number
  title: string
  source: string
  category: string
}

export interface TimelineItem {
  month: string
  count: number
  highlights: TimelineHighlight[]
}

export interface TimelineResponse {
  timeline: TimelineItem[]
}
