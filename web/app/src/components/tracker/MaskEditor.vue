<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps<{
  imageUrl: string
  editable?: boolean
  fullHeight?: boolean
  initialSkinLayerUrl?: string | null
  initialLesionLayerUrl?: string | null
}>()

const emit = defineEmits<{
  confirm: [payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string }]
  cancel: []
}>()

type Tool = 'skin-brush' | 'lesion-brush' | 'eraser'

const tool = ref<Tool>('skin-brush')
const brushSize = ref(32)
const layerOpacity = ref(0.55)

const SKIN_COLOR = 'rgba(96,165,250,1)'
const LESION_COLOR = 'rgba(244,114,182,1)'

const containerRef = ref<HTMLDivElement | null>(null)
const imgContainerRef = ref<HTMLDivElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)
const skinCanvasRef = ref<HTMLCanvasElement | null>(null)
const lesionCanvasRef = ref<HTMLCanvasElement | null>(null)
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)

const imageLoaded = ref(false)
const imageError = ref(false)
const imageLoading = ref(false)
const imageErrorMsg = ref('')
const canvasWidth = ref(0)
const canvasHeight = ref(0)

// ── Zoom & Pan state ──
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const minZoom = 0.15
const maxZoom = 8
const zoomStep = 0.25

// ── Pan tracking ──
const isPanning = ref(false)
let _panStartX = 0
let _panStartY = 0
let _panStartPanX = 0
let _panStartPanY = 0

const isPainting = ref(false)
const skinAreaPct = ref(0)
const lesionAreaPct = ref(0)
const regionAreaPct = ref(0)

const history = ref<Array<{ skin: ImageData; lesion: ImageData }>>([])
const historyIndex = ref(-1)
const HISTORY_MAX = 30

const canUndo = computed(() => historyIndex.value > 0)
const canRedo = computed(() => historyIndex.value < history.value.length - 1)

const areaPercent = computed(() => {
  if (regionAreaPct.value < 0.01) return 0
  return Math.round((lesionAreaPct.value / regionAreaPct.value) * 1000) / 10
})

function getCtx(canvas: HTMLCanvasElement | null) {
  return canvas?.getContext('2d', { willReadFrequently: true }) || null
}

function clientToCanvas(clientX: number, clientY: number): [number, number] {
  const overlay = overlayCanvasRef.value
  const skin = skinCanvasRef.value
  if (!overlay || !skin) return [0, 0]
  const rect = overlay.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) return [0, 0]
  // The overlay canvas CSS dimensions match the image natural dimensions.
  // getBoundingClientRect returns post-transform (zoom+pan applied via parent).
  // To map client coords → canvas pixel coords, divide by the visual scale factor.
  const displayW = rect.width
  const displayH = rect.height
  if (displayW === 0 || displayH === 0) return [0, 0]
  const scaleX = skin.width / displayW
  const scaleY = skin.height / displayH
  return [(clientX - rect.left) * scaleX, (clientY - rect.top) * scaleY]
}

// ── Pan helpers ──
function clampPan() {
  const container = imgContainerRef.value
  const img = imgRef.value
  if (!container || !img) return
  const cw = container.clientWidth, ch = container.clientHeight
  const iw = img.naturalWidth * zoom.value, ih = img.naturalHeight * zoom.value
  // Allow panning up to half the image outside the container
  const limitX = Math.max(0, (iw - cw) / 2 + cw * 0.3)
  const limitY = Math.max(0, (ih - ch) / 2 + ch * 0.3)
  panX.value = Math.max(-limitX, Math.min(limitX, panX.value))
  panY.value = Math.max(-limitY, Math.min(limitY, panY.value))
}

function resetPan() {
  panX.value = 0
  panY.value = 0
}

