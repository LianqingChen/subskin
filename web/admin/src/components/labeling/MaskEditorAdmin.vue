<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick, reactive } from 'vue'
import { useCanvasTools } from '@/composables/useCanvasTools'
import { useLabelHistory } from '@/composables/useLabelHistory'
import { ALL_TOOLS, type ToolName, type ToolContext } from '@/components/labeling/tools/BaseTool'
import { FloodFillTool } from '@/components/labeling/tools/FloodFillTool'

const props = defineProps<{
  imageUrl: string
  editable?: boolean
  initialSkinLayerUrl?: string | null
  initialLesionLayerUrl?: string | null
}>()

const emit = defineEmits<{
  confirm: [payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string }]
  cancel: []
}>()

// ── Tool system ──
const { activeToolName, activeTool, availableTools, setTool, setContext, handleToolShortcut, getFloodFillTool } = useCanvasTools()

const brushSize = ref(32)
const layerOpacity = ref(0.55)

// ── Flood fill tolerance (only relevant when flood-fill tool active) ──
const fillTolerance = computed({
  get: () => {
    const tool = getFloodFillTool()
    return tool?.tolerance ?? 24
  },
  set: (val: number) => {
    const tool = getFloodFillTool()
    if (tool) tool.tolerance = val
  },
})
const showFillTolerance = computed(() => activeToolName.value === 'flood-fill')

// ── Refs ──
const wrapperRef = ref<HTMLDivElement | null>(null)
const canvasAreaRef = ref<HTMLDivElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)
const skinCanvasRef = ref<HTMLCanvasElement | null>(null)
const lesionCanvasRef = ref<HTMLCanvasElement | null>(null)
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
const imageLoaded = ref(false)
const imageError = ref(false)
const imageLoading = ref(false)
const imgKey = ref(0)
const naturalSize = ref({ width: 0, height: 0 })

const isPainting = ref(false)
const skinAreaPct = ref(0)
const lesionAreaPct = ref(0)
const regionAreaPct = ref(0)

// ── Undo/Redo ──
const { canUndo, canRedo, snapshot: historySnapshot, undo, redo, reset: resetHistory } = useLabelHistory()

// ── Pan & Zoom ──
const transform = reactive({ scale: 1, offsetX: 0, offsetY: 0 })
const MIN_SCALE = 0.1
const MAX_SCALE = 10
const baseFitScale = ref(1)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, offsetX: 0, offsetY: 0 })
let spaceHeld = false

// ── Fullscreen ──
const isFullscreen = ref(false)
const isFullscreenFallback = computed(() => isFullscreen.value && !document.fullscreenElement)

async function toggleFullscreen() {
  if (isFullscreen.value) {
    try { if (document.fullscreenElement) await document.exitFullscreen() } catch { /* ignore */ }
    isFullscreen.value = false
  } else {
    try {
      if (wrapperRef.value) { await wrapperRef.value.requestFullscreen(); isFullscreen.value = true }
    } catch { isFullscreen.value = true }
  }
  nextTick(() => { fitToContainer(); drawOverlay() })
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  nextTick(() => { fitToContainer(); drawOverlay() })
}

// ── Coordinate conversion ──
function clientToImage(clientX: number, clientY: number): [number, number] | null {
  const img = imgRef.value
  if (!img || naturalSize.value.width === 0) return null
  const rect = img.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) return null
  const relX = clientX - rect.left
  const relY = clientY - rect.top
  const totalScale = baseFitScale.value * transform.scale
  if (totalScale <= 0) return null
  const natX = relX / totalScale
  const natY = relY / totalScale
  if (natX < 0 || natY < 0 || natX > naturalSize.value.width || natY > naturalSize.value.height) return null
  return [natX, natY]
}

function getCtx(canvas: HTMLCanvasElement | null) {
  return canvas?.getContext('2d', { willReadFrequently: true }) || null
}

