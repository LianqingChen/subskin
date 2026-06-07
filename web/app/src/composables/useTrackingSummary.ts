import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { vasiApi } from '@/api/vasi'
import type { VasiHistoryItem } from '@/api/vasi'

function formatNumber(value: number | null | undefined, decimals: number): string {
  if (value == null || !Number.isFinite(value)) return '-'
  return value.toFixed(decimals).replace(/\.0$/, '')
}

function formatPercent(value: number): string {
  const rounded = Math.round(value * 10) / 10
  const normalized = rounded.toFixed(1).replace(/\.0$/, '')
  return `${value > 0 ? '+' : ''}${normalized}%`
}

function calculateTrackingDays(items: VasiHistoryItem[]): string {
  if (!items.length) return '-'
  const timestamps = items
    .map((item) => new Date(item.assessment_date).getTime())
    .filter((value) => Number.isFinite(value))
  if (!timestamps.length) return '-'
  const min = Math.min(...timestamps)
  const max = Math.max(...timestamps)
  const days = Math.max(1, Math.floor((max - min) / (1000 * 60 * 60 * 24)) + 1)
  return `${days}`
}

function calculateImprovementRate(items: VasiHistoryItem[]): string {
  if (items.length < 2) return '-'
  const sorted = [...items].sort(
    (a, b) => new Date(a.assessment_date).getTime() - new Date(b.assessment_date).getTime(),
  )
  const firstScore = sorted[0]?.vasi_score ?? null
  const lastScore = sorted[sorted.length - 1]?.vasi_score ?? null
  if (!firstScore || lastScore === null) return '-'
  const improvement = ((firstScore - lastScore) / firstScore) * 100
  return Number.isFinite(improvement) ? formatPercent(improvement) : '-'
}

export interface TrackingSummary {
  assessmentCount: string
  trackingDays: string
  improvementRate: string
  vasiScore: string
}

export function useTrackingSummary() {
  const authStore = useAuthStore()

  const isLoading = ref(false)
  const summary = reactive<TrackingSummary>({
    assessmentCount: '-',
    trackingDays: '-',
    improvementRate: '-',
    vasiScore: '-',
  })

  function reset() {
    summary.assessmentCount = '-'
    summary.trackingDays = '-'
    summary.improvementRate = '-'
    summary.vasiScore = '-'
  }

  async function fetch() {
    if (!authStore.isLoggedIn) {
      reset()
      return
    }

    isLoading.value = true
    try {
      const history = await vasiApi.getHistory(50, 0)
      summary.assessmentCount = history.total ? String(history.total) : '-'
      summary.trackingDays = calculateTrackingDays(history.items)
      summary.improvementRate = calculateImprovementRate(history.items)
      summary.vasiScore = history.items.length
        ? formatNumber(history.items[0].vasi_score, 1)
        : '-'
    } catch (error) {
      console.error('Failed to fetch VASI history:', error)
      reset()
    } finally {
      isLoading.value = false
    }
  }

  return { summary, isLoading, fetch, reset }
}