function paintAt(targetCanvas: HTMLCanvasElement, x: number, y: number, fromX: number, fromY: number, color: string, erase: boolean) {
  const ctx = getCtx(targetCanvas)
  if (!ctx) return
  ctx.globalCompositeOperation = erase ? 'destination-out' : 'source-over'
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = brushSize.value * 2
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(fromX, fromY)
  ctx.lineTo(x, y)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(x, y, brushSize.value, 0, Math.PI * 2)
  ctx.fill()
  ctx.globalCompositeOperation = 'source-over'
}

function activeCanvas(): HTMLCanvasElement | null {
  if (tool.value === 'lesion-brush') return lesionCanvasRef.value
  return skinCanvasRef.value
}

let lastPos: [number, number] = [0, 0]

function onPointerDown(e: PointerEvent) {
  if (!imageLoaded.value) return

  // Right-click or middle-click → pan
  if (e.button === 1 || e.button === 2) {
    isPanning.value = true
    _panStartX = e.clientX
    _panStartY = e.clientY
    _panStartPanX = panX.value
    _panStartPanY = panY.value
    e.preventDefault()
    return
  }

  // Left-click with Space held → pan
  if (e.button === 0 && (e.metaKey || e.ctrlKey)) {
    isPanning.value = true
    _panStartX = e.clientX
    _panStartY = e.clientY
    _panStartPanX = panX.value
    _panStartPanY = panY.value
    e.preventDefault()
    return
  }

  if (!props.editable) return
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  e.preventDefault()
  const [x, y] = clientToCanvas(e.clientX, e.clientY)

  if (tool.value === 'eraser') {
    isPainting.value = true
    lastPos = [x, y]
    if (skinCanvasRef.value) paintAt(skinCanvasRef.value, x, y, x, y, SKIN_COLOR, true)
    if (lesionCanvasRef.value) paintAt(lesionCanvasRef.value, x, y, x, y, LESION_COLOR, true)
    drawOverlay()
    return
  }

  const target = activeCanvas()
  const color = tool.value === 'lesion-brush' ? LESION_COLOR : SKIN_COLOR
  if (!target) return
  isPainting.value = true
  lastPos = [x, y]
  paintAt(target, x, y, x, y, color, false)
  if (tool.value === 'skin-brush' && lesionCanvasRef.value) {
    paintAt(lesionCanvasRef.value, x, y, x, y, LESION_COLOR, true)
  } else if (tool.value === 'lesion-brush' && skinCanvasRef.value) {
    paintAt(skinCanvasRef.value, x, y, x, y, SKIN_COLOR, true)
  }
  drawOverlay()
}

function onPointerMove(e: PointerEvent) {
  if (isPanning.value) {
    const dx = e.clientX - _panStartX
    const dy = e.clientY - _panStartY
    panX.value = _panStartPanX + dx
    panY.value = _panStartPanY + dy
    return
  }

  if (!props.editable || !isPainting.value) return
  e.preventDefault()
  const [x, y] = clientToCanvas(e.clientX, e.clientY)

  if (tool.value === 'eraser') {
    if (skinCanvasRef.value) paintAt(skinCanvasRef.value, x, y, lastPos[0], lastPos[1], SKIN_COLOR, true)
    if (lesionCanvasRef.value) paintAt(lesionCanvasRef.value, x, y, lastPos[0], lastPos[1], LESION_COLOR, true)
  } else {
    const target = activeCanvas()
    const color = tool.value === 'lesion-brush' ? LESION_COLOR : SKIN_COLOR
    if (target) paintAt(target, x, y, lastPos[0], lastPos[1], color, false)
    if (tool.value === 'skin-brush' && lesionCanvasRef.value) {
      paintAt(lesionCanvasRef.value, x, y, lastPos[0], lastPos[1], LESION_COLOR, true)
    } else if (tool.value === 'lesion-brush' && skinCanvasRef.value) {
      paintAt(skinCanvasRef.value, x, y, lastPos[0], lastPos[1], SKIN_COLOR, true)
    }
  }
  lastPos = [x, y]
  drawOverlay()
}