// ── Overlay rendering ──
function drawOverlay() {
  const overlay = overlayCanvasRef.value
  const skin = skinCanvasRef.value
  const lesion = lesionCanvasRef.value
  if (!overlay || !skin || !lesion) return
  const ctx = getCtx(overlay)
  if (!ctx) return
  ctx.clearRect(0, 0, overlay.width, overlay.height)
  ctx.drawImage(skin, 0, 0)
  ctx.globalAlpha = layerOpacity.value
  ctx.drawImage(lesion, 0, 0)
  ctx.globalAlpha = 1
}

// ── Area calculation ──
function countAlpha(canvas: HTMLCanvasElement): number {
  const ctx = getCtx(canvas)
  if (!ctx) return 0
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
  let count = 0
  for (let i = 3; i < data.length; i += 4) { if (data[i] > 32) count++ }
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

// ── Snapshot (bridge to useLabelHistory) ──
function snapshot() {
  if (skinCanvasRef.value && lesionCanvasRef.value) {
    historySnapshot(skinCanvasRef.value, lesionCanvasRef.value)
  }
}

// ── Build tool context ──
function buildToolContext(): ToolContext | null {
  if (!skinCanvasRef.value || !lesionCanvasRef.value || !overlayCanvasRef.value) return null
  return {
    skinCanvas: skinCanvasRef.value,
    lesionCanvas: lesionCanvasRef.value,
    overlayCanvas: overlayCanvasRef.value,
    naturalSize: naturalSize.value,
    brushSize: brushSize.value,
    transform,
    clientToImage,
    drawOverlay,
    snapshot,
    updateAreas,
  }
}

// ── Pointer event handlers (delegate to active tool) ──
function onCanvasPointerDown(e: PointerEvent) {
  if (!props.editable || spaceHeld || isPanning.value) return
  e.preventDefault(); (e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  const pos = clientToImage(e.clientX, e.clientY)
  if (!pos) return

  // Shift+Click for flood fill → fill as skin
  if (activeToolName.value === 'flood-fill' && e.shiftKey) {
    const tool = getFloodFillTool()
    if (tool) {
      const ctx = buildToolContext()
      if (ctx) {
        tool.cacheImageData(ctx)
        tool.fillSkin(Math.round(pos[0]), Math.round(pos[1]), ctx)
        return
      }
    }
  }

  isPainting.value = true
  const ctx = buildToolContext()
  if (ctx) activeTool.value.onPointerDown(pos, ctx)
}

function onCanvasPointerMove(e: PointerEvent) {
  if (!props.editable || !isPainting.value) return
  e.preventDefault()
  const pos = clientToImage(e.clientX, e.clientY)
  if (!pos) return
  const ctx = buildToolContext()
  if (ctx) activeTool.value.onPointerMove(pos, ctx)
}

function onCanvasPointerUp() {
  if (!isPainting.value) return
  const ctx = buildToolContext()
  if (ctx) activeTool.value.onPointerUp(ctx)
  isPainting.value = false
}

// ── Pan interaction ──
function onContainerPointerDown(e: PointerEvent) {
  if (!spaceHeld) return
  isPanning.value = true
  panStart.value = { x: e.clientX, y: e.clientY, offsetX: transform.offsetX, offsetY: transform.offsetY }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onContainerPointerMove(e: PointerEvent) {
  if (!isPanning.value) return
  transform.offsetX = panStart.value.offsetX + (e.clientX - panStart.value.x)
  transform.offsetY = panStart.value.offsetY + (e.clientY - panStart.value.y)
}

function onContainerPointerUp(e: PointerEvent) {
  if (!isPanning.value) return
  isPanning.value = false
  ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  if (!canvasAreaRef.value) return
  const rect = canvasAreaRef.value.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top
  const delta = e.deltaY < 0 ? 1.15 : 1 / 1.15
  const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, transform.scale * delta))
  if (newScale === transform.scale) return
  const imageX = (cx - transform.offsetX) / transform.scale
  const imageY = (cy - transform.offsetY) / transform.scale
  transform.offsetX = cx - imageX * newScale
  transform.offsetY = cy - imageY * newScale
  transform.scale = newScale
}

function zoomIn() {
  if (!canvasAreaRef.value) return
  const cw = canvasAreaRef.value.clientWidth / 2; const ch = canvasAreaRef.value.clientHeight / 2
  const newScale = Math.min(MAX_SCALE, transform.scale * 1.3)
  const imageX = (cw - transform.offsetX) / transform.scale; const imageY = (ch - transform.offsetY) / transform.scale
  transform.offsetX = cw - imageX * newScale; transform.offsetY = ch - imageY * newScale
  transform.scale = newScale
}

function zoomOut() {
  if (!canvasAreaRef.value) return
  const cw = canvasAreaRef.value.clientWidth / 2; const ch = canvasAreaRef.value.clientHeight / 2
  const newScale = Math.max(MIN_SCALE, transform.scale / 1.3)
  const imageX = (cw - transform.offsetX) / transform.scale; const imageY = (ch - transform.offsetY) / transform.scale
  transform.offsetX = cw - imageX * newScale; transform.offsetY = ch - imageY * newScale
  transform.scale = newScale
}

function fitToContainer() {
  if (!canvasAreaRef.value || !imgRef.value) return
  const cw = canvasAreaRef.value.clientWidth; const ch = canvasAreaRef.value.clientHeight
  const iw = imgRef.value.naturalWidth; const ih = imgRef.value.naturalHeight
  if (cw === 0 || ch === 0 || iw === 0 || ih === 0) return
  const scale = Math.min(cw / iw, ch / ih) * 0.92
  baseFitScale.value = scale
  transform.scale = 1
  transform.offsetX = (cw - iw * scale) / 2; transform.offsetY = (ch - ih * scale) / 2
}

function zoomActualSize() {
  transform.scale = 1
  if (!canvasAreaRef.value || !imgRef.value) return
  const cw = canvasAreaRef.value.clientWidth; const ch = canvasAreaRef.value.clientHeight
  const iw = imgRef.value.naturalWidth; const ih = imgRef.value.naturalHeight
  transform.offsetX = (cw - iw * baseFitScale.value) / 2; transform.offsetY = (ch - ih * baseFitScale.value) / 2
}

// ── History actions ──
function undoAction() {
  if (!canUndo.value || !skinCanvasRef.value || !lesionCanvasRef.value) return
  undo(skinCanvasRef.value, lesionCanvasRef.value, () => { drawOverlay(); updateAreas() })
}

function redoAction() {
  if (!canRedo.value || !skinCanvasRef.value || !lesionCanvasRef.value) return
  redo(skinCanvasRef.value, lesionCanvasRef.value, () => { drawOverlay(); updateAreas() })
}

// ── Clear layers ──
function clearLayer(layer: 'skin' | 'lesion' | 'all') {
  const targets: HTMLCanvasElement[] = []
  if (layer === 'skin' || layer === 'all') targets.push(skinCanvasRef.value!)
  if (layer === 'lesion' || layer === 'all') targets.push(lesionCanvasRef.value!)
  for (const c of targets) { if (!c) continue; getCtx(c)?.clearRect(0, 0, c.width, c.height) }
  drawOverlay(); snapshot(); updateAreas()
}

// ── Layer loading ──
function loadLayerFromDataUrl(canvas: HTMLCanvasElement, url: string) {
  return new Promise<void>((resolve) => {
    const img = new Image()
    img.onload = () => { const ctx = getCtx(canvas); if (ctx) { ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.drawImage(img, 0, 0, canvas.width, canvas.height) } resolve() }
    img.onerror = () => resolve()
    img.src = url
  })
}

// ── Image load ──
async function onImgLoad() {
  if (imageLoading.value || imageLoaded.value) return
  imageLoading.value = true
  const img = imgRef.value; const skin = skinCanvasRef.value; const lesion = lesionCanvasRef.value; const overlay = overlayCanvasRef.value
  if (!img || !skin || !lesion || !overlay) { imageLoading.value = false; return }
  const w = img.naturalWidth, h = img.naturalHeight
  if (w === 0 || h === 0) { imageLoading.value = false; onImgError(); return }
  try {
    naturalSize.value = { width: w, height: h }
    for (const c of [skin, lesion, overlay]) { c.width = w; c.height = h }
    await nextTick()
    for (const c of [skin, lesion]) { getCtx(c)?.clearRect(0, 0, w, h) }
    const loadJobs: Promise<void>[] = []
    if (props.initialSkinLayerUrl) loadJobs.push(loadLayerFromDataUrl(skin, props.initialSkinLayerUrl))
    if (props.initialLesionLayerUrl) loadJobs.push(loadLayerFromDataUrl(lesion, props.initialLesionLayerUrl))
    await Promise.all(loadJobs)
    resetHistory()
    snapshot(); drawOverlay(); updateAreas()
    imageLoaded.value = true; imageError.value = false
    fitToContainer()

    // Wire up tool context once canvases are ready
    const ctx = buildToolContext()
    if (ctx) setContext(ctx)
  } catch (e) { console.error('MaskEditorAdmin onImgLoad failed:', e); onImgError() }
  finally { imageLoading.value = false }
}

function onImgError() { imageError.value = true; imageLoaded.value = false }

function retryLoad() { imageError.value = false; imageLoaded.value = false; imgKey.value++ }

// ── Keyboard (global) ──
function onKeyDown(e: KeyboardEvent) {
  const target = e.target as HTMLElement
  if (target?.closest('input,textarea,[contenteditable]')) return

  // Tool shortcuts (handled by useCanvasTools)
  if (handleToolShortcut(e.key, e.shiftKey)) { e.preventDefault(); return }

  // Tool-specific keys (delegated)
  if (e.key !== ' ' && e.key !== 'F' && e.key !== 'f' && e.key !== 'R' && e.key !== 'r') {
    const ctx = buildToolContext()
    if (ctx) activeTool.value.onKeyDown(e.key, ctx)
  }

  if (e.code === 'Space' && !e.repeat) { e.preventDefault(); spaceHeld = true }
  else if ((e.key === 'f' || e.key === 'F') && !e.ctrlKey && !e.metaKey) { toggleFullscreen() }
  else if ((e.key === 'r' || e.key === 'R') && !e.ctrlKey && !e.metaKey) { fitToContainer() }
  else if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) { e.preventDefault(); undoAction() }
  else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) { e.preventDefault(); redoAction() }
}

