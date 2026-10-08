<script setup lang="ts">
/**
 * SkinReportPoster — 白斑变化报告分享海报
 *
 * 竖版 1080×1920 Canvas 绘制，适合微信/抖音/小红书等社交媒体。
 * 内容：SubSkin 品牌 + 短标题 + 趋势 + 前后对比照片（核心）+ 客观指标与变化摘要 + 二维码 + 免责声明。
 * 周报/月报绘制各部位前后对比照片对；对比报告绘制首末照片对。
 */
import { ref, computed, watch } from 'vue'
import QRCode from 'qrcode'
import type { SkinReport } from '@/api/skin_report'
import { toProtectedFileUrl } from '@/utils/file-url'

const props = defineProps<{ visible: boolean; report: SkinReport | null }>()
const emit = defineEmits<{ close: [] }>()

const posterUrl = ref('')
const generating = ref(false)

const isPeriodic = computed(
  () => props.report?.report_type === 'weekly' || props.report?.report_type === 'monthly',
)

watch(
  () => props.visible,
  async (v) => {
    if (v && props.report) await generate()
  },
  { immediate: true },
)

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

async function tryLoadPhoto(url?: string): Promise<HTMLImageElement | null> {
  if (!url) return null
  const protectedUrl = toProtectedFileUrl(url) || url
  try {
    return await loadImage(protectedUrl)
  } catch {
    return null
  }
}

/** 裁剪为正方形后绘制并圆角化 */
function drawRoundedSquarePhoto(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  x: number,
  y: number,
  size: number,
) {
  const side = Math.min(img.width, img.height)
  const sx = (img.width - side) / 2
  const sy = (img.height - side) / 2
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(x + 20, y)
  ctx.arcTo(x + size, y, x + size, y + size, 20)
  ctx.arcTo(x + size, y + size, x, y + size, 20)
  ctx.arcTo(x, y + size, x, y, 20)
  ctx.arcTo(x, y, x + size, y, 20)
  ctx.closePath()
  ctx.clip()
  ctx.drawImage(img, sx, sy, side, side, x, y, size, size)
  ctx.restore()
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines = 99,
): number {
  const chars = (text || '').split('')
  let line = ''
  let yy = y
  let lineCount = 0
  for (const ch of chars) {
    if (ch === '\n') {
      ctx.fillText(line, x, yy)
      line = ''
      yy += lineHeight
      lineCount++
      if (lineCount >= maxLines) return yy
      continue
    }
    const test = line + ch
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, yy)
      line = ch
      yy += lineHeight
      lineCount++
      if (lineCount >= maxLines) {
        // 截断省略
        return yy
      }
    } else {
      line = test
    }
  }
  ctx.fillText(line, x, yy)
  return yy
}

function trendColor(trend: string): { bg: string; text: string } {
  if (trend === '好转') return { bg: '#0f766e', text: '好转 ↓' }
  if (trend === '加重') return { bg: '#dc2626', text: '加重 ↑' }
  if (trend === '稳定') return { bg: '#b45309', text: '稳定 →' }
  return { bg: '#64748b', text: trend }
}

interface PosterPair {
  label: string
  trendText: string
  trendBg: string
  before?: HTMLImageElement | null
  after?: HTMLImageElement | null
  beforeDate: string
  afterDate: string
}