function onPointerUp() {
  if (isPainting.value) {
    isPainting.value = false
    snapshot()
    updateAreas()
  }
  if (isPanning.value) {
    isPanning.value = false
    clampPan()
  }
}

function drawOverlay() {
  const overlay = overlayCanvasRef.value
  const skin = skinCanvasRef.value
  const lesion = lesionCanvasRef.value
  if (!overlay || !skin || !lesion) return
  const ctx = getCtx(overlay)
  if (!ctx) return
  ctx.clearRect(0, 0, overlay.width, overlay.height)
  ctx.globalAlpha = layerOpacity.value
  ctx.drawImage(skin, 0, 0)
  ctx.drawImage(lesion, 0, 0)
  ctx.globalAlpha = 1
  renderContourOutlines(ctx)
}

// ── Animated contour outlines ──
const dashOffset = ref(0)
const edgePixelsSkin = ref<[number, number][]>([])
const edgePixelsLesion = ref<[number, number][]>([])
let _animFrameId = 0

function extractEdgePixels(maskCanvas: HTMLCanvasElement, step: number): [number, number][] {
  const maskCtx = maskCanvas.getContext('2d', { willReadFrequently: true })
  if (!maskCtx) return []
  const w = maskCanvas.width, h = maskCanvas.height
  const imgData = maskCtx.getImageData(0, 0, w, h)
  const data = imgData.data
  const pixels: [number, number][] = []

  for (let y = step; y < h - step; y += step) {
    for (let x = step; x < w - step; x += step) {
      const idx = (y * w + x) * 4 + 3
      if (data[idx] <= 32) continue
      const top = data[((y - step) * w + x) * 4 + 3]
      const bottom = data[((y + step) * w + x) * 4 + 3]
      const left = data[(y * w + (x - step)) * 4 + 3]
      const right = data[(y * w + (x + step)) * 4 + 3]
      if (top > 32 && bottom > 32 && left > 32 && right > 32) continue
      pixels.push([x, y])
    }
  }
  return pixels
}

function rebuildEdgeCaches() {
  const skin = skinCanvasRef.value
  const lesion = lesionCanvasRef.value
  if (!skin || !lesion) return
  const maxDim = Math.max(skin.width, skin.height)
  const step = Math.max(1, Math.floor(maxDim / 400))
  edgePixelsSkin.value = extractEdgePixels(skin, step)
  edgePixelsLesion.value = extractEdgePixels(lesion, step)
}

function renderContourOutlines(ctx: CanvasRenderingContext2D) {
  const offset = dashOffset.value
  const step = Math.max(1, Math.floor(Math.max(
    skinCanvasRef.value?.width || 1,
    skinCanvasRef.value?.height || 1,
  ) / 400))
  const dashLen = Math.max(3, Math.floor(10 / step))
  const dotSize = Math.max(step * 1.6, 2.5)

  ctx.fillStyle = '#f472b6'
  for (const [x, y] of edgePixelsLesion.value) {
    const phase = Math.floor((x + y + offset * 3) / (step * dashLen)) % 2
    if (phase === 0) ctx.fillRect(x - dotSize / 2, y - dotSize / 2, dotSize, dotSize)
  }
}

function startAnimation() {
  function tick() {
    dashOffset.value = (dashOffset.value + 1) % 60
    const overlay = overlayCanvasRef.value
    if (!overlay) return
    const ctx = getCtx(overlay)
    if (!ctx) return
    ctx.clearRect(0, 0, overlay.width, overlay.height)
    ctx.globalAlpha = layerOpacity.value
    if (skinCanvasRef.value) ctx.drawImage(skinCanvasRef.value, 0, 0)
    if (lesionCanvasRef.value) ctx.drawImage(lesionCanvasRef.value, 0, 0)
    ctx.globalAlpha = 1
    renderContourOutlines(ctx)
    _animFrameId = requestAnimationFrame(tick)
  }
  _animFrameId = requestAnimationFrame(tick)
}

