<script setup lang="ts">
/**
 * BeforeAfterSlider — 前后对比滑块。
 *
 * 两种交互模式：
 * - 对比模式（默认）：拖动任意位置移动分隔条；
 * - 手动调整模式（adjustMode）：分隔条固定、拖动平移上方（after）照片、
 *   双指捏合缩放/旋转上方照片，配合页面上的微调按钮做手工对齐；
 *   变换通过 update:afterTransform 交给父级按照片位持久化。
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

export interface ImageTransform {
  dx: number
  dy: number
  scale: number
  rotate: number
}

const props = withDefaults(defineProps<{
  beforeUrl: string
  afterUrl: string
  beforeLabel?: string
  afterLabel?: string
  alt?: string
  imageFit?: 'cover' | 'contain'
  beforeTransform?: ImageTransform | null
  afterTransform?: ImageTransform | null
  /** 手动调整模式：拖动/双指手势调整上方照片，分隔条暂不可拖动 */
  adjustMode?: boolean
}>(), {
  beforeLabel: '之前',
  afterLabel: '现在',
  alt: '前后对比',
  imageFit: 'cover',
  beforeTransform: null,
  afterTransform: null,
  adjustMode: false,
})

const emit = defineEmits<{
  (e: 'update:afterTransform', t: ImageTransform): void
}>()

const sliderPos = ref(50)
const containerRef = ref<HTMLDivElement | null>(null)
const isDragging = ref(false)

const clipStyle = computed(() => ({
  clipPath: `inset(0 ${100 - sliderPos.value}% 0 0)`,
}))

function updateFromEvent(clientX: number) {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const pct = ((clientX - rect.left) / rect.width) * 100
  sliderPos.value = Math.max(0, Math.min(100, pct))
}

// ── 对比模式：分隔条拖动 ──
function onPointerDown(e: PointerEvent) {
  if (props.adjustMode) {
    onAdjustDown(e)
    return
  }
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  isDragging.value = true
  updateFromEvent(e.clientX)
}
function onPointerMove(e: PointerEvent) {
  if (props.adjustMode) {
    onAdjustMove(e)
    return
  }
  if (!isDragging.value) return
  updateFromEvent(e.clientX)
}
function onPointerUp(e: PointerEvent) {
  if (props.adjustMode) {
    onAdjustUp(e)
    return
  }
  isDragging.value = false
}

// ── 手动调整模式：单指平移 / 双指缩放旋转 ──
interface PointerPt { x: number; y: number }
interface Gesture {
  mode: 'pan' | 'pinch'
  startT: ImageTransform
  startX: number
  startY: number
  startDist: number
  startAngle: number
  startMidX: number
  startMidY: number
}
const pointers = new Map<number, PointerPt>()
const gesture = ref<Gesture | null>(null)

function baseTransform(t: ImageTransform | null | undefined): ImageTransform {
  return t ? { dx: t.dx, dy: t.dy, scale: t.scale, rotate: t.rotate } : { dx: 0, dy: 0, scale: 1, rotate: 0 }
}

function onAdjustDown(e: PointerEvent) {
  e.preventDefault()
  try { containerRef.value?.setPointerCapture(e.pointerId) } catch { /* 忽略 */ }
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (pointers.size === 1) {
    const t = baseTransform(props.afterTransform)
    gesture.value = { mode: 'pan', startT: t, startX: e.clientX, startY: e.clientY, startDist: 0, startAngle: 0, startMidX: e.clientX, startMidY: e.clientY }
  } else if (pointers.size === 2) {
    const [p1, p2] = [...pointers.values()]
    const t = baseTransform(props.afterTransform)
    gesture.value = {
      mode: 'pinch',
      startT: t,
      startX: 0,
      startY: 0,
      startDist: Math.max(1, Math.hypot(p2.x - p1.x, p2.y - p1.y)),
      startAngle: (Math.atan2(p2.y - p1.y, p2.x - p1.x) * 180) / Math.PI,
      startMidX: (p1.x + p2.x) / 2,
      startMidY: (p1.y + p2.y) / 2,
    }
  }
}

