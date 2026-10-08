<script setup lang="ts">
/**
 * Step 1: 拍照评估（功能卡片 v4 —— 双功能块布局）
 *
 * 布局（单屏，无页面滚动、无卡片内部滚动）：
 *   1. 数字小人 — 全幅铺底（略收边距），部位标签清晰可点
 *   2. 功能卡片 — 一个完整单元，高度始终自适应内容：
 *      - 整卡任意位置按住上下拖动（translateY 平移，丝滑跟手），
 *        松手停在原地；纵向为主才判定为拖卡，不影响按钮点击与历史卡横滑
 *      - 卡内两大一级功能模块（各为独立描边底容器 + 编号徽章 1/2 +
 *        加粗模块标题 + 模块级历史入口，层级明确高于模块内的按钮）：
 *        ① 单次测评（主题色容器）—— 拍 1 张照片，AI 分析当前白斑（主流程）；
 *           「历史」= 浏览测评历史
 *        ② 多选对比（暖色容器）—— 选 2–4 张照片，生成变化对比报告；
 *           历史测评照片（复用单次测评）或 上传相册照片（无需先做测评），
 *           两条路径「或」分隔、殊途同归；「历史」= 直接进入多选模式勾选历史记录做对比；
 *           块间连接线提示两功能的关联
 *      - 选中照片后隐藏功能②，聚焦单次测评主流程；移除照片后恢复
 *      - 选定部位 / 添加照片后卡片自动回位，保证主流程控件可见
 */
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import DigitalHuman from '@/components/tracker/DigitalHuman.vue'
import BodyPartCamera from '@/components/tracker/BodyPartCamera.vue'
import { useToast } from '@/composables/useToast'
import { PART_LABELS } from '@/constants/bodySites'
import type { QualityCheckResult } from '@/api/vasi'

const props = defineProps<{
  selectedBodySite: string; imagePreview: string | null
  qualityResult: QualityCheckResult | null; qualityChecking: boolean
  isSubmitting?: boolean; uploadStage?: string
}>()

const emit = defineEmits<{
  selectPart: [site: string]; uploadFile: [event: Event]; openCamera: []
  cameraCapture: [file: File, meta?: { hasReferenceCard?: boolean }]; removeImage: []; submit: []; cancel: []
  multiHistory: []; multiGallery: []; openHistory: []; compareHistory: []
}>()

const showCamera = ref(false); const fileInputEl = ref<HTMLInputElement | null>(null)
const toast = useToast()
const submittingLabel = computed(() => ({ uploading:'上传中', segmenting:'AI识别中', analyzing:'AI分析中' }[props.uploadStage||''] || '分析中'))

/** 多选对比块：仅在未进入单次测评流程时展示（选中照片/分析中隐藏，聚焦主流程） */
const showCompareSection = computed(() => !props.imagePreview && !props.isSubmitting)

/** 拍照 / 相册统一样式（不高亮拍照，功能按钮视觉一致） */
const neutralBtnClass = computed(() => props.imagePreview
  ? 'min-h-[44px] font-medium bg-gray-50 hover:bg-gray-100 dark:bg-gray-700 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300'
  : 'min-h-[48px] font-medium bg-gray-50 hover:bg-gray-100 dark:bg-gray-700 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200')

// ── AI 分析倒计时（预估约 2 分钟，避免用户误以为页面卡住）──
const ANALYZE_ESTIMATE_SECONDS = 120
const remainingSeconds = ref(ANALYZE_ESTIMATE_SECONDS)
const elapsedSeconds = ref(0)
let analyzeTimer: ReturnType<typeof setInterval> | null = null
const countdownText = computed(() => remainingSeconds.value > 0 ? `预计${remainingSeconds.value}秒` : `已等待${elapsedSeconds.value}秒`)

watch(() => props.isSubmitting, (submitting) => {
  if (analyzeTimer) { clearInterval(analyzeTimer); analyzeTimer = null }
  remainingSeconds.value = ANALYZE_ESTIMATE_SECONDS
  elapsedSeconds.value = 0
  if (submitting) {
    analyzeTimer = setInterval(() => {
      elapsedSeconds.value += 1
      if (remainingSeconds.value > 0) remainingSeconds.value -= 1
    }, 1000)
  }
})

function triggerUpload() {
  if (!props.selectedBodySite) { toast.warning('请先选择身体部位'); return }
  fileInputEl.value?.click()
}

function openCamera() {
  if (!props.selectedBodySite) { toast.warning('请先选择身体部位'); return }
  showCamera.value = true
}
function onCameraCapture(f: File, m?: { hasReferenceCard?: boolean }) { emit('cameraCapture', f, m); showCamera.value = false }

