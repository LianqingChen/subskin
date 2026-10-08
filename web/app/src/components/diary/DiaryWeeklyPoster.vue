<script setup lang="ts">
/**
 * DiaryWeeklyPoster — 周报分享海报（Canvas生成PNG）
 * 复用 PageSharePoster 的模态/下载/分享模式，内容换为周报数据
 */
import { ref, watch } from 'vue'
import QRCode from 'qrcode'
import type { WeeklyReport } from '@/api/diary'
import { parseDate } from '@/utils/date'

const props = defineProps<{
  visible: boolean
  report: WeeklyReport | null
  moodConfig: Record<string, { emoji: string; label: string; color: string }>
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
  } catch {
    return false
  }
})()

const FONT =
  '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
const WEEK_LABELS = ['一', '二', '三', '四', '五', '六', '日']

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function fmtDay(dateStr: string): string {
  const d = parseDate(dateStr)
  if (!d) return dateStr
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

/** 文本换行（按canvas测量宽度切分） */
function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = []
  let line = ''
  for (const ch of text) {
    if (ch === '\n') {
      lines.push(line)
      line = ''
      continue
    }
    const test = line + ch
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line)
      line = ch
    } else {
      line = test
    }
  }
  if (line) lines.push(line)
  return lines
}

async function generatePoster() {
  if (!props.report) return
  isGenerating.value = true
  posterImageUrl.value = ''

  try {
    const report = props.report
    const W = 750
    const padX = 48
    const headerH = 220
    const footerH = 200
    const disclaimerH = 40

    // ── Measure middle content heights ──
    const measureCanvas = document.createElement('canvas')
    const mctx = measureCanvas.getContext('2d')!

    // Stats row
    const statsH = 140
    // Mood trend row
    const moodH = report.daily_moods.length ? 150 : 0
    // AI summary block
    let summaryLines: string[] = []
    let summaryH = 0
    if (report.ai_summary) {
      mctx.font = `24px ${FONT}`
      summaryLines = wrapText(mctx, report.ai_summary, W - padX * 2 - 64).slice(0, 6)
      summaryH = 70 + summaryLines.length * 38 + 32
    }
    // Insights (max 3)
    const insightItems = report.insights.slice(0, 3)
    mctx.font = `22px ${FONT}`
    const insightWrapped: string[][] = insightItems.map((t) =>
      wrapText(mctx, t, W - padX * 2 - 70).slice(0, 2),
    )
    const insightsH = insightItems.length
      ? 60 + insightWrapped.reduce((acc, lines) => acc + lines.length * 34 + 20, 0) + 8
      : 0

    const middleH = 24 + statsH + 16 + moodH + (summaryH ? summaryH + 16 : 0) + insightsH + 24
    const H = headerH + middleH + footerH + disclaimerH

    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext('2d')!

    const C = {
      textDark: '#1e293b',
      textMid: '#475569',
      textLight: '#94a3b8',
      bgWhite: '#ffffff',
      bgCard: '#f8fafc',
      divider: '#eef2f6',
    }

    // Background
    ctx.fillStyle = C.bgWhite
    ctx.fillRect(0, 0, W, H)

    // ── Header ──
    const hGrad = ctx.createLinearGradient(0, 0, W, headerH)
    hGrad.addColorStop(0, '#26A69A')
    hGrad.addColorStop(1, '#00897B')
    ctx.fillStyle = hGrad
    ctx.fillRect(0, 0, W, headerH)

    // Decorative circles
    ctx.fillStyle = 'rgba(255,255,255,0.08)'
    ctx.beginPath()
    ctx.arc(690, 20, 90, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.arc(600, 190, 55, 0, Math.PI * 2)
    ctx.fill()

    // Logo + brand
    const logoImg = await loadImage('/subskin_logo.png')
    const logoSize = 56
    if (logoImg) ctx.drawImage(logoImg, padX, 36, logoSize, logoSize)
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold 34px ${FONT}`
    ctx.fillText('SubSkin · AI病情日记', padX + logoSize + 16, 42)
    ctx.fillStyle = 'rgba(255,255,255,0.85)'
    ctx.font = `20px ${FONT}`
    ctx.fillText("What's beneath? SubSkin更懂你", padX + logoSize + 16, 82)

    // Week title
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold 40px ${FONT}`
    ctx.fillText('我的本周报告 ✨', padX, 130)
    ctx.fillStyle = 'rgba(255,255,255,0.85)'
    ctx.font = `22px ${FONT}`
    ctx.fillText(`${fmtDay(report.week_start)} - ${fmtDay(report.week_end)}`, padX, 178)

    // ── Middle content ──
    let curY = headerH + 24

    // Stats row card
    const statItems = [
      { value: String(report.recorded_days), label: '记录天数' },
      { value: String(report.entry_count), label: '日记条数' },
      { value: String(report.current_streak), label: '连续天数 🔥' },
    ]
    ctx.fillStyle = C.bgCard
    ctx.beginPath()
    ctx.roundRect(padX, curY, W - padX * 2, statsH - 20, 20)
    ctx.fill()
    statItems.forEach((item, i) => {
      const cellW = (W - padX * 2) / 3
      const cx = padX + cellW * i + cellW / 2
      ctx.textAlign = 'center'
      ctx.fillStyle = '#26A69A'
      ctx.font = `bold 46px ${FONT}`
      ctx.fillText(item.value, cx, curY + 26)
      ctx.fillStyle = C.textLight
      ctx.font = `20px ${FONT}`
      ctx.fillText(item.label, cx, curY + 86)
      ctx.textAlign = 'left'
    })
    curY += statsH

    // Mood trend row
    if (moodH) {
      ctx.fillStyle = C.textDark
      ctx.font = `bold 26px ${FONT}`
      ctx.fillText('心情轨迹', padX, curY)
      curY += 50

      const rowW = W - padX * 2
      const cellW = rowW / 7
      report.daily_moods.forEach((day, i) => {
        const cx = padX + cellW * i + cellW / 2
        const mood = day.moods[0]
        const emoji = mood ? props.moodConfig[mood]?.emoji || '🙂' : ''
        // circle
        ctx.fillStyle = emoji ? 'rgba(38,166,154,0.08)' : '#f1f5f9'
        ctx.beginPath()
        ctx.arc(cx, curY + 30, 34, 0, Math.PI * 2)
        ctx.fill()
        ctx.textAlign = 'center'
        if (emoji) {
          ctx.font = `34px ${FONT}`
          ctx.textBaseline = 'middle'
          ctx.fillText(emoji, cx, curY + 32)
          ctx.textBaseline = 'top'
        }
        ctx.fillStyle = C.textLight
        ctx.font = `18px ${FONT}`
        ctx.fillText(WEEK_LABELS[i], cx, curY + 76)
        ctx.textAlign = 'left'
      })
      curY += moodH - 50
    }

    // AI summary block
    if (summaryH) {
      ctx.fillStyle = 'rgba(38,166,154,0.06)'
      ctx.beginPath()
      ctx.roundRect(padX, curY, W - padX * 2, summaryH - 16, 16)
      ctx.fill()
      ctx.strokeStyle = 'rgba(38,166,154,0.2)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.roundRect(padX, curY, W - padX * 2, summaryH - 16, 16)
      ctx.stroke()

      ctx.fillStyle = '#26A69A'
      ctx.font = `bold 24px ${FONT}`
      ctx.fillText('✨ AI本周总结', padX + 28, curY + 24)
      ctx.fillStyle = C.textMid
      ctx.font = `24px ${FONT}`
      summaryLines.forEach((line, i) => {
        ctx.fillText(line, padX + 28, curY + 66 + i * 38)
      })
      curY += summaryH
    }

    // Insights
    if (insightItems.length) {
      ctx.fillStyle = C.textDark
      ctx.font = `bold 26px ${FONT}`
      ctx.fillText('AI洞察', padX, curY)
      curY += 48
      insightWrapped.forEach((lines) => {
        ctx.fillStyle = '#26A69A'
        ctx.beginPath()
        ctx.arc(padX + 10, curY + 12, 6, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = C.textMid
        ctx.font = `22px ${FONT}`
        lines.forEach((line, i) => {
          ctx.fillText(line, padX + 32, curY + i * 34)
        })
        curY += lines.length * 34 + 20
      })
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

    // QR code (right)
    const qrSize = 120
    const qrPad = 12
    const qrX = W - padX - qrSize - qrPad * 2
    const qrY = footerY + (footerH - qrSize - qrPad * 2) / 2
    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    ctx.roundRect(qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 12)
    ctx.fill()
    ctx.strokeStyle = '#f0f0f5'
    ctx.beginPath()
    ctx.roundRect(qrX - qrPad, qrY - qrPad, qrSize + qrPad * 2, qrSize + qrPad * 2, 12)
    ctx.stroke()

    const pageUrl = `${window.location.origin}/diary`
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
    ctx.fillText('扫码记录你的每一天', padX, footerMidY - 24)
    ctx.fillStyle = C.textLight
    ctx.font = `20px ${FONT}`
    ctx.fillText('SubSkin · 白癜风患者AI社区', padX, footerMidY + 14)
    ctx.fillText('长按识别二维码', padX, footerMidY + 44)

    // Disclaimer
    ctx.fillStyle = C.textLight
    ctx.font = `14px ${FONT}`
    ctx.textAlign = 'center'
    ctx.fillText('分享内容仅供参考，不构成医疗建议，治疗请遵医嘱', W / 2, H - disclaimerH + 14)
    ctx.textAlign = 'left'

    posterImageUrl.value = canvas.toDataURL('image/png')
  } catch (error) {
    console.error('Failed to generate weekly poster:', error)
  } finally {
    isGenerating.value = false
  }
}

async function downloadPoster() {
  if (!posterImageUrl.value) return
  const link = document.createElement('a')
  link.download = 'subskin-weekly-report.png'
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
    const file = new File([blob], 'subskin-weekly-report.png', { type: 'image/png' })
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: '我的SubSkin本周报告' })
    }
  } catch {
    /* cancelled */
  }
}

