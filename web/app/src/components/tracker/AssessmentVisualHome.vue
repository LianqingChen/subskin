<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import DigitalHuman from './DigitalHuman.vue'
import { PART_LABELS } from '@/constants/bodySites'
import { toProtectedFileUrl } from '@/utils/file-url'
import type { ObservationRecord } from './AssessmentRecords.vue'
const props = defineProps<{ bodySite: string; recent: ObservationRecord[]; loggedIn: boolean; loading: boolean }>()
const emit = defineEmits<{ select: [string]; camera: []; files: [File[]]; compare: []; history: []; needPart: []; continue: [ObservationRecord] }>()
const input = ref<HTMLInputElement | null>(null)
const scene = ref<HTMLElement | null>(null)
const scrollArea = ref<HTMLElement | null>(null)
const stack = ref<HTMLElement | null>(null)
const historyHead = ref<HTMLElement | null>(null)
const imageSize = ref(0)
const expanded = ref(false)
const inlineLayout = useMediaQuery('(min-width: 768px), (max-height: 600px)')
let resizeObserver: ResizeObserver | null = null
let userPositioned = false
/** 面板按内容高度收起或展开：展开时面板底部贴齐可视区底部，多余空间还给上方小人，不再留空白。 */
function maxScroll() {
  if (!scrollArea.value) return 0
  return Math.max(0, scrollArea.value.scrollHeight - scrollArea.value.clientHeight)
}
function syncScene() {
  if (!scene.value || !scrollArea.value || !stack.value || !historyHead.value) return
  if (inlineLayout.value) { imageSize.value = 0; expanded.value = false; userPositioned = false; return }
  const height = scene.value.clientHeight
  if (!height) return
  // 固定首屏露出功能卡、最近记录标题及内容开头，不受历史条数影响。
  const overviewHeight = historyHead.value.getBoundingClientRect().bottom - stack.value.getBoundingClientRect().top + 24
  const panelTop = Math.max(0, height - overviewHeight)
  // 小人沿用原始尺寸规则，卡片停靠位置不参与缩放；允许局部遮挡。
  imageSize.value = Math.min(scene.value.clientWidth, Math.max(0, height - 8), 576)
  const range = maxScroll()
  scrollArea.value.scrollTop = !userPositioned
    ? Math.max(0, Math.min(range, height - 60 - panelTop))
    : expanded.value ? range : Math.min(range, scrollArea.value.scrollTop)
  onScroll()
}
function rememberPosition() { userPositioned = true }
function rememberKeyboard(event: KeyboardEvent) {
  if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'].includes(event.key)) rememberPosition()
}
function onScroll() {
  expanded.value = !inlineLayout.value && !!scrollArea.value && scrollArea.value.scrollTop >= maxScroll() - 2
}
function togglePanel() {
  rememberPosition()
  scrollArea.value?.scrollTo({ top: expanded.value ? 0 : maxScroll(),
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
}
onMounted(() => {
  syncScene()
  resizeObserver = new ResizeObserver(syncScene)
  if (scene.value) resizeObserver.observe(scene.value)
  // 历史加载可改变滚动范围，但不改变尚未操作的默认首屏停靠位置。
  if (stack.value) resizeObserver.observe(stack.value)
})
onUnmounted(() => resizeObserver?.disconnect())
/** 最近记录：按拍摄时间倒序，默认展示最近 5 次。 */
const recent = computed(() => props.recent
  .filter(item => !props.bodySite || item.bodySite === props.bodySite || item.bodySite === PART_LABELS[props.bodySite] || (props.bodySite === 'neck' && item.bodySite === '颈部'))
  .sort((a, b) => (b.date || '').localeCompare(a.date || ''))
  .slice(0, 5))
function selected(event: Event) {
  const element = event.target as HTMLInputElement
  const files = Array.from(element.files || [])
  if (files.length) emit('files', files)
  element.value = ''
}
</script>
<template>
  <section ref="scene" class="assessment-visual-home relative mx-auto h-full min-h-0 w-full overflow-hidden">
    <div class="body-scene absolute inset-0 z-0">
      <div class="body-model mx-auto aspect-square max-w-full" :style="{ width: imageSize ? imageSize + 'px' : '100%' }">
        <DigitalHuman mode="rain" :show-parts="true" :active-part="bodySite" @select-part="emit('select', $event)" />
      </div>
    </div>

    <div ref="scrollArea" tabindex="0" role="region" aria-label="白斑记录和最近记录，可上下滑动"
      class="record-scroll pointer-events-none absolute inset-0 z-30 overflow-y-auto overscroll-y-contain focus-visible:outline focus-visible:outline-primary-500"
      @scroll.passive="onScroll" @wheel.passive="rememberPosition" @pointerdown="rememberPosition" @keydown="rememberKeyboard">
      <div class="scene-spacer h-[calc(100%_-_60px)]" aria-hidden="true"></div>
      <div ref="stack" class="record-stack pointer-events-auto mx-auto w-full max-w-xl space-y-3 rounded-t-3xl bg-gray-50 px-1 pb-2 shadow-[0_-5px_20px_rgba(0,0,0,0.07)] dark:bg-gray-900">
        <button type="button" class="panel-toggle flex min-h-[44px] w-full items-center justify-center gap-2 rounded-t-3xl text-xs text-gray-500 dark:text-gray-400"
          :aria-label="expanded ? '下滑收起记录面板' : '上滑展开记录面板'" :aria-expanded="expanded" @click="togglePanel">
          <span>{{ expanded ? '收起面板' : '展开记录面板' }}</span>
          <span class="h-1 w-10 rounded-full bg-gray-300 dark:bg-gray-600" aria-hidden="true"></span>
          <i :class="expanded ? 'ri-arrow-down-s-line' : 'ri-arrow-up-s-line'" aria-hidden="true"></i>
        </button>
      <!-- 平板/桌面：右栏标题，交代这一页能做什么 -->
      <header class="hidden pb-1 md:block">
        <h2 class="page-title">白斑记录</h2>
        <p class="page-subtitle leading-6">选部位、拍一张照片，AI 圈出白斑范围，留下下次对照的参照。</p>
      </header>
      <section aria-label="白斑记录" class="rounded-2xl border border-gray-200/80 bg-white p-4 shadow-sm md:p-5 md:shadow-none dark:border-gray-700 dark:bg-gray-800">
        <p class="mb-3 flex items-center gap-2 text-sm" role="status">
          <template v-if="bodySite">
            <i class="ri-map-pin-2-line text-base text-primary-600 dark:text-primary-300" aria-hidden="true"></i>
            <span class="text-gray-600 dark:text-gray-300">当前部位：<strong class="font-medium text-primary-700 dark:text-primary-200">{{ PART_LABELS[bodySite] || bodySite }}</strong></span>
          </template>
          <template v-else>
            <i class="ri-cursor-line text-base text-gray-400" aria-hidden="true"></i>
            <span class="text-gray-500 dark:text-gray-400">点选小人身上的部位标签</span>
          </template>
        </p>
        <div class="grid grid-cols-2 gap-2">
          <button class="flex min-h-[48px] items-center justify-center gap-2 rounded-xl bg-primary-600 px-3 text-white transition-colors hover:bg-primary-700" @click="emit('camera')">
            <i class="ri-camera-line text-xl" aria-hidden="true"></i><span class="text-sm font-medium">拍照记录</span>
          </button>
          <button class="flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-primary-100 bg-primary-50 px-3 text-primary-800 transition-colors hover:bg-primary-100 dark:border-primary-800 dark:bg-primary-900 dark:text-primary-200" @click="bodySite ? input?.click() : emit('needPart')">
            <i class="ri-image-add-line text-xl" aria-hidden="true"></i><span class="text-sm font-medium">从相册添加</span>
          </button>
        </div>
        <button class="mt-2 flex min-h-[48px] w-full items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 text-left transition-colors hover:border-primary-200 dark:border-gray-600 dark:bg-gray-900/40" @click="bodySite ? emit('compare') : emit('needPart')">
          <span class="relative flex h-8 w-10 shrink-0 items-center justify-center text-primary-600 dark:text-primary-300" aria-hidden="true"><i class="ri-image-line absolute left-0 -rotate-12 text-2xl opacity-45"></i><i class="ri-image-line absolute right-0 rotate-6 text-2xl"></i></span>
          <span class="min-w-0 flex-1"><span class="block text-sm font-semibold">白斑对比</span><span class="mt-0.5 block whitespace-nowrap text-xs text-gray-500 dark:text-gray-400">两张照片或两次记录</span></span><i class="ri-arrow-right-s-line shrink-0 text-xl text-gray-400" aria-hidden="true"></i>
        </button>
        <input ref="input" type="file" multiple accept="image/jpeg,image/png,image/webp" class="hidden" @change="selected" />
      </section>

      <section class="rounded-2xl border border-gray-200/80 bg-white px-4 md:px-5 dark:border-gray-700 dark:bg-gray-800">
        <div ref="historyHead" class="flex min-h-[48px] items-center justify-between"><h2 class="text-sm font-medium"><i class="ri-history-line mr-1.5 text-primary-600 dark:text-primary-300" aria-hidden="true"></i>最近记录</h2><button class="min-h-[44px] px-2 text-xs text-gray-500 dark:text-gray-400" @click="emit('history')">查看全部 <i class="ri-arrow-right-s-line" aria-hidden="true"></i></button></div>
        <p v-if="loading" role="status" class="pb-4 text-sm text-gray-500 dark:text-gray-400">正在加载最近记录…</p>
        <div v-else-if="recent.length" class="divide-y divide-gray-100 pb-2 dark:divide-gray-700">
          <div v-for="item in recent" :key="item.id" class="flex w-full items-center gap-2 py-1">
            <router-link :to="{ name: 'vasi-detail', params: { id: item.id } }" :aria-label="`查看${item.observation?.label || item.bodySite}的记录结果`" class="flex min-h-[52px] min-w-0 flex-1 items-center gap-3 rounded-lg py-2 text-left">
              <img v-if="item.imageUrl" :src="toProtectedFileUrl(item.imageUrl)" alt="记录照片缩略图" class="h-9 w-9 shrink-0 rounded-xl object-cover" />
              <span class="min-w-0 flex-1"><span class="block truncate text-sm font-medium">{{ item.observation?.label || item.bodySite }}</span><time :datetime="item.date" class="text-xs text-gray-500">{{ item.date }}</time></span>
              <i class="ri-arrow-right-s-line shrink-0 text-gray-400" aria-hidden="true"></i>
            </router-link>
            <button type="button" class="min-h-[44px] shrink-0 rounded-full bg-primary-50 px-3 text-xs font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-200" @click="emit('continue', item)">继续拍 <i class="ri-camera-line" aria-hidden="true"></i></button>
          </div>
        </div>
        <div v-else class="pb-4 text-sm leading-6 text-gray-500 dark:text-gray-400"><p>{{ !loggedIn ? '登录后可查看你的照片记录' : bodySite ? '最近记录中暂无这个部位的照片' : '从第一张照片开始，留下变化的参照' }}</p><button v-if="!loggedIn" class="min-h-11 text-primary-700 dark:text-primary-300" @click="emit('history')">登录查看记录 <i class="ri-arrow-right-line" aria-hidden="true"></i></button></div>
      </section>
      <MedicalDisclaimer variant="inline" message="照片记录仅供参考，不构成医疗建议" />
      </div>
    </div>
  </section>
</template>
<style scoped>
.record-scroll { scrollbar-width: thin; -webkit-overflow-scrolling: touch; }
.record-stack { touch-action: pan-y; }
.body-scene { padding-top: 8px; }
.record-stack > .panel-toggle + section { margin-top: 0; }
@media (min-width: 768px), (max-height: 600px) {
  .assessment-visual-home { height: auto; overflow: visible; display: grid; gap: 1.5rem; padding-block: 1.5rem; }
  .body-scene { position: relative; inset: auto; min-width: 0; padding-top: 0; }
  .body-model { width: 100% !important; max-width: 32rem; }
  .record-scroll { position: relative; inset: auto; overflow: visible; pointer-events: auto; }
  .scene-spacer, .panel-toggle { display: none; }
  .record-stack { min-height: 0; padding: 0; box-shadow: none; background: transparent; }
}
/* 平板/桌面：左侧小人放进白色卡片，尺寸随视口高度收紧，保证首屏完整；右侧固定宽度的操作栏 */
@media (min-width: 768px) {
  .assessment-visual-home { grid-template-columns: minmax(0, 1fr) minmax(0, 20rem); align-items: start; padding-block: 1.5rem 2.5rem; }
  .body-scene { display: flex; justify-content: center; border: 1px solid rgb(229 231 235 / 0.8); border-radius: 1rem; background: #fff; padding: 1rem; }
  .body-model { max-width: min(32rem, max(21rem, calc(100dvh - 56px - 53px - 6rem))); }
  .record-stack { max-width: none; }
}
@media (min-width: 1024px) {
  .assessment-visual-home { grid-template-columns: minmax(0, 1fr) minmax(0, 24rem); gap: 2rem; }
  /* 吸附在全站顶栏（56px）+ 记录工具条（53px）下方 */
  .record-stack { position: sticky; top: calc(56px + 53px + 1.5rem); }
}
@media (min-width: 768px) {
  :global(html.dark) .body-scene { border-color: rgb(55 65 81); background: rgb(31 41 55); }
}
@media (max-width: 767px) and (max-height: 600px) {
  .body-model { max-width: 15rem; }
  .assessment-visual-home { padding-bottom: calc(5rem + env(safe-area-inset-bottom, 0px)); }
}
</style>