// ── 功能卡片：整卡平移拖动（无内部滚动）──
const rootRef = ref<HTMLElement | null>(null)
const sheetRef = ref<HTMLElement | null>(null)
/** 卡片向下平移量（px）。0 = 完全展示；越大露出的小人越多 */
const sheetOffset = ref(0)
const dragging = ref(false)
/** 根容器高度（分析期间卡片全屏用） */
const rootH = ref(0)
/** 下移时至少保留可见的卡片高度（把手） */
const KEEP_VISIBLE = 56
const maxOffset = ref(0)

function measureCard() {
  const el = sheetRef.value
  rootH.value = rootRef.value?.clientHeight ?? 0
  if (!el) return
  maxOffset.value = Math.max(0, el.offsetHeight - KEEP_VISIBLE)
  sheetOffset.value = Math.min(sheetOffset.value, maxOffset.value)
}

let pressX = 0
let pressY = 0
let dragStartOffset = 0
let maybeDrag = false
let suppressClick = false
let dragDistance = 0
let pressTarget: HTMLElement | null = null

/**
 * 拖卡启动判定：点在交互控件（按钮/输入/滑杆等）上时不启动拖卡，
 * 保证「拍照 / 相册 / 历史测评照片 / 直接上传多张」等按钮**第一次点击就响应**，
 * 不会被误判为拖拽而吞掉 click（此前手指轻抖 >10px 即被当成拖卡、点击失效）。
 */
function onCardPointerDown(e: PointerEvent) {
  if (props.isSubmitting) return
  const t = e.target as HTMLElement | null
  if (t && t.closest('button, input, select, textarea, label, [role="slider"]')) return
  pressX = e.clientX; pressY = e.clientY
  dragStartOffset = sheetOffset.value
  maybeDrag = true
  pressTarget = e.currentTarget as HTMLElement
}

function onCardPointerMove(e: PointerEvent) {
  if (!maybeDrag || props.isSubmitting) return
  const dx = e.clientX - pressX
  const dy = e.clientY - pressY
  if (!dragging.value) {
    // 位移不足或横向为主时不启动拖卡：让点击正常生效
    if (Math.abs(dy) < 10 || Math.abs(dx) > Math.abs(dy)) return
    dragging.value = true
    suppressClick = true
    dragDistance = Math.abs(dy)
    pressTarget?.setPointerCapture(e.pointerId)
  }
  dragDistance = Math.max(dragDistance, Math.abs(dy))
  sheetOffset.value = Math.min(Math.max(0, dragStartOffset + dy), maxOffset.value)
}

function onCardPointerUp(e: PointerEvent) {
  maybeDrag = false
  if (!dragging.value) return
  dragging.value = false
  sheetOffset.value = Math.min(Math.max(0, sheetOffset.value), maxOffset.value)
  try { pressTarget?.releasePointerCapture(e.pointerId) } catch { /* 已释放 */ }
  // 拖动距离很小（接近点按的抖动）不吞掉随后的 click
  suppressClick = dragDistance >= 24
}

function onCardPointerCancel(e: PointerEvent) {
  maybeDrag = false
  dragging.value = false
  // pointercancel 之后不会再有 click，若残留 suppressClick=true 会吞掉下一次点击
  suppressClick = false
  try { pressTarget?.releasePointerCapture(e.pointerId) } catch { /* 已释放 */ }
}

/** 拖动结束落在按钮上时吞掉随之而来的 click，避免误触发 */
function onCardClickCapture(e: MouseEvent) {
  if (suppressClick) {
    e.stopPropagation()
    e.preventDefault()
    suppressClick = false
  }
}

function onResize() {
  measureCard()
}

// 内容变化（部位/照片/分析态）后重测卡片高度并回位
watch(
  () => [props.selectedBodySite, props.imagePreview, props.isSubmitting],
  () => nextTick(() => { measureCard(); sheetOffset.value = 0 }),
)

onMounted(() => {
  measureCard()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (analyzeTimer) { clearInterval(analyzeTimer); analyzeTimer = null }
})
</script>

