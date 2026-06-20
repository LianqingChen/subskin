<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '@/api/client'

export interface CircleSelection {
  id: string
  centerX: number
  centerY: number
  radiusX: number
  radiusY: number
  refinedPolygon?: number[][]
  confidence?: number
  areaPercent?: number
}

const props = defineProps<{
  imageUrl: string
  cacheKey: string
  imageWidth: number
  imageHeight: number
}>()

const emit = defineEmits<{
  (e: 'update:selections', selections: CircleSelection[]): void
  (e: 'refined', result: CircleSelection): void
}>()

const containerRef = ref<HTMLDivElement>()
const circles = ref<CircleSelection[]>([])
const drawing = ref(false)
const startX = ref(0)
const startY = ref(0)
const currentRx = ref(0)
const currentRy = ref(0)
const loading = ref(false)
const displayW = ref(0)
const displayH = ref(0)

const refinedCircles = computed(() => circles.value.filter(c => c.refinedPolygon))

function onPointerDown(e: PointerEvent) {
  if (loading.value) return
  const rect = containerRef.value!.getBoundingClientRect()
  startX.value = e.clientX - rect.left
  startY.value = e.clientY - rect.top
  currentRx.value = 0
  currentRy.value = 0
  drawing.value = true
  ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!drawing.value) return
  const rect = containerRef.value!.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top
  currentRx.value = Math.abs(cx - startX.value)
  currentRy.value = Math.abs(cy - startY.value)
}

async function onPointerUp(e: PointerEvent) {
  if (!drawing.value) return
  drawing.value = false

  if (currentRx.value < 15 || currentRy.value < 15) return

  const rect = containerRef.value!.getBoundingClientRect()
  displayW.value = rect.width
  displayH.value = rect.height

  const normCenterX = (startX.value + (e.clientX - rect.left)) / 2 / rect.width
  const normCenterY = (startY.value + (e.clientY - rect.top)) / 2 / rect.height
  const normRx = currentRx.value / rect.width
  const normRy = currentRy.value / rect.height

  const circle: CircleSelection = {
    id: Date.now().toString(),
    centerX: startX.value + (e.clientX - rect.left - startX.value) / 2,
    centerY: startY.value + (e.clientY - rect.top - startY.value) / 2,
    radiusX: currentRx.value,
    radiusY: currentRy.value,
  }

  circles.value.push(circle)
  await refineCircle(circle, normCenterX, normCenterY, normRx, normRy)
}

async function refineCircle(
  circle: CircleSelection,
  normCX: number,
  normCY: number,
  normRx: number,
  normRy: number,
) {
  loading.value = true
  try {
    const { data: res } = await apiClient.post('/vasi/promptable/refine-circle', {
      cache_key: props.cacheKey,
      circle: {
        center_x: normCX,
        center_y: normCY,
        radius_x: normRx,
        radius_y: normRy,
      },
    })

    const idx = circles.value.findIndex(c => c.id === circle.id)
    if (idx !== -1) {
      const polygon = res.data.mask_polygon as number[][]
      const converted = polygon.map(([px, py]) => [px * displayW.value, py * displayH.value])
      circles.value[idx] = {
        ...circles.value[idx],
        refinedPolygon: converted,
        confidence: res.data.confidence,
        areaPercent: res.data.area_percent_in_image,
      }
      emit('update:selections', circles.value)
      emit('refined', circles.value[idx])
    }
  } catch (err) {
    console.error('refine-circle failed:', err)
  } finally {
    loading.value = false
  }
}

function undoLast() {
  circles.value.pop()
  emit('update:selections', circles.value)
}

function clearAll() {
  circles.value = []
  emit('update:selections', circles.value)
}

onMounted(() => {
  if (containerRef.value) {
    const rect = containerRef.value.getBoundingClientRect()
    displayW.value = rect.width
    displayH.value = rect.height
  }
})
</script>

<template>
  <div ref="containerRef" class="relative select-none" style="touch-action: none">
    <img :src="imageUrl" class="max-w-full block" draggable="false" />

    <svg class="absolute inset-0 w-full h-full pointer-events-none">
      <ellipse
        v-for="c in circles"
        :key="c.id"
        :cx="c.centerX"
        :cy="c.centerY"
        :rx="c.radiusX"
        :ry="c.radiusY"
        fill="none"
        stroke="#ef4444"
        stroke-dasharray="6 4"
        stroke-width="2"
        opacity="0.7"
      />
      <polygon
        v-for="c in refinedCircles"
        :key="'r-' + c.id"
        :points="c.refinedPolygon?.map(p => p.join(',')).join(' ') || ''"
        fill="rgba(244, 114, 182, 0.25)"
        stroke="#F472B6"
        stroke-width="2"
      />
      <ellipse
        v-if="drawing"
        :cx="startX + currentRx"
        :cy="startY + currentRy"
        :rx="currentRx"
        :ry="currentRy"
        fill="none"
        stroke="#ef4444"
        stroke-dasharray="6 4"
        stroke-width="2"
        opacity="0.5"
      />
    </svg>

    <div
      class="absolute inset-0 cursor-crosshair"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    />

    <div class="absolute top-2 right-2 flex gap-1.5 z-10">
      <button
        class="w-8 h-8 rounded-lg bg-white/80 backdrop-blur flex items-center justify-center text-gray-600 shadow text-sm"
        title="撤销"
        @click.stop="undoLast"
        :disabled="circles.length === 0"
      >
        <i class="ri-arrow-go-back-line"></i>
      </button>
      <button
        class="w-8 h-8 rounded-lg bg-white/80 backdrop-blur flex items-center justify-center text-red-500 shadow text-sm"
        title="清空"
        @click.stop="clearAll"
        :disabled="circles.length === 0"
      >
        <i class="ri-delete-bin-line"></i>
      </button>
    </div>

    <div v-if="loading" class="absolute inset-0 bg-black/20 flex items-center justify-center z-20">
      <div class="bg-white rounded-xl px-4 py-2 shadow-lg flex items-center gap-2">
        <i class="ri-loader-4-line animate-spin text-primary-500"></i>
        <span class="text-sm text-gray-700">AI 精修中...</span>
      </div>
    </div>

    <div v-if="circles.length > 0" class="absolute bottom-2 left-2 z-10">
      <div class="bg-white/90 backdrop-blur rounded-lg px-2 py-1 text-xs text-gray-600 shadow">
        已圈选 {{ circles.length }} 个区域
        <span v-if="refinedCircles.length > 0" class="text-primary-600 ml-1">
          · AI 已精修 {{ refinedCircles.length }} 个
        </span>
      </div>
    </div>
  </div>
</template>
