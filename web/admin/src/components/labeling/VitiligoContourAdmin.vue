<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, reactive, nextTick } from 'vue'

// ── 本地类型（与 admin 解耦，不依赖 app 的 API）──
export interface AdminContourRegion {
  label: string
  polygon: number[][]  // [[x,y], ...] 归一化 0-1
  area_percent?: number
  source?: 'ai' | 'admin'  // ai 预标注 vs 人工
}

const props = defineProps<{
  imageUrl: string
  contours: AdminContourRegion[]
  editable?: boolean
}>()

const emit = defineEmits<{
  update: [contours: AdminContourRegion[]]
  confirm: [contours: AdminContourRegion[]]
}>()

// ── DOM 引用 ──
const containerRef = ref<HTMLDivElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
const imgDisplaySize = ref({ width: 1, height: 1 })
const imgReady = ref(false)
const naturalSize = ref({ width: 1, height: 1 })

const localContours = ref<AdminContourRegion[]>([])
const selectedContourIdx = ref(-1)
const selectedPointIdx = ref(-1)
const mode = ref<'select' | 'draw' | 'move'>('select')
const isDrawing = ref(false)
const drawPoints = ref<number[][]>([])
const isDragging = ref(false)
const dragStartPos = ref({ x: 0, y: 0 })
const dragOrigins = ref<number[][]>([])

// ── Pan & Zoom 状态 ──
const transform = reactive({
  scale: 1,
  offsetX: 0,
  offsetY: 0,
})
const MIN_SCALE = 0.1
const MAX_SCALE = 10
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, offsetX: 0, offsetY: 0 })
let spaceHeld = false  // 空格键临时启用平移

// 基础适配: 图片刚好放下时的缩放比
const baseFitScale = ref(1)

// ── Fullscreen ──
const isFullscreen = ref(false)

// ── 同步父组件 contours ──
watch(() => props.contours, (val) => {
  localContours.value = val.map(c => ({ ...c, polygon: c.polygon.map(p => [...p]) }))
}, { immediate: true, deep: true })

watch(() => props.imageUrl, () => {
  imgReady.value = false
  transform.scale = 1
  transform.offsetX = 0
  transform.offsetY = 0
})

// ── 坐标转换: 归一化 (0-1) → 原图像素 ──
function toPixel(nx: number, ny: number): [number, number] {
  return [nx * naturalSize.value.width, ny * naturalSize.value.height]
}

function toNorm(px: number, py: number): [number, number] {
  return [
    Math.max(0, Math.min(1, px / (naturalSize.value.width || 1))),
    Math.max(0, Math.min(1, py / (naturalSize.value.height || 1))),
  ]
}

function polygonPoints(contour: AdminContourRegion): string {
  return contour.polygon
    .map(([nx, ny]) => {
      const [px, py] = toPixel(nx, ny)
      return `${px},${py}`
    })
    .join(' ')
}

// ── 图片加载: 测量真实显示尺寸 ──
function onImgLoad() {
  if (!imgRef.value) return
  naturalSize.value = { width: imgRef.value.naturalWidth, height: imgRef.value.naturalHeight }
  imgReady.value = true
  updateImgDisplaySize()
  // 初始: 自适应填充容器
  fitToContainer()
}

function updateImgDisplaySize() {
  if (!imgRef.value) return
  const rect = imgRef.value.getBoundingClientRect()
  if (rect.width > 0 && rect.height > 0) {
    imgDisplaySize.value = { width: rect.width, height: rect.height }
  }
}

function fitToContainer() {
  if (!containerRef.value || !imgRef.value) return
  const cw = containerRef.value.clientWidth
  const ch = containerRef.value.clientHeight
  const iw = imgRef.value.naturalWidth
  const ih = imgRef.value.naturalHeight
  if (cw === 0 || ch === 0 || iw === 0 || ih === 0) return
  // 选宽高中缩得较小的, 让图完整放下
  const scale = Math.min(cw / iw, ch / ih) * 0.95  // 留 5% 边距
  baseFitScale.value = scale
  transform.scale = 1  // 保持在 fit 状态 (zoomIn/Out 改 transform.scale)
  // 居中
  const scaledW = iw * scale
  const scaledH = ih * scale
  transform.offsetX = (cw - scaledW) / 2
  transform.offsetY = (ch - scaledH) / 2
  // 等 CSS 把图渲染到对应尺寸, 同步 imgDisplaySize
  requestAnimationFrame(() => updateImgDisplaySize())
}

