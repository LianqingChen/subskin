/**
 * 统一时间解析/相对时间工具
 *
 * 背景：
 * - date-only 字符串（如 "2026-08-05"）按 ES 规范会被 `new Date()` 解析为
 *   **UTC 午夜**，在 UTC+8 时区会产生 8 小时偏移（日记卡片误显示"16小时前"）。
 *   此类字符串必须按本地日期解析：new Date(y, m-1, d)。
 * - 带时区后缀的时间戳（如 "2026-08-04T16:17:44+00:00"）`new Date()` 能正确
 *   解析为 UTC 时刻，计算差值时自动换算到本地时间，无需特殊处理。
 * - 不带时区的 datetime（如 "2026-08-04 16:17:44"）按本地时间处理。
 */

const DATE_ONLY_RE = /^(\d{4})-(\d{1,2})-(\d{1,2})$/
const NAIVE_DATETIME_RE = /^\d{4}-\d{1,2}-\d{1,2}[ T]\d{1,2}:\d{2}/
const TZ_SUFFIX_RE = /(?:[Zz]|[+-]\d{2}:?\d{2})$/

/**
 * 安全解析时间字符串为 Date：
 * - date-only → 本地午夜
 * - 无时区 datetime → 本地时间
 * - 带时区时间戳 → 正确换算
 * 解析失败返回 null。
 */
export function parseDate(input: string | Date | null | undefined): Date | null {
  if (!input) return null
  if (input instanceof Date) {
    return Number.isNaN(input.getTime()) ? null : input
  }
  const s = String(input).trim()
  if (!s) return null

  const dateOnly = s.match(DATE_ONLY_RE)
  if (dateOnly) {
    const d = new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    return Number.isNaN(d.getTime()) ? null : d
  }

  let normalized = s
  if (NAIVE_DATETIME_RE.test(s) && !TZ_SUFFIX_RE.test(s)) {
    // "YYYY-MM-DD HH:mm:ss" → 统一为 ISO 形式，按本地时间解析
    normalized = s.replace(' ', 'T')
  }
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * 相对时间文案：刚刚 / N分钟前 / N小时前 / N天前 / N个月前 / N年前
 * 解析失败返回空字符串。
 */
export function timeAgo(input: string | Date | null | undefined): string {
  const d = parseDate(input)
  if (!d) return ''
  const diff = Date.now() - d.getTime()
  if (diff < 60_000) return '刚刚'
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}个月前`
  return `${Math.floor(months / 12)}年前`
}
