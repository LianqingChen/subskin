<script setup lang="ts">
import { ref, shallowRef, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

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

const tool = ref<Tool>('lesion-brush')
const brushSize = ref(32)
const layerOpacity = ref(0.55)
const showOnboardingTooltip = ref(true)

// Auto-dismiss onboarding tooltip after 8 seconds
let onboardingTimer: ReturnType<typeof setTimeout> | null = null
watch(showOnboardingTooltip, (val) => {
  if (val && props.editable) {
    if (onboardingTimer) clearTimeout(onboardingTimer)
    onboardingTimer = setTimeout(() => {
      showOnboardingTooltip.value = false
    }, 8000)
  }
})

// Auto-select lesion brush when AI layers load (user mainly needs to mark lesions)
watch(() => [props.initialSkinLayerUrl, props.initialLesionLayerUrl], () => {
  if (props.initialLesionLayerUrl) {
    tool.value = 'lesion-brush'
  }
})

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

// ── Working resolution cap ──
// Phone cameras produce 4000×3000+ images. At full resolution, each canvas
// buffer is ~45MB and pixel operations (extractEdgePixels, countAlpha, snapshot)
// iterate billions of bytes. Capping to 1024px max dimension reduces memory
// and CPU by ~48× while keeping mask quality sufficient for visual feedback.
// The CSS display size remains at natural resolution for crisp rendering.
const MAX_CANVAS_DIM = 1024

// ── Zoom & Pan state ──
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const minZoom = 0.05
const maxZoom = 8
const zoomStep = 0.25

// ── Pan tracking ──
const isPanning = ref(false)
let _panStartX = 0
let _panStartY = 0
let _panStartPanX = 0
let _panStartPanY = 0

// ── Pinch-to-zoom & two-finger pan (mobile) ──
const _pointers = new Map<number, { x: number; y: number }>()
let _pinchStartDist = 0
let _pinchStartZoom = 1
let _pinchStartCenterX = 0
let _pinchStartCenterY = 0
let _pinchStartPanX = 0
let _pinchStartPanY = 0

const isPainting = ref(false)
const skinAreaPct = ref(0)
const lesionAreaPct = ref(0)
const regionAreaPct = ref(0)

// Use shallowRef for history — ImageData objects are ~3MB each and should
// NOT be wrapped in Vue's deep reactive proxy. shallowRef tracks the array
// reference only, so we must reassign .value (not .push/.shift in place).
const history = shallowRef<Array<{ skin: ImageData; lesion: ImageData }>>([])
const historyIndex = ref(-1)
const HISTORY_MAX = 10

const canUndo = computed(() => historyIndex.value > 0)
const canRedo = computed(() => historyIndex.value < history.value.length - 1)

/** Compute working dimensions capped at MAX_CANVAS_DIM, preserving aspect ratio */
function workingDims(natW: number, natH: number): [number, number] {
  const maxDim = Math.max(natW, natH)
  if (maxDim <= MAX_CANVAS_DIM) return [natW, natH]
  const scale = MAX_CANVAS_DIM / maxDim
  return [Math.round(natW * scale), Math.round(natH * scale)]
}

const areaPercent = computed(() => {
  if (regionAreaPct.value < 0.01) return 0
  return Math.round((lesionAreaPct.value / regionAreaPct.value) * 1000) / 10
})

/** Get context for mask canvases that need getImageData (read-heavy). */
function getCtx(canvas: HTMLCanvasElement | null) {
  return canvas?.getContext('2d', { willReadFrequently: true }) || null
}

/** Get context for the overlay canvas (write-only, never getImageData).
 *  WITHOUT willReadFrequently — this allows the browser to use GPU
 *  acceleration for compositing, which is dramatically faster on mobile. */
function getOverlayCtx(canvas: HTMLCanvasElement | null) {
  return canvas?.getContext('2d') || null
}

// ── Cached overlay context (avoid getContext overhead per animation frame) ──
let _overlayCtx: CanvasRenderingContext2D | null = null

function clientToCanvas(clientX: number, clientY: number): [number, number] {
  const overlay = overlayCanvasRef.value
  const skin = skinCanvasRef.value
  if (!overlay || !skin) return [0, 0]
  const rect = overlay.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) return [0, 0]
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

  _pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })

  if (_pointers.size === 2) {
    const pts = Array.from(_pointers.values())
    _pinchStartDist = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y)
    _pinchStartZoom = zoom.value
    _pinchStartCenterX = (pts[0].x + pts[1].x) / 2
    _pinchStartCenterY = (pts[0].y + pts[1].y) / 2
    _pinchStartPanX = panX.value
    _pinchStartPanY = panY.value
    isPanning.value = true
    isPainting.value = false
    e.preventDefault()
    return
  }

  if (_pointers.size > 2) return

  if (e.button === 1 || e.button === 2) {
    isPanning.value = true
    _panStartX = e.clientX
    _panStartY = e.clientY
    _panStartPanX = panX.value
    _panStartPanY = panY.value
    e.preventDefault()
    return
  }

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
  if (_pointers.has(e.pointerId)) {
    _pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  }

  if (_pointers.size === 2 && _pinchStartDist > 0) {
    const pts = Array.from(_pointers.values())
    const curDist = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y)
    const scale = curDist / _pinchStartDist
    zoom.value = Math.max(minZoom, Math.min(maxZoom, _pinchStartZoom * scale))

    const curCenterX = (pts[0].x + pts[1].x) / 2
    const curCenterY = (pts[0].y + pts[1].y) / 2
    panX.value = _pinchStartPanX + (curCenterX - _pinchStartCenterX)
    panY.value = _pinchStartPanY + (curCenterY - _pinchStartCenterY)
    return
  }

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