function zoomActualSize() {
  transform.scale = 1
  if (!containerRef.value || !imgRef.value) return
  const cw = containerRef.value.clientWidth
  const ch = containerRef.value.clientHeight
  const iw = imgRef.value.naturalWidth
  const ih = imgRef.value.naturalHeight
  if (cw === 0 || ch === 0) return
  // 100% 显示, 居中
  const scaledW = iw * baseFitScale.value
  const scaledH = ih * baseFitScale.value
  transform.offsetX = (cw - scaledW) / 2
  transform.offsetY = (ch - scaledH) / 2
  updateImgDisplaySize()
}

// ── 全屏切换 ──
async function toggleFullscreen() {
  if (isFullscreen.value) {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      }
    } catch { /* ignore */ }
    isFullscreen.value = false
  } else {
    try {
      if (containerRef.value) {
        await containerRef.value.requestFullscreen()
        isFullscreen.value = true
      }
    } catch {
      // Fallback: use fixed positioning to fill viewport
      isFullscreen.value = true
    }
  }
  nextTick(() => fitToContainer())
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  nextTick(() => fitToContainer())
}

// ── 滚轮缩放 (以光标为锚点) ──
function onWheel(e: WheelEvent) {
  e.preventDefault()
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top

  // 缩放因子: 向上滚放大, 向下滚缩小
  const delta = e.deltaY < 0 ? 1.15 : 1 / 1.15
  const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, transform.scale * delta))
  if (newScale === transform.scale) return

  // 保持鼠标位置固定: 缩放前后, 鼠标下的"图片内容点"不变
  // 公式: imagePos = (mousePos - offset) / scale
  // 缩放后: newOffset = mousePos - imagePos * newScale
  const imageX = (cx - transform.offsetX) / transform.scale
  const imageY = (cy - transform.offsetY) / transform.scale
  transform.offsetX = cx - imageX * newScale
  transform.offsetY = cy - imageY * newScale
  transform.scale = newScale
}

