<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4 overflow-y-auto" @click.self="close">
    <div class="relative w-full max-w-[375px] flex flex-col gap-3">
      <!-- Close button -->
      <button @click="close" class="absolute -top-1 -right-1 z-10 w-8 h-8 rounded-full bg-black/50 text-white flex items-center justify-center">
        <i class="ri-close-line text-lg"></i>
      </button>

      <!-- Poster image — long-press to save on mobile -->
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
          @click="downloadPoster"
          :disabled="!posterImageUrl || isGenerating"
          class="flex-1 py-3 px-4 rounded-xl text-white font-medium shadow-lg active:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          :class="canShareFiles && !isWeChat ? 'bg-primary-500' : 'bg-primary-500'"
        >
          <i class="ri-download-line mr-1"></i>保存图片
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import QRCode from 'qrcode'

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
  post: {
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

// Detect WeChat in-app browser
const isWeChat = /MicroMessenger/i.test(navigator.userAgent)

// Check if Web Share API with files is available
const canShareFiles = (() => {
  if (!navigator.share) return false
  try {
    const testFile = new File([''], 'test.png', { type: 'image/png' })
    return !!navigator.canShare?.({ files: [testFile] })
  } catch {
    return false
  }
})()

const FONT = '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'

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
        // Empty paragraph = blank line
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
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diff < 60) return '刚刚'
  const min = Math.floor(diff / 60)
  if (min < 60) return `${min}分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day}天前`
  const mo = Math.floor(day / 30)
  if (mo < 12) return `${mo}个月前`
  return `${Math.floor(mo / 12)}年前`
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

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

async function generatePoster() {
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
    ctx.roundRect(0, 0, W, headerH, [0, 0, 32, 32])
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

    // Logo (no circular clip — draw as-is)
    const logoImg = await loadImage('/subskin_logo.png')
    const logoSize = 80
    const logoX = 56
    // Brand + Slogan are beside logo, vertically centered with it
    // URL is below logo, left-aligned with logo
    const brandTextH = 74 // brand(48px) + gap(6) + slogan(24px) ≈ 74
    const groupH = logoSize + 8 + 28 // logo + gap + url line
    const groupY = (headerH - groupH) / 2
    const logoY = groupY
    if (logoImg) {
      ctx.drawImage(logoImg, logoX, logoY, logoSize, logoSize)
    }

    // Brand name — vertically centered with logo
    const brandX = logoX + logoSize + 20
    const brandY = logoY + (logoSize - brandTextH) / 2
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold 48px ${FONT}`
    ctx.fillText('SubSkin', brandX, brandY)

    // Slogan — below brand name
    ctx.fillStyle = 'rgba(255,255,255,0.8)'
    ctx.font = `24px ${FONT}`
    ctx.fillText("What's beneath? SubSkin更懂你", brandX, brandY + 52)

    // URL — left-aligned with brand name
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
      const catText = `${post.category.icon || ''} ${post.category.name}`
      ctx.font = `22px ${FONT}`
      const catW = ctx.measureText(catText).width + 36
      const catH = 42
      ctx.fillStyle = C.primaryLight
      ctx.beginPath()
      ctx.roundRect(padX, curY, catW, catH, 21)
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
    ctx.fillText(authorName.charAt(0).toUpperCase(), avatarX, avatarY - 10)
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
      // Fallback: plain text from content
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
    ctx.roundRect(qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 14)
    ctx.fill()
    ctx.strokeStyle = '#f0f0f5'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.roundRect(qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 14)
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

    // Footer text (left) — aligned with content left edge
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

async function downloadPoster() {
  if (!posterImageUrl.value) return
  try {
    const link = document.createElement('a')
    link.download = `subskin-post-${props.post?.id || 'share'}.png`
    link.href = posterImageUrl.value
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch {
    // Fallback: open in new tab
    window.open(posterImageUrl.value, '_blank')
  }
}

async function sharePoster() {
  if (!posterImageUrl.value) return

  // WeChat browser doesn't support Web Share API — user must long-press save
  if (isWeChat || !navigator.share) return

  try {
    const response = await fetch(posterImageUrl.value)
    const blob = await response.blob()
    const file = new File([blob], `subskin-post-${props.post?.id || 'share'}.png`, { type: 'image/png' })

    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({
        files: [file],
        title: `${props.post?.title || 'SubSkin帖子'} - SubSkin`,
      })
    } else {
      // Fallback: share URL
      const postUrl = `${window.location.origin}/community/${props.post?.id}`
      await navigator.share({
        title: `${props.post?.title || 'SubSkin帖子'} - SubSkin`,
        text: stripHtml(props.post?.content || '').slice(0, 100),
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
    setTimeout(() => {
      posterImageUrl.value = ''
    }, 300)
  }
})
</script>