function close() {
  emit('close')
}

watch(
  () => props.visible,
  async (newVal) => {
    if (newVal) {
      document.body.style.overflow = 'hidden'
      await generatePoster()
    } else {
      document.body.style.overflow = ''
      setTimeout(() => {
        posterImageUrl.value = ''
      }, 300)
    }
  },
)
</script>

<template>
  <div
    v-if="visible"
    class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4 overflow-y-auto"
    @click.self="close"
  >
    <div class="relative w-full max-w-[375px] flex flex-col gap-3">
      <!-- Close button -->
      <button
        class="absolute -top-1 -right-1 z-10 w-8 h-8 rounded-full bg-black/50 text-white flex items-center justify-center"
        @click="close"
      >
        <i class="ri-close-line text-lg"></i>
      </button>

      <!-- Poster image -->
      <div
        class="w-full rounded-xl overflow-hidden shadow-2xl bg-white min-h-[400px] flex items-center justify-center"
      >
        <div v-if="isGenerating" class="flex flex-col items-center gap-3 text-gray-400 py-20">
          <i class="ri-loader-4-line animate-spin text-3xl text-primary-500"></i>
          <span class="text-sm font-medium">正在生成海报...</span>
        </div>
        <img
          v-else-if="posterImageUrl"
          :src="posterImageUrl"
          alt="周报分享海报"
          class="w-full h-auto block"
          style="-webkit-touch-callout: default; user-select: auto"
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
          :disabled="!posterImageUrl || isGenerating"
          class="flex-1 py-3 px-4 rounded-xl bg-primary-500 text-white font-medium shadow-lg active:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          @click="sharePoster"
        >
          <i class="ri-share-line mr-1"></i>分享
        </button>
        <button
          :disabled="!posterImageUrl || isGenerating"
          class="flex-1 py-3 px-4 rounded-xl bg-primary-500 text-white font-medium shadow-lg active:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          @click="downloadPoster"
        >
          <i class="ri-download-line mr-1"></i>保存图片
        </button>
      </div>
    </div>
  </div>
</template>
