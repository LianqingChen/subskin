<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePhotoMaskCanvas, type PhotoCanvasOptions } from '@/composables/usePhotoMaskCanvas'
import { referenceOutlineUrl } from '@/utils/photo-mask-canvas'
const props = defineProps<PhotoCanvasOptions & { fill?: boolean; reference?: string | null }>()
const emit = defineEmits<{ ready: [boolean]; refining: [boolean] }>()
const canvas = ref<HTMLCanvasElement | null>(null)
const stage = ref<HTMLElement | null>(null)
const state = usePhotoMaskCanvas(props, canvas)
watch(state.ready, value => emit('ready', value))
watch(() => state.refining.value || state.outlining.value, value => emit('refining', value))
defineExpose({ snapshot: state.snapshot, outline: state.runOutline })

// ── 缩放 / 平移：只改 CSS transform，坐标换算仍基于 getBoundingClientRect，画笔半径随缩放按屏幕像素换算，放大后更精细 ──
const MIN_ZOOM = 1, MAX_ZOOM = 6
const view = ref({ zoom: 1, x: 0, y: 0 })
const panMode = ref(false)
const zoomed = computed(() => view.value.zoom > 1.001)
const viewTransform = computed(() => `translate(${view.value.x}px, ${view.value.y}px) scale(${view.value.zoom})`)
function setView(zoom: number, x: number, y: number) {
  const z = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom))
  const box = canvas.value, frame = stage.value
  if (!box || !frame || z <= MIN_ZOOM + 0.001) { view.value = { zoom: 1, x: 0, y: 0 }; panMode.value = false; return }
  const limitX = Math.max(0, (box.offsetWidth * z - frame.clientWidth) / 2), limitY = Math.max(0, (box.offsetHeight * z - frame.clientHeight) / 2)
  view.value = { zoom: z, x: Math.min(limitX, Math.max(-limitX, x)), y: Math.min(limitY, Math.max(-limitY, y)) }
}
/** 以屏幕点为焦点缩放（画布居中于舞台，因此以舞台中心为原点）。 */
function zoomAround(next: number, clientX: number, clientY: number) {
  const frame = stage.value?.getBoundingClientRect()
  if (!frame) return
  const fx = clientX - (frame.left + frame.width / 2), fy = clientY - (frame.top + frame.height / 2)
  const { zoom, x, y } = view.value, z = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next)), k = z / zoom
  setView(z, fx - k * (fx - x), fy - k * (fy - y))
}
function zoomBy(factor: number) {
  const frame = stage.value?.getBoundingClientRect()
  if (frame) zoomAround(view.value.zoom * factor, frame.left + frame.width / 2, frame.top + frame.height / 2)
}
function resetView() { setView(1, 0, 0) }
function onWheel(e: WheelEvent) {
  if (!props.editable || !state.ready.value) return
  zoomAround(view.value.zoom * Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY)
}

const pointers = new Map<number, { x: number; y: number }>()
let pinch: { dist: number; cx: number; cy: number; zoom: number; x: number; y: number } | null = null
let drag: { id: number; sx: number; sy: number; x: number; y: number } | null = null
function pair() { const [a, b] = [...pointers.values()]; return { dist: Math.hypot(a.x - b.x, a.y - b.y) || 1, cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 } }
// 在舞台的捕获阶段观察指针：双指不拦截事件，让画布按原逻辑撤销刚开始的笔画；「移动」模式下单指拖动才拦截。
function gestureDown(e: PointerEvent) {
  if (!props.editable) return
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (pointers.size === 2) { drag = null; pinch = { ...pair(), zoom: view.value.zoom, x: view.value.x, y: view.value.y } }
  else if (pointers.size === 1 && panMode.value && zoomed.value) {
    e.stopPropagation(); e.preventDefault(); stage.value?.setPointerCapture(e.pointerId)
    drag = { id: e.pointerId, sx: e.clientX, sy: e.clientY, x: view.value.x, y: view.value.y }
  }
}
function gestureMove(e: PointerEvent) {
  const p = pointers.get(e.pointerId)
  if (!p) return
  p.x = e.clientX; p.y = e.clientY
  if (pinch && pointers.size >= 2) {
    const frame = stage.value?.getBoundingClientRect(), now = pair()
    if (!frame) return
    const z = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, pinch.zoom * now.dist / pinch.dist)), k = z / pinch.zoom
    const sx = pinch.cx - (frame.left + frame.width / 2), sy = pinch.cy - (frame.top + frame.height / 2)
    const nx = now.cx - (frame.left + frame.width / 2), ny = now.cy - (frame.top + frame.height / 2)
    setView(z, nx - k * (sx - pinch.x), ny - k * (sy - pinch.y))
  } else if (drag && e.pointerId === drag.id) {
    e.stopPropagation(); e.preventDefault()
    setView(view.value.zoom, drag.x + e.clientX - drag.sx, drag.y + e.clientY - drag.sy)
  }
}
function gestureUp(e: PointerEvent) {
  pointers.delete(e.pointerId)
  if (pointers.size < 2) pinch = null
  if (drag && e.pointerId === drag.id) { drag = null; if (stage.value?.hasPointerCapture(e.pointerId)) stage.value.releasePointerCapture(e.pointerId) }
}