function onPointerUp(e: PointerEvent) {
  _pointers.delete(e.pointerId)
  if (_pointers.size < 2) {
    _pinchStartDist = 0
  }
  if (isPainting.value) {
    isPainting.value = false
    snapshot()
    updateAreasDebounced()
  }
  if (isPanning.value && _pointers.size === 0) {
    isPanning.value = false
    clampPan()
  }
}

function drawOverlay() {
  const overlay = overlayCanvasRef.value
  const skin = skinCanvasRef.value
  const lesion = lesionCanvasRef.value
  if (!overlay || !skin || !lesion) return
  // Use cached overlay context (write-optimized, no willReadFrequently)
  if (!_overlayCtx) _overlayCtx = getOverlayCtx(overlay)
  const ctx = _overlayCtx
  if (!ctx) return
  ctx.clearRect(0, 0, overlay.width, overlay.height)
  ctx.globalAlpha = layerOpacity.value
  ctx.drawImage(skin, 0, 0)
  ctx.drawImage(lesion, 0, 0)
  ctx.globalAlpha = 1
  // Render contour outlines using pre-baked offscreen buffers (fast path)
  renderContourOutlines(ctx)
}

// ── Animated contour outlines (offscreen canvas batching) ──
// These are animation-loop-only values, NOT template dependencies.
// Using plain variables avoids 60fps Vue reactivity overhead.
let dashOffset = 0
// @ts-expect-error TS6133 — skin edge cache kept for future contour rendering
let edgePixelsSkin: [number, number][] = []
let edgePixelsLesion: [number, number][] = []
let _animFrameId = 0
let _animPaused = false   // paused when tab hidden

