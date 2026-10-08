<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4 overflow-y-auto" @click.self="close">
    <div class="relative w-full max-w-[375px] flex flex-col gap-3">
      <!-- Close button -->
      <button @click="close" class="absolute -top-1 -right-1 z-10 w-8 h-8 rounded-full bg-black/50 text-white flex items-center justify-center">
        <i class="ri-close-line text-lg"></i>
      </button>

      <!-- Poster image -->
      <div class="w-full rounded-xl overflow-hidden shadow-2xl bg-white min-h-[400px] flex items-center justify-center" :class="{ 'animate-pulse-once': posterImageUrl && !isGenerating }">
        <div v-if="isGenerating" class="flex flex-col items-center gap-3 text-gray-400 py-20">
          <i class="ri-loader-4-line animate-spin text-3xl text-primary-500"></i>
          <span class="text-sm font-medium">正在生成海报...</span>
        </div>
        <img
          v-else-if="posterImageUrl"
          :src="posterImageUrl"
          alt="分享海报"
          class="w-full h-auto block"
          style="-webkit-touch-callout: default; user-select: auto;"
        />
        <div v-else class="text-sm text-red-500 py-20">生成失败，请重试</div>
      </div>

      <!-- Hint -->
      <div v-if="posterImageUrl && !isGenerating" class="text-center text-white/70 text-xs">
        <template v-if="isWeChat">
          <i class="ri-hand-heart-line mr-1"></i>长按图片保存到相册，再分享到微信
        </template>
        <template v-else-if="canShareFiles">
          <i class="ri-share-line mr-1"></i>点击「分享」可直接发送到微信等应用
        </template>
        <template v-else>
          <i class="ri-hand-heart-line mr-1"></i>长按图片保存到相册，再分享到微信
        </template>
      </div>

      <!-- Action buttons -->
      <div class="flex gap-3">
        <button
          v-if="canShareFiles && !isWeChat"
          @click="sharePoster"
          :disabled="!posterImageUrl || isGenerating"
          class="flex-1 py-3 px-4 rounded-xl bg-primary-500 text-white font-medium shadow-lg active:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <i class="ri-share-line mr-1"></i>分享
        </button>
        <button
          v-if="!isWeChat"
          @click="downloadPoster"
          :disabled="!posterImageUrl || isGenerating"
          class="flex-1 py-3 px-4 rounded-xl bg-primary-500 text-white font-medium shadow-lg active:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <i class="ri-download-line mr-1"></i>保存图片
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import html2canvas from 'html2canvas'
import QRCode from 'qrcode'
import { timeAgo } from '@/utils/date'
import { avatarInitial } from '@/utils/avatar'

// ── Types for Tiptap JSON parsing (post mode only) ──
interface TiptapNode {
  type: string
  attrs?: Record<string, any>
  content?: TiptapNode[]
  text?: string
  marks?: { type: string }[]
}

interface ContentBlock {
  type: 'heading' | 'paragraph'
  level?: number
  text: string
  bold?: boolean
}

const props = defineProps<{
  visible: boolean
  pageTitle?: string
  pageUrl?: string
  post?: {
    id: number
    title: string
    content: string
    content_json: string | null
    created_at: string
    author?: { username: string }
    category?: { name: string; icon: string | null }
    city?: string | null
    [key: string]: unknown
  } | null
}>()

const emit = defineEmits<{ close: [] }>()

const posterImageUrl = ref('')
const isGenerating = ref(false)

const isWeChat = /MicroMessenger/i.test(navigator.userAgent)

const canShareFiles = (() => {
  if (!navigator.share) return false
  try {
    const testFile = new File([''], 'test.png', { type: 'image/png' })
    return !!navigator.canShare?.({ files: [testFile] })
  } catch { return false }
})()

const FONT = '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'

// ── Shared utilities ──

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function traceRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number | number[],
) {
  // CanvasRenderingContext2D.roundRect is unavailable in many older Android
  // WebView and iOS WeChat clients. Draw the same path with universally
  // supported arcTo operations.
  const radii = Array.isArray(radius) ? radius : [radius, radius, radius, radius]
  const [tl, tr, br, bl] = radii.map((value) => Math.min(value, width / 2, height / 2))
  ctx.beginPath()
  ctx.moveTo(x + tl, y)
  ctx.arcTo(x + width, y, x + width, y + height, tr)
  ctx.arcTo(x + width, y + height, x, y + height, br)
  ctx.arcTo(x, y + height, x, y, bl)
  ctx.arcTo(x, y, x + width, y, tl)
  ctx.closePath()
}