// ── 平移: 中键 / 空格+拖拽 / 双指 (移动端简化: 单指空白处) ──
function onPointerDownPan(e: PointerEvent) {
  // 条件: 空白处 OR 按住空格
  if (e.button !== 0 && e.button !== 1) return
  if (!spaceHeld && (e.target as HTMLElement)?.tagName !== 'IMG' && !(e.target as HTMLElement)?.closest('.pan-zone')) {
    return
  }
  isPanning.value = true
  panStart.value = { x: e.clientX, y: e.clientY, offsetX: transform.offsetX, offsetY: transform.offsetY }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMovePan(e: PointerEvent) {
  if (!isPanning.value) return
  transform.offsetX = panStart.value.offsetX + (e.clientX - panStart.value.x)
  transform.offsetY = panStart.value.offsetY + (e.clientY - panStart.value.y)
}

function onPointerUpPan(e: PointerEvent) {
  if (!isPanning.value) return
  isPanning.value = false
  ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
}

// ── 缩放按钮 ──
function zoomIn() {
  if (!containerRef.value) return
  const cw = containerRef.value.clientWidth / 2
  const ch = containerRef.value.clientHeight / 2
  const newScale = Math.min(MAX_SCALE, transform.scale * 1.3)
  const imageX = (cw - transform.offsetX) / transform.scale
  const imageY = (ch - transform.offsetY) / transform.scale
  transform.offsetX = cw - imageX * newScale
  transform.offsetY = ch - imageY * newScale
  transform.scale = newScale
}
function zoomOut() {
  if (!containerRef.value) return
  const cw = containerRef.value.clientWidth / 2
  const ch = containerRef.value.clientHeight / 2
  const newScale = Math.max(MIN_SCALE, transform.scale / 1.3)
  const imageX = (cw - transform.offsetX) / transform.scale
  const imageY = (ch - transform.offsetY) / transform.scale
  transform.offsetX = cw - imageX * newScale
  transform.offsetY = ch - imageY * newScale
  transform.scale = newScale
}

// ── 键盘: 空格临时启用平移, R 重置 ──
function onKeyDown(e: KeyboardEvent) {
  if (e.code === 'Space' && !e.repeat) {
    spaceHeld = true
  } else if (e.key === 'r' || e.key === 'R') {
    fitToContainer()
  } else if (e.key === '0') {
    zoomActualSize()
  } else if (e.key === '+' || e.key === '=') {
    zoomIn()
  } else if (e.key === '-' || e.key === '_') {
    zoomOut()
  } else if (e.key === 'f' || e.key === 'F') {
    if (!(e.target as HTMLElement)?.closest('input,textarea,[contenteditable]')) {
      toggleFullscreen()
    }
  }
}
function onKeyUp(e: KeyboardEvent) {
  if (e.code === 'Space') spaceHeld = false
}

// 父组件传来 contour 已变化时 (AI 预标注后), 重新测量
watch(() => props.contours, () => {
  requestAnimationFrame(() => updateImgDisplaySize())
}, { deep: true })

const resizeObserver = new ResizeObserver(() => {
  if (imgReady.value) updateImgDisplaySize()
})

onMounted(() => {
  if (containerRef.value) resizeObserver.observe(containerRef.value)
  window.addEventListener('mouseup', finishInteraction)
  window.addEventListener('touchend', finishInteraction)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  window.removeEventListener('mouseup', finishInteraction)
  window.removeEventListener('touchend', finishInteraction)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (document.fullscreenElement) {
    try { document.exitFullscreen() } catch { /* ignore */ }
  }
})

// ── 指针位置 (在原图坐标系中) ──
function getPointerPos(e: MouseEvent | TouchEvent): { x: number; y: number } {
  if (!imgRef.value) return { x: 0, y: 0 }
  const rect = imgRef.value.getBoundingClientRect()
  let cx: number, cy: number
  if ('touches' in e) {
    const t = (e as TouchEvent).touches[0] || (e as TouchEvent).changedTouches[0]
    if (!t) return { x: 0, y: 0 }
    cx = t.clientX
    cy = t.clientY
  } else {
    cx = (e as MouseEvent).clientX
    cy = (e as MouseEvent).clientY
  }
  // rect 是变换后 (含 baseFitScale) 的位置, 转回 naturalSize 坐标系
  // 实际显示尺寸 = naturalSize * baseFitScale
  const totalScale = baseFitScale.value * transform.scale
  if (totalScale <= 0) return { x: 0, y: 0 }
  return {
    x: (cx - rect.left) / totalScale,
    y: (cy - rect.top) / totalScale,
  }
}

function onPointerDown(e: MouseEvent | TouchEvent) {
  if (!props.editable) return
  if (spaceHeld) return  // 空格模式下不画
  if (mode.value === 'select') {
    const { x, y } = getPointerPos(e)
    // 检查是否点中控制点 (naturalSize 坐标系, 用 ~30px 容差)
    const HIT_RADIUS = 30
    for (let ci = 0; ci < localContours.value.length; ci++) {
      for (let pi = 0; pi < localContours.value[ci].polygon.length; pi++) {
        const [px, py] = toPixel(localContours.value[ci].polygon[pi][0], localContours.value[ci].polygon[pi][1])
        const dx = x - px, dy = y - py
        if (dx * dx + dy * dy <= HIT_RADIUS * HIT_RADIUS) {
          selectedContourIdx.value = ci
          selectedPointIdx.value = pi
          isDragging.value = true
          dragStartPos.value = { x, y }
          return
        }
      }
    }
    // 点击空白: 取消选择
    selectedContourIdx.value = -1
    selectedPointIdx.value = -1
  } else if (mode.value === 'draw') {
    const { x, y } = getPointerPos(e)
    const [nx, ny] = toNorm(x, y)
    if (!isDrawing.value) {
      isDrawing.value = true
      drawPoints.value = [[nx, ny]]
    } else {
      drawPoints.value.push([nx, ny])
    }
  } else if (mode.value === 'move') {
    const { x, y } = getPointerPos(e)
    for (let ci = 0; ci < localContours.value.length; ci++) {
      const inside = isInsidePolygon(x, y, localContours.value[ci].polygon)
      if (inside) {
        selectedContourIdx.value = ci
        isDragging.value = true
        dragStartPos.value = { x, y }
        dragOrigins.value = localContours.value[ci].polygon.map(p => [...p])
        return
      }
    }
  }
}

function onPointerMove(e: MouseEvent | TouchEvent) {
  if (!props.editable) return
  const { x, y } = getPointerPos(e)
  if (mode.value === 'draw' && isDrawing.value) {
    const [nx, ny] = toNorm(x, y)
    drawPoints.value.push([nx, ny])
  } else if (mode.value === 'select' && isDragging.value && selectedContourIdx.value >= 0 && selectedPointIdx.value >= 0) {
    const [nx, ny] = toNorm(x, y)
    localContours.value[selectedContourIdx.value].polygon[selectedPointIdx.value] = [nx, ny]
  } else if (mode.value === 'move' && isDragging.value && selectedContourIdx.value >= 0) {
    const [nx, ny] = toNorm(x, y)
    const [ox, oy] = toNorm(dragStartPos.value.x, dragStartPos.value.y)
    const dx = nx - ox, dy = ny - oy
    const ci = selectedContourIdx.value
    localContours.value[ci].polygon = dragOrigins.value.map(p => [
      Math.max(0, Math.min(1, p[0] + dx)),
      Math.max(0, Math.min(1, p[1] + dy)),
    ])
  }
}

function finishInteraction() {
  if (isDrawing.value && drawPoints.value.length >= 3) {
    // 完成绘制
    const label = `白斑${localContours.value.filter(c => c.source !== 'ai').length + 1}`
    const polygon = simplifyPoints(drawPoints.value, 0.003)
    const area = polygonArea(polygon) * 100
    localContours.value.push({
      label,
      polygon,
      area_percent: Math.round(area * 10) / 10,
      source: 'admin',
    })
    emitUpdate()
  }
  isDrawing.value = false
  drawPoints.value = []
  isDragging.value = false
}

function isInsidePolygon(px: number, py: number, polygon: number[][]): boolean {
  // 射线法
  let inside = false
  const [nx, ny] = toNorm(px, py)
  const n = polygon.length
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const [xi, yi] = polygon[i]
    const [xj, yj] = polygon[j]
    if (((yi > ny) !== (yj > ny)) && (nx < (xj - xi) * (ny - yi) / (yj - yi + 1e-9) + xi)) {
      inside = !inside
    }
  }
  return inside
}

