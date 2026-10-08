import type { AssessmentResult, PhotoMeasurement } from '@/types/assessment'
import { siteLabel } from './content'
/** 仅在用户核对过范围且测量有效时返回“照片内白斑占比”，否则 null。 */
export function measuredPercentage(m: PhotoMeasurement | null | undefined): number | null {
  const value = m?.area_percentage
  const reviewed = m?.annotation?.review_state === 'user_reviewed'
  return reviewed && ['measured', 'partial'].includes(m?.status || '') && typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null
}
export function journalSummary(result: AssessmentResult) {
  const m = result.measurement, reviewed = m?.annotation?.review_state === 'user_reviewed'
  const percentage = measuredPercentage(m), measurable = percentage !== null
  const label = percentage === null ? '暂不可量化' : `${Number(percentage.toFixed(2))}%`
  const site = siteLabel(result.bodySite), date = result.observation?.capture_date || ''
  const revision = m?.annotation?.mask_revision || m?.mask_revision || ''
  const notice = !reviewed ? '请先核对照片范围' : !measurable ? '本次暂不能提供可靠占比' : m?.touches_frame || m?.status === 'partial' ? '范围到达画面边缘，仅反映照片内可见部分' : percentage === 0 ? '当前确认范围内无白斑标注' : ''
  const dataLines = [`${site}${date ? ` · ${date}` : ''}`, `照片内白斑占比：${label}`]
  if (measurable && Number.isInteger(m?.region_count) && (m?.region_count ?? -1) >= 0) dataLines.push(`可见标注区域：${m?.region_count} 处`)
  if (measurable && Number.isInteger(m?.lesion_pixels) && Number.isInteger(m?.skin_pixels) && (m?.lesion_pixels ?? -1) >= 0 && (m?.skin_pixels ?? 0) > 0) dataLines.push(`白斑标注 ${m?.lesion_pixels} 像素 / 可见皮肤 ${m?.skin_pixels} 像素`)
  if (measurable && typeof m?.area_cm2 === 'number' && Number.isFinite(m.area_cm2) && m.area_cm2 >= 0) dataLines.push(`参照物估算：${m.area_cm2} cm²（二维投影）`)
  if (notice) dataLines.push(notice)
  return { reviewed, measurable, percentage, label, site, date, revision, notice, dataLines,
    line: `${site}${date ? ` · ${date}` : ''} · 照片内白斑占比${label}` }
}