function stopAnimation() {
  if (_animFrameId) {
    cancelAnimationFrame(_animFrameId)
    _animFrameId = 0
  }
}

function countAlpha(canvas: HTMLCanvasElement): number {
  const ctx = getCtx(canvas)
  if (!ctx) return 0
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
  let count = 0
  for (let i = 3; i < data.length; i += 4) {
    if (data[i] > 32) count++
  }
  return count
}

function countUnionAlpha(skinCanvas: HTMLCanvasElement, lesionCanvas: HTMLCanvasElement): number {
  const skinCtx = getCtx(skinCanvas)
  const lesionCtx = getCtx(lesionCanvas)
  if (!skinCtx || !lesionCtx) return 0
  const skinData = skinCtx.getImageData(0, 0, skinCanvas.width, skinCanvas.height).data
  const lesionData = lesionCtx.getImageData(0, 0, lesionCanvas.width, lesionCanvas.height).data
  let count = 0
  for (let i = 3; i < skinData.length; i += 4) {
    if (skinData[i] > 32 || lesionData[i] > 32) count++
  }
  return count
}

function updateAreas() {
  if (!skinCanvasRef.value || !lesionCanvasRef.value) return
  const total = skinCanvasRef.value.width * skinCanvasRef.value.height
  if (total === 0) return
  skinAreaPct.value = (countAlpha(skinCanvasRef.value) / total) * 100
  lesionAreaPct.value = (countAlpha(lesionCanvasRef.value) / total) * 100
  regionAreaPct.value = (countUnionAlpha(skinCanvasRef.value, lesionCanvasRef.value) / total) * 100
}

function snapshot() {
  if (!skinCanvasRef.value || !lesionCanvasRef.value) return
  const w = skinCanvasRef.value.width, h = skinCanvasRef.value.height
  if (w === 0 || h === 0) return
  const skinCtx = getCtx(skinCanvasRef.value)
  const lesionCtx = getCtx(lesionCanvasRef.value)
  if (!skinCtx || !lesionCtx) return
  const skin = skinCtx.getImageData(0, 0, w, h)
  const lesion = lesionCtx.getImageData(0, 0, w, h)
  history.value = history.value.slice(0, historyIndex.value + 1)
  history.value.push({ skin, lesion })
  if (history.value.length > HISTORY_MAX) history.value.shift()
  else historyIndex.value++
  rebuildEdgeCaches()
}

function applySnapshot(idx: number) {
  const snap = history.value[idx]
  if (!snap || !skinCanvasRef.value || !lesionCanvasRef.value) return
  getCtx(skinCanvasRef.value)?.putImageData(snap.skin, 0, 0)
  getCtx(lesionCanvasRef.value)?.putImageData(snap.lesion, 0, 0)
  drawOverlay()
  updateAreas()
  rebuildEdgeCaches()
}

function undo() { if (canUndo.value) { historyIndex.value--; applySnapshot(historyIndex.value) } }
function redo() { if (canRedo.value) { historyIndex.value++; applySnapshot(historyIndex.value) } }

function clearLayer(layer: 'skin' | 'lesion' | 'all') {
  const targets: HTMLCanvasElement[] = []
  if (layer === 'skin' || layer === 'all') targets.push(skinCanvasRef.value!)
  if (layer === 'lesion' || layer === 'all') targets.push(lesionCanvasRef.value!)
  for (const c of targets) {
    if (!c) continue
    getCtx(c)?.clearRect(0, 0, c.width, c.height)
  }
  drawOverlay()
  snapshot()
  updateAreas()
  rebuildEdgeCaches()
}

function loadLayerFromDataUrl(canvas: HTMLCanvasElement, url: string) {
  return new Promise<void>((resolve) => {
    const img = new Image()
    img.onload = () => {
      const ctx = getCtx(canvas)
      if (!ctx) return resolve()
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      resolve()
    }
    img.onerror = () => resolve()
    img.src = url
  })
}

