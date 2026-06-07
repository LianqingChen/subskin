<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4 overflow-y-auto" @click.self="close">
    <div class="relative w-full max-w-[375px] flex flex-col gap-3">
      <!-- Close button -->
      <button @click="close" class="absolute -top-1 -right-1 z-10 w-8 h-8 rounded-full bg-black/50 text-white flex items-center justify-center">
        <i class="ri-close-line text-lg"></i>
      </button>

      <!-- Poster image -->
      <div class="w-full rounded-xl overflow-hidden shadow-2xl bg-white min-h-[400px] flex items-center justify-center">
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
          class="flex-1 py-3 px-4 rounded-xl bg-primary-500 text-white font-medium shadow-lg active:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <i class="ri-download-line mr-1"></i>保存图片
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import html2canvas from 'html2canvas'
import QRCode from 'qrcode'

const props = defineProps<{
  visible: boolean
  pageTitle: string
  pageUrl?: string
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
      contentH = 48 + clipH + 16 // title + screenshot + gap
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
    ctx.roundRect(0, 0, W, headerH, [0, 0, 24, 24])
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
    ctx.fillText("What's beneath? SubSkin更懂你", brandX, brandY + 44)

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
    ctx.fillText(props.pageTitle, padX, curY)
    curY += 48

    // Screenshot — maintain aspect ratio, fit within display area
    if (screenshotImg) {
      const displayW = W - padX * 2  // available width in poster
      const displayH = contentMaxH - 48 - 16  // available height (after title + gap)
      const srcRatio = screenshotImg.naturalWidth / screenshotImg.naturalHeight
      const displayRatio = displayW / displayH

      let imgW: number, imgH: number
      if (srcRatio > displayRatio) {
        // Source is wider than display area → fit by height, crop sides
        imgH = displayH
        imgW = imgH * srcRatio
      } else {
        // Source is taller than display area → fit by width, crop top/bottom
        imgW = displayW
        imgH = imgW / srcRatio
      }

      // Draw centered within the display area (source-centered crop)
      const clipW = Math.min(imgW, displayW)
      const clipH = Math.min(imgH, displayH)

      ctx.save()
      ctx.beginPath()
      ctx.roundRect(padX, curY, displayW, clipH, 12)
      ctx.clip()

      // Source rectangle: center-crop from the screenshot
      const sx = (screenshotImg.naturalWidth - (clipW / imgW) * screenshotImg.naturalWidth) / 2
      const sy = 0
      const sw = (clipW / imgW) * screenshotImg.naturalWidth
      const sh = (clipH / imgH) * screenshotImg.naturalHeight

      ctx.drawImage(screenshotImg, sx, sy, sw, sh, padX, curY, clipW, clipH)
      ctx.restore()
      curY += clipH + 16
    } else {
      // Fallback text
      ctx.fillStyle = C.textMid
      ctx.font = `24px ${FONT}`
      ctx.fillText('SubSkin · 白癜风智能助手', padX, curY)
      ctx.fillStyle = C.textLight
      ctx.font = `20px ${FONT}`
      ctx.fillText('AI赋能的白癜风知识库与社区平台', padX, curY + 32)
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
    ctx.roundRect(qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 12)
    ctx.fill()
    ctx.strokeStyle = '#f0f0f5'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.roundRect(qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 12)
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
  const link = document.createElement('a')
  link.download = `subskin-share.png`
  link.href = posterImageUrl.value
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

async function sharePoster() {
  if (!posterImageUrl.value || isWeChat || !navigator.share) return
  try {
    const response = await fetch(posterImageUrl.value)
    const blob = await response.blob()
    const file = new File([blob], 'subskin-share.png', { type: 'image/png' })
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: props.pageTitle })
    }
  } catch { /* cancelled */ }
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
</script>
