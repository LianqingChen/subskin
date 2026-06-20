<script setup lang="ts">
/**
 * Step 2: AI分析 + 画布标注
 * 全屏高度布局：info bar (shrink-0) → 视觉特征卡片(shrink-0, collapsible) → MaskEditor (flex-1) → bottom actions (shrink-0, sticky)
 */
import { ref, computed } from 'vue'
import MaskEditor from '@/components/tracker/MaskEditor.vue'
import VisualFeaturesCard from '@/components/tracker/VisualFeaturesCard.vue'
import type { VisualFeatures } from '@/api/vasi'

const props = defineProps<{
  isUploading: boolean; uploadStage: string; imagePreview: string | null
  showContourEditor: boolean; aiSkinLayerUrl: string | null; aiLesionLayerUrl: string | null
  assessmentSource: string | null; suspectedLesions: any[] | null; visualFeatures: VisualFeatures | null
  highConfidence: boolean; isSubmittingContour: boolean
  assessmentResult: { confidence?: number; vasiScore?: number; stage?: string } | null
}>()

const emit = defineEmits<{ maskConfirm: [skinMask: string, lesionMask: string, annotatedImage: string | null]; skipContourEdit: []; cancelAssessment: [] }>()

const showAiInfo = ref(false)
// Default COLLAPSED: when expanded, the VisualFeaturesCard takes up the entire
// mobile viewport, leaving 0 height for the MaskEditor (flex-1 min-h-0).
// Users must see the annotation canvas first; they can expand the card to
// view visual features if interested.
const showVisualFeatures = ref(false)
const lesionSummary = computed(() => {
  const l = props.suspectedLesions; if (!l?.length) return null
  return { total: l.length, highConf: l.filter((x: any) => x.confidence >= 0.6).length }
})

// Ref to MaskEditor for triggering confirm (submit manual annotations)
const maskEditorRef = ref<InstanceType<typeof MaskEditor> | null>(null)

function onConfirmMasks() {
  if (!maskEditorRef.value) return
  // Capture annotated composite image (original + skin/lesion layers) for sharing
  const annotatedImage = maskEditorRef.value.getAnnotatedImageDataUrl()
  // confirmMasks() emits MaskEditor's own @confirm with skin/lesion data URLs.
  // The template's @confirm handler re-emits as maskConfirm — but we need to
  // also pass annotatedImage. To avoid double-emit, we intercept here: call
  // confirmMasks() to trigger the internal flow, but the actual maskConfirm
  // emission happens in the @confirm handler which doesn't have annotatedImage.
  // So instead: we DON'T call confirmMasks(). We get masks directly and emit
  // everything in one shot.
  // However, MaskEditor doesn't expose getMaskDataUrls() yet — confirmMasks()
  // is the only way. Let's just call it and handle the @confirm event to also
  // pass annotatedImage via a closure variable.
  _pendingAnnotatedImage = annotatedImage
  maskEditorRef.value.confirmMasks()
}

// Closure variable to pass annotatedImage from onConfirmMasks to the @confirm handler
let _pendingAnnotatedImage: string | null = null
</script>

<template>
  <!-- Bottom padding accounts for global BottomNav (~54px + safe-area) so
       MaskEditor toolbar and action bar aren't obscured on mobile. -->
  <div class="flex flex-col bg-white dark:bg-gray-800 h-full pb-[calc(54px+env(safe-area-inset-bottom,0px))]">

    <template v-if="showContourEditor && imagePreview">
      <!-- Info bar -->
      <div class="shrink-0 px-3 pt-1.5 pb-1">
        <div class="flex items-center gap-2 text-xs">
          <span v-if="assessmentResult" class="font-medium text-gray-700 dark:text-gray-300">VASI {{ assessmentResult.vasiScore }} · {{ assessmentResult.stage }}</span>
          <span v-if="lesionSummary" class="text-gray-400 dark:text-gray-500">{{ lesionSummary.total }}处白斑<span v-if="lesionSummary.highConf" class="text-green-600 ml-0.5">{{ lesionSummary.highConf }}高置信</span></span>
          <button class="text-primary-500 text-xs min-h-[36px] px-1 ml-auto" @click="showAiInfo=!showAiInfo">{{ showAiInfo?'收起':'详情' }}</button>
        </div>
        <div v-if="showAiInfo" class="mt-1 p-2 rounded-lg bg-primary-50/50 dark:bg-primary-900/10 text-xs text-gray-500 dark:text-gray-400">
          蓝色=皮肤 · 粉色=AI识别白斑 · 可手动修正
          <span v-if="assessmentResult?.confidence !== undefined"> · AI信心度{{ Math.round((assessmentResult.confidence||0)*100) }}%</span>
        </div>
      </div>

      <!-- Visual features card (collapsible) -->
      <div v-if="visualFeatures" class="shrink-0 px-3 pb-1">
        <button class="w-full flex items-center justify-between py-1.5 px-2 rounded-lg bg-gray-50 dark:bg-gray-700/50 text-xs text-gray-500 dark:text-gray-400" @click="showVisualFeatures = !showVisualFeatures">
          <span class="flex items-center gap-1"><i class="ri-search-eye-line text-primary-500"></i>白斑视觉特征分析</span>
          <i :class="showVisualFeatures ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'" class="text-gray-400"></i>
        </button>
        <div v-if="showVisualFeatures" class="mt-1">
          <VisualFeaturesCard :visual-features="visualFeatures" />
        </div>
      </div>

      <!-- MaskEditor — fills ALL remaining space -->
      <div class="flex-1 min-h-0 mx-2 rounded-xl overflow-hidden border border-gray-100 dark:border-gray-700">
        <MaskEditor
          ref="maskEditorRef"
          :image-url="imagePreview" :editable="true"
          :initial-skin-layer-url="aiSkinLayerUrl" :initial-lesion-layer-url="aiLesionLayerUrl"
          :full-height="true"
          @confirm="(p: any) => { emit('maskConfirm', p.skinMaskDataUrl, p.lesionMaskDataUrl, _pendingAnnotatedImage); _pendingAnnotatedImage = null }"
          @cancel="emit('cancelAssessment')"
        />
      </div>

      <!-- Bottom actions — always visible above BottomNav -->
      <div class="shrink-0 px-3 py-2.5 flex items-center gap-2 bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700">
        <button class="min-h-[44px] px-3 text-sm text-gray-400" @click="emit('cancelAssessment')">取消</button>
        <button class="min-h-[44px] px-3 py-2 rounded-xl text-sm border border-gray-200 dark:border-gray-700 text-gray-500 transition-colors" :disabled="isSubmittingContour" @click="emit('skipContourEdit')">
          跳过
        </button>
        <button class="flex-1 min-h-[44px] py-2 rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-1.5 bg-primary-500 text-white hover:bg-primary-600 shadow-sm" :disabled="isSubmittingContour" @click="onConfirmMasks">
          <template v-if="isSubmittingContour"><svg class="animate-spin w-4 h-4 inline mr-1" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>提交中...</template>
          <template v-else><i class="ri-check-line"></i>确认提交标注</template>
        </button>
      </div>
    </template>

    <!-- Fallback waiting -->
    <section v-else class="flex-1 flex flex-col items-center justify-center text-gray-400">
      <svg class="animate-spin w-8 h-8 mb-4 text-primary-500" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      <p class="text-sm">AI 正在分析您的照片...</p>
      <button class="btn-ghost mt-4 text-sm" @click="emit('cancelAssessment')">取消</button>
    </section>
  </div>
</template>