async function generate() {
  const report = props.report
  if (!report) return
  generating.value = true
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 1080
    canvas.height = 1920
    const ctx = canvas.getContext('2d')!
    ctx.textBaseline = 'top'

    // 背景：上部 teal 渐变，下部白色
    const grad = ctx.createLinearGradient(0, 0, 0, 520)
    grad.addColorStop(0, '#0f766e')
    grad.addColorStop(1, '#14b8a6')
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, 1080, 520)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 520, 1080, 1400)

    // 品牌区
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 56px sans-serif'
    ctx.fillText('SubSkin', 70, 80)
    ctx.font = '30px sans-serif'
    ctx.globalAlpha = 0.9
    ctx.fillText('白癜风病友的AI记录和分享社区', 70, 150)
    ctx.globalAlpha = 1

    // 报告标签
    const tagText = isPeriodic.value
      ? report.report_type === 'weekly'
        ? '白斑周报'
        : '白斑月报'
      : '白斑变化报告'
    ctx.fillStyle = 'rgba(255,255,255,0.25)'
    roundRect(ctx, 70, 220, 200, 56, 28)
    ctx.fill()
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 26px sans-serif'
    ctx.fillText(tagText, 110, 234)

    // 标题（周报/月报优先大字亮点；对比报告用短标题）
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 52px sans-serif'
    const bigTitle =
      isPeriodic.value && report.metrics?.headline
        ? report.metrics.headline
        : isPeriodic.value
          ? report.title
          : `${report.body_site_label}白斑变化报告`
    wrapText(ctx, bigTitle, 70, 306, 940, 64, 2)

    // 周期 + 部位
    ctx.fillStyle = 'rgba(255,255,255,0.85)'
    ctx.font = '28px sans-serif'
    const ps = report.period_start ? report.period_start.slice(0, 10) : ''
    const pe = report.period_end ? report.period_end.slice(0, 10) : ''
    const scopeText = isPeriodic.value
      ? `${report.metrics?.site_count ?? 0} 个部位 · ${ps} ~ ${pe}`
      : `${report.body_site_label}  ·  ${ps} ~ ${pe}`
    ctx.fillText(scopeText, 70, 440)

    // 趋势徽章
    const metrics = report.metrics
    let cardY = 570
    if (metrics) {
      const tc = trendColor(metrics.trend)
      ctx.fillStyle = tc.bg
      roundRect(ctx, 70, cardY, 300, 90, 16)
      ctx.fill()
      ctx.fillStyle = '#ffffff'
      ctx.font = '24px sans-serif'
      ctx.fillText('整体趋势', 96, cardY + 16)
      ctx.font = 'bold 36px sans-serif'
      ctx.fillText(tc.text, 96, cardY + 46)
      // 周报/月报：部位小结
      if (isPeriodic.value && metrics.sites_summary) {
        ctx.fillStyle = '#f0fdfa'
        roundRect(ctx, 400, cardY, 610, 90, 16)
        ctx.fill()
        ctx.strokeStyle = '#ccfbf1'
        ctx.lineWidth = 2
        roundRect(ctx, 400, cardY, 610, 90, 16)
        ctx.stroke()
        ctx.fillStyle = '#0f766e'
        ctx.font = 'bold 30px sans-serif'
        const ss = metrics.sites_summary
        ctx.fillText(
          `好转 ${ss.improving} · 稳定 ${ss.stable} · 关注 ${ss.worsening}`,
          430,
          cardY + 28,
        )
      }
      cardY += 130
    }

    // 前后对比照片区（核心视觉）
    const pairs: PosterPair[] = []
    if (isPeriodic.value) {
      const sites = metrics?.sites ?? []
      for (const s of sites.slice(0, 2)) {
        const [before, after] = await Promise.all([
          tryLoadPhoto(s.first_image_url),
          tryLoadPhoto(s.last_image_url),
        ])
        if (!before || !after) continue
        const tc = trendColor(s.trend)
        pairs.push({
          label: s.body_site_label,
          trendText: tc.text,
          trendBg: tc.bg,
          before,
          after,
          beforeDate: s.first?.date?.slice(5) ?? '',
          afterDate: s.last?.date?.slice(5) ?? '',
        })
      }
    } else if (metrics?.first?.image_url && metrics?.last?.image_url) {
      const [before, after] = await Promise.all([
        tryLoadPhoto(metrics.first.image_url),
        tryLoadPhoto(metrics.last.image_url),
      ])
      if (before && after) {
        const tc = trendColor(metrics.trend)
        pairs.push({
          label: report.body_site_label,
          trendText: tc.text,
          trendBg: tc.bg,
          before,
          after,
          beforeDate: metrics.first.date?.slice(5) ?? '',
          afterDate: metrics.last.date?.slice(5) ?? '',
        })
      }
    }

    if (pairs.length) {
      ctx.fillStyle = '#0f172a'
      ctx.font = 'bold 32px sans-serif'
      ctx.fillText('白斑前后对比', 70, cardY)
      cardY += 52
      for (const p of pairs) {
        const size = pairs.length > 1 ? 380 : 430
        // 部位名 + 趋势
        ctx.fillStyle = '#0f172a'
        ctx.font = 'bold 30px sans-serif'
        ctx.fillText(p.label, 70, cardY)
        const trendWidth = ctx.measureText(p.trendText).width
        ctx.fillStyle = p.trendBg
        roundRect(ctx, 1010 - trendWidth - 30, cardY - 4, trendWidth + 30, 42, 21)
        ctx.fill()
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 24px sans-serif'
        ctx.fillText(p.trendText, 1010 - trendWidth - 15, cardY + 4)
        cardY += 56
        const gap = 1080 - 70 * 2 - size * 2
        drawRoundedSquarePhoto(ctx, p.before!, 70, cardY, size)
        drawRoundedSquarePhoto(ctx, p.after!, 70 + size + gap, cardY, size)
        // 日期标注
        ctx.fillStyle = '#94a3b8'
        ctx.font = '24px sans-serif'
        ctx.fillText(p.beforeDate, 70, cardY + size + 10)
        ctx.fillText(p.afterDate, 70 + size + gap, cardY + size + 10)
        cardY += size + 56
      }
    }

    // 客观指标卡（对比报告：从可用指标中取两个，最多两张）
    if (!isPeriodic.value && metrics && cardY < 1400) {
      const pm = metrics.pair_metrics?.comparison_status === 'measured' ? metrics.pair_metrics : null
      const cards: { label: string; value: string }[] = []
      if (metrics.has_vasi && metrics.vasi_change != null) {
        cards.push({ label: 'VASI 评分变化', value: formatDelta(metrics.vasi_change) })
      }
      if (pm?.melanin_score_a != null && pm?.melanin_score_b != null) {
        cards.push({ label: '复色指数', value: `${pm.melanin_score_a} → ${pm.melanin_score_b}` })
      }
      const areaDelta = pm?.size_change_percent ?? null
      if (areaDelta != null && cards.length < 2) {
        cards.push({ label: '共同范围相对面积变化', value: formatDelta(areaDelta) + '%' })
      }
      for (let i = 0; i < Math.min(2, cards.length); i++) {
        drawMetric(ctx, cards[i].label, cards[i].value, i === 0 ? 70 : 560, cardY)
      }
      if (cards.length) cardY += 170
    }

    // 变化摘要（客观事实，每条一句话；不再放 AI 分析与洞察）
    const summaryLines = (metrics?.change_summary ?? []).slice(0, 4)
    if (summaryLines.length && cardY < 1500) {
      ctx.fillStyle = '#0f172a'
      ctx.font = 'bold 32px sans-serif'
      ctx.fillText('变化摘要', 70, cardY)
      cardY += 50
      ctx.fillStyle = '#475569'
      ctx.font = '27px sans-serif'
      for (const line of summaryLines) {
        if (cardY > 1580) break
        ctx.fillText('• ' + line, 70, cardY, 940)
        cardY += 42
      }
    }

    // 底部二维码 + 提示
    const shareUrl = `${location.origin}/share/report/${report.share_token}`
    try {
      const qrDataUrl = await QRCode.toDataURL(shareUrl, { margin: 1, width: 320 })
      const qrImg = await loadImage(qrDataUrl)
      ctx.fillStyle = '#ffffff'
      roundRect(ctx, 740, 1620, 250, 250, 16)
      ctx.fill()
      ctx.drawImage(qrImg, 752, 1632, 226, 226)
    } catch {
      // 二维码失败不阻断
    }

    ctx.fillStyle = '#0f766e'
    ctx.font = 'bold 30px sans-serif'
    ctx.fillText('扫码查看完整报告', 70, 1670)
    ctx.fillStyle = '#94a3b8'
    ctx.font = '24px sans-serif'
    ctx.fillText('SubSkin · 小白日记', 70, 1720)

    // 免责声明
    ctx.fillStyle = '#94a3b8'
    ctx.font = '22px sans-serif'
    ctx.fillText('本报告不构成医疗诊断建议，请遵医嘱', 70, 1830)

    posterUrl.value = canvas.toDataURL('image/png')
  } finally {
    generating.value = false
  }
}