// ── Offscreen contour buffers ──
// Instead of 40K-80K fillRect calls per frame, we pre-render the static dots
// into two offscreen canvases (even/odd phase) and simply composite them
// with a shifting offset each frame. This reduces per-frame draw calls from
// ~80K individual fillRect to ONE drawImage per phase buffer per frame.
let _contourBufA: HTMLCanvasElement | null = null   // phase 0 dots
let _contourBufB: HTMLCanvasElement | null = null   // phase 1 dots
let _contourBufStep = 0   // remember step used for buffer generation
let _contourBufDirty = true  // set true when edge caches change

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
  edgePixelsSkin = extractEdgePixels(skin, step)
  edgePixelsLesion = extractEdgePixels(lesion, step)
  _contourBufDirty = true  // trigger contour buffer rebuild on next frame
}

/**
 * Rebuild the offscreen contour buffers from the current edge pixel cache.
 * Called only when edge pixels change (after snapshot/undo/paint), NOT per frame.
 * Pre-renders ~40-80K dots into two static canvases (phase A and phase B),
 * so the animation loop only needs drawImage (1-2 draw calls) instead of
 * 40-80K individual fillRect calls per frame.
 */
function rebuildContourBuffers() {
  const canvasW = skinCanvasRef.value?.width || 1
  const canvasH = skinCanvasRef.value?.height || 1
  const maxDim = Math.max(canvasW, canvasH)
  const step = Math.max(1, Math.floor(maxDim / 400))
  _contourBufStep = step
  const dotSize = Math.max(step * 1.6, 2.5)
  const dashLen = Math.max(3, Math.floor(10 / step))

  // Create buffers only if needed or size changed
  if (!_contourBufA || _contourBufA.width !== canvasW || _contourBufA.height !== canvasH) {
    _contourBufA = document.createElement('canvas')
    _contourBufA.width = canvasW
    _contourBufA.height = canvasH
  }
  if (!_contourBufB || _contourBufB.width !== canvasW || _contourBufB.height !== canvasH) {
    _contourBufB = document.createElement('canvas')
    _contourBufB.width = canvasW
    _contourBufB.height = canvasH
  }

  // Clear buffers
  const ctxA = _contourBufA.getContext('2d')!
  const ctxB = _contourBufB.getContext('2d')!
  ctxA.clearRect(0, 0, canvasW, canvasH)
  ctxB.clearRect(0, 0, canvasW, canvasH)
  ctxA.fillStyle = '#f472b6'
  ctxB.fillStyle = '#f472b6'

  for (const [x, y] of edgePixelsLesion) {
    // At offset 0, determine which phase this dot belongs to
    const phase = Math.floor((x + y) / (step * dashLen)) % 2
    const targetCtx = phase === 0 ? ctxA : ctxB
    targetCtx.fillRect(x - dotSize / 2, y - dotSize / 2, dotSize, dotSize)
  }

  _contourBufDirty = false
}

/**
 * Render the marching-ants contour overlay using pre-baked offscreen buffers.
 * This is called per animation frame but only does 2-3 drawImage calls
 * (phase A + phase B + dry shift), NOT 40-80K fillRect calls.
 */
function renderContourOutlines(ctx: CanvasRenderingContext2D) {
  if (_contourBufDirty || !_contourBufA || !_contourBufB) {
    rebuildContourBuffers()
  }
  if (!_contourBufA || !_contourBufB) return

  const step = _contourBufStep
  const offset = dashOffset
  // Shift the rendering offset to create the marching-ants animation effect.
  // We shift by a small pixel offset proportional to dashOffset, creating
  // the illusion of movement without redrawing thousands of dots per frame.
  const shift = (offset * step * 0.5) % (step * 6)

  ctx.save()
  // Phase A: visible when dash cycle is in "on" position
  ctx.globalAlpha = 0.9
  ctx.drawImage(_contourBufA, shift, shift)
  // Phase B: visible when dash cycle is in "off" position (the gaps)
  ctx.globalAlpha = 0.5
  ctx.drawImage(_contourBufB, -shift, -shift)
  ctx.restore()
}

