/** 日期统一显示为 YYYY-MM-DD；无效值返回空串 */
export function fmtDate(value?: string | null): string {
  if (!value) return ''
  return /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : ''
}