async function onImgLoad() {
  if (imageLoading.value || imageLoaded.value) return
  imageLoading.value = true

  const img = imgRef.value
  const skin = skinCanvasRef.value
  const lesion = lesionCanvasRef.value
  const overlay = overlayCanvasRef.value
  if (!img || !skin || !lesion || !overlay) {
    imageLoading.value = false
    return
  }

  const w = img.naturalWidth, h = img.naturalHeight
  if (w === 0 || h === 0) {
    imageLoading.value = false
    onImgError()
    return
  }

  try {
    for (const c of [skin, lesion, overlay]) {
      c.width = w
      c.height = h
    }
    await nextTick()

    for (const c of [skin, lesion]) {
      const ctx = getCtx(c)
      if (ctx) ctx.clearRect(0, 0, w, h)
    }

    const loadJobs: Promise<void>[] = []
    if (props.initialSkinLayerUrl) loadJobs.push(loadLayerFromDataUrl(skin, props.initialSkinLayerUrl))
    if (props.initialLesionLayerUrl) loadJobs.push(loadLayerFromDataUrl(lesion, props.initialLesionLayerUrl))
    await Promise.all(loadJobs)

    history.value = []
    historyIndex.value = -1
    snapshot()
    drawOverlay()
    updateAreas()
    rebuildEdgeCaches()
    stopAnimation()
    startAnimation()
    imageLoaded.value = true
    imageError.value = false
    imageErrorMsg.value = ''
    canvasWidth.value = w
    canvasHeight.value = h
    // Reset zoom to fit and center
    zoomToFit()
  } catch (e) {
    console.error('MaskEditor onImgLoad failed:', e)
    onImgError()
  } finally {
    imageLoading.value = false
  }
}

function onImgError() {
  imageError.value = true
  imageLoaded.value = false
  imageLoading.value = false
  imageErrorMsg.value = '图片加载失败，请检查网络连接或图片是否已删除'
}

// ── Zoom controls ──
function zoomIn() {
  zoom.value = Math.min(maxZoom, +(zoom.value + zoomStep).toFixed(2))
  clampPan()
}

function zoomOut() {
  zoom.value = Math.max(minZoom, +(zoom.value - zoomStep).toFixed(2))
  clampPan()
}

function zoomToFit() {
  const container = imgContainerRef.value
  const img = imgRef.value
  if (!container || !img) { zoom.value = 1; resetPan(); return }
  const cw = container.clientWidth, ch = container.clientHeight
  const iw = img.naturalWidth, ih = img.naturalHeight
  if (iw === 0 || ih === 0) { zoom.value = 1; resetPan(); return }
  // Fit image inside container with small padding
  const pad = 16
  const scaleX = (cw - pad * 2) / iw
  const scaleY = (ch - pad * 2) / ih
  zoom.value = Math.max(minZoom, Math.min(1, Math.min(scaleX, scaleY)))
  resetPan()
}

function onWheel(e: WheelEvent) {
  // Only zoom when not painting
  if (isPainting.value) return
  e.preventDefault()
  const rect = imgContainerRef.value?.getBoundingClientRect()
  if (!rect) return

  // Zoom toward cursor position
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top
  const oldZoom = zoom.value
  const delta = e.deltaY > 0 ? -zoomStep : zoomStep
  const newZoom = Math.max(minZoom, Math.min(maxZoom, +(oldZoom + delta).toFixed(2)))

  // Adjust pan to zoom toward cursor
  const scale = newZoom / oldZoom
  panX.value = mouseX - scale * (mouseX - panX.value)
  panY.value = mouseY - scale * (mouseY - panY.value)

  zoom.value = newZoom
  clampPan()
}

const isFullscreen = ref(false)

