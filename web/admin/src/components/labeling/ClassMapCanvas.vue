<template>
  <div ref="container" class="canvas-host" :class="{ panning: panning || spaceDown }"
    @wheel.prevent="onWheel" @pointerdown="onDown" @pointermove="onMove" @pointerup="onUp"
    @pointercancel="onUp" @pointerleave="cursor.visible = false" @contextmenu.prevent>
    <div class="stage" :style="stageStyle">
      <img v-if="imageUrl" :src="imageUrl" :width="editor.width.value" :height="editor.height.value"
        alt="待标注照片（规范化后）" draggable="false" @load="onImageLoad" />
      <canvas ref="overlay" :width="editor.width.value" :height="editor.height.value" :style="{ opacity: showOverlay ? 1 : 0 }" />
    </div>
    <div v-if="cursor.visible && showBrush" class="brush-cursor" :style="cursorStyle" />
    <div v-if="peekLabel" class="peek-badge"><i class="ri-eye-line" /> 正在查看：{{ peekLabel }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import type { ClassMapEditor } from '@/composables/useClassMapEditor'
import { paintOverlay } from '@/utils/classMap'

const props = defineProps<{
  editor: ClassMapEditor
  imageUrl: string | null
  opacity: number
  showOverlay: boolean
  reference: Uint8Array | null
  peekLabel: string
}>()

const container = ref<HTMLDivElement | null>(null)
const overlay = ref<HTMLCanvasElement | null>(null)
const view = reactive({ scale: 1, tx: 0, ty: 0 })
const cursor = reactive({ x: 0, y: 0, visible: false })
const panning = ref(false)
const spaceDown = ref(false)
const pointers = new Map<number, { x: number; y: number }>()
let panStart: { x: number; y: number; tx: number; ty: number } | null = null
let pinch: { dist: number; scale: number; cx: number; cy: number; tx: number; ty: number } | null = null
let drawing = false
let frame = 0
let buffer: ImageData | null = null

const stageStyle = computed(() => ({ transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})` }))
const showBrush = computed(() => props.editor.tool.value === 'brush' && !props.reference && !spaceDown.value)
const cursorStyle = computed(() => {
  const size = props.editor.brushSize.value * view.scale
  return { width: `${size}px`, height: `${size}px`, left: `${cursor.x - size / 2}px`, top: `${cursor.y - size / 2}px` }
})

function render() {
  frame = 0
  const canvas = overlay.value
  const w = props.editor.width.value; const h = props.editor.height.value
  const ctx = canvas?.getContext('2d')
  if (!canvas || !ctx || !w || !h) return
  if (!buffer || buffer.width !== w || buffer.height !== h) buffer = ctx.createImageData(w, h)
  const source = props.reference ?? props.editor.map.value
  if (source.length !== w * h) return
  paintOverlay(source, buffer, props.opacity)
  ctx.putImageData(buffer, 0, 0)
}
function schedule() { if (!frame) frame = requestAnimationFrame(render) }
watch(() => [props.editor.version.value, props.reference, props.opacity], schedule)

function fit() {
  const host = container.value
  const w = props.editor.width.value; const h = props.editor.height.value
  if (!host || !w || !h) return
  const scale = Math.min(host.clientWidth / w, host.clientHeight / h) * 0.96
  view.scale = scale
  view.tx = (host.clientWidth - w * scale) / 2
  view.ty = (host.clientHeight - h * scale) / 2
}
function zoomAt(factor: number, cx?: number, cy?: number) {
  const host = container.value
  if (!host) return
  const x = cx ?? host.clientWidth / 2; const y = cy ?? host.clientHeight / 2
  const next = Math.min(12, Math.max(0.1, view.scale * factor))
  view.tx = x - ((x - view.tx) / view.scale) * next
  view.ty = y - ((y - view.ty) / view.scale) * next
  view.scale = next
}
function actualSize() { zoomAt(1 / view.scale) }

function local(e: PointerEvent | WheelEvent) {
  const rect = (container.value as HTMLDivElement).getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}
function toImage(p: { x: number; y: number }) { return { x: (p.x - view.tx) / view.scale, y: (p.y - view.ty) / view.scale } }

function onWheel(e: WheelEvent) {
  const p = local(e)
  zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, p.x, p.y)
}
function onDown(e: PointerEvent) {
  const p = local(e)
  pointers.set(e.pointerId, p)
  container.value?.setPointerCapture(e.pointerId)
  if (pointers.size === 2) {
    if (drawing) { props.editor.strokeEnd(); drawing = false }
    const [a, b] = [...pointers.values()]
    pinch = { dist: Math.hypot(a.x - b.x, a.y - b.y), scale: view.scale, cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2, tx: view.tx, ty: view.ty }
    return
  }
  if (spaceDown.value || e.button === 1 || e.button === 2) {
    panning.value = true
    panStart = { x: p.x, y: p.y, tx: view.tx, ty: view.ty }
    return
  }
  if (e.button !== 0 || props.reference) return
  const q = toImage(p)
  if (props.editor.tool.value === 'brush') { props.editor.strokeStart(q.x, q.y); drawing = true }
  else props.editor.clickAt(q.x, q.y)
}
function onMove(e: PointerEvent) {
  const p = local(e)
  cursor.x = p.x; cursor.y = p.y; cursor.visible = true
  if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p)
  if (pinch && pointers.size === 2) {
    const [a, b] = [...pointers.values()]
    const next = Math.min(12, Math.max(0.1, pinch.scale * Math.hypot(a.x - b.x, a.y - b.y) / pinch.dist))
    const cx = (a.x + b.x) / 2; const cy = (a.y + b.y) / 2
    view.tx = cx - ((pinch.cx - pinch.tx) / pinch.scale) * next
    view.ty = cy - ((pinch.cy - pinch.ty) / pinch.scale) * next
    view.scale = next
    return
  }
  if (panning.value && panStart) {
    view.tx = panStart.tx + p.x - panStart.x
    view.ty = panStart.ty + p.y - panStart.y
    return
  }
  if (drawing) { const q = toImage(p); props.editor.strokeMove(q.x, q.y) }
}
function onUp(e: PointerEvent) {
  pointers.delete(e.pointerId)
  if (pointers.size < 2) pinch = null
  if (drawing) { props.editor.strokeEnd(); drawing = false }
  panning.value = false
  panStart = null
}

function onImageLoad(e: Event) {
  const img = e.target as HTMLImageElement
  const w = props.editor.width.value; const h = props.editor.height.value
  const canvas = document.createElement('canvas')
  canvas.width = w; canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return
  ctx.drawImage(img, 0, 0, w, h)
  props.editor.setPhoto(ctx.getImageData(0, 0, w, h).data)
  fit()
  schedule()
}

function onKey(e: KeyboardEvent) {
  if (e.code !== 'Space' || (e.target as HTMLElement)?.closest('input, textarea, [contenteditable]')) return
  spaceDown.value = e.type === 'keydown'
  if (e.type === 'keydown') e.preventDefault()
}
const observer = new ResizeObserver(() => fit())
onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('keyup', onKey)
  if (container.value) observer.observe(container.value)
  nextTick(schedule)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('keyup', onKey)
  observer.disconnect()
  if (frame) cancelAnimationFrame(frame)
})

defineExpose({ fit, zoomAt, actualSize, zoom: computed(() => view.scale) })
</script>

<style scoped>
.canvas-host { position: relative; flex: 1; min-width: 0; min-height: 0; overflow: hidden; background: #111827; touch-action: none; cursor: crosshair; user-select: none; }
.canvas-host.panning { cursor: grab; }
.stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
.stage img, .stage canvas { position: absolute; left: 0; top: 0; display: block; image-rendering: pixelated; }
.stage img { image-rendering: auto; max-width: none; height: auto; }
.brush-cursor { position: absolute; pointer-events: none; border: 1.5px solid #fff; border-radius: 50%; box-shadow: 0 0 0 1px rgba(0, 0, 0, .6); }
.peek-badge { position: absolute; left: 12px; top: 12px; padding: 6px 10px; border-radius: 8px; background: rgba(15, 23, 42, .85); color: #f8fafc; font-size: 12px; pointer-events: none; }
</style>
