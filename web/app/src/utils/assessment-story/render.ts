import QRCode from 'qrcode'
import { STORY_URL, type StoryFormat, type StoryTheme } from './content'
import { analyzeStoryMask, type StoryShape } from './mask'
import { storyArtworkRect } from './geometry'
export const STORY_PALETTES = {
  sky: { top: '#c1deeb', bottom: '#f4e9d6', ink: '#204f60', light: '#fffdf6', accent: '#80b4cd' },
  island: { top: '#8ac5c4', bottom: '#e9efe2', ink: '#1a5353', light: '#f9e8bd', accent: '#438b82' },
  stars: { top: '#15273f', bottom: '#475b73', ink: '#f8f0dc', light: '#fff4cc', accent: '#c4d9e9' },
} as const
export function loadStoryImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const timer = window.setTimeout(() => { img.src = ''; reject(new Error('图片加载超时，请重试')) }, 15000)
    img.crossOrigin = 'anonymous'
    img.onload = () => { clearTimeout(timer); resolve(img) }
    img.onerror = () => { clearTimeout(timer); reject(new Error('图片暂时无法读取，请重试')) }
    img.src = src
  })
}
export async function loadStoryShape(src: string): Promise<StoryShape | null> {
  const img = await loadStoryImage(src)
  if (img.naturalWidth * img.naturalHeight > 16777216) throw new Error('轮廓尺寸过大，请重新保存范围')
  const canvas = document.createElement('canvas')
  canvas.width = img.naturalWidth; canvas.height = img.naturalHeight
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('当前浏览器无法生成图片')
  ctx.drawImage(img, 0, 0)
  return analyzeStoryMask(ctx.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height)
}
function text(ctx: CanvasRenderingContext2D, value: string, x: number, y: number, width: number, size: number, color: string, maxLines = 2) {
  let lines: string[] = []
  // Fit the complete text; never silently truncate the user's selected words.
  for (let attempt = size; attempt >= 16; attempt--) {
    ctx.font = `${attempt >= 48 ? '500' : '400'} ${attempt}px "Noto Serif CJK SC", "Songti SC", "Microsoft YaHei", serif`
    lines = []; let line = ''
    for (const char of value) {
      if (char === '\n') { lines.push(line); line = ''; continue }
      if (line && ctx.measureText(line + char).width > width) { lines.push(line); line = char } else line += char
    }
    if (line) lines.push(line)
    if (lines.length <= maxLines) { size = attempt; break }
  }
  ctx.fillStyle = color
  lines.forEach((line, index) => ctx.fillText(line, x, y + index * size * 1.4))
}
export function silhouette(shape: StoryShape, theme: StoryTheme, artwork?: HTMLImageElement): HTMLCanvasElement {
  const b = shape.bounds, c = document.createElement('canvas')
  c.width = b.width; c.height = b.height
  const ctx = c.getContext('2d')
  if (!ctx) throw new Error('无法绘制轮廓')
  const image = ctx.createImageData(b.width, b.height)
  for (let y = 0; y < b.height; y++) for (let x = 0; x < b.width; x++) {
    if (!shape.pixels[(y + b.y) * shape.width + x + b.x]) continue
    const i = (y * b.width + x) * 4
    image.data[i] = 255; image.data[i + 1] = 255; image.data[i + 2] = 255; image.data[i + 3] = 255
  }
  ctx.putImageData(image, 0, 0)
  if (artwork) {
    // Generated pixels are clipped to the original binary mask; every hole stays empty.
    ctx.globalCompositeOperation = 'source-in'
    // Match the server's centered 512px guide, retaining coordinates across all islands.
    const guideScale = Math.min(1, 512 / Math.max(shape.width, shape.height))
    const guideWidth = Math.max(1, Math.round(shape.width * guideScale)), guideHeight = Math.max(1, Math.round(shape.height * guideScale))
    const sx = artwork.naturalWidth / 512, sy = artwork.naturalHeight / 512
    const left = Math.floor((512 - guideWidth) / 2), top = Math.floor((512 - guideHeight) / 2)
    ctx.drawImage(artwork, (left + b.x * guideWidth / shape.width) * sx, (top + b.y * guideHeight / shape.height) * sy,
      b.width * guideWidth / shape.width * sx, b.height * guideHeight / shape.height * sy, 0, 0, c.width, c.height)
    return c
  }
  ctx.globalCompositeOperation = 'source-in'
  const gradient = ctx.createLinearGradient(0, 0, c.width * .7, c.height)
  gradient.addColorStop(0, STORY_PALETTES[theme].light)
  gradient.addColorStop(.45, theme === 'island' ? '#b6cb94' : theme === 'stars' ? '#e3d3ae' : '#ffffff')
  gradient.addColorStop(1, theme === 'island' ? '#478d80' : theme === 'stars' ? '#809dbd' : '#accbd9')
  ctx.fillStyle = gradient; ctx.fillRect(0, 0, c.width, c.height)
  // Texture is clipped inside the exact binary silhouette; geometry stays intact.
  ctx.globalCompositeOperation = 'source-atop'
  let seed = shape.area + 17
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296 }
  for (let i = 0; i < 32; i++) {
    const x = random() * c.width, y = random() * c.height
    const radius = Math.max(8, Math.min(c.width, c.height) * (.09 + random() * .2))
    const mist = ctx.createRadialGradient(x, y, 0, x, y, radius)
    mist.addColorStop(0, theme === 'island' ? '#eef3c44d' : theme === 'stars' ? '#fff2d655' : '#ffffffaa')
    mist.addColorStop(1, '#ffffff00'); ctx.fillStyle = mist; ctx.fillRect(0, 0, c.width, c.height)
  }
  return c
}
function art(ctx: CanvasRenderingContext2D, shape: StoryShape, theme: StoryTheme, y: number, height: number, artwork?: HTMLImageElement) {
  const p = STORY_PALETTES[theme]
  ctx.save()
  ctx.beginPath(); ctx.rect(0, y, 1080, height); ctx.clip()
  // Delicate horizon lines frame the actual silhouette; no invented lesion shapes.
  ctx.strokeStyle = theme === 'stars' ? '#ffffff18' : '#ffffff55'; ctx.lineWidth = 1
  for (let i = 0; i < 5; i++) {
    ctx.beginPath(); ctx.ellipse(540, y + height + 140 + i * 27, 690, height * .64, -.12, Math.PI, Math.PI * 2); ctx.stroke()
  }
  const c = silhouette(shape, theme, artwork)
  const { width: w, height: h, x, y: top, scale } = storyArtworkRect(shape.bounds, y, height)
  ctx.shadowColor = theme === 'stars' ? '#fce3a0' : theme === 'island' ? '#247c7d88' : '#598ca366'
  ctx.shadowBlur = theme === 'stars' ? 28 : 24; ctx.shadowOffsetY = theme === 'island' ? 16 : 12
  ctx.drawImage(c, x, top, w, h); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0
  // A deterministic texture follows the same filled pixels, including all holes.
  let seed = shape.area + shape.width * 31 + shape.height
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296 }
  for (let i = 0; i < (theme === 'stars' ? 500 : 1000); i++) {
    const px = Math.floor(random() * c.width), py = Math.floor(random() * c.height)
    if (!shape.pixels[(py + shape.bounds.y) * shape.width + px + shape.bounds.x]) continue
    const xx = x + px * scale, yy = top + py * scale
    ctx.fillStyle = theme === 'stars' ? '#fff9dfbb' : '#ffffff30'
    ctx.beginPath(); ctx.arc(xx, yy, theme === 'stars' ? 1 + random() * 2.5 : .6 + random(), 0, Math.PI * 2); ctx.fill()
  }
  ctx.fillStyle = p.ink; ctx.globalAlpha = .5
  ctx.font = '16px sans-serif'; ctx.fillText('CONTOURS OF ME', 74, y + height - 8)
  ctx.textAlign = 'right'; ctx.fillText('每一种形状，都有风景', 1006, y + height - 8)
  ctx.restore(); ctx.textAlign = 'left'; ctx.globalAlpha = 1
}
export interface StoryPosterInput {
  shape: StoryShape; theme: StoryTheme; format: StoryFormat
  story: { title: string }; title?: string
  facts?: { site: string; percentage: number | null; date: string }
  photo?: HTMLImageElement
  artwork?: HTMLImageElement
}
export async function renderStoryPoster(input: StoryPosterInput): Promise<Blob> {
  await document.fonts.ready
  const { shape, theme, story } = input
  const height = { portrait: 1440, square: 1080, full: 1920 }[input.format]
  const canvas = document.createElement('canvas'); canvas.width = 1080; canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('当前浏览器无法导出图片')
  const palette = STORY_PALETTES[theme], bg = ctx.createLinearGradient(0, 0, 0, height)
  bg.addColorStop(0, palette.top); bg.addColorStop(1, palette.bottom)
  ctx.fillStyle = bg; ctx.fillRect(0, 0, 1080, height)
  text(ctx, '我的轮廓故事', 72, 88, 650, 28, palette.ink, 1)
  art(ctx, shape, theme, 130, height - 610, input.artwork)
  text(ctx, input.title || story.title, 72, height - 360, 936, 58, palette.ink, 2)
  ctx.strokeStyle = theme === 'stars' ? '#ffffff44' : '#204f6033'
  ctx.beginPath(); ctx.moveTo(72, height - 190); ctx.lineTo(1008, height - 190); ctx.stroke()
  text(ctx, 'SubSkin', 72, height - 122, 600, 36, palette.ink, 1)
  text(ctx, '记录自己，也遇见同行的人', 72, height - 74, 700, 24, palette.ink, 1)
  text(ctx, '轮廓创意 · subskin.cn', 72, height - 35, 650, 18, palette.ink, 1)
  const qr = document.createElement('canvas')
  await QRCode.toCanvas(qr, STORY_URL, { width: 152, margin: 4, errorCorrectionLevel: 'M', color: { dark: '#153f49', light: '#ffffff' } })
  ctx.drawImage(qr, 856, height - 168, 152, 152)
  return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('导出失败，请重试')), 'image/png'))
}