function onKeyUp(e: KeyboardEvent) { if (e.code === 'Space') spaceHeld = false }

// ── ResizeObserver ──
const resizeObserver = new ResizeObserver(() => { if (imageLoaded.value) { fitToContainer(); drawOverlay() } })

onMounted(() => {
  if (canvasAreaRef.value) resizeObserver.observe(canvasAreaRef.value)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  if (imgRef.value?.complete && imgRef.value.naturalWidth > 0) onImgLoad()
  else if (imgRef.value?.complete && imgRef.value.naturalWidth === 0) onImgError()
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (document.fullscreenElement) { try { document.exitFullscreen() } catch { /* ignore */ } }
})

watch(() => props.imageUrl, () => {
  imageLoaded.value = false; imageError.value = false
  resetHistory()
  transform.scale = 1; transform.offsetX = 0; transform.offsetY = 0
})

watch(() => props.initialSkinLayerUrl, async (newUrl) => {
  if (!newUrl || !imageLoaded.value || !skinCanvasRef.value) return
  await loadLayerFromDataUrl(skinCanvasRef.value, newUrl)
  drawOverlay(); updateAreas(); snapshot()
})

watch(() => props.initialLesionLayerUrl, async (newUrl) => {
  if (!newUrl || !imageLoaded.value || !lesionCanvasRef.value) return
  await loadLayerFromDataUrl(lesionCanvasRef.value, newUrl)
  drawOverlay(); updateAreas(); snapshot()
})

