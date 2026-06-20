<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import type { ContourRegion } from '@/api/vasi'

const props = defineProps<{
  imageUrl: string
  contours: ContourRegion[]
  editable?: boolean
}>()

const emit = defineEmits<{
  update: [contours: ContourRegion[]]
  confirm: [contours: ContourRegion[]]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)
const imgDisplaySize = ref({ width: 1, height: 1 })
const imgReady = ref(false)

const localContours = ref<ContourRegion[]>([])
const selectedContourIdx = ref(-1)
const selectedPointIdx = ref(-1)
const mode = ref<'select' | 'draw' | 'move'>('select')
const isDrawing = ref(false)
const drawPoints = ref<number[][]>([])
const isDragging = ref(false)
const dragStartPos = ref({ x: 0, y: 0 })
const dragOrigins = ref<number[][]>([])

watch(() => props.contours, (val) => {
  localContours.value = val.map(c => ({ ...c, polygon: c.polygon.map(p => [...p]) }))
}, { immediate: true, deep: true })

watch(() => props.imageUrl, () => {
  imgReady.value = false
})

function toPixel(nx: number, ny: number): [number, number] {
  return [nx * imgDisplaySize.value.width, ny * imgDisplaySize.value.height]
}

function toNorm(px: number, py: number): [number, number] {
  return [
    Math.max(0, Math.min(1, px / (imgDisplaySize.value.width || 1))),
    Math.max(0, Math.min(1, py / (imgDisplaySize.value.height || 1))),
  ]
}

function polygonPoints(contour: ContourRegion): string {
  return contour.polygon
    .map(([nx, ny]) => {
      const [px, py] = toPixel(nx, ny)
      return `${px},${py}`
    })
    .join(' ')
}

function onImgLoad() {
  if (!imgRef.value) return
  imgReady.value = true
  updateImgDisplaySize()
}

function updateImgDisplaySize() {
  if (!imgRef.value) return
  const rect = imgRef.value.getBoundingClientRect()
  if (rect.width > 0 && rect.height > 0) {
    imgDisplaySize.value = { width: rect.width, height: rect.height }
  }
}

const resizeObserver = new ResizeObserver(() => {
  if (imgReady.value) updateImgDisplaySize()
})

onMounted(() => {
  if (containerRef.value) resizeObserver.observe(containerRef.value)
  window.addEventListener('mouseup', finishInteraction)
  window.addEventListener('touchend', finishInteraction)
})

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  window.removeEventListener('mouseup', finishInteraction)
  window.removeEventListener('touchend', finishInteraction)
})

function getPointerPos(e: MouseEvent | TouchEvent): { x: number; y: number } {
  if (!imgRef.value) return { x: 0, y: 0 }
  const rect = imgRef.value.getBoundingClientRect()
  let cx: number, cy: number
  if ('touches' in e) {
    if (e.touches.length === 0) return { x: 0, y: 0 }
    cx = e.touches[0].clientX; cy = e.touches[0].clientY
  } else {
    cx = e.clientX; cy = e.clientY
  }
  return { x: cx - rect.left, y: cy - rect.top }
}

function onPointerDown(e: MouseEvent | TouchEvent) {
  if (!props.editable) return
  e.preventDefault()
  const pos = getPointerPos(e)

  if (mode.value === 'draw') {
    isDrawing.value = true
    drawPoints.value = [toNorm(pos.x, pos.y)]
    return
  }

  const hit = hitTestPoint(pos.x, pos.y)
  if (hit) {
    selectedContourIdx.value = hit.contourIdx
    selectedPointIdx.value = hit.pointIdx
    isDragging.value = true
    dragStartPos.value = pos
    if (mode.value === 'move') {
      dragOrigins.value = localContours.value[hit.contourIdx].polygon.map(p => [...p])
    }
    return
  }
  selectedContourIdx.value = -1
  selectedPointIdx.value = -1
}

function onPointerMove(e: MouseEvent | TouchEvent) {
  if (!isDragging.value && !isDrawing.value) return
  if ('touches' in e) e.preventDefault()
  const pos = getPointerPos(e)

  if (isDrawing.value && mode.value === 'draw') {
    drawPoints.value.push(toNorm(pos.x, pos.y))
    return
  }

  if (!isDragging.value) return

  if (mode.value === 'move' && selectedContourIdx.value >= 0) {
    const dx = (pos.x - dragStartPos.value.x) / (imgDisplaySize.value.width || 1)
    const dy = (pos.y - dragStartPos.value.y) / (imgDisplaySize.value.height || 1)
    localContours.value[selectedContourIdx.value].polygon = dragOrigins.value.map(([ox, oy]) => [
      Math.max(0, Math.min(1, ox + dx)),
      Math.max(0, Math.min(1, oy + dy)),
    ])
  } else if (selectedContourIdx.value >= 0 && selectedPointIdx.value >= 0) {
    const [nx, ny] = toNorm(pos.x, pos.y)
    localContours.value[selectedContourIdx.value].polygon[selectedPointIdx.value] = [nx, ny]
  }
  emitUpdate()
}