function startAnimation() {
  // Guard: prevent double RAF loops
  if (_animFrameId) stopAnimation()
  let lastDraw = 0
  // Target ~12fps for marching ants — visually smooth enough, 5× less CPU than 60fps
  const FRAME_INTERVAL = 1000 / 12

  function tick(now: number) {
    // Pause animation when tab is hidden to save CPU/battery
    if (_animPaused) { _animFrameId = requestAnimationFrame(tick); return }
    const elapsed = now - lastDraw
    if (elapsed >= FRAME_INTERVAL) {
      lastDraw = now - (elapsed % FRAME_INTERVAL)
      dashOffset = (dashOffset + 1) % 60
      const overlay = overlayCanvasRef.value
      if (!overlay) { _animFrameId = requestAnimationFrame(tick); return }
      // Use cached overlay context (write-optimized, no willReadFrequently)
      if (!_overlayCtx) _overlayCtx = getOverlayCtx(overlay)
      const ctx = _overlayCtx
      if (!ctx) { _animFrameId = requestAnimationFrame(tick); return }
      ctx.clearRect(0, 0, overlay.width, overlay.height)
      ctx.globalAlpha = layerOpacity.value
      if (skinCanvasRef.value) ctx.drawImage(skinCanvasRef.value, 0, 0)
      if (lesionCanvasRef.value) ctx.drawImage(lesionCanvasRef.value, 0, 0)
      ctx.globalAlpha = 1
      renderContourOutlines(ctx)
    }
    _animFrameId = requestAnimationFrame(tick)
  }
  _animFrameId = requestAnimationFrame(tick)
}

function stopAnimation() {
  if (_animFrameId) {
    cancelAnimationFrame(_animFrameId)
    _animFrameId = 0
  }
  _animPaused = false
}

/** Pause/resume animation when tab visibility changes */
function onVisibilityChange() {
  if (document.hidden) {
    _animPaused = true
  } else {
    _animPaused = false
  }
}