function onKey(e: KeyboardEvent) {
  if (!props.editable || !(e.ctrlKey || e.metaKey)) return
  const el = e.target instanceof HTMLElement ? e.target : null
  if (el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable)) return
  const key = e.key.toLowerCase()
  if (key === 'z') { e.preventDefault(); e.shiftKey ? state.redo() : state.undo() }
  else if (key === 'y') { e.preventDefault(); state.redo() }
}

// ── 上次范围参考层：与画布同位同变换，仅描边，不进入导出 ──
const referenceUrl = ref(''), showReference = ref(true)
const layout = ref({ left: 0, top: 0, width: 0, height: 0 })
function syncLayout() {
  const box = canvas.value
  if (box) layout.value = { left: box.offsetLeft, top: box.offsetTop, width: box.offsetWidth, height: box.offsetHeight }
}
const referenceStyle = computed(() => ({ left: `${layout.value.left}px`, top: `${layout.value.top}px`, width: `${layout.value.width}px`, height: `${layout.value.height}px`, transform: viewTransform.value }))
watch(() => props.reference, async url => {
  referenceUrl.value = ''
  if (!url) return
  try { const outline = await referenceOutlineUrl(url); if (props.reference === url) referenceUrl.value = outline } catch { /* 参考层缺失不影响核对 */ }
}, { immediate: true })
watch([state.ready, () => props.image], async () => { resetView(); await nextTick(); syncLayout() })
let observer: ResizeObserver | null = null
onMounted(() => {
  window.addEventListener('keydown', onKey)
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(() => { syncLayout(); if (zoomed.value) setView(view.value.zoom, view.value.x, view.value.y) })
    if (stage.value) observer.observe(stage.value)
    if (canvas.value) observer.observe(canvas.value)
  }
})
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); observer?.disconnect() })
</script>
<template>
  <div ref="stage" data-swipe-ignore class="photo-mask-stage relative flex w-full items-center justify-center overflow-hidden rounded-2xl bg-gray-100 dark:bg-gray-950" :class="{ 'photo-mask-stage--edit': editable, 'photo-mask-stage--fill': fill }" @touchstart.stop @touchmove.stop @touchend.stop @touchcancel.stop @click.stop @dragstart.prevent @contextmenu.prevent @wheel.prevent="onWheel" @pointerdown.capture="gestureDown" @pointermove.capture="gestureMove" @pointerup.capture="gestureUp" @pointercancel.capture="gestureUp">
    <canvas ref="canvas" v-show="state.ready.value" role="img" aria-label="照片标注：浅蓝为皮肤，浅粉为白斑" class="block max-h-full max-w-full select-none" :class="editable ? (panMode && zoomed ? 'touch-none cursor-grab' : 'touch-none cursor-crosshair') : ''" :style="{ transform: viewTransform, transformOrigin: 'center center' }" @pointerdown.stop="state.down" @pointermove.stop="state.move" @pointerup.stop="state.up" @pointercancel="state.cancelStroke" @lostpointercapture="state.cancelStroke" />
    <img v-if="referenceUrl && showReference && state.ready.value" :src="referenceUrl" alt="" aria-hidden="true" class="pointer-events-none absolute select-none object-contain" :style="{ ...referenceStyle, transformOrigin: 'center center' }" />
    <div v-if="editable && state.ready.value" class="pointer-events-none absolute inset-x-2 top-2 flex items-start justify-between gap-2">
      <div class="pointer-events-auto flex gap-1" role="group" aria-label="撤销与重做">
        <button type="button" class="photo-mask-btn" aria-label="撤销" :disabled="!state.canUndo.value || busy || state.refining.value || state.outlining.value" @click.stop="state.undo"><i class="ri-arrow-go-back-line" aria-hidden="true"></i></button>
        <button type="button" class="photo-mask-btn" aria-label="重做" :disabled="!state.canRedo.value || busy || state.refining.value || state.outlining.value" @click.stop="state.redo"><i class="ri-arrow-go-forward-line" aria-hidden="true"></i></button>
      </div>
      <div class="pointer-events-auto flex flex-col items-end gap-1" role="group" aria-label="缩放与移动">
        <div class="flex gap-1">
          <button type="button" class="photo-mask-btn" aria-label="缩小" :disabled="!zoomed" @click.stop="zoomBy(1 / 1.5)"><i class="ri-zoom-out-line" aria-hidden="true"></i></button>
          <button type="button" class="photo-mask-btn" aria-label="放大" :disabled="view.zoom >= MAX_ZOOM - 0.001" @click.stop="zoomBy(1.5)"><i class="ri-zoom-in-line" aria-hidden="true"></i></button>
        </div>
        <div v-if="zoomed" class="flex gap-1">
          <button type="button" class="photo-mask-btn" :class="panMode ? 'photo-mask-btn--on' : ''" :aria-pressed="panMode" aria-label="移动画面（开启后单指拖动画面，关闭后单指涂画）" @click.stop="panMode = !panMode"><i class="ri-drag-move-2-line" aria-hidden="true"></i></button>
          <button type="button" class="photo-mask-btn" aria-label="恢复整图" @click.stop="resetView"><i class="ri-fullscreen-exit-line" aria-hidden="true"></i></button>
        </div>
      </div>
    </div>
    <button v-if="referenceUrl && state.ready.value" type="button" class="absolute bottom-2 left-2 min-h-[36px] rounded-lg bg-white/90 px-3 text-xs text-amber-800 shadow-sm dark:bg-gray-900/90 dark:text-amber-300" :aria-pressed="showReference" @click.stop="showReference = !showReference"><i :class="showReference ? 'ri-eye-line' : 'ri-eye-off-line'" class="mr-1" aria-hidden="true"></i>上次范围（仅参考）</button>
    <div v-if="!state.ready.value" role="status" class="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-white/90 p-4 text-sm text-gray-600 dark:bg-gray-900/90 dark:text-gray-300">
      <span>{{ state.error.value || '加载照片…' }}</span>
      <button v-if="state.error.value" class="btn-ghost min-h-[44px] px-4" :disabled="busy" @click="state.load">重新加载</button>
    </div>
    <p v-if="state.ready.value && state.error.value" role="status" class="pointer-events-none absolute bottom-2 rounded-lg bg-white/95 px-3 py-2 text-xs text-gray-700 dark:bg-gray-900/95 dark:text-gray-200">{{ state.error.value }}</p>
    <p v-if="state.refining.value || state.outlining.value" role="status" class="pointer-events-none absolute bottom-2 right-2 rounded-lg bg-white/95 px-3 py-2 text-xs text-primary-800 dark:bg-gray-900/95 dark:text-primary-200">{{ state.busyNote.value }}</p>
  </div>
</template>
<style scoped>
.photo-mask-stage { height: clamp(220px, 54svh, 640px); }
.photo-mask-stage--edit { touch-action: none; user-select: none; -webkit-user-select: none; height: clamp(240px, calc(100svh - 260px), 820px); }
.photo-mask-stage--fill { flex: 1 1 0%; min-height: 0; height: 0; }
canvas { width: auto; height: auto; }
.photo-mask-btn { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 12px; font-size: 1.25rem; color: rgb(55 65 81); background: rgba(255, 255, 255, 0.92); box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18); }
.photo-mask-btn:disabled { opacity: 0.35; }
.photo-mask-btn--on { color: rgb(255 255 255); background: var(--color-primary-600, #0d9488); }
:global(html.dark) .photo-mask-btn { color: rgb(229 231 235); background: rgba(31, 41, 55, 0.92); }
</style>
