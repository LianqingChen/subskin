<script setup lang="ts">
/**
 * 画笔/橡皮粗细调节 — 竖向弹层方案。
 *
 * 横向空间不足（普通模式单行工具条、全屏模式第二行都排不下横向滑杆），
 * 因此改为紧凑触发按钮（尺子图标 + 当前数值），点击后在按钮上方弹出竖向调节弹层：
 * 「＋」按钮 + 自绘竖向滑杆（pointer 事件驱动，上大下小，兼容 iOS Safari——
 * transform 旋转的原生 range 滑杆在 Chromium 下无法响应指针/点击）+ 「－」按钮 + 数值；
 * 点弹层外任意处关闭；滑杆支持键盘方向键微调。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  brushSize: number
  /** 全屏模式：深色工具条配色 */
  fullscreen?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:brushSize', size: number): void
}>()

const MIN = 8
const MAX = 80
const STEP = 4
/** 滑杆可拖动内区高度（去上下各 4px 内边距） */
const TRACK_INNER = 140

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const trackRef = ref<HTMLElement | null>(null)
const dragging = ref(false)

/**
 * 点击组件外任意处关闭弹层。
 * 不用 fixed 透明遮罩：工具条带 backdrop-filter/sticky（会改变 fixed 的包含块，
 * 遮罩只盖住工具条条带），改为 document 捕获阶段监听更可靠。
 */
function onDocPointerDown(e: PointerEvent) {
  if (!open.value) return
  const t = e.target as Node | null
  if (t && rootRef.value && !rootRef.value.contains(t)) open.value = false
}

onMounted(() => document.addEventListener('pointerdown', onDocPointerDown, true))
onUnmounted(() => document.removeEventListener('pointerdown', onDocPointerDown, true))

function clamp(v: number) {
  return Math.min(MAX, Math.max(MIN, v))
}

/** 依据指针 Y 坐标换算粗细（上大下小） */
function valueFromY(y: number) {
  const el = trackRef.value
  if (!el) return props.brushSize
  const r = el.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (r.bottom - 4 - y) / TRACK_INNER))
  return clamp(MIN + Math.round((ratio * (MAX - MIN)) / STEP) * STEP)
}

function onTrackDown(e: PointerEvent) {
  e.preventDefault()
  dragging.value = true
  try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId) } catch { /* 忽略 */ }
  emit('update:brushSize', valueFromY(e.clientY))
}

function onTrackMove(e: PointerEvent) {
  if (!dragging.value) return
  emit('update:brushSize', valueFromY(e.clientY))
}

function onTrackUp() {
  dragging.value = false
}

function nudge(delta: number) {
  emit('update:brushSize', clamp(props.brushSize + delta))
}

const fillPercent = computed(() => ((props.brushSize - MIN) / (MAX - MIN)) * 100)
const fillHeight = computed(() => `${Math.round((TRACK_INNER * fillPercent.value) / 100)}px`)
const thumbBottom = computed(() => `${Math.round(4 + (TRACK_INNER * fillPercent.value) / 100 - 9)}px`)
</script>

<template>
  <div ref="rootRef" class="relative shrink-0">
    <!-- 触发按钮：尺子 + 当前数值 -->
    <button
      type="button"
      class="h-10 px-2 min-w-[56px] rounded-lg flex items-center justify-center gap-1 transition-colors"
      :class="fullscreen
        ? 'bg-white/10 hover:bg-white/15 text-gray-100'
        : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300'"
      :title="`画笔粗细（当前 ${brushSize}）`"
      aria-label="画笔粗细"
      @click="open = !open"
    >
      <i class="ri-ruler-line text-sm"></i>
      <span class="text-xs tabular-nums">{{ brushSize }}</span>
    </button>

    <!-- 竖向调节弹层：＋ / 竖向滑杆（上大下小）/ － / 数值 -->
    <template v-if="open">
      <div
        class="absolute bottom-[calc(100%+10px)] left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-0.5 rounded-2xl p-2 shadow-xl border"
        :class="fullscreen
          ? 'bg-gray-800 border-white/10'
          : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-600'"
      >
        <button
          type="button"
          class="size-btn"
          :class="fullscreen ? 'text-gray-100 hover:bg-white/10' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'"
          aria-label="加粗"
          @click="nudge(STEP)"
        >
          <i class="ri-add-line"></i>
        </button>

        <!-- 自绘竖向滑杆：pointer 事件驱动，点击/拖动任意位置直接跳转或连续调节 -->
        <div
          ref="trackRef"
          class="brush-track"
          role="slider"
          tabindex="0"
          :aria-label="'画笔粗细'"
          :aria-valuemin="MIN"
          :aria-valuemax="MAX"
          :aria-valuenow="brushSize"
          :aria-valuetext="String(brushSize)"
          @pointerdown="onTrackDown"
          @pointermove="onTrackMove"
          @pointerup="onTrackUp"
          @pointercancel="onTrackUp"
          @keydown.up.prevent="nudge(STEP)"
          @keydown.right.prevent="nudge(STEP)"
          @keydown.down.prevent="nudge(-STEP)"
          @keydown.left.prevent="nudge(-STEP)"
        >
          <div class="brush-rail" aria-hidden="true"></div>
          <div class="brush-fill" aria-hidden="true" :style="{ height: fillHeight }"></div>
          <div class="brush-thumb" aria-hidden="true" :style="{ bottom: thumbBottom }"></div>
        </div>

        <button
          type="button"
          class="size-btn"
          :class="fullscreen ? 'text-gray-100 hover:bg-white/10' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'"
          aria-label="变细"
          @click="nudge(-STEP)"
        >
          <i class="ri-subtract-line"></i>
        </button>

        <span class="text-[11px] tabular-nums" :class="fullscreen ? 'text-gray-300' : 'text-gray-500 dark:text-gray-400'">
          {{ brushSize }}
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.size-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 竖向滑杆：28px 宽热区（触控友好），视觉轨道 6px 居中 */
.brush-track {
  position: relative;
  width: 28px;
  height: 148px;
  display: flex;
  justify-content: center;
  cursor: pointer;
  touch-action: none;
  outline: none;
  border-radius: 8px;
}
.brush-track:focus-visible {
  box-shadow: 0 0 0 2px var(--color-primary-400);
}
.brush-rail {
  position: absolute;
  top: 4px;
  bottom: 4px;
  width: 6px;
  border-radius: 3px;
  background: rgba(148, 163, 184, 0.45);
}
.brush-fill {
  position: absolute;
  bottom: 4px;
  width: 6px;
  border-radius: 3px;
  background: var(--color-primary-500);
}
.brush-thumb {
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid var(--color-primary-500);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}
</style>