/** Invalidate cached overlay context (e.g., when canvas resizes) */
function invalidateOverlayCache() {
  _overlayCtx = null
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

/** Debounced version of updateAreas — prevents rapid successive calls
 *  (e.g., during fast brush strokes) from blocking the main thread. */
let _updateAreasTimer: ReturnType<typeof setTimeout> | null = null
function updateAreasDebounced() {
  if (_updateAreasTimer) clearTimeout(_updateAreasTimer)
  _updateAreasTimer = setTimeout(() => {
    _updateAreasTimer = null
    updateAreas()
  }, 150)
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
  // shallowRef requires new array references to trigger reactivity.
  // Never mutate in-place — always create a new array.
  const newHistory = history.value.slice(0, historyIndex.value + 1)
  newHistory.push({ skin, lesion })
  if (newHistory.length > HISTORY_MAX) {
    newHistory.shift()
  } else {
    historyIndex.value++
  }
  history.value = newHistory
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
// @ts-expect-error TS6133 — kept for future toolbar use
function redo() { if (canRedo.value) { historyIndex.value++; applySnapshot(historyIndex.value) } }

// @ts-expect-error TS6133 — kept for future toolbar use
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
  updateAreasDebounced()
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
      // Wait for browser paint before resolving, so getImageData() downstream
      // reads the actual pixel data instead of a blank canvas.
      requestAnimationFrame(() => resolve())
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

  const natW = img.naturalWidth, natH = img.naturalHeight
  if (natW === 0 || natH === 0) {
    imageLoading.value = false
    onImgError()
    return
  }

  // Use downscaled working dimensions for canvas pixel buffers
  const [w, h] = workingDims(natW, natH)

  try {
    for (const c of [skin, lesion, overlay]) {
      c.width = w
      c.height = h
    }
    // Canvas resize invalidates cached contexts and contour buffers
    invalidateOverlayCache()
    _contourBufDirty = true
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
    stopAnimation()
    // Break heavy pixel operations into multiple async steps to avoid
    // blocking the main thread. Each step gets its own frame, allowing
    // the browser to process user input between steps.
    // Step 1: Show the image immediately (no heavy operations)
    imageLoaded.value = true
    imageError.value = false
    imageErrorMsg.value = ''
    canvasWidth.value = natW
    canvasHeight.value = natH
    imageLoading.value = false
    nextTick().then(() => {
      setTimeout(() => zoomToFit(), 50)
    })

    // Step 2: Build snapshot + edge caches (2× getImageData + edge detection)
    requestAnimationFrame(() => {
      snapshot()
      // Step 3: Draw overlay + build contour buffers (2× drawImage + 37K fillRect)
      requestAnimationFrame(() => {
        drawOverlay()
        // Step 4: Start animation loop
        requestAnimationFrame(() => {
          startAnimation()
          // Step 5: Defer area calculation to idle (3× getImageData + pixel iteration)
          void ((window as any).requestIdleCallback
            ? (window as any).requestIdleCallback(() => updateAreas(), { timeout: 500 })
            : window.setTimeout(() => updateAreas(), 300))
        })
      })
    })
  } catch (e) {
    console.error('MaskEditor onImgLoad failed:', e)
    onImgError()
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

// Retry counter for zoomToFit — prevents infinite loop when container
// has 0 dimensions (e.g., flex layout not yet settled, or VisualFeaturesCard
// consumes all vertical space on mobile).
let _zoomToFitRetries = 0
const MAX_ZOOM_FIT_RETRIES = 10

function zoomToFit() {
  const container = imgContainerRef.value
  const img = imgRef.value
  if (!container || !img) { zoom.value = 1; resetPan(); _zoomToFitRetries = 0; return }
  const cw = container.clientWidth, ch = container.clientHeight
  const iw = img.naturalWidth, ih = img.naturalHeight
  if (iw === 0 || ih === 0) { zoom.value = 1; resetPan(); _zoomToFitRetries = 0; return }
  if (cw === 0 || ch === 0) {
    // CRITICAL: Use requestAnimationFrame (NOT nextTick) here.
    // nextTick is a microtask (Promise.resolve().then()) that runs BEFORE
    // the browser performs layout. If the container has 0 height, nextTick
    // would loop infinitely because clientHeight never changes between
    // microtasks — permanently freezing the main thread.
    // requestAnimationFrame runs AFTER layout/paint, so dimensions can
    // actually change between retries.
    if (_zoomToFitRetries < MAX_ZOOM_FIT_RETRIES) {
      _zoomToFitRetries++
      requestAnimationFrame(() => zoomToFit())
    } else {
      // Fallback: container never got dimensions (shouldn't happen in normal
      // layout, but guard against edge cases like hidden tabs or 0-size flex)
      _zoomToFitRetries = 0
      zoom.value = 1
      resetPan()
    }
    return
  }
  _zoomToFitRetries = 0
  const pad = 16
  const scaleX = (cw - pad * 2) / iw
  const scaleY = (ch - pad * 2) / ih
  const fit = Math.min(scaleX, scaleY)
  const fitFloor = 0.02
  zoom.value = Math.max(fitFloor, fit)
  resetPan()
}

function onWheel(e: WheelEvent) {
  if (isPainting.value) return
  e.preventDefault()
  const rect = imgContainerRef.value?.getBoundingClientRect()
  if (!rect) return

  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top
  const oldZoom = zoom.value
  const delta = e.deltaY > 0 ? -zoomStep : zoomStep
  const newZoom = Math.max(minZoom, Math.min(maxZoom, +(oldZoom + delta).toFixed(2)))

  const scale = newZoom / oldZoom
  panX.value = mouseX - scale * (mouseX - panX.value)
  panY.value = mouseY - scale * (mouseY - panY.value)

  zoom.value = newZoom
  clampPan()
}

const isFullscreen = ref(false)

// @ts-expect-error TS6133 — kept for future toolbar use
function toggleFullscreen() {
  const el = imgContainerRef.value
  if (!el) return
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    el.requestFullscreen().catch(() => {})
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  nextTick(() => {
    if (imageLoaded.value) zoomToFit()
  })
}

const zoomPercent = computed(() => Math.round(zoom.value * 100))

let _resizePending = false
let _resizeRafId = 0
const resizeObserver = new ResizeObserver(() => {
  if (_resizePending) return
  _resizePending = true
  if (_resizeRafId) cancelAnimationFrame(_resizeRafId)
  _resizeRafId = requestAnimationFrame(() => {
    _resizeRafId = 0
    _resizePending = false
    drawOverlay()
    clampPan()
  })
})

onMounted(() => {
  if (containerRef.value) resizeObserver.observe(containerRef.value)
  if (imgRef.value?.complete && imgRef.value.naturalWidth > 0) {
    onImgLoad()
  } else if (imgRef.value?.complete && imgRef.value.naturalWidth === 0) {
    onImgError()
  }
  imgContainerRef.value?.addEventListener('contextmenu', (e) => e.preventDefault())
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  if (_resizeRafId) cancelAnimationFrame(_resizeRafId)
  stopAnimation()
  invalidateOverlayCache()
  // Clean up contour buffers
  _contourBufA = null
  _contourBufB = null
  _contourBufDirty = true
  if (_updateAreasTimer) { clearTimeout(_updateAreasTimer); _updateAreasTimer = null }
  if (onboardingTimer) clearTimeout(onboardingTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

watch(() => props.imageUrl, async () => {
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
  await nextTick()
  const img = imgRef.value
  if (img?.complete) {
    if (img.naturalWidth > 0) onImgLoad()
    else onImgError()
  }
})

watch(
  () => [props.initialSkinLayerUrl, props.initialLesionLayerUrl] as const,
  async ([newSkin, newLesion], [oldSkin, oldLesion]) => {
    if (!imageLoaded.value) return
    if (newSkin === oldSkin && newLesion === oldLesion) return
    const skin = skinCanvasRef.value
    const lesion = lesionCanvasRef.value
    if (!skin || !lesion) return
    const w = skin.width, h = skin.height
    if (w === 0 || h === 0) return
    for (const c of [skin, lesion]) {
      const ctx = getCtx(c)
      if (ctx) ctx.clearRect(0, 0, w, h)
    }
    // Stop animation before heavy pixel work to prevent RAF contention
    stopAnimation()
    const jobs: Promise<void>[] = []
    if (newSkin) jobs.push(loadLayerFromDataUrl(skin, newSkin))
    if (newLesion) jobs.push(loadLayerFromDataUrl(lesion, newLesion))
    await Promise.all(jobs)
    history.value = []
    historyIndex.value = -1
    // Break heavy pixel operations into multiple async steps to avoid
    // blocking the main thread after AI results load.
    // Step 1: Build snapshot + edge caches
    requestAnimationFrame(() => {
      snapshot()
      // Step 2: Draw overlay + build contour buffers
      requestAnimationFrame(() => {
        drawOverlay()
        // Step 3: Start animation loop
        requestAnimationFrame(() => {
          startAnimation()
          // Step 4: Defer area calculation to idle
          void ((window as any).requestIdleCallback
            ? (window as any).requestIdleCallback(() => updateAreas(), { timeout: 500 })
            : window.setTimeout(() => updateAreas(), 300))
        })
      })
    })
  },
)


// Expose areaPercent for parent components to display
// confirmMasks: generate data URLs from both canvases and emit confirm event
function confirmMasks() {
  const skin = skinCanvasRef.value
  const lesion = lesionCanvasRef.value
  if (!skin || !lesion) return
  const skinMaskDataUrl = skin.toDataURL('image/png')
  const lesionMaskDataUrl = lesion.toDataURL('image/png')
  emit('confirm', { skinMaskDataUrl, lesionMaskDataUrl })
}

/**
 * Generate a composite annotated image: original photo + skin layer (blue) +
 * lesion layer (pink) composited together, matching what the user sees on
 * screen. Used as the share cover image so the community post shows the AI
 * analysis result visually.
 */
function getAnnotatedImageDataUrl(): string | null {
  const skin = skinCanvasRef.value
  const lesion = lesionCanvasRef.value
  const img = imgRef.value
  if (!skin || !lesion || !img) return null

  const w = skin.width
  const h = skin.height
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  // 1. Draw original photo
  ctx.drawImage(img, 0, 0, w, h)
  // 2. Composite skin layer (blue, semi-transparent)
  ctx.globalAlpha = layerOpacity.value
  ctx.drawImage(skin, 0, 0)
  // 3. Composite lesion layer (pink, semi-transparent)
  ctx.drawImage(lesion, 0, 0)
  ctx.globalAlpha = 1

  return canvas.toDataURL('image/png')
}

defineExpose({ areaPercent, confirmMasks, getAnnotatedImageDataUrl })
</script>

<template>
  <div ref="containerRef" class="w-full select-none relative" :class="{ 'h-full flex flex-col': fullHeight }">

    <!-- Image + Canvas viewport -->
    <div
      ref="imgContainerRef"
      class="mask-editor-viewport relative rounded-2xl bg-gray-300"
      :class="{ 'flex-1': fullHeight }"
      :style="{ minHeight: isFullscreen || fullHeight ? '0' : '280px', maxHeight: isFullscreen || fullHeight ? 'none' : 'calc(100dvh - 200px)', touchAction: 'none' }"
      @wheel="onWheel"
    >
      <!-- Onboarding Tooltip - compact, inside viewport at top -->
      <div v-if="showOnboardingTooltip && editable && imageLoaded" class="absolute top-3 left-1/2 -translate-x-1/2 z-40 p-2 rounded-lg bg-amber-50 dark:bg-amber-900/40 border border-amber-200 dark:border-amber-800/50 max-w-[260px] shadow-lg">
        <div class="flex items-center gap-2">
          <i class="ri-lightbulb-line text-amber-500 text-sm shrink-0"></i>
          <p class="text-[11px] text-amber-700 dark:text-amber-400 flex-1">粉色=白斑 · 蓝色=皮肤 · 8秒后自动关闭</p>
          <button class="w-5 h-5 flex items-center justify-center text-amber-400 hover:text-amber-600 dark:hover:text-amber-300 rounded-full hover:bg-amber-100 dark:hover:bg-amber-900/40 shrink-0" @click="showOnboardingTooltip = false" aria-label="关闭提示">
            <i class="ri-close-line text-xs"></i>
          </button>
        </div>
      </div>

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
      <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div
          :style="{
            transform: `translate(${panX}px, ${panY}px) scale(${zoom})`,
            transformOrigin: 'center center',
            willChange: isPanning || isPainting ? 'transform' : 'auto',
          }"
          class="relative inline-block pointer-events-auto"
        >
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
            data-pannable="true"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="onPointerUp"
            @pointerleave="onPointerUp"
          />
        </div>
      </div>

      <!-- Area % badge at top-left -->
      <div v-if="imageLoaded" class="absolute top-3 left-3 z-30">
        <span
          class="text-xs font-medium px-2 py-1 rounded-lg backdrop-blur-sm"
          :class="areaPercent > 50 ? 'bg-red-100/80 text-red-700 dark:bg-red-900/50 dark:text-red-300' : areaPercent > 25 ? 'bg-amber-100/80 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300' : 'bg-primary-100/80 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300'"
        >
          白斑占比 {{ areaPercent.toFixed(1) }}%
        </span>
      </div>

      <!-- Mobile hint at top-right -->
      <div v-if="imageLoaded" class="absolute top-3 right-3 z-30">
        <span class="text-[10px] text-gray-400 dark:text-gray-500 bg-white/60 dark:bg-gray-800/60 backdrop-blur px-2 py-0.5 rounded-full md:hidden">
          双指缩放 · 单指绘画 · 长按拖拽
        </span>
        <span class="text-[10px] text-gray-400 dark:text-gray-500 bg-white/60 dark:bg-gray-800/60 backdrop-blur px-2 py-0.5 rounded-full hidden md:inline">
          滚轮缩放 · 右键拖拽
        </span>
      </div>

      <!-- Zoom controls - hidden on mobile, minimal on desktop -->
      <div v-if="imageLoaded" class="hidden md:flex absolute bottom-12 left-3 items-center gap-1 z-30">
        <button class="w-7 h-7 rounded-lg bg-white/80 backdrop-blur flex items-center justify-center text-gray-600 hover:bg-white dark:hover:bg-gray-300 shadow text-xs" title="放大" @click="zoomIn">
          <i class="ri-zoom-in-line"></i>
        </button>
        <button class="w-7 h-7 rounded-lg bg-white/80 backdrop-blur flex items-center justify-center text-gray-600 hover:bg-white dark:hover:bg-gray-300 shadow text-xs" title="缩小" @click="zoomOut">
          <i class="ri-zoom-out-line"></i>
        </button>
        <span class="text-xs text-gray-500 bg-white/80 backdrop-blur px-1.5 py-0.5 rounded shadow tabular-nums">{{ zoomPercent }}%</span>
      </div>
    </div>

    <!-- Floating toolbar at bottom - moved outside viewport to avoid overflow:hidden clipping -->
    <div v-if="imageLoaded && editable" class="sticky bottom-0 left-0 right-0 z-30 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md border-t border-gray-200/50 dark:border-gray-700/50 px-3 py-2 pb-[env(safe-area-inset-bottom)]">
      <div class="flex items-center gap-3">
        <!-- Tool selector: skin / lesion / eraser -->
        <div class="flex items-center gap-1 p-1 rounded-xl bg-gray-100 dark:bg-gray-700">
          <button
            class="w-10 h-10 rounded-lg text-sm font-medium transition-colors flex items-center justify-center"
            :class="tool === 'skin-brush' ? 'bg-blue-500 text-white shadow-sm' : 'text-blue-600 dark:text-blue-300'"
            @click="tool = 'skin-brush'"
            title="皮肤画笔"
          ><i class="ri-hand-heart-line"></i></button>
          <button
            class="w-10 h-10 rounded-lg text-sm font-medium transition-colors flex items-center justify-center"
            :class="tool === 'lesion-brush' ? 'bg-pink-500 text-white shadow-sm' : 'text-pink-600 dark:text-pink-300'"
            @click="tool = 'lesion-brush'"
            title="白斑画笔"
          ><i class="ri-virus-line"></i></button>
          <button
            class="w-10 h-10 rounded-lg text-sm font-medium transition-colors flex items-center justify-center"
            :class="tool === 'eraser' ? 'bg-gray-500 text-white shadow-sm' : 'text-gray-600 dark:text-gray-300'"
            @click="tool = 'eraser'"
            title="橡皮擦"
          ><i class="ri-eraser-line"></i></button>
        </div>

        <!-- Brush size slider - compact -->
        <div class="flex items-center gap-1.5 flex-1 max-w-[140px]">
          <i class="ri-ruler-line text-xs text-gray-400"></i>
          <input type="range" min="8" max="80" step="4" v-model.number="brushSize" class="flex-1 accent-primary-500 h-1" />
          <span class="text-xs text-gray-500 w-6 text-right tabular-nums">{{ brushSize }}</span>
        </div>

        <!-- Undo button only -->
        <button
          class="w-10 h-10 rounded-lg flex items-center justify-center text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30"
          :disabled="!canUndo || !editable"
          title="撤销"
          @click="undo"
        >
          <i class="ri-arrow-go-back-line text-lg"></i>
        </button>
      </div>
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