async function loadMaskLayers(skinDataUrl: string | null, lesionDataUrl: string | null) {
  if (!imageLoaded.value) {
    let waited = 0
    while (!imageLoaded.value && waited < 100) { await new Promise(r => setTimeout(r, 100)); waited++ }
    if (!imageLoaded.value) { console.warn('[MaskEditorAdmin] loadMaskLayers: image never loaded'); return }
  }
  const jobs: Promise<void>[] = []
  if (skinDataUrl && skinCanvasRef.value) jobs.push(loadLayerFromDataUrl(skinCanvasRef.value, skinDataUrl))
  if (lesionDataUrl && lesionCanvasRef.value) jobs.push(loadLayerFromDataUrl(lesionCanvasRef.value, lesionDataUrl))
  if (jobs.length > 0) {
    await Promise.all(jobs)
    resetHistory(); drawOverlay(); updateAreas(); snapshot()
  }
}

function canvasToDataUrl(canvas: HTMLCanvasElement | null): string {
  if (!canvas) return ''
  try { return canvas.toDataURL('image/png') } catch { return '' }
}

const maskConfirmed = ref(false)

function confirm() {
  maskConfirmed.value = true
  emit('confirm', { skinMaskDataUrl: canvasToDataUrl(skinCanvasRef.value), lesionMaskDataUrl: canvasToDataUrl(lesionCanvasRef.value) })
  setTimeout(() => { maskConfirmed.value = false }, 2000)
}