<template>
  <div ref="rootRef" class="relative h-full overflow-hidden bg-gray-50 dark:bg-gray-900">

    <!-- ① 数字小人 — 正方形容器顶部锚定（图形撑满方块、无垂直留白），保证上半身始终可见；pt-10 为顶部提示留出空间。
         z-10 建立层叠上下文：把小人内部的高 z-index 元素（如正面/背面切换按钮 z-30）约束在功能卡片（z-20）之下，避免遮挡卡片与全屏分析态 -->
    <div class="absolute inset-0 z-10 flex items-start justify-center pt-10 px-7">
      <div class="w-full max-w-xl aspect-square">
        <DigitalHuman mode="rain" :show-parts="true" :active-part="selectedBodySite" @select-part="emit('selectPart', $event)" />
      </div>
    </div>

    <!-- 部位引导提示（居中，位于小人上方） -->
    <div
      v-if="!selectedBodySite"
      class="absolute top-2 left-1/2 -translate-x-1/2 z-10 pointer-events-none flex items-center gap-1 px-3 py-1 rounded-full
        bg-amber-50/95 dark:bg-amber-900/40 border border-amber-200/80 dark:border-amber-800/50 shadow-sm whitespace-nowrap"
    >
      <i class="ri-hand-point-up-line text-amber-500 text-sm shrink-0"></i>
      <span class="text-xs text-amber-700 dark:text-amber-300">请先选择白斑测评部位</span>
    </div>

    <!-- ② 功能卡片 — 一个完整单元：高度自适应内容、整卡可拖、无内部滚动 -->
    <section
      ref="sheetRef"
      class="absolute bottom-0 left-0 right-0 z-20 max-h-full overflow-hidden bg-white dark:bg-gray-800 rounded-t-2xl
        shadow-[0_-6px_24px_rgba(0,0,0,0.10)] flex flex-col select-none cursor-grab"
      :class="[dragging ? 'cursor-grabbing' : 'sheet-anim']"
      :style="{
        height: isSubmitting ? rootH + 'px' : undefined,
        transform: `translateY(${sheetOffset}px)`,
        touchAction: 'pan-x',
      }"
      aria-label="拍照评估操作面板"
      @pointerdown="onCardPointerDown"
      @pointermove="onCardPointerMove"
      @pointerup="onCardPointerUp"
      @pointercancel="onCardPointerCancel"
      @click.capture="onCardClickCapture"
    >
      <!-- 拖拽把手（整卡均可拖，把手是视觉锚点）；各功能模块内自有历史入口 -->
      <div class="shrink-0 flex items-center justify-center gap-2 pt-2.5 pb-1.5 touch-none" aria-hidden="true">
        <i class="ri-arrow-up-s-line text-xs text-gray-300 dark:text-gray-600"></i>
        <div class="w-12 h-1.5 rounded-full bg-gray-300 dark:bg-gray-600"></div>
        <i class="ri-arrow-down-s-line text-xs text-gray-300 dark:text-gray-600"></i>
      </div>

      <!-- 卡片内容（不滚动；分析期间照片区自适应伸展） -->
      <div class="flex-1 min-h-0 px-4 pb-3 space-y-2.5" :class="isSubmitting ? 'flex flex-col overflow-hidden' : ''">

        <!-- 部位上下文（两大功能共享）：选中部位后显示 -->
        <div v-if="selectedBodySite" class="flex justify-center shrink-0">
          <span
            class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-primary-50 dark:bg-primary-900
              text-primary-700 dark:text-primary-300 text-xs font-semibold"
          >
            <i class="ri-focus-3-line"></i>{{ PART_LABELS[selectedBodySite] || selectedBodySite }}
          </span>
        </div>

        <!-- ═══ 功能一：单次测评（一级模块 · 主流程；主题色描边底衬托，编号徽章 1）═══
             分析期间模块变为 flex 列并撑满卡片（flex-1 min-h-0），照片区自适应收缩，
             「AI 分析中」按钮（shrink-0）稳定钉在底部、倒计时始终可见 -->
        <div
          class="rounded-xl border border-primary-200 dark:border-primary-800 bg-primary-100 dark:bg-primary-900 p-3 space-y-2.5"
          :class="isSubmitting ? 'flex flex-col flex-1 min-h-0 overflow-hidden' : 'shrink-0'"
        >
          <!-- 模块头部：编号徽章 + 加粗标题（层级高于模块内按钮）+ 说明 + 历史入口 -->
          <div class="shrink-0">
            <div class="flex items-center gap-2">
              <span
                class="w-5 h-5 rounded-full bg-primary-500 text-white text-[11px] font-bold
                  flex items-center justify-center shrink-0"
                aria-hidden="true"
              >1</span>
              <h3 class="text-[15px] font-bold text-gray-900 dark:text-gray-100 leading-tight">单次测评</h3>
              <button
                type="button"
                class="ml-auto inline-flex items-center gap-1 pl-2 pr-2.5 h-8 rounded-full shrink-0
                  text-[11px] font-medium text-gray-500 dark:text-gray-400
                  bg-white/80 dark:bg-gray-800/70 border border-gray-200/70 dark:border-gray-600/60
                  hover:text-primary-600 dark:hover:text-primary-300 hover:border-primary-300 dark:hover:border-primary-700 transition-colors"
                data-track-id="assessment_single_history"
                aria-label="查看测评历史"
                @click="emit('openHistory')"
              >
                <i class="ri-history-line text-sm"></i>历史
              </button>
            </div>
            <p class="text-[11px] text-gray-500 dark:text-gray-400 leading-tight mt-1 pl-7">拍 1 张照片，AI 分析当前白斑</p>
          </div>

          <!-- 照片预览（分析期间 flex-1 撑满剩余空间、照片自适应收缩，不再把按钮挤出屏幕） -->
          <div v-if="imagePreview" class="flex flex-col items-center gap-2" :class="isSubmitting ? 'flex-1 min-h-0 justify-center' : 'shrink-0'">
            <div class="relative w-full max-w-xs" :class="isSubmitting ? 'max-w-md flex-1 min-h-0 flex items-center justify-center' : ''">
              <img :src="imagePreview" alt="预览照片" class="object-contain rounded-xl shadow-md transition-[max-height] duration-300" :class="isSubmitting ? 'max-h-full max-w-full' : 'w-full max-h-28'" />
              <button v-if="!isSubmitting" class="absolute top-2 right-2 w-8 h-8 bg-black/40 text-white rounded-full flex items-center justify-center hover:bg-red-500 min-h-[44px] min-w-[44px] -mt-1.5 -mr-1.5" @click="emit('removeImage')" aria-label="移除照片"><i class="ri-close-line"></i></button>
              <!-- 停止分析：分析期间置于照片右上角，更醒目 -->
              <button v-if="isSubmitting" type="button" class="absolute top-2 right-2 flex items-center gap-1 px-3 py-1.5 min-h-[40px] rounded-full bg-red-500 hover:bg-red-600 text-white text-xs font-medium shadow-md" @click="emit('cancel')" aria-label="停止分析">
                <i class="ri-close-line"></i>停止分析
              </button>
            </div>
            <p v-if="qualityResult && qualityResult.overall !== 'good'" class="text-xs text-amber-600 px-3 py-1.5 rounded-full bg-amber-50 dark:bg-amber-900/20">
              <i class="ri-information-line mr-1"></i>{{ qualityResult.suggestions[0] || '照片质量一般' }}
            </p>
          </div>

          <!-- AI 分析（有照片时为唯一主色按钮，倒计时内嵌） -->
          <div v-if="imagePreview && selectedBodySite" class="max-w-xs mx-auto w-full shrink-0">
            <button class="w-full flex items-center justify-center gap-2 min-h-[48px] rounded-xl text-[15px] font-semibold bg-primary-500 hover:bg-primary-600 text-white shadow-sm" :disabled="isSubmitting" @click="emit('submit')">
              <template v-if="isSubmitting">
                <svg class="animate-spin w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                <span role="status" aria-live="polite">{{ submittingLabel }}（{{ countdownText }}）</span>
              </template>
              <template v-else><i class="ri-scan-line text-lg"></i>开始 AI 分析</template>
            </button>
          </div>

          <!-- 拍照 + 相册（未选照片时为功能一主入口；已选照片后降为次级换图行）；两按钮视觉统一不高亮 -->
          <div v-if="!isSubmitting" class="grid grid-cols-2 gap-2.5 w-full shrink-0">
            <button
              class="flex items-center justify-center gap-1.5 rounded-xl text-sm transition-colors"
              :class="neutralBtnClass"
              @click="openCamera"
            ><i class="ri-camera-line" :class="imagePreview ? 'text-sm' : 'text-base'"></i>拍照</button>
            <button
              class="flex items-center justify-center gap-1.5 rounded-xl text-sm transition-colors"
              :class="neutralBtnClass"
              @click="triggerUpload"
            ><i class="ri-image-line" :class="imagePreview ? 'text-sm' : 'text-base'"></i>相册</button>
          </div>
        </div>

        <!-- ═══ 功能关联提示：单次测评的照片自动沉淀为对比素材 ═══ -->
        <div v-if="showCompareSection" class="shrink-0 flex items-center gap-2">
          <span class="h-px flex-1 bg-gray-100 dark:bg-gray-700/60" aria-hidden="true"></span>
          <i class="ri-links-line text-xs text-gray-300 dark:text-gray-500 shrink-0" aria-hidden="true"></i>
          <span class="text-[10px] text-gray-400 dark:text-gray-500 whitespace-nowrap">测评照片自动存入历史，可直接用于对比</span>
          <span class="h-px flex-1 bg-gray-100 dark:bg-gray-700/60" aria-hidden="true"></span>
        </div>

        <!-- ═══ 功能二：多选对比（一级模块 · 暖色描边底，编号徽章 2；两条来源路径殊途同归）═══ -->
        <div v-if="showCompareSection" class="shrink-0 rounded-xl border border-amber-200/70 dark:border-amber-800/50 bg-amber-100/70 dark:bg-amber-900/25 p-3 space-y-2.5">
          <!-- 模块头部：编号徽章 + 加粗标题 + 说明 + 历史入口 -->
          <div>
            <div class="flex items-center gap-2">
              <span
                class="w-5 h-5 rounded-full bg-white dark:bg-gray-600 text-gray-500 dark:text-gray-300 text-[11px] font-bold
                  flex items-center justify-center shrink-0"
                aria-hidden="true"
              >2</span>
              <h3 class="text-[15px] font-bold text-gray-900 dark:text-gray-100 leading-tight">多选对比</h3>
              <button
                type="button"
                class="ml-auto inline-flex items-center gap-1 pl-2 pr-2.5 h-8 rounded-full shrink-0
                  text-[11px] font-medium text-gray-500 dark:text-gray-400
                  bg-white/80 dark:bg-gray-800/70 border border-gray-200/70 dark:border-gray-600/60
                  hover:text-primary-600 dark:hover:text-primary-300 hover:border-primary-300 dark:hover:border-primary-700 transition-colors"
                data-track-id="assessment_compare_history"
                aria-label="查看对比报告历史"
                @click="emit('compareHistory')"
              >
                <i class="ri-history-line text-sm"></i>历史
              </button>
            </div>
            <p class="text-[11px] text-gray-500 dark:text-gray-400 leading-tight mt-1 pl-7">选 2–4 张照片，生成变化对比报告</p>
          </div>

          <!-- 路径 A：历史测评照片（复用单次测评） / 路径 B：直接上传多张（无需先做测评） -->
          <div class="relative grid grid-cols-2 gap-2.5">
            <button
              type="button"
              class="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-gray-300/80 dark:border-gray-600 bg-white/70 dark:bg-gray-800/60 text-left
                hover:border-primary-300 dark:hover:border-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors"
              data-track-id="assessment_card_multi_history"
              @click="emit('multiHistory')"
            >
              <i class="ri-history-line text-lg text-primary-500 shrink-0" aria-hidden="true"></i>
              <span class="min-w-0">
                <span class="block text-[13px] font-medium text-gray-800 dark:text-gray-200 leading-tight">历史测评照片</span>
                <span class="block text-[10px] text-gray-400 dark:text-gray-500 leading-tight mt-0.5">复用单次测评</span>
              </span>
            </button>
            <button
              type="button"
              class="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-gray-300/80 dark:border-gray-600 bg-white/70 dark:bg-gray-800/60 text-left
                hover:border-primary-300 dark:hover:border-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors"
              data-track-id="assessment_card_multi_gallery"
              @click="emit('multiGallery')"
            >
              <i class="ri-gallery-line text-lg text-primary-500 shrink-0" aria-hidden="true"></i>
              <span class="min-w-0">
                <span class="block text-[13px] font-medium text-gray-800 dark:text-gray-200 leading-tight">上传相册照片</span>
                <span class="block text-[10px] text-gray-400 dark:text-gray-500 leading-tight mt-0.5">无需先做测评</span>
              </span>
            </button>
            <!-- 「或」分隔：两条路径任选其一，均可生成对比报告 -->
            <span
              class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full
                bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600
                text-[10px] text-gray-400 flex items-center justify-center pointer-events-none"
              aria-hidden="true"
            >或</span>
          </div>
        </div>

        <!-- 免责声明（卡片最下方，代替全站页脚） -->
        <p class="pt-1.5 text-center text-[10px] text-gray-400 dark:text-gray-500 border-t border-gray-100 dark:border-gray-700/60 shrink-0">
          本平台不构成医疗建议，所有内容仅供参考。
        </p>
        <input ref="fileInputEl" type="file" accept="image/*" class="hidden" @change="emit('uploadFile', $event)" />
      </div>
    </section>

    <BodyPartCamera v-model="showCamera" :body-part="selectedBodySite" @captured="onCameraCapture" />
  </div>
</template>

<style scoped>
/* 非拖动状态下的平移/高度过渡；拖拽中禁用以保证跟手 */
.sheet-anim {
  transition: transform 0.25s ease, height 0.25s ease;
}
</style>