function onAdjustMove(e: PointerEvent) {
  if (!pointers.has(e.pointerId) || !gesture.value) return
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  const g = gesture.value
  if (g.mode === 'pan') {
    emit('update:afterTransform', {
      ...g.startT,
      dx: g.startT.dx + (e.clientX - g.startX),
      dy: g.startT.dy + (e.clientY - g.startY),
    })
    return
  }
  if (pointers.size < 2) return
  const [p1, p2] = [...pointers.values()]
  const dist = Math.hypot(p2.x - p1.x, p2.y - p1.y)
  let dAngle = (Math.atan2(p2.y - p1.y, p2.x - p1.x) * 180) / Math.PI - g.startAngle
  if (dAngle > 180) dAngle -= 360
  if (dAngle < -180) dAngle += 360
  const midX = (p1.x + p2.x) / 2
  const midY = (p1.y + p2.y) / 2
  emit('update:afterTransform', {
    dx: g.startT.dx + (midX - g.startMidX),
    dy: g.startT.dy + (midY - g.startMidY),
    scale: Math.min(3, Math.max(0.5, g.startT.scale * (dist / g.startDist))),
    rotate: Math.min(30, Math.max(-30, g.startT.rotate + dAngle)),
  })
}

function onAdjustUp(e: PointerEvent) {
  pointers.delete(e.pointerId)
  if (pointers.size === 1) {
    const [p] = [...pointers.values()]
    const t = baseTransform(props.afterTransform)
    gesture.value = { mode: 'pan', startT: t, startX: p.x, startY: p.y, startDist: 0, startAngle: 0, startMidX: p.x, startMidY: p.y }
  } else if (pointers.size === 0) {
    gesture.value = null
  }
}

function cssTransform(t: ImageTransform | null | undefined): string | undefined {
  const b = baseTransform(t)
  if (b.dx === 0 && b.dy === 0 && b.scale === 1 && b.rotate === 0) return undefined
  return `translate(${b.dx}px, ${b.dy}px) scale(${b.scale}) rotate(${b.rotate}deg)`
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'ArrowLeft') sliderPos.value = Math.max(0, sliderPos.value - 2)
  if (e.key === 'ArrowRight') sliderPos.value = Math.min(100, sliderPos.value + 2)
}

onMounted(() => {
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
})
</script>

<template>
  <div class="w-full">
    <!-- 日期标签在图片上方，不遮挡照片 -->
    <div
      v-if="beforeLabel || afterLabel"
      class="mb-2 flex items-center justify-between text-xs font-medium text-gray-500 dark:text-gray-400"
    >
      <span class="inline-flex items-center gap-1">
        <i class="ri-arrow-left-line"></i>{{ beforeLabel }}
      </span>
      <span class="inline-flex items-center gap-1">
        {{ afterLabel }}<i class="ri-arrow-right-line"></i>
      </span>
    </div>
    <div
      ref="containerRef"
      data-swipe-ignore
      class="relative w-full aspect-square overflow-hidden rounded-2xl bg-gray-900 select-none touch-none"
      :class="adjustMode ? 'cursor-move' : 'cursor-ew-resize'"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
    >
      <img
        :src="afterUrl"
        :alt="alt"
        class="absolute inset-0 w-full h-full pointer-events-none will-change-transform"
        :style="{ transform: cssTransform(afterTransform), objectFit: imageFit }"
        draggable="false"
      />
      <div class="absolute inset-0 pointer-events-none" :style="clipStyle">
        <img
          :src="beforeUrl"
          :alt="alt"
          class="absolute inset-0 w-full h-full will-change-transform"
          :style="{ transform: cssTransform(beforeTransform), objectFit: imageFit }"
          draggable="false"
        />
      </div>

      <div
        class="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(0,0,0,0.5)] pointer-events-none"
        :style="{ left: `${sliderPos}%` }"
      />
      <button
        v-if="!adjustMode"
        type="button"
        role="slider"
        aria-label="前后照片分隔位置"
        :aria-valuenow="Math.round(sliderPos)"
        aria-valuemin="0"
        aria-valuemax="100"
        class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-11 h-11 rounded-full bg-white shadow-lg flex items-center justify-center cursor-ew-resize focus:outline-none focus:ring-2 focus:ring-primary-400"
        :style="{ left: `${sliderPos}%` }"
        @keydown="onKeyDown"
      >
        <i class="ri-arrow-left-right-line text-gray-700"></i>
      </button>
    </div>
  </div>
</template>