// ── Computed ──
const areaPercent = computed(() => {
  if (regionAreaPct.value < 0.01) return 0
  return Math.round((lesionAreaPct.value / regionAreaPct.value) * 1000) / 10
})

const toolHint = computed(() => {
  const tool = ALL_TOOLS.find(t => t.name === activeToolName.value)
  const hints: Record<string, string> = {
    'skin-brush': '涂抹整个待测评的皮肤区域（蓝色涂层）',
    'lesion-brush': '在皮肤区域上涂出白斑范围（粉色涂层）',
    'eraser': '擦除涂层 — 在已涂区域上滑动即可擦除',
    'flood-fill': '点击填充相似颜色区域 — 拖动滑块调整容差 — Shift+点击填充皮肤',
    'lasso': '按住拖拽绘制自由选区 — 松开自动闭合填充白斑',
    'polygon': '点击放置顶点 — 双击或 Enter 闭合填充 — Backspace 删除顶点 — Esc 取消',
  }
  return hints[activeToolName.value] || ''
})

const zoomPercent = computed(() => Math.round(transform.scale * 100))

const overlayCursor = computed(() => {
  if (!props.editable) return 'default'
  if (spaceHeld) return isPanning.value ? 'grabbing' : 'grab'
  if (isPanning.value) return 'grabbing'
  return 'crosshair'
})

const imageStyle = computed(() => ({
  transform: `translate(${transform.offsetX}px, ${transform.offsetY}px) scale(${transform.scale * baseFitScale.value})`,
  transformOrigin: '0 0',
  width: `${naturalSize.value.width}px`,
  height: `${naturalSize.value.height}px`,
}))

const overlayStyle = computed(() => ({ ...imageStyle.value, zIndex: 10 }))

function getAnnotatedImageDataUrl(): string {
  if (!imgRef.value || !skinCanvasRef.value || !lesionCanvasRef.value) return ''
  const w = naturalSize.value.width; const h = naturalSize.value.height
  if (w === 0 || h === 0) return ''
  try {
    const composite = document.createElement('canvas')
    composite.width = w; composite.height = h
    const ctx = composite.getContext('2d')
    if (!ctx) return ''
    ctx.drawImage(imgRef.value, 0, 0, w, h)
    ctx.globalAlpha = 0.4; ctx.drawImage(skinCanvasRef.value, 0, 0)
    ctx.globalAlpha = 0.55; ctx.drawImage(lesionCanvasRef.value, 0, 0)
    ctx.globalAlpha = 1
    return composite.toDataURL('image/png')
  } catch { return '' }
}

defineExpose({
  getLesionDataUrl: () => canvasToDataUrl(lesionCanvasRef.value),
  getSkinDataUrl: () => canvasToDataUrl(skinCanvasRef.value),
  getAreaPercent: () => areaPercent.value,
  getAnnotatedImageDataUrl,
  loadMaskLayers,
})
</script>