function formatDelta(v: number): string {
  return (v > 0 ? '+' : '') + v.toFixed(1).replace(/\.0$/, '')
}

function drawMetric(ctx: CanvasRenderingContext2D, label: string, value: string, x: number, y: number) {
  ctx.fillStyle = '#f0fdfa'
  roundRect(ctx, x, y, 450, 130, 16)
  ctx.fill()
  ctx.strokeStyle = '#ccfbf1'
  ctx.lineWidth = 2
  roundRect(ctx, x, y, 450, 130, 16)
  ctx.stroke()
  ctx.fillStyle = '#64748b'
  ctx.font = '24px sans-serif'
  ctx.fillText(label, x + 28, y + 24)
  ctx.fillStyle = '#0f766e'
  ctx.font = 'bold 48px sans-serif'
  ctx.fillText(value, x + 28, y + 64)
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function downloadPoster() {
  if (!posterUrl.value) return
  const a = document.createElement('a')
  a.href = posterUrl.value
  a.download = `SubSkin-白斑变化报告.png`
  a.click()
}

async function sharePoster() {
  if (!posterUrl.value) return
  try {
    const res = await fetch(posterUrl.value)
    const blob = await res.blob()
    const file = new File([blob], 'SubSkin-白斑变化报告.png', { type: 'image/png' })
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: 'SubSkin 白斑变化报告' })
      return
    }
  } catch {
    // 降级
  }
  downloadPoster()
}
</script>