function toggleFullscreen() {
  const el = imgContainerRef.value
  if (!el) return
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    el.requestFullscreen().catch(() => {
      // Fullscreen denied — silently ignore
    })
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  // Re-fit after entering/exiting fullscreen
  nextTick(() => {
    if (imageLoaded.value) zoomToFit()
  })
}

const zoomPercent = computed(() => Math.round(zoom.value * 100))

const resizeObserver = new ResizeObserver(() => {
  drawOverlay()
  clampPan()
})

onMounted(() => {
  if (containerRef.value) resizeObserver.observe(containerRef.value)
  if (imgRef.value?.complete && imgRef.value.naturalWidth > 0) {
    onImgLoad()
  } else if (imgRef.value?.complete && imgRef.value.naturalWidth === 0) {
    onImgError()
  }
  // Prevent context menu on the image container for right-click pan
  imgContainerRef.value?.addEventListener('contextmenu', (e) => e.preventDefault())
  // Track fullscreen changes
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  stopAnimation()
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange)
})

watch(() => props.imageUrl, () => {
  history.value = []
  historyIndex.value = -1
  imageLoaded.value = false
  imageError.value = false
  imageErrorMsg.value = ''
  imageLoading.value = false
  canvasWidth.value = 0
  canvasHeight.value = 0
  zoom.value = 1
  resetPan()
})

function canvasToDataUrl(canvas: HTMLCanvasElement | null): string {
  if (!canvas) return ''
  try { return canvas.toDataURL('image/png') } catch { return '' }
}

function confirm() {
  emit('confirm', {
    skinMaskDataUrl: canvasToDataUrl(skinCanvasRef.value),
    lesionMaskDataUrl: canvasToDataUrl(lesionCanvasRef.value),
  })
}

const toolHint = computed(() => {
  if (tool.value === 'skin-brush') return '涂抹整个待测评的皮肤区域（如整张脸）'
  if (tool.value === 'lesion-brush') return '在皮肤上涂出白斑区域'
  return '擦除两种涂层'
})
</script>

