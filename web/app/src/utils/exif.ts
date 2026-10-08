/**
 * EXIF 拍摄日期读取工具
 *
 * 从用户上传的照片文件中读取 EXIF 拍摄时间（DateTimeOriginal 等标签），
 * 返回 YYYY-MM-DD 本地日期字符串；读取失败或照片无 EXIF 时返回 null。
 * 支持 JPEG / PNG / WebP / HEIC 等 exifr 可解析的格式。
 */
import { parse } from 'exifr'

/** 按优先级取用：原始拍摄时间 > 数字化时间 > 文件修改时间 > 通用时间 */
const DATE_TAGS = ['DateTimeOriginal', 'CreateDate', 'ModifyDate', 'DateTime']

function toDateStr(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** 解析 EXIF 日期字符串（"YYYY:MM:DD HH:MM:SS" 或 "YYYY-MM-DD ..."） */
function parseExifDateStr(raw: string): string | null {
  const m = raw.trim().match(/^(\d{4})[:/-](\d{1,2})[:/-](\d{1,2})/)
  if (!m) return null
  const y = Number(m[1])
  const mo = Number(m[2])
  const d = Number(m[3])
  if (y < 1000 || mo < 1 || mo > 12 || d < 1 || d > 31) return null
  return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

/**
 * 读取照片的 EXIF 拍摄日期。
 * @param file 用户选择的图片文件
 * @returns 拍摄日期 YYYY-MM-DD（本地时区），无有效 EXIF 时返回 null
 */
export async function readPhotoTakenDate(file: File): Promise<string | null> {
  try {
    const exif = await parse(file, {
      pick: [...DATE_TAGS],
    })
    if (!exif || typeof exif !== 'object') return null
    const record = exif as Record<string, unknown>
    for (const tag of DATE_TAGS) {
      const v = record[tag]
      if (v instanceof Date && !Number.isNaN(v.getTime())) return toDateStr(v)
      if (typeof v === 'string' && v.trim()) {
        const s = parseExifDateStr(v)
        if (s) return s
      }
    }
    return null
  } catch {
    // 无 EXIF / 解析失败：静默降级为手动填写
    return null
  }
}