<template>
  <teleport to="body">
    <div v-if="visible" class="poster-overlay" @click.self="emit('close')">
      <div class="poster-modal">
        <div class="poster-modal__header">
          <h3>报告海报</h3>
          <button class="poster-modal__close" @click="emit('close')">
            <i class="ri-close-line"></i>
          </button>
        </div>

        <div class="poster-modal__body">
          <div v-if="generating" class="poster-loading">
            <i class="ri-loader-4-line animate-spin"></i>
            <span>海报生成中...</span>
          </div>
          <img v-else-if="posterUrl" :src="posterUrl" alt="报告海报" class="poster-img" />
        </div>

        <div class="poster-modal__footer">
          <p class="poster-tip">长按图片可保存，或点击下方按钮分享</p>
          <div class="poster-actions">
            <button class="poster-btn poster-btn--primary" @click="sharePoster">
              <i class="ri-share-line"></i> 分享
            </button>
            <button class="poster-btn" @click="downloadPoster">
              <i class="ri-download-line"></i> 保存
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.poster-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.poster-modal {
  background: white;
  border-radius: 16px;
  max-width: 420px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

html.dark .poster-modal {
  background: #1e293b;
}

.poster-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}

html.dark .poster-modal__header {
  border-color: #334155;
}

.poster-modal__header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

html.dark .poster-modal__header h3 {
  color: #e2e8f0;
}

.poster-modal__close {
  border: none;
  background: transparent;
  font-size: 22px;
  color: #94a3b8;
  cursor: pointer;
}

.poster-modal__body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  min-height: 200px;
}

.poster-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 14px;
}

.poster-loading i {
  font-size: 28px;
  color: var(--color-primary-500);
}

.poster-img {
  max-width: 100%;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.poster-modal__footer {
  padding: 12px 16px;
  border-top: 1px solid #f1f5f9;
}

html.dark .poster-modal__footer {
  border-color: #334155;
}

.poster-tip {
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 10px;
}

.poster-actions {
  display: flex;
  gap: 10px;
}

.poster-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: white;
  color: #475569;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

html.dark .poster-btn {
  background: #0f172a;
  border-color: #334155;
  color: #cbd5e1;
}

.poster-btn--primary {
  background: var(--color-primary-500);
  border-color: var(--color-primary-500);
  color: white;
}

html.dark .poster-btn--primary {
  background: var(--color-primary-500);
  color: white;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