<template>
  <div ref="containerRef" class="w-full select-none" :class="{ 'h-full flex flex-col': fullHeight }">
    <!-- Toolbar -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <div class="flex items-center gap-1 p-1 rounded-xl bg-gray-100">
        <button
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
          :class="tool === 'skin-brush' ? 'bg-blue-500 text-white shadow-sm' : 'text-blue-600 dark:text-blue-300 hover:bg-white/60 dark:hover:bg-gray-300/60'"
          :disabled="!editable || !imageLoaded"
          @click="tool = 'skin-brush'"
        ><span class="inline-block w-3 h-3 rounded-full bg-blue-400 mr-0.5"></span>皮肤画笔</button>
        <button
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
          :class="tool === 'lesion-brush' ? 'bg-pink-500 text-white shadow-sm' : 'text-pink-600 dark:text-pink-300 hover:bg-white/60 dark:hover:bg-gray-300/60'"
          :disabled="!editable || !imageLoaded"
          @click="tool = 'lesion-brush'"
        ><span class="inline-block w-3 h-3 rounded-full bg-pink-400 mr-0.5"></span>白斑画笔</button>
        <button
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1"
          :class="tool === 'eraser' ? 'bg-white text-gray-700 shadow-sm' : 'text-gray-600  hover:bg-white/60 dark:hover:bg-gray-300/60'"
          :disabled="!editable || !imageLoaded"
          @click="tool = 'eraser'"
        ><i class="ri-eraser-line"></i>橡皮擦</button>
      </div>

      <div class="flex items-center gap-1.5 text-xs text-gray-500  px-2">
        <i class="ri-ruler-line"></i>
        <input type="range" min="8" max="80" step="2" v-model.number="brushSize" class="w-20 md:w-28 accent-primary-500" :disabled="!editable || !imageLoaded" />
        <span class="w-6 text-right">{{ brushSize }}</span>
      </div>

      <div class="flex items-center gap-1.5 text-xs text-gray-500  px-2">
        <i class="ri-contrast-2-line"></i>
        <input type="range" min="0.2" max="0.95" step="0.05" v-model.number="layerOpacity" class="w-20 md:w-28 accent-primary-500" @input="drawOverlay" />
      </div>

      <div class="ml-auto flex items-center gap-1">
        <button class="p-1.5 rounded-lg text-gray-500  hover:bg-gray-100 dark:hover:bg-gray-300 disabled:opacity-30" :disabled="!canUndo || !editable" title="撤销" @click="undo"><i class="ri-arrow-go-back-line"></i></button>
        <button class="p-1.5 rounded-lg text-gray-500  hover:bg-gray-100 dark:hover:bg-gray-300 disabled:opacity-30" :disabled="!canRedo || !editable" title="重做" @click="redo"><i class="ri-arrow-go-forward-line"></i></button>
        <button class="p-1.5 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20" :disabled="!editable || !imageLoaded" title="清空全部" @click="clearLayer('all')"><i class="ri-delete-bin-line"></i></button>
      </div>
    </div>

    <!-- Image + Canvas viewport -->
    <div
      ref="imgContainerRef"
      class="mask-editor-viewport relative rounded-2xl bg-gray-300"
      :class="{ 'flex-1': fullHeight }"
      :style="{ minHeight: isFullscreen || fullHeight ? '0' : '280px', maxHeight: isFullscreen || fullHeight ? 'none' : '65vh', touchAction: 'none' }"
      @wheel="onWheel"
    >
      <!-- Loading state -->
      <div v-if="!imageLoaded && !imageError" class="absolute inset-0 flex items-center justify-center z-20 bg-gray-200">
        <div class="text-center text-gray-400">
          <i class="ri-loader-4-line ri-lg animate-spin block mb-2"></i>
          <p class="text-xs">加载图片中...</p>
        </div>
      </div>

      <!-- Error state -->
      <div v-if="imageError" class="absolute inset-0 flex items-center justify-center z-20 bg-gray-200">
        <div class="text-center text-gray-400 p-4">
          <i class="ri-image-2-line text-4xl mb-2 block"></i>
          <p class="text-sm font-medium">图片加载失败</p>
          <p class="text-xs mt-1 max-w-xs mx-auto">{{ imageErrorMsg || '请检查网络连接或图片是否已删除' }}</p>
        </div>
      </div>

      <!-- Image + canvas wrapper with zoom + pan transform -->
      <div
        :style="{
          transform: `translate(${panX}px, ${panY}px) scale(${zoom})`,
          transformOrigin: 'center center',
          willChange: isPanning || isPainting ? 'transform' : 'auto',
        }"
        class="absolute top-1/2 left-1/2"
      >
        <div class="relative inline-block" style="transform: translate(-50%, -50%)">
          <img
            ref="imgRef"
            :src="imageUrl"
            alt="评估照片"
            class="block max-w-none select-none pointer-events-none"
            draggable="false"
            @load="onImgLoad"
            @error="onImgError"
          />
          <canvas ref="skinCanvasRef" class="hidden" />
          <canvas ref="lesionCanvasRef" class="hidden" />
          <canvas
            ref="overlayCanvasRef"
            class="absolute top-0 left-0"
            :style="{ width: canvasWidth + 'px', height: canvasHeight + 'px', zIndex: 10 }"
            :class="imageLoaded && editable && !isPanning ? 'cursor-crosshair' : 'cursor-grab'"
            :data-pannable="'true'"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="onPointerUp"
            @pointerleave="onPointerUp"
          />
        </div>
      </div>

      <!-- Zoom controls overlay -->
      <div v-if="imageLoaded" class="absolute bottom-3 left-3 flex items-center gap-1 z-30">
        <button class="w-8 h-8 rounded-lg bg-white/80  backdrop-blur flex items-center justify-center text-gray-600 hover:bg-white dark:hover:bg-gray-300 shadow text-sm" title="放大" @click="zoomIn">
          <i class="ri-zoom-in-line"></i>
        </button>
        <button class="w-8 h-8 rounded-lg bg-white/80  backdrop-blur flex items-center justify-center text-gray-600 hover:bg-white dark:hover:bg-gray-300 shadow text-sm" title="缩小" @click="zoomOut">
          <i class="ri-zoom-out-line"></i>
        </button>
        <span class="text-xs text-gray-500  bg-white/80  backdrop-blur px-2 py-1 rounded-lg shadow tabular-nums">{{ zoomPercent }}%</span>
        <button class="w-8 h-8 rounded-lg bg-white/80  backdrop-blur flex items-center justify-center text-gray-600 hover:bg-white dark:hover:bg-gray-300 shadow text-sm" title="适应窗口" @click="zoomToFit">
          <i class="ri-aspect-ratio-line"></i>
        </button>
        <button class="w-8 h-8 rounded-lg bg-white/80  backdrop-blur flex items-center justify-center text-gray-600 hover:bg-white dark:hover:bg-gray-300 shadow text-sm" title="全屏" @click="toggleFullscreen">
          <i :class="isFullscreen ? 'ri-fullscreen-exit-line' : 'ri-fullscreen-line'"></i>
        </button>
      </div>

      <!-- Fullscreen hint -->
      <div v-if="imageLoaded" class="absolute top-3 right-3 z-30">
        <span class="text-[10px] text-gray-400  bg-white/60  backdrop-blur px-2 py-0.5 rounded-full">
          滚轮缩放 · 右键拖拽移动
        </span>
      </div>
    </div>

    <div class="mt-3 grid grid-cols-3 gap-2 text-center">
      <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-2">
        <div class="text-xs text-blue-600 dark:text-blue-400">评估区域</div>
        <div class="text-base font-semibold text-blue-700 dark:text-blue-300">{{ regionAreaPct.toFixed(1) }}%</div>
      </div>
      <div class="bg-pink-50 dark:bg-pink-900/20 rounded-lg p-2">
        <div class="text-xs text-pink-600 dark:text-pink-400">白斑</div>
        <div class="text-base font-semibold text-pink-700 dark:text-pink-300">{{ lesionAreaPct.toFixed(1) }}%</div>
      </div>
      <div class="bg-primary-50 dark:bg-primary-900/20 rounded-lg p-2">
        <div class="text-xs text-primary-600 dark:text-primary-400">白斑占比</div>
        <div class="text-base font-semibold text-primary-700 dark:text-primary-300">{{ areaPercent.toFixed(1) }}%</div>
      </div>
    </div>

    <div class="mt-2 text-xs text-gray-500  text-center">
      <i class="ri-information-line"></i> {{ toolHint }}
    </div>

    <div v-if="editable" class="mt-4 flex items-center justify-end gap-2">
      <button class="text-xs px-3 py-1.5 rounded-lg text-gray-500  hover:text-gray-700 dark:hover:text-gray-200" @click="emit('cancel')">取消</button>
      <button class="btn-primary text-xs px-4 py-1.5" :disabled="!imageLoaded" @click="confirm"><i class="ri-check-line mr-1"></i>确认提交</button>
    </div>
  </div>
</template>

<style scoped>
input[type='range'] {
  height: 4px;
}

.mask-editor-viewport {
  overflow: hidden;
  position: relative;
}

/* Fullscreen support */
.mask-editor-viewport:fullscreen {
  max-height: none !important;
  min-height: 100vh !important;
  border-radius: 0;
  background: #1a1a1a;
}

.mask-editor-viewport:-webkit-full-screen {
  max-height: none !important;
  min-height: 100vh !important;
  border-radius: 0;
  background: #1a1a1a;
}
</style>