function polygonArea(polygon: number[][]): number {
  if (polygon.length < 3) return 0
  let area = 0
  for (let i = 0; i < polygon.length; i++) {
    const [x1, y1] = polygon[i]
    const [x2, y2] = polygon[(i + 1) % polygon.length]
    area += x1 * y2 - x2 * y1
  }
  return Math.abs(area) / 2
}

function simplifyPoints(points: number[][], epsilon: number): number[][] {
  if (points.length <= 6) return points
  // 简化: 取每 N 个点的代表 (道格拉斯-普克的简化版: 按距离)
  const result: number[][] = [points[0]]
  for (let i = 1; i < points.length - 1; i++) {
    const [px, py] = result[result.length - 1]
    const [x, y] = points[i]
    const dist = Math.hypot(x - px, y - py)
    if (dist >= epsilon) result.push(points[i])
  }
  result.push(points[points.length - 1])
  return result
}

function deleteContour(ci: number) {
  localContours.value.splice(ci, 1)
  selectedContourIdx.value = -1
  emitUpdate()
}

function addPoint(ci: number, afterIdx: number) {
  const polygon = localContours.value[ci].polygon
  const i = (afterIdx + 1) % polygon.length
  const prev = polygon[afterIdx]
  const next = polygon[i]
  polygon.splice(i, 0, [(prev[0] + next[0]) / 2, (prev[1] + next[1]) / 2])
  emitUpdate()
}

function removePoint(ci: number, pi: number) {
  if (localContours.value[ci].polygon.length <= 3) return
  localContours.value[ci].polygon.splice(pi, 1)
  selectedPointIdx.value = -1
  emitUpdate()
}

function emitUpdate() {
  emit('update', localContours.value.map(c => ({ ...c, polygon: c.polygon.map(p => [...p]) })))
}

function handleConfirm() {
  emit('confirm', localContours.value.map(c => ({ ...c, polygon: c.polygon.map(p => [...p]) })))
}
void handleConfirm