function finishInteraction() {
  if (isDrawing.value && drawPoints.value.length >= 3) {
    const simplified = simplifyPath(drawPoints.value)
    localContours.value.push({
      label: `白斑${localContours.value.length + 1}`,
      polygon: simplified,
    })
    selectedContourIdx.value = localContours.value.length - 1
  }
  isDrawing.value = false
  drawPoints.value = []
  isDragging.value = false
  selectedPointIdx.value = -1
  emitUpdate()
}

function hitTestPoint(px: number, py: number, threshold = 18): { contourIdx: number; pointIdx: number } | null {
  for (let ci = localContours.value.length - 1; ci >= 0; ci--) {
    for (let pi = 0; pi < localContours.value[ci].polygon.length; pi++) {
      const [npx, npy] = localContours.value[ci].polygon[pi]
      const [ppx, ppy] = toPixel(npx, npy)
      if (Math.sqrt((px - ppx) ** 2 + (py - ppy) ** 2) <= threshold) {
        return { contourIdx: ci, pointIdx: pi }
      }
    }
  }
  return null
}

function simplifyPath(points: number[][], tolerance = 0.015): number[][] {
  if (points.length <= 8) return points
  const result: number[][] = [points[0]]
  let prev = points[0]
  for (let i = 1; i < points.length; i++) {
    const d = Math.sqrt((points[i][0] - prev[0]) ** 2 + (points[i][1] - prev[1]) ** 2)
    if (d > tolerance) { result.push(points[i]); prev = points[i] }
  }
  return result.length >= 3 ? result : points.slice(0, Math.min(8, points.length))
}

function addPoint(ci: number, afterPi: number) {
  const c = localContours.value[ci]
  const prev = c.polygon[afterPi]
  const next = c.polygon[(afterPi + 1) % c.polygon.length]
  c.polygon.splice(afterPi + 1, 0, [(prev[0] + next[0]) / 2, (prev[1] + next[1]) / 2])
  emitUpdate()
}

function removePoint(ci: number, pi: number) {
  const c = localContours.value[ci]
  if (c.polygon.length <= 3) {
    localContours.value.splice(ci, 1)
    if (selectedContourIdx.value >= localContours.value.length)
      selectedContourIdx.value = localContours.value.length - 1
  } else {
    c.polygon.splice(pi, 1)
  }
  selectedPointIdx.value = -1
  emitUpdate()
}

function deleteContour(ci: number) {
  localContours.value.splice(ci, 1)
  selectedContourIdx.value = -1
  selectedPointIdx.value = -1
  emitUpdate()
}

function emitUpdate() {
  emit('update', localContours.value.map(c => ({ ...c, polygon: c.polygon.map(p => [...p] as [number, number]) })))
}

function handleConfirm() {
  emit('confirm', localContours.value.map(c => ({ ...c, polygon: c.polygon.map(p => [...p] as [number, number]) })))
}

const drawPath = computed(() => {
  if (!isDrawing.value || drawPoints.value.length < 2) return ''
  return drawPoints.value.map(([nx, ny]) => { const [px, py] = toPixel(nx, ny); return `${px},${py}` }).join(' ')
})

const contourColors = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6']

const totalAreaPercent = computed(() =>
  localContours.value.reduce((sum, c) => sum + (c.area_percent ?? 0), 0)
)

function contourColor(ci: number, selected: boolean) {
  const base = contourColors[ci % contourColors.length]
  return selected ? base : base + 'b3'
}
function contourFill(ci: number) {
  const hex = contourColors[ci % contourColors.length].slice(1)
  const r = parseInt(hex.slice(0,2), 16)
  const g = parseInt(hex.slice(2,4), 16)
  const b = parseInt(hex.slice(4,6), 16)
  return `rgba(${r},${g},${b},0.08)`
}
</script>

