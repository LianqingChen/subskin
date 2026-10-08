<script setup lang="ts">
import { computed, watch } from 'vue'
import type { CSSProperties } from 'vue'
import type { StoryPeelArtwork } from '@/types/story-peel'
import { useStoryPeelSource } from '@/composables/useStoryPeelSource'
import { useStoryPeelMotion } from '@/composables/useStoryPeelMotion'
import { storyArtworkRect } from '@/utils/assessment-story/geometry'

const props = defineProps<{
  image?: string | null; skin?: string | null; lesion?: string | null
  poster: string; title: string; artwork: StoryPeelArtwork | null; selection: string
}>()
const source = useStoryPeelSource(props)
const { progress, set, animate, toggle } = useStoryPeelMotion()
const ready = computed(() => !!source.url.value && !!props.artwork)
const caption = computed(() => progress.value === 0 ? '这片轮廓，会变成什么？' : progress.value === 1 ? '灵感来自你的这片白斑' : '同一片轮廓，正在变成风景')
const photoOpacity = computed(() => 1 - Math.max(0, Math.min(1, (progress.value - .4) / .4)))
const posterOpacity = computed(() => Math.max(0, Math.min(1, (progress.value - .5) / .4)))
const origin = computed(() => {
  const art = props.artwork
  if (!art) return { x: 0, y: 0, width: 0, height: 0 }
  const width = Math.min(1080, 1440 * source.aspect.value), height = width / source.aspect.value
  return { x: (1080 - width) / 2 + art.bounds.x / art.width * width,
    y: (1440 - height) / 2 + art.bounds.y / art.height * height,
    width: art.bounds.width / art.width * width, height: art.bounds.height / art.height * height }
})
function rectStyle(rect: { x: number; y: number; width: number; height: number }): CSSProperties {
  return { left: `${rect.x / 1080 * 100}%`, top: `${rect.y / 1440 * 100}%`, width: `${rect.width / 1080 * 100}%`, height: `${rect.height / 1440 * 100}%` }
}
const imprintStyle = computed<CSSProperties>(() => ({ ...rectStyle(origin.value),
  maskImage: `url("${props.artwork?.url}")`, WebkitMaskImage: `url("${props.artwork?.url}")`, opacity: photoOpacity.value * .35 }))
const stickerStyle = computed<CSSProperties>(() => {
  const art = props.artwork
  if (!art) return {}
  const destination = storyArtworkRect(art.bounds)
  const from = origin.value, t = Math.min(1, progress.value / .92), lift = Math.sin(t * Math.PI)
  return { ...rectStyle({ x: from.x + (destination.x - from.x) * t, y: from.y + (destination.y - from.y) * t - lift * 60,
    width: from.width + (destination.width - from.width) * t, height: from.height + (destination.height - from.height) * t }),
    opacity: Math.min(1, progress.value / .12), transform: `perspective(800px) rotateX(${lift * 22}deg) rotate(${-lift * 6}deg)`,
    filter: `drop-shadow(0 ${lift * 12}px ${lift * 10}px rgb(0 0 0 / .22))` }
})
let drag: { id: number; x: number; y: number; from: number; span: number; moved: boolean } | null = null
let suppressClick = false
function startDrag(event: PointerEvent) {
  if (!ready.value || drag || !event.isPrimary || event.button !== 0) return
  const handle = event.currentTarget as HTMLElement
  set(progress.value); suppressClick = false
  drag = { id: event.pointerId, x: event.clientX, y: event.clientY, from: progress.value,
    span: Math.max(100, (handle.parentElement?.clientWidth || 300) * .65), moved: false }
  handle.setPointerCapture(event.pointerId)
}
function moveDrag(event: PointerEvent) {
  if (!drag || drag.id !== event.pointerId) return
  const distance = Math.hypot(event.clientX - drag.x, event.clientY - drag.y)
  if (distance < 5 && !drag.moved) return
  drag.moved = true
  set(drag.from + distance / drag.span * (drag.from >= .5 ? -1 : 1))
}
function endDrag(event: PointerEvent) {
  if (!drag || drag.id !== event.pointerId) return
  const moved = drag.moved, handle = event.currentTarget as HTMLElement
  drag = null; suppressClick = moved
  if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId)
  if (moved || event.type !== 'pointerup') animate(progress.value >= .5 ? 1 : 0)
}
function clickHandle() { if (suppressClick) { suppressClick = false; return }; toggle() }
function scrub(event: Event) { set(Number((event.target as HTMLInputElement).value) / 100) }
watch(() => [props.selection, props.image, props.lesion], () => { drag = null; suppressClick = false; set(0) })
</script>