// ── Post-specific helpers (used only when post prop is set) ──

function extractText(node: TiptapNode): string {
  if (node.text) return node.text
  if (node.content) return node.content.map(extractText).join('')
  return ''
}

function hasBoldMark(node: TiptapNode): boolean {
  return node.marks?.some(m => m.type === 'bold') ?? false
}

function isBlockBold(node: TiptapNode): boolean {
  if (hasBoldMark(node)) return true
  if (node.content) return node.content.some(isBlockBold)
  return false
}

function parseContentJson(jsonStr: string | null): ContentBlock[] {
  if (!jsonStr) return []
  try {
    const doc = JSON.parse(jsonStr)
    if (doc.type !== 'doc' || !doc.content) return []
    const blocks: ContentBlock[] = []
    for (const node of doc.content) {
      if (node.type === 'heading' && node.content) {
        blocks.push({
          type: 'heading',
          level: node.attrs?.level ?? 2,
          text: extractText(node),
          bold: isBlockBold(node),
        })
      } else if (node.type === 'paragraph' && node.content) {
        blocks.push({
          type: 'paragraph',
          text: extractText(node),
          bold: isBlockBold(node),
        })
      } else if (node.type === 'paragraph' && !node.content) {
        blocks.push({ type: 'paragraph', text: '' })
      }
    }
    return blocks
  } catch {
    return []
  }
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>?/gm, '').trim()
}

function relativeTime(dateStr: string): string {
  return timeAgo(dateStr) || dateStr
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, lineHeight: number, maxLines: number): { height: number; truncated: boolean } {
  if (!text) return { height: 0, truncated: false }
  const lines: string[] = []
  let line = ''
  for (const ch of text) {
    const test = line + ch
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line)
      line = ch
    } else {
      line = test
    }
  }
  if (line) lines.push(line)

  const displayLines = lines.slice(0, maxLines)
  const truncated = lines.length > maxLines
  for (let i = 0; i < displayLines.length; i++) {
    let drawText = displayLines[i]
    if (i === maxLines - 1 && truncated) {
      drawText = drawText.slice(0, -1) + '...'
    }
    ctx.fillText(drawText, x, y + i * lineHeight)
  }
  return { height: displayLines.length * lineHeight, truncated }
}

// ── Dispatcher ──

async function generatePoster() {
  if (props.post) {
    await generatePostPoster()
  } else {
    await generatePagePoster()
  }
}

// ── Post poster: renders Tiptap JSON content blocks on Canvas ──