<template>
  <div ref="containerRef" class="relative select-none">
    <img
      ref="imgRef"
      :src="imageUrl"
      class="max-w-full max-h-[85vh] object-contain rounded-xl"
      @load="onImgLoad"
      draggable="false"
    />

    <!-- Area summary panel -->
    <div v-if="localContours.length > 0" class="absolute top-3 right-3 bg-white/90  backdrop-blur rounded-lg px-3 py-2 text-xs shadow z-10">
      <div v-for="(c, i) in localContours" :key="i">
        <span :style="{color: contourColors[i % contourColors.length]}">●</span>
        {{ c.label }}: {{ (c.area_percent ?? 0).toFixed(1) }}%
      </div>
      <div v-if="localContours.length > 1" class="font-bold mt-1 pt-1 border-t border-gray-200 dark:border-gray-600">
        合计: {{ totalAreaPercent.toFixed(1) }}%
      </div>
    </div>

    <!-- SVG overlay -->
    <svg
      v-if="imgReady"
      class="absolute inset-0 w-full h-full pointer-events-auto"
      :viewBox="`0 0 ${imgDisplaySize.width} ${imgDisplaySize.height}`"
      preserveAspectRatio="xMidYMid meet"
      :style="{ cursor: editable ? (mode === 'draw' ? 'crosshair' : mode === 'move' ? 'grab' : 'default') : 'default' }"
      @mousedown="onPointerDown"
      @mousemove="onPointerMove"
      @touchstart="onPointerDown"
      @touchmove="onPointerMove"
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
        :fill="contourFill(ci)"
        :stroke="contourColor(ci, selectedContourIdx === ci)"
        :stroke-width="selectedContourIdx === ci ? 2.5 : 1.5"
        stroke-dasharray="8 4"
        stroke-linejoin="round"
        :filter="selectedContourIdx === ci ? 'url(#contour-glow)' : ''"
        class="contour-animated"
      />

      <g v-for="(contour, ci) in localContours" :key="'lbl-'+ci">
        <text
          :x="toPixel(contour.polygon[0][0], contour.polygon[0][1])[0]"
          :y="toPixel(contour.polygon[0][0], contour.polygon[0][1])[1] - 10"
          :fill="contourColors[ci % contourColors.length]"
          font-size="12" font-weight="600" text-anchor="middle"
          class="pointer-events-none"
          style="filter: drop-shadow(0 1px 1px rgba(255,255,255,0.8))"
        >{{ contour.label }}</text>
      </g>

      <template v-if="editable" v-for="(contour, ci) in localContours" :key="'pts-'+ci">
        <g v-for="(point, pi) in contour.polygon" :key="pi">
          <circle
            :cx="toPixel(point[0], point[1])[0]"
            :cy="toPixel(point[0], point[1])[1]"
            :r="selectedContourIdx === ci && selectedPointIdx === pi ? 22 : 18"
            :fill="selectedContourIdx === ci && selectedPointIdx === pi ? contourColors[ci % contourColors.length] : 'white'"
            :stroke="contourColors[ci % contourColors.length]"
            :stroke-width="2"
            class="cursor-pointer"
            style="filter: drop-shadow(0 1px 2px rgba(0,0,0,0.3))"
          />
        </g>
      </template>

      <polyline
        v-if="isDrawing && drawPoints.length >= 2"
        :points="drawPath"
        fill="none" stroke="#ef4444" stroke-width="2"
        stroke-dasharray="6 3" stroke-linecap="round" stroke-linejoin="round"
        class="contour-animated"
      />
    </svg>

    <!-- Toolbar -->
    <div v-if="editable" class="absolute top-3 right-3 flex flex-col gap-1.5">
      <button
        v-for="tool in ([
          { id: 'select', label: '⬚', tip: '选择/拖拽控制点' },
          { id: 'draw', label: '✎', tip: '手绘新白斑区域' },
          { id: 'move', label: '⤡', tip: '整体移动轮廓' },
        ] as const)"
        :key="tool.id"
        class="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold transition-all duration-200 shadow-lg"
        :class="mode === tool.id
          ? 'bg-primary-500 text-white shadow-primary-500/30'
          : 'bg-white/90  text-gray-600 hover:bg-primary-50 dark:hover:bg-primary-900/30 backdrop-blur-sm'"
        :title="tool.tip"
        @click="mode = tool.id"
      >{{ tool.label }}</button>
    </div>

    <!-- Selected contour actions -->
    <div v-if="editable && selectedContourIdx >= 0" class="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-white/90  backdrop-blur-sm rounded-xl px-3 py-2 shadow-lg border border-gray-200 dark:border-gray-700">
      <button class="text-xs px-2.5 py-1.5 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        @click="addPoint(selectedContourIdx, selectedPointIdx >= 0 ? selectedPointIdx : 0)"
      >+ 添加控制点</button>
      <button v-if="selectedPointIdx >= 0"
        class="text-xs px-2.5 py-1.5 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        @click="removePoint(selectedContourIdx, selectedPointIdx)"
      >- 删除控制点</button>
      <button
        class="text-xs px-2.5 py-1.5 rounded-lg bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
        @click="deleteContour(selectedContourIdx)"
      >删除区域</button>
    </div>

    <!-- Confirm button -->
    <div v-if="editable" class="absolute bottom-3 right-3">
      <button
        class="btn-primary px-4 py-2 rounded-xl text-sm shadow-lg"
        @click="handleConfirm"
      >确认轮廓</button>
    </div>

    <!-- Hint for drawing -->
    <div v-if="editable && mode === 'draw' && !isDrawing" class="absolute top-3 left-3 right-16 text-center">
      <span class="inline-block text-xs bg-white/90  backdrop-blur-sm text-gray-600 px-3 py-1.5 rounded-lg shadow-sm">
        在图片上划线圈出白斑区域
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
</style>