const drawPath = computed(() => {
  if (!isDrawing.value || drawPoints.value.length < 2) return ''
  return drawPoints.value.map(([nx, ny]) => { const [px, py] = toPixel(nx, ny); return `${px},${py}` }).join(' ')
})

// ── 应用 transform 到 img / svg ──
const imgStyle = computed(() => ({
  transform: `translate(${transform.offsetX}px, ${transform.offsetY}px) scale(${transform.scale * baseFitScale.value})`,
  transformOrigin: '0 0',
  width: `${naturalSize.value.width}px`,
  height: `${naturalSize.value.height}px`,
}))

const svgStyle = computed(() => ({
  transform: `translate(${transform.offsetX}px, ${transform.offsetY}px) scale(${transform.scale * baseFitScale.value})`,
  transformOrigin: '0 0',
  width: `${naturalSize.value.width}px`,
  height: `${naturalSize.value.height}px`,
  cursor: !props.editable ? 'default' :
    spaceHeld ? (isPanning.value ? 'grabbing' : 'grab') :
    mode.value === 'draw' ? 'crosshair' :
    mode.value === 'move' ? 'move' : 'default',
}))

const isFullscreenFallback = computed(() => isFullscreen.value && !document.fullscreenElement)

const containerStyle = computed(() => ({
  cursor: isPanning.value ? 'grabbing' : (spaceHeld ? 'grab' : 'default'),
  borderRadius: isFullscreenFallback.value ? '0' : '8px',
  ...(isFullscreenFallback.value ? {
    position: 'fixed' as const,
    top: '0',
    left: '0',
    width: '100vw',
    height: '100vh',
    zIndex: 9999,
  } : {
    height: '100%',
    minHeight: '0',
  }),
}))

// AI 标注用半透明冷色（蓝色），管理员标注用饱和色
const aiColor = '#3b82f6'      // 蓝色 AI
const adminColors = ['#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899']

function contourColor(contour: AdminContourRegion, ci: number, selected: boolean): string {
  if (contour.source === 'ai') {
    return selected ? aiColor : aiColor + 'b3'
  }
  const base = adminColors[ci % adminColors.length]
  return selected ? base : base + 'b3'
}

function contourFill(contour: AdminContourRegion, ci: number): string {
  if (contour.source === 'ai') return 'rgba(59,130,246,0.10)'
  const hex = adminColors[ci % adminColors.length].slice(1)
  const r = parseInt(hex.slice(0,2), 16)
  const g = parseInt(hex.slice(2,4), 16)
  const b = parseInt(hex.slice(4,6), 16)
  return `rgba(${r},${g},${b},0.18)`
}

const totalAreaPercent = computed(() =>
  localContours.value.reduce((sum, c) => sum + (c.area_percent ?? 0), 0)
)

const adminContourCount = computed(() =>
  localContours.value.filter(c => c.source !== 'ai').length
)

const zoomPercent = computed(() => Math.round(transform.scale * 100))

defineExpose({
  getContours: () => localContours.value,
  clear: () => { localContours.value = []; emitUpdate() },
  fitToContainer,
  zoomIn,
  zoomOut,
})
</script>

