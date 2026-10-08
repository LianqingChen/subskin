import { readPhotoTakenDate } from './exif'

export type CaptureSource = 'gallery' | 'camera'
export function localToday(now = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
export function validPhotoDate(value: string | null, today = localToday()): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value > today) return false
  const [y, m, d] = value.split('-').map(Number)
  const parsed = new Date(y, m - 1, d)
  return y >= 1900 && parsed.getFullYear() === y && parsed.getMonth() === m - 1 && parsed.getDate() === d
}
export async function defaultCaptureDate(file: File, source: CaptureSource, today = localToday()) {
  if (source === 'camera') return { date: today, note: '已填写本次拍摄日期' }
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    const date = await Promise.race([readPhotoTakenDate(file), new Promise<null>(resolve => { timer = setTimeout(() => resolve(null), 3000) })])
    return validPhotoDate(date, today)
      ? { date, note: '已读取照片中的日期，可修改' }
      : { date: today, note: '照片没有可用日期，已填今天，可修改' }
  } finally { clearTimeout(timer) }
}