<template>
  <div ref="wrapperRef" class="select-none" :style="{ display: 'flex', flexDirection: 'column', height: isFullscreenFallback ? '100vh' : '100%', minHeight: 0, ...(isFullscreenFallback ? { position: 'fixed', top: '0', left: '0', width: '100vw', zIndex: 9999, background: '#0f172a', padding: '8px' } : {}) }">
    <!-- Toolbar -->
    <div :style="{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px', padding: '8px 0', flexShrink: 0 }">
      <!-- Tool switcher -->
      <div :style="{ display: 'flex', gap: '2px', padding: '3px', background: '#0f172a', borderRadius: '8px' }">
        <button
          v-for="tool in availableTools" :key="tool.name"
          :style="{ padding: '6px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px', transition: 'all 0.15s',
            background: activeToolName === tool.name ? '#6366f1' : 'transparent',
            color: activeToolName === tool.name ? '#fff' : '#94a3b8',
            border: activeToolName !== tool.name ? '1px solid rgba(148,163,184,0.2)' : '1px solid transparent',
            cursor: tool.available ? 'pointer' : 'not-allowed', opacity: tool.available ? 1 : 0.4 }"
          :disabled="!editable || !tool.available"
          :title="`${tool.label} (${tool.shortcut})`"
          @click="setTool(tool.name)"
        >
          <i :class="tool.icon" style="font-size: 13px;"></i>
          <span style="font-size: 10px; color: inherit; opacity: 0.6; font-weight: 600;">{{ tool.shortcut }}</span>
        </button>
      </div>

      <div :style="{ height: '20px', width: '1px', background: 'rgba(148,163,184,0.2)' }"></div>

      <!-- Brush size -->
      <div :style="{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#94a3b8', padding: '0 4px' }">
        <i class="ri-ruler-line"></i>
        <input type="range" min="8" max="80" step="2" v-model.number="brushSize" :style="{ width: '60px', height: '4px', accentColor: '#6366f1' }" :disabled="!editable" />
        <span :style="{ width: '22px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }">{{ brushSize }}</span>
      </div>

      <!-- Flood fill tolerance (only when that tool is active) -->
      <div v-if="showFillTolerance" :style="{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#fbbf24', padding: '0 4px' }">
        <i class="ri-contrast-drop-line"></i>
        <span style="font-size: 10px;">容差</span>
        <input type="range" min="2" max="64" step="2" v-model.number="fillTolerance" :style="{ width: '50px', height: '4px', accentColor: '#f59e0b' }" />
        <span :style="{ width: '20px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: '10px' }">{{ fillTolerance }}</span>
      </div>

      <!-- Opacity -->
      <div :style="{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#94a3b8', padding: '0 4px' }">
        <i class="ri-contrast-2-line"></i>
        <input type="range" min="0.2" max="0.95" step="0.05" v-model.number="layerOpacity" :style="{ width: '60px', height: '4px', accentColor: '#6366f1' }" @input="drawOverlay" />
      </div>

      <!-- Undo / Redo / Clear -->
      <div :style="{ display: 'flex', alignItems: 'center', gap: '2px', marginLeft: 'auto' }">
        <button :style="{ padding: '6px 8px', borderRadius: '6px', color: '#94a3b8', background: 'transparent', border: 'none', fontSize: '14px', opacity: canUndo && editable ? 1 : 0.3, cursor: canUndo && editable ? 'pointer' : 'not-allowed' }" :disabled="!canUndo || !editable" title="撤销 (Ctrl+Z)" @click="undoAction">
          <i class="ri-arrow-go-back-line"></i>
        </button>
        <button :style="{ padding: '6px 8px', borderRadius: '6px', color: '#94a3b8', background: 'transparent', border: 'none', fontSize: '14px', opacity: canRedo && editable ? 1 : 0.3, cursor: canRedo && editable ? 'pointer' : 'not-allowed' }" :disabled="!canRedo || !editable" title="重做 (Ctrl+Y)" @click="redoAction">
          <i class="ri-arrow-go-forward-line"></i>
        </button>
        <button :style="{ padding: '6px 8px', borderRadius: '6px', color: '#ef4444', background: 'transparent', border: 'none', fontSize: '14px', opacity: editable ? 1 : 0.3, cursor: editable ? 'pointer' : 'not-allowed' }" :disabled="!editable" title="清空全部涂层" @click="clearLayer('all')">
          <i class="ri-delete-bin-line"></i>
        </button>
      </div>
    </div>

    <!-- Canvas area -->
    <div ref="canvasAreaRef" :style="{ flex: '1 1 0', minHeight: '300px', minWidth: 0, position: 'relative', overflow: 'hidden', background: '#0f172a', borderRadius: '8px', border: '1px solid rgba(148,163,184,0.12)', cursor: spaceHeld ? (isPanning ? 'grabbing' : 'grab') : 'default', touchAction: 'none' }"
      @wheel.prevent="onWheel"
      @pointerdown="onContainerPointerDown" @pointermove="onContainerPointerMove" @pointerup="onContainerPointerUp" @pointercancel="onContainerPointerUp">

      <!-- Loading state -->
      <div v-if="!imageLoaded && !imageError" :style="{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '8px', zIndex: 20 }">
        <div :style="{ width: '28px', height: '28px', border: '3px solid rgba(148,163,184,0.2)', borderTopColor: '#6366f1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }"></div>
        <span :style="{ fontSize: '12px', color: '#64748b' }">加载图片中...</span>
      </div>

      <!-- Error state -->
      <div v-if="imageError" :style="{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '8px', zIndex: 20 }">
        <i class="ri-image-line" :style="{ fontSize: '40px', color: '#475569' }"></i>
        <span :style="{ fontSize: '13px', color: '#94a3b8' }">图片加载失败</span>
        <button :style="{ padding: '6px 14px', borderRadius: '6px', fontSize: '12px', background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer' }" @click="retryLoad">重试</button>
      </div>

      <!-- Hidden canvases for painting -->
      <canvas ref="skinCanvasRef" style="position: absolute; left: -9999px; top: -9999px;" />
      <canvas ref="lesionCanvasRef" style="position: absolute; left: -9999px; top: -9999px;" />

      <!-- Image layer -->
      <img v-show="imageLoaded" ref="imgRef" :key="imgKey" :src="imageUrl"
        :style="{ ...imageStyle, maxWidth: 'none', maxHeight: 'none', display: 'block', position: 'absolute', top: 0, left: 0, userSelect: 'none', WebkitUserDrag: 'none' }"
        draggable="false" alt="" @load="onImgLoad" @error="onImgError" />

      <!-- Overlay canvas -->
      <canvas v-show="imageLoaded" ref="overlayCanvasRef"
        :style="{ ...overlayStyle, display: 'block', position: 'absolute', top: 0, left: 0, touchAction: 'none' }"
        @pointerdown.stop="onCanvasPointerDown" @pointermove.stop="onCanvasPointerMove"
        @pointerup="onCanvasPointerUp" @pointercancel="onCanvasPointerUp" @pointerleave="onCanvasPointerUp" />

      <!-- Zoom controls -->
      <div v-if="imageLoaded" :style="{ position: 'absolute', top: '10px', left: '56px', display: 'flex', alignItems: 'center', gap: '2px', zIndex: 20, background: 'rgba(15,23,42,0.92)', backdropFilter: 'blur(8px)', borderRadius: '8px', padding: '4px 4px', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }">
        <button class="mask-zoom-btn" @click="zoomOut" title="缩小 (-)"><i class="ri-subtract-line"></i></button>
        <span :style="{ fontSize: '11px', color: '#cbd5e1', minWidth: '40px', textAlign: 'center', fontVariantNumeric: 'tabular-nums' }">{{ zoomPercent }}%</span>
        <button class="mask-zoom-btn" @click="zoomIn" title="放大 (+)"><i class="ri-add-line"></i></button>
        <span :style="{ width: '1px', height: '16px', background: 'rgba(148,163,184,0.3)' }"></span>
        <button class="mask-zoom-btn" @click="fitToContainer" title="适应窗口 (R)"><i class="ri-fullscreen-line"></i></button>
        <button class="mask-zoom-btn" @click="zoomActualSize" title="1:1 实际大小"><i class="ri-aspect-ratio-line"></i></button>
        <span :style="{ width: '1px', height: '16px', background: 'rgba(148,163,184,0.3)' }"></span>
        <button class="mask-zoom-btn" @click="toggleFullscreen" title="画布全屏 (F)">
          <i :class="isFullscreen ? 'ri-fullscreen-exit-line' : 'ri-fullscreen-fill'"></i>
        </button>
      </div>

      <!-- Hint -->
      <div v-if="imageLoaded" :style="{ position: 'absolute', bottom: '10px', right: '10px', zIndex: 20, pointerEvents: 'none' }">
        <span :style="{ display: 'inline-block', fontSize: '10px', background: 'rgba(15,23,42,0.85)', color: '#94a3b8', padding: '4px 8px', borderRadius: '6px', boxShadow: '0 2px 8px rgba(0,0,0,0.3)', border: '1px solid rgba(148,163,184,0.2)' }">
          滚轮缩放 · 空格拖拽 · R 适应 · F 全屏 · 1-6 切换工具
        </span>
      </div>
    </div>

    <!-- Stats bar -->
    <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', padding: '8px 0 0', flexShrink: 0 }">
      <div :style="{ background: 'rgba(59,130,246,0.15)', borderRadius: '8px', padding: '8px', textAlign: 'center' }">
        <div :style="{ fontSize: '11px', color: '#93c5fd' }">评估区域</div>
        <div :style="{ fontSize: '14px', fontWeight: 600, color: '#60a5fa' }">{{ regionAreaPct.toFixed(1) }}%</div>
      </div>
      <div :style="{ background: 'rgba(236,72,153,0.15)', borderRadius: '8px', padding: '8px', textAlign: 'center' }">
        <div :style="{ fontSize: '11px', color: '#f9a8d4' }">白斑</div>
        <div :style="{ fontSize: '14px', fontWeight: 600, color: '#f472b6' }">{{ lesionAreaPct.toFixed(1) }}%</div>
      </div>
      <div :style="{ background: 'rgba(99,102,241,0.15)', borderRadius: '8px', padding: '8px', textAlign: 'center' }">
        <div :style="{ fontSize: '11px', color: '#a5b4fc' }">白斑占比</div>
        <div :style="{ fontSize: '14px', fontWeight: 600, color: '#818cf8' }">{{ areaPercent.toFixed(1) }}%</div>
      </div>
    </div>

    <!-- Tool hint -->
    <div :style="{ textAlign: 'center', fontSize: '11px', color: '#94a3b8', padding: '4px 0', flexShrink: 0 }">
      <i class="ri-information-line"></i> {{ toolHint }}
    </div>

    <!-- Action buttons -->
    <div v-if="editable" :style="{ display: 'flex', justifyContent: 'flex-end', gap: '8px', padding: '8px 0 0', flexShrink: 0 }">
      <button :style="{ fontSize: '12px', padding: '6px 12px', borderRadius: '6px', color: '#94a3b8', background: 'transparent', border: '1px solid rgba(148,163,184,0.2)', cursor: 'pointer' }" @click="emit('cancel')">取消</button>
      <button :style="{ fontSize: '12px', padding: '8px 16px', borderRadius: '6px', fontWeight: 500, border: 'none', cursor: 'pointer', transition: 'all 0.2s', background: maskConfirmed ? '#10b981' : '#6366f1', color: '#fff' }" @click="confirm">
        <i :class="maskConfirmed ? 'ri-check-double-line' : 'ri-check-line'" :style="{ marginRight: '4px' }"></i>
        {{ maskConfirmed ? '已确认 ✓' : '确认填涂' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
.mask-zoom-btn {
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; color: #cbd5e1;
  border: none; border-radius: 4px;
  font-size: 12px; cursor: pointer; transition: all 0.15s;
}
.mask-zoom-btn:hover { background: rgba(99, 102, 241, 0.2); color: #c7d2fe; }
</style>
