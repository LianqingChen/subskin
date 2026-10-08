import type { ContributionDistribution, ContributionMetric, ContributionPersonalVisuals } from '@/types/contribution'

export const CONTRIBUTION_PARTS = [
  { code: 'head', label: '头面部', sites: ['face', 'scalp'] },
  { code: 'neck', label: '颈部', sites: ['neck'] },
  { code: 'trunk', label: '躯干', sites: ['front', 'back'] },
  { code: 'arms', label: '上肢', sites: ['upper_arm', 'lower_arm', 'arms'] },
  { code: 'hands', label: '手部', sites: ['hands'] },
  { code: 'legs', label: '下肢', sites: ['upper_leg', 'lower_leg', 'legs'] },
  { code: 'feet', label: '足部', sites: ['feet'] },
  { code: 'other', label: '其他 / 待归类', sites: ['genitals', 'other', 'unknown'] },
] as const

export function compactContributionCount(value: number): string {
  return new Intl.NumberFormat('zh-CN', value >= 10000 ? { notation: 'compact', maximumFractionDigits: 1 } : { useGrouping: false }).format(value)
}

export function contributionMetricLabel(metric: ContributionMetric): string {
  if (metric.status !== 'available' || metric.value === null) return metric.status === 'suppressed' ? '未公开' : '待统计'
  return compactContributionCount(metric.value)
}

export function contributionTiles(total: number, mine: number, maximum = 140) {
  const safeTotal = Math.max(0, Math.floor(total))
  const safeMine = Math.min(safeTotal, Math.max(0, Math.floor(mine)))
  if (safeTotal === 0) return { unit: 0, tiles: [] }
  const unit = Math.max(1, Math.ceil(safeTotal / maximum))
  let remaining = safeMine
  const tiles = Array.from({ length: Math.ceil(safeTotal / unit) }, (_, index) => {
    const count = Math.min(unit, safeTotal - index * unit)
    const myCount = Math.min(remaining, count)
    remaining -= myCount
    return { count, mine: myCount, fill: count / unit, mineFill: myCount / unit }
  })
  return { unit, tiles }
}

export function contributionParts(distribution: ContributionDistribution | null, personal: ContributionPersonalVisuals | null, mode: 'community' | 'mine') {
  const source = mode === 'mine' ? personal?.body_sites : distribution?.rows
  return CONTRIBUTION_PARTS.map(part => {
    const rows = part.sites.map(code => source?.find(row => row.code === code))
    const available = !!source && rows.every(row => row?.count !== null && row?.count !== undefined)
    const count = available ? rows.reduce((sum, row) => sum + (row?.count ?? 0), 0) : null
    return { ...part, count }
  })
}
