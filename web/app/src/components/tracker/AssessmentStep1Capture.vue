<script setup lang="ts">
/**
 * Step 1: 拍照评估
 *
 * 布局：
 *   1. 数字小人（大尺寸，与体检页一致）— 与 ReportPage 相同视觉比例
 *   2. 操作卡片 — 白色圆角卡片，可滚动
 *
 * 背景: #F5F7FA（与其他页面一致）
 */
import { ref, computed, watch, nextTick } from 'vue'
import { PART_LABELS } from '@/constants/bodySites'
import DigitalHuman from '@/components/tracker/DigitalHuman.vue'
import BodyPartCamera from '@/components/tracker/BodyPartCamera.vue'
import { useToast } from '@/composables/useToast'
import type { QualityCheckResult } from '@/api/vasi'

const props = defineProps<{
  selectedBodySite: string; imagePreview: string | null
  qualityResult: QualityCheckResult | null; qualityChecking: boolean
  isSubmitting?: boolean; uploadStage?: string
}>()

const emit = defineEmits<{
  selectPart: [site: string]; uploadFile: [event: Event]; openCamera: []
  cameraCapture: [file: File, meta?: { hasReferenceCard?: boolean }]; removeImage: []; submit: []
}>()

const showCamera = ref(false); const fileInputEl = ref<HTMLInputElement | null>(null)
const actionCardRef = ref<HTMLElement | null>(null)
const submitBtnRef = ref<HTMLElement | null>(null)
const toast = useToast()
const partLabel = computed(() => props.selectedBodySite ? (PART_LABELS[props.selectedBodySite] || props.selectedBodySite) : '')
const submittingLabel = computed(() => ({ uploading:'上传中...', segmenting:'AI识别中...', analyzing:'AI分析中...' }[props.uploadStage||''] || '分析中...'))

function triggerUpload() {
  if (!props.selectedBodySite) {
    toast.warning('请先在数字人上点击选择身体部位，再上传照片')
    return
  }
  fileInputEl.value?.click()
}

function openCamera() {
  if (!props.selectedBodySite) {
    toast.warning('请先在数字人上点击选择身体部位，再拍照')
    return
  }
  showCamera.value = true
}
function onCameraCapture(f: File, m?: { hasReferenceCard?: boolean }) { emit('cameraCapture', f, m); showCamera.value = false }

// Auto-scroll to the "开始AI分析" button (not just the card top) when image
// is uploaded or body part selected — ensures the button is always visible
// without requiring the user to manually scroll down.
watch(
  () => [props.imagePreview, props.selectedBodySite],
  () => {
    if (props.imagePreview && props.selectedBodySite) {
      nextTick(() => {
        // Prioritize scrolling to the submit button itself; fall back to card.
        const target = submitBtnRef.value || actionCardRef.value
        if (target) {
          const mainEl = target.closest('main')
          if (mainEl) {
            const scrollTarget = target.getBoundingClientRect().top - mainEl.getBoundingClientRect().top + mainEl.scrollTop
            mainEl.scrollTo({ top: scrollTarget - 20, behavior: 'smooth' })
          }
        }
      })
    }
  },
)
</script>

<template>
  <div class="min-h-[100dvh] flex flex-col bg-[#F5F7FA] dark:bg-gray-900">

    <!-- ① DH — large enough to see full body, matches ReportPage visual size -->
    <div class="relative w-full shrink-0 bg-[#F5F7FA] dark:bg-gray-900" style="height: 50vh; min-height: 320px; max-height: 480px">
      <div class="w-full max-w-md mx-auto h-full">
        <DigitalHuman mode="rain" :show-parts="true" :active-part="selectedBodySite" @select-part="emit('selectPart', $event)" />
      </div>
      <!-- Selected badge on DH -->
      <div v-if="selectedBodySite" class="absolute bottom-3 left-0 right-0 text-center z-10">
        <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary-50 dark:bg-primary-900/20 text-sm font-medium text-primary-700 dark:text-primary-300 shadow-sm">
          <i class="ri-check-line text-primary-500"></i>{{ partLabel }}
        </span>
      </div>
    </div>

    <!-- ② Card — below DH, scrolls independently -->
    <div ref="actionCardRef" class="bg-white dark:bg-gray-800 rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.06)] -mt-2 relative z-10 px-4 pt-3 pb-28 max-w-lg mx-auto w-full space-y-3">

      <!-- Guide text (before selection) -->
      <p v-if="!selectedBodySite" class="text-center text-sm text-gray-400 dark:text-gray-500 pt-1">
        点击上图身体部位 · 拍照或上传照片 · AI 自动分析
      </p>

      <!-- Selected hint -->
      <p v-else class="text-center text-xs text-gray-400 dark:text-gray-500">
        已选择 {{ partLabel }}，请拍照或上传照片
      </p>

      <!-- Photo preview -->
      <div v-if="imagePreview" class="flex flex-col items-center gap-2">
        <div class="relative w-full max-w-xs">
          <img :src="imagePreview" alt="预览照片" class="w-full max-h-44 object-contain rounded-xl shadow-md" />
          <button class="absolute top-2 right-2 w-8 h-8 bg-black/40 text-white rounded-full flex items-center justify-center hover:bg-red-500 min-h-[44px] min-w-[44px]" @click="emit('removeImage')" aria-label="移除照片"><i class="ri-close-line"></i></button>
        </div>
        <p v-if="qualityResult && qualityResult.overall !== 'good'" class="text-xs text-amber-600 px-3 py-1.5 rounded-full bg-amber-50 dark:bg-amber-900/20">
          <i class="ri-information-line mr-1"></i>{{ qualityResult.suggestions[0] || '照片质量一般' }}
        </p>
      </div>

      <!-- 拍照 + 相册 -->
      <div class="flex gap-3 max-w-xs mx-auto w-full">
        <button class="flex-1 py-3 text-sm font-medium flex items-center justify-center gap-1.5 min-h-[48px] rounded-xl bg-primary-500 hover:bg-primary-600 text-white shadow-sm" @click="openCamera"><i class="ri-camera-line text-lg"></i>拍照</button>
        <button class="flex-1 py-3 text-sm font-medium flex items-center justify-center gap-1.5 min-h-[48px] rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-600" @click="triggerUpload"><i class="ri-image-line text-lg"></i>相册</button>
      </div>
      <input ref="fileInputEl" type="file" accept="image/*" class="hidden" @change="emit('uploadFile', $event)" />

      <p class="text-xs text-gray-400 text-center"><i class="ri-lightbulb-line mr-0.5"></i>光线充足 · 白斑清晰 · 可附参照物</p>

      <!-- AI 分析 -->
      <div v-if="imagePreview && selectedBodySite" ref="submitBtnRef" class="max-w-xs mx-auto w-full pt-1">
        <button class="w-full py-3.5 flex items-center justify-center gap-2 min-h-[54px] rounded-xl text-base font-semibold bg-primary-500 hover:bg-primary-600 text-white shadow-md" :disabled="isSubmitting" @click="emit('submit')">
          <template v-if="isSubmitting"><svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg><span>{{ submittingLabel }}</span></template>
          <template v-else><i class="ri-scan-line text-lg"></i>开始 AI 分析</template>
        </button>
      </div>
    </div>

    <BodyPartCamera v-model="showCamera" :body-part="selectedBodySite" @captured="onCameraCapture" />
  </div>
</template>
