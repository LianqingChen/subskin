export interface ContributionMetric { value: number | null; status: 'available' | 'unavailable' | 'suppressed'; unit: string; note: string }
export interface ContributionLevel { level: number; name: string; threshold: number }
export interface ContributionRule { kind: string; title: string; points: number; enabled: boolean; note: string }
export interface ContributionOverview {
  updated_at: string; version: string; users: ContributionMetric; contributors: ContributionMetric
  images: ContributionMetric; checked: ContributionMetric; doctor_ratio: ContributionMetric; followup: ContributionMetric
  rules: ContributionRule[]; levels: ContributionLevel[]
}
export interface MyContributions {
  updated_at: string; version: string; images: ContributionMetric; checked: ContributionMetric; reports: ContributionMetric
  doctor: ContributionMetric; impact: ContributionMetric; uploaded: number; personally_checked: number; pending: number
  report_contribution: ContributionMetric; active_consent: boolean
  membership: { points: number; current: ContributionLevel; next: ContributionLevel | null; progress: number; remaining: number }
  badges: { name: string; icon: string; earned: boolean }[]
}
export interface ContributionDistribution {
  status: 'available' | 'suppressed'; updated_at: string; version: string; note: string
  rows: { code: string; label: string; count: number | null }[]
  types: { status: 'unavailable'; note: string; columns: string[] }
  dimensions: { name: string; status: 'available' | 'unavailable' }[]; coverage: ContributionMetric
}
export interface ContributionEvent { id: number; title: string; points: number; rule_version: string; awarded_at: string }
export interface ContributionEvents { total: number; items: ContributionEvent[] }
