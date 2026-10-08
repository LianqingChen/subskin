<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AlignmentTransform } from '@/types/comparison-alignment'
import { alignmentMatrix, identityAlignment } from '@/utils/comparison-alignment'
import { useAlignmentImages } from '@/composables/useAlignmentImages'
const props = defineProps<{ beforeUrl: string; afterUrl: string; modelValue: AlignmentTransform; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [AlignmentTransform]; ready: [boolean] }>()
const images = useAlignmentImages(props), opacity = ref(50)
const ready = computed(() => !!images.before.value && !!images.after.value && !images.loading.value && !images.error.value)
const matrix = computed(() => images.before.value && images.after.value ? alignmentMatrix(images.before.value, images.after.value, props.modelValue).join(' ') : '')
const ratio = computed(() => images.before.value ? images.before.value.width / images.before.value.height : 1)
watch(ready, value => emit('ready', value), { immediate: true })
watch(() => [props.beforeUrl, props.afterUrl], () => { drag = null; opacity.value = 50 })
let drag: { id: number; x: number; y: number; width: number; height: number; start: AlignmentTransform } | null = null
function change(key: keyof AlignmentTransform, raw: number) {
  if (props.disabled || !ready.value) return
  const limits = { scale: [.25, 4], rotation: [-180, 180], x: [-1, 1], y: [-1, 1] }[key]
  emit('update:modelValue', { ...props.modelValue, [key]: Math.min(limits[1], Math.max(limits[0], raw)) })
}
function input(key: keyof AlignmentTransform, event: Event) { change(key, Number((event.target as HTMLInputElement).value)) }
function down(event: PointerEvent) {
  if (props.disabled || !ready.value || drag || !event.isPrimary || event.button !== 0) return
  const element = event.currentTarget as HTMLElement, box = element.querySelector('svg')?.getBoundingClientRect()
  if (!box?.width || !box.height) return
  drag = { id: event.pointerId, x: event.clientX, y: event.clientY, width: box.width, height: box.height, start: { ...props.modelValue } }
  element.setPointerCapture(event.pointerId)
}
function move(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.id || props.disabled) return
  emit('update:modelValue', { ...drag.start, x: Math.max(-1, Math.min(1, drag.start.x + (event.clientX - drag.x) / drag.width)), y: Math.max(-1, Math.min(1, drag.start.y + (event.clientY - drag.y) / drag.height)) })
}
function up(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.id) return
  drag = null
  const element = event.currentTarget as HTMLElement
  if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId)
}
function key(event: KeyboardEvent) {
  const directions: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }
  const direction = directions[event.key]
  if (!direction || props.disabled || !ready.value) return
  event.preventDefault()
  const amount = event.shiftKey ? .05 : .01
  change(direction[0] ? 'x' : 'y', (direction[0] ? props.modelValue.x : props.modelValue.y) + (direction[0] || direction[1]) * amount)
}
</script>
<template>
  <section aria-label="手动对齐照片" class="space-y-3">
    <p class="text-sm text-gray-500 dark:text-gray-400">第一张固定，拖动第二张并调整旋转、缩放，尽量对齐周围皮肤纹理。</p>
    <div v-if="images.loading.value || images.error.value" role="status" class="rounded-xl bg-gray-50 p-4 text-sm dark:bg-gray-900">{{ images.error.value || '正在加载照片…' }}<button v-if="images.error.value" type="button" class="min-h-[44px] px-3 text-primary-700 dark:text-primary-300" @click="images.load">重试</button></div>
    <div v-else-if="images.before.value && images.after.value" data-swipe-ignore tabindex="0" role="group" aria-label="拖动调整第二张照片，方向键也可移动" class="alignment-stage mx-auto touch-none select-none overflow-hidden rounded-xl border border-gray-200 bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-500 dark:border-gray-700 dark:bg-gray-900" :style="{ '--alignment-ratio': ratio }" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up" @lostpointercapture="up" @keydown="key">
      <svg class="block h-full w-full" :viewBox="`0 0 ${images.before.value.width} ${images.before.value.height}`" role="img" aria-label="两张照片的对齐叠影">
        <image :href="images.beforeUrl.value" :width="images.before.value.width" :height="images.before.value.height" />
        <image :href="images.afterUrl.value" :width="images.after.value.width" :height="images.after.value.height" :transform="`matrix(${matrix})`" :opacity="opacity / 100" />
      </svg>
    </div>
    <fieldset :disabled="disabled || !ready" class="grid min-w-0 gap-2 sm:grid-cols-2">
      <label class="flex min-h-[44px] min-w-0 items-center gap-3 text-sm"><span class="w-24 shrink-0">旋转 {{ Math.round(modelValue.rotation) }}°</span><input aria-label="旋转角度" type="range" min="-180" max="180" step="1" :value="modelValue.rotation" class="alignment-range h-11 min-w-0 flex-1" @input="input('rotation', $event)" /></label>
      <label class="flex min-h-[44px] min-w-0 items-center gap-3 text-sm"><span class="w-24 shrink-0">缩放 {{ Math.round(modelValue.scale * 100) }}%</span><input aria-label="缩放比例" type="range" min="0.25" max="4" step="0.01" :value="modelValue.scale" class="alignment-range h-11 min-w-0 flex-1" @input="input('scale', $event)" /></label>
      <label class="flex min-h-[44px] min-w-0 items-center gap-3 text-sm"><span class="w-24 shrink-0">叠影 {{ opacity }}%</span><input v-model.number="opacity" aria-label="叠影透明度" type="range" min="0" max="100" step="1" class="alignment-range h-11 min-w-0 flex-1" /></label>
      <button type="button" class="btn-ghost min-h-[44px] rounded-lg text-sm" @click="emit('update:modelValue', identityAlignment())"><i class="ri-restart-line mr-1" aria-hidden="true"></i>重置对齐</button>
    </fieldset>
  </section>
</template>
<style scoped>
.alignment-stage { aspect-ratio: var(--alignment-ratio); width: min(100%, calc(52dvh * var(--alignment-ratio))); max-width: 640px; }
.alignment-range { accent-color: var(--color-primary-600); }
</style>
