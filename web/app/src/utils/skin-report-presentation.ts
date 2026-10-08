import type { SkinReport, SiteSection } from '@/api/skin_report'
import { toProtectedFileUrl } from '@/utils/file-url'
export function trendStyle(trend: string) {
  if (trend === '好转')
    return { bg: 'bg-primary-50 text-primary-700 border-primary-200', icon: 'ri-arrow-down-line', label: '好转' }
  if (trend === '加重')
    return { bg: 'bg-rose-50 text-rose-700 border-rose-200', icon: 'ri-arrow-up-line', label: '加重' }
  if (trend === '稳定')
    return { bg: 'bg-amber-50 text-amber-700 border-amber-200', icon: 'ri-subtract-line', label: '稳定' }
  return { bg: 'bg-slate-50 text-slate-600 border-slate-200', icon: 'ri-question-line', label: trend }
}

/** 部位卡片指标徽章：VASI 数值优先，spot_compare 指标仅在置信度足够时展示 */
export function siteBadges(s: SiteSection) {
  const badges: { icon: string; text: string; cls: string }[] = []
  const pm = s.pair_metrics

  if (s.vasi_change != null) {
    badges.push({
      icon: 'ri-line-chart-line',
      text: `VASI ${s.vasi_change > 0 ? '+' : ''}${s.vasi_change}`,
      cls: s.vasi_change < 0 ? 'ps-badge--good' : s.vasi_change > 0 ? 'ps-badge--bad' : 'ps-badge--flat',
    })
  }
  if (pm?.comparison_status === 'measured' && !pm.low_confidence && !pm.duplicate) {
    if (pm.melanin_score_b != null) {
      const up = (pm.melanin_change ?? 0) > 0
      badges.push({
        icon: 'ri-drop-line',
        text: `复色指数 ${pm.melanin_score_a ?? '—'}→${pm.melanin_score_b}`,
        cls: up ? 'ps-badge--good' : 'ps-badge--flat',
      })
    }
    if (pm.size_change_percent != null) {
      const shrink = pm.size_change_percent < 0
      badges.push({
        icon: shrink ? 'ri-zoom-out-line' : 'ri-zoom-in-line',
        text: `面积 ${shrink ? '' : '+'}${pm.size_change_percent}%`,
        cls: shrink ? 'ps-badge--good' : 'ps-badge--bad',
      })
    }
    if (pm.melanin_signals?.edge_inward) {
      badges.push({ icon: 'ri-shrink-line', text: '边缘内收', cls: 'ps-badge--good' })
    }
    if ((pm.melanin_signals?.follicular_repigmentation ?? 0) >= 2) {
      badges.push({ icon: 'ri-sparkling-line', text: '点状复色明显', cls: 'ps-badge--good' })
    }
  } else if (pm?.comparison_status === 'measured' && !pm.duplicate) {
    badges.push({ icon: 'ri-error-warning-line', text: '此次无法可靠比较', cls: 'ps-badge--flat' })
  }
  return badges
}

export function fmtDate(d: string | null) {
  return d ? d.slice(0, 10) : ''
}

export function protectedUrl(url?: string | null) {
  if (!url) return ''
  return toProtectedFileUrl(url) || url
}


export function coverChips(report: SkinReport | null) {
  const m = report?.metrics
  if (!m || report?.report_type !== 'comparison') return []
  const good = 'rc-chip--good'
  const bad = 'rc-chip--bad'
  const flat = 'rc-chip--flat'
  const chips: { icon: string; text: string; cls: string }[] = []
  const trend = trendStyle(m.trend)
  chips.push({ icon: trend.icon, text: trend.label, cls: trend.bg })
  const pm = m.pair_metrics
  if (pm?.comparison_status === 'measured' && !pm.duplicate) {
    if (pm.size_change_percent != null) {
      const shrink = pm.size_change_percent < 0
      chips.push({
        icon: shrink ? 'ri-zoom-out-line' : 'ri-zoom-in-line',
        text: `面积 ${shrink ? '' : '+'}${pm.size_change_percent}%`,
        cls: shrink ? good : bad,
      })
    }
    if (pm.melanin_score_a != null && pm.melanin_score_b != null) {
      const up = (pm.melanin_change ?? 0) > 0
      chips.push({ icon: 'ri-drop-line', text: `复色指数 ${pm.melanin_score_a}→${pm.melanin_score_b}`, cls: up ? good : flat })
    }
  }
  if (m.has_vasi && m.vasi_change != null) {
    chips.push({
      icon: 'ri-line-chart-line',
      text: `VASI ${m.vasi_change > 0 ? '+' : ''}${m.vasi_change}`,
      cls: m.vasi_change < 0 ? good : m.vasi_change > 0 ? bad : flat,
    })
  }
  return chips
}

