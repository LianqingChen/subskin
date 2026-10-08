/**
 * 前端 PII（个人隐私信息）预检 — 与后端 utils/pii_detect.py 保持一致的检测口径。
 * 用于发布/分享前的用户提示（真正强制脱敏在服务端）。
 */

const PHONE_RE = /(?<!\d)(1[3-9]\d{9})(?!\d)/
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/
const ID_CARD_RE = /(?<!\d)(\d{17}[\dXx])(?!\d)/

export type PiiType = 'phone' | 'email' | 'id_card'

const LABELS: Record<PiiType, string> = {
  phone: '手机号',
  email: '邮箱',
  id_card: '身份证号',
}

export function detectPii(text: string): string[] {
  if (!text) return []
  const hits: PiiType[] = []
  if (PHONE_RE.test(text)) hits.push('phone')
  if (EMAIL_RE.test(text)) hits.push('email')
  if (ID_CARD_RE.test(text)) hits.push('id_card')
  return hits.map((h) => LABELS[h])
}
