<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

withDefaults(defineProps<{
  beforeUrl: string
  afterUrl: string
  beforeLabel?: string
  afterLabel?: string
  alt?: string
}>(), {
  beforeLabel: '之前',
  afterLabel: '现在',
  alt: '前后对比',
})

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

function onPointerDown(e: PointerEvent) {
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  isDragging.value = true
  updateFromEvent(e.clientX)
}
function onPointerMove(e: PointerEvent) {
  if (!isDragging.value) return
  updateFromEvent(e.clientX)
}
function onPointerUp() {
  isDragging.value = false
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'ArrowLeft') sliderPos.value = Math.max(0, sliderPos.value - 2)
  if (e.key === 'ArrowRight') sliderPos.value = Math.min(100, sliderPos.value + 2)
}

onMounted(() => {
  window.addEventListener('pointerup', onPointerUp)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerup', onPointerUp)
})
</script>

<template>
  <div
    ref="containerRef"
    class="relative w-full aspect-square overflow-hidden rounded-2xl bg-gray-900 select-none touch-none"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
  >
    <img
      :src="afterUrl"
      :alt="alt"
      class="absolute inset-0 w-full h-full object-cover pointer-events-none"
      draggable="false"
    />
    <div class="absolute inset-0 pointer-events-none" :style="clipStyle">
      <img
        :src="beforeUrl"
        :alt="alt"
        class="absolute inset-0 w-full h-full object-cover"
        draggable="false"
      />
    </div>

    <span
      class="absolute top-3 left-3 text-xs font-medium px-2 py-1 rounded-full bg-black/55 text-white pointer-events-none"
    >{{ beforeLabel }}</span>
    <span
      class="absolute top-3 right-3 text-xs font-medium px-2 py-1 rounded-full bg-black/55 text-white pointer-events-none"
    >{{ afterLabel }}</span>

    <div
      class="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(0,0,0,0.5)] pointer-events-none"
      :style="{ left: `${sliderPos}%` }"
    />
    <button
      type="button"
      role="slider"
      :aria-valuenow="Math.round(sliderPos)"
      aria-valuemin="0"
      aria-valuemax="100"
      class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-9 h-9 rounded-full bg-white shadow-lg flex items-center justify-center cursor-ew-resize focus:outline-none focus:ring-2 focus:ring-primary-400"
      :style="{ left: `${sliderPos}%` }"
      @keydown="onKeyDown"
    >
      <i class="ri-arrow-left-right-line text-gray-700"></i>
    </button>
  </div>
</template>