<template>
  <figure data-swipe-ignore class="min-w-0">
    <div class="peel-stage relative isolate mx-auto overflow-hidden rounded-xl bg-gray-50 dark:bg-gray-900">
      <img :src="poster" :alt="`轮廓创意卡：${title}`" width="1080" height="1440" class="absolute inset-0 h-full w-full object-contain" :style="{ opacity: ready ? posterOpacity : 1 }" />
      <template v-if="ready">
        <img :src="source.url.value" alt="这张创意图的来源照片，浅粉涂层为已确认的白斑范围" class="absolute inset-0 h-full w-full object-contain" :style="{ opacity: photoOpacity }" />
        <span class="peel-imprint pointer-events-none absolute bg-primary-300" :style="imprintStyle" aria-hidden="true"></span>
        <img v-if="artwork && progress < 1" :src="artwork.url" alt="" aria-hidden="true" draggable="false" class="peel-sticker pointer-events-none absolute" :style="stickerStyle" />
        <button type="button" :aria-label="progress >= .5 ? '把创意贴纸放回白斑涂层' : '拖动或点击，揭下创意贴纸'" class="peel-handle absolute right-2 top-2 flex h-12 w-12 touch-none items-center justify-center rounded-bl-2xl rounded-tr-lg border border-primary-200 bg-white text-xl text-primary-700 shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-500 dark:border-primary-600 dark:bg-gray-800 dark:text-primary-200" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="endDrag" @pointercancel="endDrag" @lostpointercapture="endDrag" @click="clickHandle">
          <i :class="progress >= .5 ? 'ri-arrow-go-back-line' : 'ri-sticky-note-line'" aria-hidden="true"></i>
        </button>
      </template>
    </div>
    <figcaption class="mt-3">
      <div v-if="ready" class="flex items-center gap-3">
        <img :src="source.url.value" alt="白斑涂层来源缩略图" width="48" height="56" class="h-14 w-12 shrink-0 rounded-lg bg-gray-100 object-contain dark:bg-gray-900" />
        <div class="min-w-0"><p class="text-xs text-gray-500 dark:text-gray-400">白斑涂层 <i class="ri-arrow-right-line" aria-hidden="true"></i> 创意贴纸</p><p class="mt-1 text-sm text-primary-800 dark:text-primary-200" role="status">{{ caption }}</p></div>
      </div>
      <p v-else role="status" class="text-xs leading-5 text-gray-500 dark:text-gray-400">{{ source.loading.value ? '正在准备轮廓来源…' : source.error.value || '轮廓互动暂不可用，创意图片仍可保存' }}<button v-if="source.error.value" type="button" class="min-h-[44px] px-2 text-primary-700 dark:text-primary-300" @click="source.load">重试来源</button></p>
      <div v-if="ready" class="mt-2 flex items-center gap-3">
        <label class="flex min-h-[44px] min-w-0 flex-1 items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span class="shrink-0">拖动揭开</span>
          <input type="range" min="0" max="100" step="1" :value="Math.round(progress * 100)" :aria-valuetext="`${Math.round(progress * 100)}%，${progress < .5 ? '白斑涂层' : '创意贴纸'}`" class="peel-range h-11 min-w-0 flex-1 cursor-pointer" @input="scrub" />
        </label>
        <button type="button" class="min-h-[44px] shrink-0 rounded-lg px-2 text-sm font-medium text-primary-700 hover:bg-primary-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-500 dark:text-primary-300 dark:hover:bg-primary-900" @click="toggle">{{ progress >= .5 ? '查看来源' : '揭下贴纸' }}</button>
      </div>
    </figcaption>
  </figure>
</template>

<style scoped>
.peel-stage { aspect-ratio: 3 / 4; width: min(100%, 420px); }
.peel-imprint { mask-size: 100% 100%; -webkit-mask-size: 100% 100%; mask-repeat: no-repeat; }
.peel-sticker { transform-origin: center; }
.peel-range { accent-color: var(--color-primary-600); }
.peel-handle { user-select: none; -webkit-user-select: none; }
@media (prefers-reduced-motion: reduce) { .peel-sticker { transform: none !important; filter: none !important; } }
</style>