<template>
  <div
    ref="containerRef"
    class="relative select-none w-full h-full pan-zone"
    :style="containerStyle"
    style="background: #0f172a; overflow: hidden;"
    @wheel.passive.prevent="onWheel"
    @pointerdown="onPointerDownPan"
    @pointermove="onPointerMovePan"
    @pointerup="onPointerUpPan"
    @pointercancel="onPointerUpPan"
  >
    <img
      ref="imgRef"
      :src="imageUrl"
      :style="{ ...imgStyle, maxWidth: 'none', maxHeight: 'none' }"
      style="display: block; position: absolute; top: 0; left: 0; user-select: none; -webkit-user-drag: none;"
      @load="onImgLoad"
      draggable="false"
      alt=""
    />

    <!-- 缩放信息条 -->
    <div class="absolute" style="top: 12px; left: 60px; display: flex; align-items: center; gap: 4px; z-index: 20; background: rgba(15,23,42,0.92); backdrop-filter: blur(8px); border-radius: 8px; padding: 4px 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
      <button class="zoom-btn" @click="zoomOut" title="缩小 (-)"><i class="ri-subtract-line"></i></button>
      <span style="font-size: 11px; color: #cbd5e1; min-width: 42px; text-align: center; font-variant-numeric: tabular-nums;">{{ zoomPercent }}%</span>
      <button class="zoom-btn" @click="zoomIn" title="放大 (+)"><i class="ri-add-line"></i></button>
      <span style="width: 1px; height: 16px; background: rgba(148,163,184,0.3); margin: 0 2px;"></span>
      <button class="zoom-btn" @click="fitToContainer" title="适应窗口 (R)"><i class="ri-fullscreen-line"></i></button>
      <button class="zoom-btn" @click="zoomActualSize" title="1:1 实际大小 (0)"><i class="ri-equalizer-2-line"></i></button>
      <span style="width: 1px; height: 16px; background: rgba(148,163,184,0.3); margin: 0 2px;"></span>
      <button class="zoom-btn" @click="toggleFullscreen" title="画布全屏 (F)">
        <i :class="isFullscreen ? 'ri-fullscreen-exit-line' : 'ri-fullscreen-fill'"></i>
      </button>
    </div>

    <!-- Area summary panel -->
    <div v-if="localContours.length > 0" class="absolute" style="top: 12px; right: 12px; background: rgba(15, 23, 42, 0.92); color: #e2e8f0; backdrop-filter: blur(8px); border-radius: 8px; padding: 8px 10px; font-size: 11px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); z-index: 10; max-width: 220px;">
      <div v-for="(c, i) in localContours" :key="i" style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
        <span :style="{color: c.source === 'ai' ? aiColor : adminColors[i % adminColors.length], fontSize: '10px'}">●</span>
        <span style="font-weight: 500;">{{ c.label }}</span>
        <span style="margin-left: auto; opacity: 0.7;">{{ (c.area_percent ?? 0).toFixed(1) }}%</span>
      </div>
      <div v-if="adminContourCount > 1" style="font-weight: 700; margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(148,163,184,0.2);">
        合计: {{ totalAreaPercent.toFixed(1) }}%
      </div>
    </div>

    <!-- SVG overlay - 与 img 同步 transform -->
    <svg
      ref="svgRef"
      class="absolute top-0 left-0"
      :style="svgStyle"
      :viewBox="`0 0 ${naturalSize.width} ${naturalSize.height}`"
      preserveAspectRatio="xMidYMid meet"
      @mousedown.stop="onPointerDown"
      @mousemove.stop="onPointerMove"
      @touchstart.stop="onPointerDown"
      @touchmove.stop="onPointerMove"
    >
      <defs>
        <filter id="contour-glow">
          <feGaussianBlur stdDeviation="2" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <polygon
        v-for="(contour, ci) in localContours"
        :key="ci"
        :points="polygonPoints(contour)"
        :fill="contourFill(contour, ci)"
        :stroke="contourColor(contour, ci, selectedContourIdx === ci)"
        :stroke-width="selectedContourIdx === ci ? 3 : 2"
        stroke-dasharray="8 4"
        stroke-linejoin="round"
        :filter="selectedContourIdx === ci ? 'url(#contour-glow)' : ''"
        class="contour-animated"
        style="pointer-events: none;"
      />

      <g v-for="(contour, ci) in localContours" :key="'lbl-'+ci">
        <text
          :x="toPixel(contour.polygon[0][0], contour.polygon[0][1])[0]"
          :y="toPixel(contour.polygon[0][0], contour.polygon[0][1])[1] - 12"
          :fill="contour.source === 'ai' ? aiColor : adminColors[ci % adminColors.length]"
          font-size="14" font-weight="600" text-anchor="middle"
          style="pointer-events: none; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.8))"
        >{{ contour.label }}</text>
      </g>

      <template v-if="editable" v-for="(contour, ci) in localContours" :key="'pts-'+ci">
        <g v-for="(point, pi) in contour.polygon" :key="pi">
          <circle
            :cx="toPixel(point[0], point[1])[0]"
            :cy="toPixel(point[0], point[1])[1]"
            :r="selectedContourIdx === ci && selectedPointIdx === pi ? 9 : 6"
            :fill="selectedContourIdx === ci && selectedPointIdx === pi ? (contour.source === 'ai' ? aiColor : adminColors[ci % adminColors.length]) : '#0f172a'"
            :stroke="contour.source === 'ai' ? aiColor : adminColors[ci % adminColors.length]"
            :stroke-width="2.5"
            style="cursor: pointer; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.5))"
          />
        </g>
      </template>

      <polyline
        v-if="isDrawing && drawPoints.length >= 2"
        :points="drawPath"
        fill="none" stroke="#f59e0b" stroke-width="3"
        stroke-dasharray="6 3" stroke-linecap="round" stroke-linejoin="round"
        class="contour-animated"
        style="pointer-events: none;"
      />
    </svg>

    <!-- Toolbar (左) -->
    <div v-if="editable" class="absolute" style="top: 12px; left: 12px; display: flex; flex-direction: column; gap: 6px; z-index: 20;">
      <button
        v-for="tool in ([
          { id: 'select', label: '⬚', tip: '选择/拖拽控制点' },
          { id: 'draw', label: '✎', tip: '手绘新白斑区域' },
          { id: 'move', label: '⤡', tip: '整体移动轮廓' },
        ] as const)"
        :key="tool.id"
        style="width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; transition: all 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.3);"
        :style="mode === tool.id
          ? { background: '#6366f1', color: '#fff' }
          : { background: 'rgba(15,23,42,0.9)', color: '#cbd5e1', border: '1px solid rgba(148,163,184,0.2)' }"
        :title="tool.tip"
        @click.stop="mode = tool.id"
      >{{ tool.label }}</button>
    </div>

    <!-- Selected contour actions -->
    <div v-if="editable && selectedContourIdx >= 0" class="absolute" style="bottom: 12px; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 6px; background: rgba(15,23,42,0.92); backdrop-filter: blur(8px); border-radius: 10px; padding: 6px 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); border: 1px solid rgba(148,163,184,0.2); z-index: 20;">
      <button class="text-xs" style="padding: 4px 8px; border-radius: 6px; background: rgba(99,102,241,0.2); color: #c7d2fe;"
        @click.stop="addPoint(selectedContourIdx, selectedPointIdx >= 0 ? selectedPointIdx : 0)"
      >+ 控制点</button>
      <button v-if="selectedPointIdx >= 0"
        class="text-xs" style="padding: 4px 8px; border-radius: 6px; background: rgba(99,102,241,0.2); color: #c7d2fe;"
        @click.stop="removePoint(selectedContourIdx, selectedPointIdx)"
      >- 控制点</button>
      <button
        class="text-xs" style="padding: 4px 8px; border-radius: 6px; background: rgba(239,68,68,0.2); color: #fca5a5;"
        @click.stop="deleteContour(selectedContourIdx)"
      >删除区域</button>
    </div>

    <!-- Hint -->
    <div v-if="editable" class="absolute" style="bottom: 12px; right: 12px; z-index: 20; pointer-events: none;">
      <span style="display: inline-block; font-size: 10px; background: rgba(15,23,42,0.85); color: #94a3b8; padding: 5px 8px; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); border: 1px solid rgba(148,163,184,0.2);">
        <i class="ri-mouse-line"></i> 滚轮缩放 · 空格+拖拽平移 · R 适应窗口 · 0 实际大小 · F 全屏
      </span>
    </div>

    <!-- Hint for drawing -->
    <div v-if="editable && mode === 'draw' && !isDrawing" class="absolute" style="top: 60px; left: 60px; z-index: 20; pointer-events: none;">
      <span style="display: inline-block; font-size: 11px; background: rgba(15,23,42,0.92); color: #cbd5e1; padding: 6px 10px; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); border: 1px solid rgba(148,163,184,0.2);">
        在图上划线圈出白斑区域（蓝色=AI，橙色=你画的）
      </span>
    </div>
  </div>
</template>

<style scoped>
@keyframes dash-march {
  to { stroke-dashoffset: -24; }
}
.contour-animated {
  animation: dash-march 1s linear infinite;
}
.zoom-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: #cbd5e1;
  border-radius: 4px;
  font-size: 12px;
  transition: all 0.15s;
}
.zoom-btn:hover {
  background: rgba(99,102,241,0.2);
  color: #c7d2fe;
}
</style>