async function generatePostPoster() {
  if (!props.post) return

  isGenerating.value = true
  posterImageUrl.value = ''

  try {
    const post = props.post
    const W = 750
    const H = 1334
    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext('2d')!

    const C = {
      primary: '#26A69A',
      primaryDark: '#00897B',
      primaryLight: '#E0F2F1',
      textDark: '#1e1e2f',
      textMid: '#4a4a68',
      textLight: '#9a9ab0',
      bgWhite: '#ffffff',
      bgCard: '#fafbfc',
      divider: '#eeeef3',
    }

    ctx.fillStyle = C.bgWhite
    ctx.fillRect(0, 0, W, H)

    // ── Header ──
    const headerH = 240
    const hGrad = ctx.createLinearGradient(0, 0, W, headerH)
    hGrad.addColorStop(0, '#26A69A')
    hGrad.addColorStop(1, '#00897B')
    ctx.fillStyle = hGrad
    ctx.beginPath()
    traceRoundedRect(ctx, 0, 0, W, headerH, [0, 0, 32, 32])
    ctx.fill()

    // Decorative circles
    ctx.fillStyle = 'rgba(255,255,255,0.08)'
    ctx.beginPath()
    ctx.arc(680, 50, 110, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.arc(620, 190, 70, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = 'rgba(255,255,255,0.05)'
    ctx.beginPath()
    ctx.arc(80, 200, 60, 0, Math.PI * 2)
    ctx.fill()

    // Logo
    const logoImg = await loadImage('/subskin_logo.png')
    const logoSize = 80
    const logoX = 56
    const brandTextH = 74
    const groupH = logoSize + 8 + 28
    const groupY = (headerH - groupH) / 2
    const logoY = groupY
    if (logoImg) {
      ctx.drawImage(logoImg, logoX, logoY, logoSize, logoSize)
    }

    const brandX = logoX + logoSize + 20
    const brandY = logoY + (logoSize - brandTextH) / 2
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold 48px ${FONT}`
    ctx.fillText('SubSkin', brandX, brandY)

    ctx.fillStyle = 'rgba(255,255,255,0.8)'
    ctx.font = `24px ${FONT}`
    ctx.fillText('白癜风病友的AI记录和分享社区', brandX, brandY + 52)

    ctx.fillStyle = 'rgba(255,255,255,0.9)'
    ctx.font = `28px ${FONT}`
    ctx.fillText('www.subskin.cn', brandX, logoY + logoSize + 10)

    // ── Content ──
    ctx.textBaseline = 'top'
    const padX = 56
    const contentW = W - padX * 2
    const footerH = 220
    const disclaimerH = 40
    const maxContentY = H - footerH - disclaimerH - 20
    let curY = headerH + 40
    let contentTruncated = false

    // Category pill
    if (post.category) {
      const catText = post.category.name
      ctx.font = `22px ${FONT}`
      const catW = ctx.measureText(catText).width + 36
      const catH = 42
      ctx.fillStyle = C.primaryLight
      ctx.beginPath()
      traceRoundedRect(ctx, padX, curY, catW, catH, 21)
      ctx.fill()
      ctx.fillStyle = C.primary
      ctx.fillText(catText, padX + 18, curY + 10)
      curY += catH + 28
    }

    // Title
    ctx.fillStyle = C.textDark
    ctx.font = `bold 38px ${FONT}`
    const titleResult = wrapText(ctx, post.title || '无标题', padX, curY, contentW, 54, 3)
    curY += titleResult.height + 28

    // Author row
    const authorName = post.author?.username || '匿名用户'
    const avatarR = 20
    const avatarX = padX + avatarR
    const avatarY = curY + avatarR

    ctx.fillStyle = C.primaryLight
    ctx.beginPath()
    ctx.arc(avatarX, avatarY, avatarR, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = C.primary
    ctx.font = `bold 20px ${FONT}`
    ctx.textAlign = 'center'
    ctx.fillText(avatarInitial(authorName), avatarX, avatarY - 10)
    ctx.textAlign = 'left'

    const nameX = padX + avatarR * 2 + 16
    ctx.fillStyle = C.textMid
    ctx.font = `26px ${FONT}`
    const cityStr = post.city ? ` · ${post.city}` : ''
    ctx.fillText(`${authorName}${cityStr}`, nameX, curY + 2)

    const timeStr = post.created_at ? relativeTime(post.created_at) : ''
    ctx.fillStyle = C.textLight
    ctx.font = `20px ${FONT}`
    ctx.fillText(timeStr, nameX, curY + 32)

    curY += 68

    // Divider
    ctx.strokeStyle = C.divider
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(padX, curY)
    ctx.lineTo(W - padX, curY)
    ctx.stroke()
    curY += 24

    // Content blocks — parse Tiptap JSON for formatting
    const blocks = parseContentJson(post.content_json)
    if (blocks.length === 0) {
      const plainText = stripHtml(post.content || '')
      ctx.fillStyle = C.textMid
      ctx.font = `28px ${FONT}`
      const result = wrapText(ctx, plainText, padX, curY, contentW, 46, 20)
      curY += result.height + 20
      contentTruncated = result.truncated
    } else {
      for (const block of blocks) {
        if (!block.text) {
          curY += 16
          continue
        }

        if (curY >= maxContentY - 60) {
          contentTruncated = true
          break
        }

        if (block.type === 'heading') {
          const fontSize = block.level === 2 ? 34 : 30
          const lineH = block.level === 2 ? 48 : 44
          const maxLines = Math.floor((maxContentY - curY - 16) / lineH)
          if (maxLines < 1) { contentTruncated = true; break }

          ctx.fillStyle = C.textDark
          ctx.font = `bold ${fontSize}px ${FONT}`
          const result = wrapText(ctx, block.text, padX, curY, contentW, lineH, Math.min(maxLines, 3))
          curY += result.height + 20
          if (result.truncated) { contentTruncated = true; break }
        } else {
          const lineH = 44
          const maxLines = Math.floor((maxContentY - curY - 16) / lineH)
          if (maxLines < 1) { contentTruncated = true; break }

          ctx.fillStyle = C.textMid
          ctx.font = block.bold ? `bold 28px ${FONT}` : `28px ${FONT}`
          const result = wrapText(ctx, block.text, padX, curY, contentW, lineH, Math.min(maxLines, 5))
          curY += result.height + 12
          if (result.truncated) { contentTruncated = true; break }
        }
      }
    }

    // Truncation hint
    if (contentTruncated) {
      curY += 4
      ctx.fillStyle = C.primary
      ctx.font = `24px ${FONT}`
      ctx.fillText('··· 登录后查看详情', padX, curY)
      curY += 32
    }

    // ── Footer ──
    const footerY = H - footerH - disclaimerH

    ctx.fillStyle = C.bgCard
    ctx.fillRect(0, footerY, W, footerH + disclaimerH)

    ctx.strokeStyle = C.divider
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(0, footerY)
    ctx.lineTo(W, footerY)
    ctx.stroke()

    // QR Code (right)
    const postUrl = `${window.location.origin}/community/${post.id}`
    const qrSize = 140
    const qrPad = 14
    const qrX = W - padX - qrSize - qrPad * 2
    const qrY = footerY + (footerH - qrSize - qrPad * 2) / 2

    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
      traceRoundedRect(ctx, qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 14)
    ctx.fill()
    ctx.strokeStyle = '#f0f0f5'
    ctx.lineWidth = 1
    ctx.beginPath()
      traceRoundedRect(ctx, qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 14)
    ctx.stroke()

    try {
      const qrDataUrl = await QRCode.toDataURL(postUrl, {
        width: qrSize * 2,
        margin: 1,
        color: { dark: C.textDark, light: '#ffffff' },
        errorCorrectionLevel: 'M',
      })
      const qrImg = await loadImage(qrDataUrl)
      if (qrImg) {
        ctx.drawImage(qrImg, qrX, qrY, qrSize, qrSize)
      }
    } catch {
      ctx.fillStyle = '#e8e8f0'
      ctx.fillRect(qrX, qrY, qrSize, qrSize)
    }

    // Footer text (left)
    const footerMidY = footerY + footerH / 2
    ctx.fillStyle = C.textDark
    ctx.font = `bold 32px ${FONT}`
    ctx.fillText('扫码查看详情', padX, footerMidY - 16)

    ctx.fillStyle = C.textLight
    ctx.font = `24px ${FONT}`
    ctx.fillText('长按识别二维码', padX, footerMidY + 24)

    // ── Disclaimer ──
    ctx.fillStyle = C.textLight
    ctx.font = `16px ${FONT}`
    ctx.textAlign = 'center'
    ctx.fillText('分享内容仅供参考，不构成医疗建议', W / 2, H - disclaimerH + 14)
    ctx.textAlign = 'left'

    posterImageUrl.value = canvas.toDataURL('image/png')
  } catch (error) {
    console.error('Failed to generate poster:', error)
  } finally {
    isGenerating.value = false
  }
}

// ── Page poster: renders page title + DOM screenshot on Canvas ──

async function generatePagePoster() {
  isGenerating.value = true
  posterImageUrl.value = ''

  try {
    const W = 750
    const headerH = 160
    const footerH = 200
    const disclaimerH = 36

    // Capture page screenshot
    const mainEl = document.querySelector('main') || document.querySelector('#app')
    let screenshotImg: HTMLImageElement | null = null
    if (mainEl) {
      try {
        const canvas = await html2canvas(mainEl as HTMLElement, {
          scale: 2,
          useCORS: true,
          allowTaint: true,
          backgroundColor: '#ffffff',
          logging: false,
          width: mainEl.scrollWidth,
          height: Math.min(mainEl.scrollHeight, 2000),
        })
        screenshotImg = await loadImage(canvas.toDataURL('image/png'))
      } catch (e) {
        console.warn('Screenshot failed:', e)
      }
    }

    // Calculate content height (aspect-ratio-aware)
    const contentMaxH = 1334 - headerH - footerH - disclaimerH
    let contentH: number
    if (screenshotImg) {
      const displayW = W - 48 * 2
      const displayH = contentMaxH - 48 - 16
      const srcRatio = screenshotImg.naturalWidth / screenshotImg.naturalHeight
      const displayRatio = displayW / displayH
      let clipH: number
      if (srcRatio > displayRatio) {
        clipH = displayH
      } else {
        clipH = Math.min(displayW / srcRatio, displayH)
      }
      contentH = 48 + clipH + 16
    } else {
      contentH = 300
    }

    const H = headerH + Math.round(contentH) + footerH + disclaimerH

    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext('2d')!

    const C = {
      primary: '#26A69A',
      textDark: '#1e1e2f',
      textMid: '#4a4a68',
      textLight: '#9a9ab0',
      bgWhite: '#ffffff',
      bgCard: '#fafbfc',
      divider: '#eeeef3',
    }

    // Background
    ctx.fillStyle = C.bgWhite
    ctx.fillRect(0, 0, W, H)

    // ── Header ──
    const hGrad = ctx.createLinearGradient(0, 0, W, headerH)
    hGrad.addColorStop(0, '#26A69A')
    hGrad.addColorStop(1, '#00897B')
    ctx.fillStyle = hGrad
    ctx.beginPath()
    traceRoundedRect(ctx, 0, 0, W, headerH, [0, 0, 24, 24])
    ctx.fill()

    // Decorative circles
    ctx.fillStyle = 'rgba(255,255,255,0.08)'
    ctx.beginPath()
    ctx.arc(680, 30, 80, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.arc(620, 130, 50, 0, Math.PI * 2)
    ctx.fill()

    // Logo
    const logoImg = await loadImage('/subskin_logo.png')
    const logoSize = 64
    const logoX = 48
    const brandTextH = 62
    const brandH = Math.max(logoSize, brandTextH)
    const groupY = (headerH - brandH) / 2
    const logoY = groupY + (brandH - logoSize) / 2
    if (logoImg) {
      ctx.drawImage(logoImg, logoX, logoY, logoSize, logoSize)
    }

    // Brand + slogan beside logo, vertically centered
    const brandX = logoX + logoSize + 16
    const brandY = groupY + (brandH - brandTextH) / 2
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold 40px ${FONT}`
    ctx.fillText('SubSkin', brandX, brandY)

    ctx.fillStyle = 'rgba(255,255,255,0.8)'
    ctx.font = `20px ${FONT}`
    ctx.fillText('白癜风病友的AI记录和分享社区', brandX, brandY + 44)

    // URL — aligned with brand name
    ctx.fillStyle = 'rgba(255,255,255,0.9)'
    ctx.font = `22px ${FONT}`
    ctx.fillText('www.subskin.cn', brandX, headerH - 30)

    // ── Content: page title + screenshot ──
    ctx.textBaseline = 'top'
    const padX = 48
    let curY = headerH + 24

    // Page title
    ctx.fillStyle = C.textDark
    ctx.font = `bold 32px ${FONT}`
    ctx.fillText(props.pageTitle || 'SubSkin', padX, curY)
    curY += 48

    // Screenshot — maintain aspect ratio, fit within display area
    if (screenshotImg) {
      const displayW = W - padX * 2
      const displayH = contentMaxH - 48 - 16
      const srcRatio = screenshotImg.naturalWidth / screenshotImg.naturalHeight
      const displayRatio = displayW / displayH

      let imgW: number, imgH: number
      if (srcRatio > displayRatio) {
        imgH = displayH
        imgW = imgH * srcRatio
      } else {
        imgW = displayW
        imgH = imgW / srcRatio
      }

      const clipW = Math.min(imgW, displayW)
      const clipH = Math.min(imgH, displayH)

      ctx.save()
      ctx.beginPath()
      traceRoundedRect(ctx, padX, curY, displayW, clipH, 12)
      ctx.clip()

      const sx = (screenshotImg.naturalWidth - (clipW / imgW) * screenshotImg.naturalWidth) / 2
      const sy = 0
      const sw = (clipW / imgW) * screenshotImg.naturalWidth
      const sh = (clipH / imgH) * screenshotImg.naturalHeight

      ctx.drawImage(screenshotImg, sx, sy, sw, sh, padX, curY, clipW, clipH)
      ctx.restore()
      curY += clipH + 16
    } else {
      ctx.fillStyle = C.textMid
      ctx.font = `24px ${FONT}`
      ctx.fillText('SubSkin · AI记录与分享社区', padX, curY)
      ctx.fillStyle = C.textLight
      ctx.font = `20px ${FONT}`
      ctx.fillText('白癜风病友的AI记录和分享社区', padX, curY + 32)
      curY += 80
    }

    // ── Footer ──
    const footerY = H - footerH - disclaimerH
    ctx.fillStyle = C.bgCard
    ctx.fillRect(0, footerY, W, footerH + disclaimerH)

    ctx.strokeStyle = C.divider
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(0, footerY)
    ctx.lineTo(W, footerY)
    ctx.stroke()

    // QR Code (right)
    const pageUrl = props.pageUrl || window.location.href
    const qrSize = 120
    const qrPad = 12
    const qrX = W - padX - qrSize - qrPad * 2
    const qrY = footerY + (footerH - qrSize - qrPad * 2) / 2

    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    traceRoundedRect(ctx, qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 12)
    ctx.fill()
    ctx.strokeStyle = '#f0f0f5'
    ctx.lineWidth = 1
    ctx.beginPath()
    traceRoundedRect(ctx, qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 12)
    ctx.stroke()

    try {
      const qrDataUrl = await QRCode.toDataURL(pageUrl, {
        width: qrSize * 2,
        margin: 1,
        color: { dark: C.textDark, light: '#ffffff' },
        errorCorrectionLevel: 'M',
      })
      const qrImg = await loadImage(qrDataUrl)
      if (qrImg) ctx.drawImage(qrImg, qrX, qrY, qrSize, qrSize)
    } catch {
      ctx.fillStyle = '#e8e8f0'
      ctx.fillRect(qrX, qrY, qrSize, qrSize)
    }

    // Footer text (left)
    const footerMidY = footerY + footerH / 2
    ctx.fillStyle = C.textDark
    ctx.font = `bold 28px ${FONT}`
    ctx.fillText('扫码查看详情', padX, footerMidY - 12)

    ctx.fillStyle = C.textLight
    ctx.font = `20px ${FONT}`
    ctx.fillText('长按识别二维码', padX, footerMidY + 22)

    // ── Disclaimer ──
    ctx.fillStyle = C.textLight
    ctx.font = `14px ${FONT}`
    ctx.textAlign = 'center'
    ctx.fillText('分享内容仅供参考，不构成医疗建议', W / 2, H - disclaimerH + 12)
    ctx.textAlign = 'left'

    posterImageUrl.value = canvas.toDataURL('image/png')
  } catch (error) {
    console.error('Failed to generate page poster:', error)
  } finally {
    isGenerating.value = false
  }
}

async function downloadPoster() {
  if (!posterImageUrl.value) return
  try {
    const link = document.createElement('a')
    link.download = `subskin-${props.post ? `post-${props.post.id}` : 'share'}.png`
    link.href = posterImageUrl.value
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch {
    window.open(posterImageUrl.value, '_blank')
  }
}

async function sharePoster() {
  if (!posterImageUrl.value) return

  if (isWeChat || !navigator.share) return

  try {
    const response = await fetch(posterImageUrl.value)
    const blob = await response.blob()
    const filename = `subskin-${props.post ? `post-${props.post.id}` : 'share'}.png`
    const file = new File([blob], filename, { type: 'image/png' })

    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({
        files: [file],
        title: props.post
          ? `${props.post.title || 'SubSkin帖子'} - SubSkin`
          : (props.pageTitle || 'SubSkin'),
      })
    } else if (props.post) {
      // Fallback: share URL
      const postUrl = `${window.location.origin}/community/${props.post.id}`
      await navigator.share({
        title: `${props.post.title || 'SubSkin帖子'} - SubSkin`,
        text: stripHtml(props.post.content || '').slice(0, 100),
        url: postUrl,
      })
    }
  } catch {
    // User cancelled or share failed — silent
  }
}

function close() {
  emit('close')
}

watch(() => props.visible, async (newVal) => {
  if (newVal) {
    document.body.style.overflow = 'hidden'
    await generatePoster()
  } else {
    document.body.style.overflow = ''
    setTimeout(() => { posterImageUrl.value = '' }, 300)
  }
})

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>
