import apiClient from './client'

export interface OverviewData {
  total_users: number
  today_uv: number
  today_pv: number
  new_users_today: number
  today_active_users: number
}

export interface TrendData {
  days: number
  items: Array<{
    date: string
    uv: number
    pv: number
    new_users: number
  }>
}

export interface RegistrationTrendItem {
  date: string
  new_users: number
  cumulative_users: number
}

export interface JourneyLink {
  source: number
  target: number
  value: number
}

export interface TopPath {
  path: string
  count: number
}

export interface UserJourneyData {
  nodes: string[]
  links: JourneyLink[]
  top_paths: TopPath[]
  total_sessions: number
}

export interface FunnelStep {
  name: string
  count: number
  rate: number
  rate_from_prev?: number
}

export interface FeatureUsageData {
  name: string
  uv: number
  pv: number
}

export const analyticsApi = {
  overview() {
    return apiClient.get<OverviewData>('/analytics/overview').then(r => r.data)
  },
  trend(days: number = 30) {
    return apiClient.get<TrendData>('/analytics/trend', { params: { days } }).then(r => r.data)
  },
  registrationTrend(days: number = 14) {
    return apiClient.get<RegistrationTrendItem[]>('/analytics/registration-trend', { params: { days } }).then(r => r.data)
  },
  userJourneys(days: number = 7, limit: number = 50) {
    return apiClient.get<UserJourneyData>('/analytics/user-journeys', { params: { days, limit } }).then(r => r.data)
  },
  funnel(days: number = 30) {
    return apiClient.get<FunnelStep[]>('/analytics/funnel', { params: { days } }).then(r => r.data)
  },
  featureUsage(days: number = 7) {
    return apiClient.get<FeatureUsageData[]>('/analytics/feature-usage', { params: { days } }).then(r => r.data)
  },
}
