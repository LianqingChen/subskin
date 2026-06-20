<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVasiAssessment, getScoreInterpretation, getStageDescription } from '@/composables/useVasiAssessment'
import { PART_LABELS } from '@/constants/bodySites'
import { usePrivacyStore } from '@/stores/privacy'
import MaskEditor from '@/components/tracker/MaskEditor.vue'
import PhotoGuideCard from '@/components/tracker/PhotoGuideCard.vue'
import VisualFeaturesCard from '@/components/tracker/VisualFeaturesCard.vue'

import FeedbackPrompt from '@/components/tracker/FeedbackPrompt.vue'
const props = defineProps<{
  selectedPart: string | null
  activePartAssessment: { vasiScore: number; areaPercentage: number; stage: string; classification?: string } | null
  partHistory: Array<{ id: number; date: string; vasiScore: number; areaPercentage: number; stage: string; classification?: string }>
}>()

const emit = defineEmits<{
  'take-photo': []
  'upload-photo': []
  'close-part': []
  'view-detail': [id: number]
  'require-body-site': []
}>()

const privacyStore = usePrivacyStore()

const {
  selectedBodySite, uploadedImage, imagePreview, isUploading, uploadStage,
  assessmentResult, lastAssessment, showContourEditor,
  isSubmittingContour, contourDiffResult,
  qualityResult, qualityChecking,
  recentAssessments, loadingHistory,
  historyPage, historyPageSize, historyTotal, historyTotalPages,
  selectMode, selectedIds, deletingIds, currentStep,
  aiSkinLayerUrl, aiLesionLayerUrl,
  assessmentSource, suspectedLesions, visualFeatures,
  setBodySite, setHasReferenceCard, handleFileSelect, handleDrop, submitAssessment,
  removeImage, handleTwoLayerConfirm,
  skipContourEdit, cancelAssessment, loadAssessmentHistory,
  goToHistoryPage, setHistoryPageSize,
  toggleSelectMode, toggleSelect, isSwiped, onTouchStart, onTouchEnd,
  deleteSingle, deleteSelected, createAssessmentDraft,
} = useVasiAssessment()

const router = useRouter()
const fileInputEl = ref<HTMLInputElement | null>(null)
const showVisualFeaturesStep = ref(false)

// ── When assessment completes and visual features exist, show analysis step ──
watch(assessmentResult, (result) => {
  if (result && visualFeatures.value && showContourEditor.value) {
    showVisualFeaturesStep.value = true
    showContourEditor.value = false
    currentStep.value = 3
  }
})

// ── Assessment countdown timer ──
const estimatedSeconds = 80
const remainingSeconds = ref(estimatedSeconds)
let countdownTimer: ReturnType<typeof setInterval> | null = null
watch(isUploading, (uploading) => {
  if (uploading) {
    remainingSeconds.value = estimatedSeconds
    countdownTimer = setInterval(() => {
      if (remainingSeconds.value > 0) remainingSeconds.value--
    }, 1000)
  } else {
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
  }
})
onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})

function onVisualFeaturesContinue() {
  showVisualFeaturesStep.value = false
  showContourEditor.value = true
  currentStep.value = 4
}

// ── Detection summary for contour editor ──
const detectionLabel = computed(() => {
  const s = assessmentSource.value
  if (!s) return null
  if (s.includes('vlm-guided') || s.includes('sam-vlm')) return { text: 'VLM 引导识别', color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300', icon: 'ri-brain-line' }
  if (s.includes('sam-only') || s.includes('auto')) return { text: 'SAM 自动识别', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300', icon: 'ri-scan-line' }
  if (s.includes('vlm-fallback')) return { text: 'VLM 降级识别', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300', icon: 'ri-alert-line' }
  if (s.includes('mock')) return { text: '模拟数据', color: 'bg-gray-100 text-gray-600 ', icon: 'ri-question-line' }
  return { text: s, color: 'bg-gray-100 text-gray-600', icon: 'ri-information-line' }
})

const lesionSummary = computed(() => {
  const lesions = suspectedLesions.value
  if (!lesions || lesions.length === 0) return null
  const highConf = lesions.filter((l: any) => l.confidence >= 0.6).length
  return { total: lesions.length, highConf }
})

const needsCorrection = computed(() => {
  const conf = assessmentResult.value?.confidence
  return conf !== undefined && conf < 0.5
})

function compareSelected() {
  if (selectedIds.value.size < 2) return
  const ids = Array.from(selectedIds.value).slice(0, 2).join(',')
  router.push({ name: 'vasi-compare', query: { ids } })
}

function triggerUpload() {
  if (!props.selectedPart) {
    emit('require-body-site')
    return
  }
  fileInputEl.value?.click()
}

function handleCameraCapture(file: File, meta?: { hasReferenceCard?: boolean }) {
  if (meta?.hasReferenceCard) {
    setHasReferenceCard(true)
  }
  const fakeEvent = { target: { files: [file] } } as unknown as Event
  handleFileSelect(fakeEvent)
}

const displayHistory = computed(() => recentAssessments.value)

const assessmentTitle = computed(() => {
  if (props.selectedPart && PART_LABELS[props.selectedPart]) {
    return PART_LABELS[props.selectedPart] + '测评'
  }
  return '白斑测评'
})

watch(() => props.selectedPart, (part) => {
  if (part) setBodySite(part)
  historyPage.value = 1
  loadAssessmentHistory(true, part || undefined)
})

// 新评估完成后回到第 1 页刷新历史
watch(assessmentResult, (r) => {
  if (r) {
    historyPage.value = 1
    loadAssessmentHistory(true, props.selectedPart || undefined)
  }
})

onMounted(() => {
  loadAssessmentHistory()
})

defineExpose({ handleCameraCapture, triggerUpload, setBodySite })
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 pt-3 pb-24 md:pb-8 space-y-3">
    <!-- Title + Step Guidance -->
    <div>
      <h1 class="text-xl font-bold text-gray-800">{{ assessmentTitle }}</h1>
      <p class="text-sm text-gray-500 ">点击身体部位，上传照片，量化测评白斑面积</p>
      <div class="flex items-center gap-2 mt-3">
        <div class="flex items-center gap-1.5" :class="currentStep >= 1 ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'">
          <span class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2"
            :class="currentStep >= 1 ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-300'">1</span>
          <span class="text-xs font-medium">选择部位</span>
        </div>
        <div class="w-6 h-px" :class="currentStep >= 2 ? 'bg-primary-300' : 'bg-gray-300'" />
        <div class="flex items-center gap-1.5" :class="currentStep >= 2 ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'">
          <span class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2"
            :class="currentStep >= 2 ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-300'">2</span>
          <span class="text-xs font-medium">上传照片</span>
        </div>
        <div class="w-6 h-px" :class="currentStep >= 3 ? 'bg-primary-300' : 'bg-gray-300'" />
        <div class="flex items-center gap-1.5" :class="currentStep >= 3 ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'">
          <span class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2"
            :class="currentStep >= 3 ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-300'">3</span>
          <span class="text-xs font-medium">查看结果</span>
        </div>
      </div>
    </div>

    <!-- Photo Guide Tips (auto-hides if user dismissed it permanently) -->
    <PhotoGuideCard v-if="!lastAssessment && !showContourEditor" />

    <!-- Last Assessment Result -->
    <div v-if="lastAssessment" class="card p-4 border-l-4" :class="{
      'border-green-500': lastAssessment.vasiScore < 10,
      'border-amber-500': lastAssessment.vasiScore >= 10 && lastAssessment.vasiScore < 25,
      'border-orange-500': lastAssessment.vasiScore >= 25 && lastAssessment.vasiScore < 50,
      'border-red-500': lastAssessment.vasiScore >= 50,
    }">
      <div class="flex items-start justify-between mb-2">
        <div>
          <h2 class="text-lg font-semibold text-gray-900"><i class="ri-clipboard-line"></i> 评估结果解读</h2>
          <p class="text-sm text-gray-500  mt-1">最新评估于刚刚完成</p>
        </div>
        <button @click="lastAssessment = null" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl">&times;</button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
        <div class="bg-gray-50 rounded-lg p-3 text-center">
          <div class="text-xl font-bold" :class="getScoreInterpretation(lastAssessment.vasiScore).color">{{ lastAssessment.vasiScore }}</div>
          <div class="text-xs text-gray-500 ">VASI评分</div>
        </div>
        <div class="bg-gray-50 rounded-lg p-3 text-center">
          <div class="text-xl font-bold" :class="getScoreInterpretation(lastAssessment.vasiScore).color">{{ getScoreInterpretation(lastAssessment.vasiScore).level }}</div>
          <div class="text-xs text-gray-500 ">严重程度</div>
        </div>
        <div class="bg-gray-50 rounded-lg p-3 text-center">
          <div class="text-xl font-bold text-gray-700">{{ lastAssessment.areaPercentage }}%</div>
          <div class="text-xs text-gray-500 " title="白斑面积 ÷ 该部位皮肤区域面积">白斑占该部位</div>
        </div>
        <div class="bg-gray-50 rounded-lg p-3 text-center" v-if="lastAssessment.confidence !== undefined">
          <div class="text-xl font-bold" :class="lastAssessment.confidence >= 0.7 ? 'text-green-600' : lastAssessment.confidence >= 0.5 ? 'text-amber-600' : 'text-red-600'">
            {{ lastAssessment.confidence >= 0.7 ? '高' : lastAssessment.confidence >= 0.5 ? '中' : '低' }}
          </div>
          <div class="text-xs text-gray-500 ">AI 信心度</div>
        </div>
        <div class="bg-gray-50 rounded-lg p-3 text-center">
          <div class="text-xl font-bold" :class="lastAssessment.stage === '好转' ? 'text-green-600' : lastAssessment.stage === '扩散' || lastAssessment.stage === '进展期' ? 'text-red-600' : 'text-amber-600'">{{ lastAssessment.stage }}</div>
          <div class="text-xs text-gray-500 ">病情阶段</div>
        </div>
      </div>
      <div v-if="lastAssessment.confidence !== undefined && lastAssessment.confidence < 0.5" class="text-xs text-amber-600 dark:text-amber-400 mt-2 p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20">
        <i class="ri-error-warning-line mr-1"></i>本次评估信心度较低（{{ Math.round(lastAssessment.confidence * 100) }}%），建议在更好的光照条件下重新拍照，或使用参考色卡提高精度
      </div>
      <div class="space-y-2">
        <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
          <h3 class="text-sm font-medium text-blue-700 dark:text-blue-300 mb-1"><i class="ri-microscope-line"></i> 评分含义</h3>
          <p class="text-sm text-blue-600 dark:text-blue-400">{{ getScoreInterpretation(lastAssessment.vasiScore).description }}</p>
        </div>
        <div class="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
          <h3 class="text-sm font-medium text-purple-700 dark:text-purple-300 mb-1"><i class="ri-bar-chart-2-line"></i> 阶段说明</h3>
          <p class="text-sm text-purple-600 dark:text-purple-400">{{ getStageDescription(lastAssessment.stage) }}</p>
        </div>
        <div v-if="lastAssessment.classification" class="bg-gray-50 rounded-lg p-3">
          <h3 class="text-sm font-medium text-gray-700 mb-1"><i class="ri-price-tag-3-line"></i> 分型</h3>
          <p class="text-sm text-gray-600 ">{{ lastAssessment.classification }}白癜风<span class="text-[10px] text-gray-400  ml-1">（仅供参考）</span></p>
        </div>
      </div>
      <div class="mt-2">
        <button @click="createAssessmentDraft" class="btn-primary w-full flex items-center justify-center gap-2 py-2.5 text-sm">
          <i class="ri-send-plane-line"></i>分享至发现
        </button>
      </div>
      <p class="text-xs text-gray-400  mt-4"><i class="ri-error-warning-line"></i> 以上解读仅供参考，不构成医疗诊断建议。</p>
    </div>


    <!-- Self-Evolving VASI: Feedback Prompt (low confidence) -->
    <FeedbackPrompt
      v-if="lastAssessment?.id"
      :assessment-id="lastAssessment.id"
      @dismiss="() => {}"
    />

    <!-- Visual Features Analysis Step (Step 3) -->
    <div v-if="showVisualFeaturesStep && visualFeatures" class="max-w-lg mx-auto mt-4">
      <div class="flex items-center gap-2 mb-3">
        <button
          class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors min-h-[44px]"
          @click="cancelAssessment"
        >
          <i class="ri-arrow-left-s-line text-xl"></i>
        </button>
        <span class="w-6 h-6 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center font-bold">3</span>
        <span class="text-sm font-semibold text-gray-700">特征分析</span>
      </div>
      <VisualFeaturesCard
        :visual-features="visualFeatures"
        @continue="onVisualFeaturesContinue"
      />
      <div class="text-center mt-3 flex items-center justify-center gap-4">
        <button
          class="text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors min-h-[44px]"
          @click="cancelAssessment"
        >
          取消测评
        </button>
        <button
          class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors min-h-[44px]"
          @click="onVisualFeaturesContinue"
        >
          跳过，直接查看 VASI 测评结果 →
        </button>
      </div>
    </div>

    <!-- Assessment: two-column layout when contour editor active -->
    <div class="flex flex-col lg:flex-row gap-4" v-if="showContourEditor && !showVisualFeaturesStep && !lastAssessment">
      <div class="lg:w-1/2">
        <template v-if="showContourEditor && imagePreview && assessmentResult">
          <!-- Detection source badge + lesion summary -->
          <div class="mb-4 p-4 rounded-xl bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800 space-y-2">
            <div class="flex items-center gap-2 flex-wrap">
              <i class="ri-information-line text-primary-500"></i>
              <span class="text-sm font-semibold text-primary-700 dark:text-primary-300">AI 已预填两个图层</span>
              <span v-if="detectionLabel" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium" :class="detectionLabel.color">
                <i :class="detectionLabel.icon"></i> {{ detectionLabel.text }}
              </span>
            </div>
            <p class="text-xs text-primary-600 dark:text-primary-400">蓝色 = 皮肤评估区域，粉色 = 白斑区域，粉色虚线 = 白斑边界。白斑占比 = 粉色 ÷ (蓝色+粉色)。</p>
            <!-- Lesion detection summary -->
            <div v-if="lesionSummary" class="flex items-center gap-3 text-xs">
              <span class="text-primary-600 dark:text-primary-400">
                <i class="ri-scan-line mr-1"></i>检测到 <strong>{{ lesionSummary.total }}</strong> 处疑似白斑
              </span>
              <span v-if="lesionSummary.highConf > 0" class="text-green-600 dark:text-green-400">
                <i class="ri-check-double-line mr-1"></i>{{ lesionSummary.highConf }} 处高置信
              </span>
              <span v-if="lesionSummary.highConf < lesionSummary.total" class="text-amber-600 dark:text-amber-400">
                <i class="ri-error-warning-line mr-1"></i>{{ lesionSummary.total - lesionSummary.highConf }} 处需确认
              </span>
            </div>
            <!-- Quick correction CTA — prominent when confidence is low -->
            <div v-if="needsCorrection" class="flex items-center gap-2 mt-2 p-2 rounded-lg bg-amber-100 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800">
              <i class="ri-paint-brush-line text-amber-600 dark:text-amber-400 text-lg"></i>
              <div class="flex-1">
                <p class="text-xs font-medium text-amber-700 dark:text-amber-300">AI 信心度较低，建议手动修正</p>
                <p class="text-[11px] text-amber-600/80 dark:text-amber-400/80">使用下方画笔工具修正轮廓，提交后 AI 会学习您的修正</p>
              </div>
            </div>
            <div v-else class="flex items-center gap-2 mt-1 text-xs text-primary-500/70 dark:text-primary-400/70">
              <i class="ri-mouse-line"></i> 点击区域不满意？使用画笔一键修正
            </div>
          </div>
          <MaskEditor
            :image-url="imagePreview"
            :editable="true"
            :initial-skin-layer-url="aiSkinLayerUrl"
            :initial-lesion-layer-url="aiLesionLayerUrl"
            @confirm="(p) => handleTwoLayerConfirm(p.skinMaskDataUrl, p.lesionMaskDataUrl)"
            @cancel="cancelAssessment"
          />
          <div class="mt-4 flex items-center justify-between">
            <div v-if="isSubmittingContour" class="flex items-center gap-2 text-sm text-primary-500">
              <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> 提交中...
            </div>
            <button v-if="visualFeatures" class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors min-h-[44px]" :disabled="isSubmittingContour" @click="showContourEditor = false; showVisualFeaturesStep = true; currentStep = 3"><i class="ri-arrow-left-s-line mr-0.5"></i>返回特征分析</button>
            <button class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors" :disabled="isSubmittingContour" @click="skipContourEdit">跳过，直接查看结果 →</button>
          </div>
          <div v-if="contourDiffResult" class="mt-4 p-3 rounded-xl border" :class="contourDiffResult.modified ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'">
            <div class="flex items-center gap-2">
              <i :class="contourDiffResult.modified ? 'ri-error-warning-line text-amber-500' : 'ri-check-double-line text-green-500'"></i>
              <span class="text-xs font-medium" :class="contourDiffResult.modified ? 'text-amber-700 dark:text-amber-300' : 'text-green-700 dark:text-green-300'">
                {{ contourDiffResult.modified ? `AI与手动标注存在差异（平均偏差: ${(contourDiffResult.avg_point_distance ?? 0).toFixed(3)}），已记录用于模型优化` : 'AI识别结果与您的标注一致！' }}
              </span>
            </div>
          </div>
        </template>
      </div>

      <div class="lg:w-1/2">
        <div class="card p-4 h-full flex flex-col min-h-[280px]">
          <!-- Upload area: shown before assessment only -->
          <div v-if="!showContourEditor" class="flex-1 flex flex-col items-center justify-center">
            <div class="relative border-2 border-dashed rounded-2xl p-4 w-full text-center cursor-pointer transition-all duration-200"
              :class="imagePreview ? 'border-primary-400 bg-primary-50/50 dark:bg-primary-900/10' : 'border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 hover:bg-gray-50/80 dark:hover:bg-gray-300/50'"
              @dragover.prevent @drop="handleDrop">
              <input ref="fileInputEl" type="file" accept="image/*" class="hidden" aria-label="上传照片" @change="handleFileSelect" />
              <div v-if="imagePreview" class="relative inline-block">
                <img :src="imagePreview" alt="预览" class="max-h-48 rounded-xl mx-auto shadow-sm" />
                <button class="absolute top-2 right-2 w-8 h-8 bg-black/40 backdrop-blur-sm text-white rounded-full flex items-center justify-center hover:bg-red-500 transition-colors z-10" @click.stop="removeImage"><i class="ri-close-line"></i></button>
              </div>
              <div v-else class="flex flex-col items-center" @click="triggerUpload">
                <div class="w-12 h-12 rounded-2xl bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center mb-2">
                  <i class="ri-image-add-line text-2xl text-primary-500 dark:text-primary-400"></i>
                </div>
                <p class="text-sm font-medium text-gray-600">点击或拖拽上传白斑照片</p>
                <p class="text-xs text-gray-400  mt-1">支持 JPG / PNG，最大 10MB</p>
              </div>
            </div>
            <div v-if="qualityChecking" class="mt-3 flex items-center gap-2 text-sm text-gray-500 ">
              <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> 正在检查照片质量...
            </div>
            <div v-else-if="qualityResult && uploadedImage && qualityResult.overall !== 'good'" class="mt-3 p-3 rounded-xl border w-full border-amber-200 bg-amber-50/60 dark:bg-amber-900/10 dark:border-amber-800/60">
              <div class="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-300">
                <i class="ri-information-line text-amber-500 mt-0.5"></i>
                <span>{{ qualityResult.suggestions[0] || '照片不够清晰，AI 会尽力分析，您也可以稍后手动修正轮廓' }}</span>
              </div>
            </div>
            <button class="btn-primary w-full mt-4 py-3 text-base" :disabled="!uploadedImage || !selectedBodySite || isUploading" @click="submitAssessment">
              <span v-if="isUploading">
<span class="inline-flex items-center gap-2"><svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> {{ uploadStage === 'uploading' ? '上传中...' : uploadStage === 'segmenting' ? (remainingSeconds > 0 ? `AI测评中，预计还需 ${remainingSeconds} 秒...` : 'AI仍在分析中，请耐心等待...') : '分析中...' }}</span>
              </span>
              <span v-else>开始评估</span>
            </button>
          </div>
          <!-- After assessment: show VASI result summary -->
          <div v-else class="flex-1 flex flex-col items-center justify-center p-4">
            <div class="w-12 h-12 rounded-2xl bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center mb-3">
              <i class="ri-clipboard-line text-2xl text-primary-500 dark:text-primary-400"></i>
            </div>
            <p class="text-sm font-medium text-gray-700 mb-1">AI 测评已完成</p>
            <p class="text-xs text-gray-400  text-center leading-relaxed">在左侧调整白斑轮廓<br>或点击"跳过"直接查看结果</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Upload Section — full-width default -->
    <div v-else-if="!showVisualFeaturesStep && !showContourEditor && !lastAssessment" class="card p-4 flex flex-col min-h-[280px]">
      <div class="flex-1 flex flex-col items-center justify-center">
        <div
          class="relative border-2 border-dashed rounded-2xl p-6 w-full text-center transition-all duration-200"
          :class="[
            !selectedPart && !imagePreview ? 'border-amber-300 bg-amber-50/40 dark:bg-amber-900/10 cursor-not-allowed' :
            imagePreview ? 'border-primary-400 bg-primary-50/50 dark:bg-primary-900/10 cursor-pointer' :
            'border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 hover:bg-gray-50/80 dark:hover:bg-gray-300/50 cursor-pointer'
          ]"
          @dragover.prevent
          @drop="!selectedPart && !imagePreview ? emit('require-body-site') : handleDrop($event)"
        >
          <input ref="fileInputEl" type="file" accept="image/*" class="hidden" aria-label="上传照片" @change="handleFileSelect" />
          <div v-if="imagePreview" class="relative inline-block">
            <img :src="imagePreview" alt="预览" class="max-h-64 rounded-xl mx-auto shadow-sm" />
            <button class="absolute top-2 right-2 w-8 h-8 bg-black/40 backdrop-blur-sm text-white rounded-full flex items-center justify-center hover:bg-red-500 transition-colors z-10" @click.stop="removeImage"><i class="ri-close-line"></i></button>
          </div>
          <div v-else-if="!selectedPart" class="flex flex-col items-center py-6" @click="emit('require-body-site')">
            <div class="w-16 h-16 rounded-2xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mb-3">
              <i class="ri-error-warning-line text-3xl text-amber-500 dark:text-amber-400"></i>
            </div>
            <p class="text-base font-medium text-amber-700 dark:text-amber-300">请先选择身体部位</p>
            <p class="text-sm text-amber-600/80 dark:text-amber-400/80 mt-1">
              在上方数字人上点击对应部位，再上传照片
            </p>
          </div>
          <div v-else class="flex flex-col items-center py-6" @click="triggerUpload">
            <div class="w-16 h-16 rounded-2xl bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center mb-3">
              <i class="ri-image-add-line text-3xl text-primary-500 dark:text-primary-400"></i>
            </div>
            <p class="text-base font-medium text-gray-600">点击或拖拽上传白斑照片</p>
            <p class="text-sm text-gray-400  mt-1">支持 JPG / PNG，最大 10MB</p>
          </div>
        </div>
        <div v-if="qualityChecking" class="mt-3 flex items-center gap-2 text-sm text-gray-500 ">
          <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> 正在检查照片质量...
        </div>
        <div v-else-if="qualityResult && uploadedImage && qualityResult.overall !== 'good'" class="mt-3 p-3 rounded-xl border w-full border-amber-200 bg-amber-50/60 dark:bg-amber-900/10 dark:border-amber-800/60">
          <div class="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-300">
            <i class="ri-information-line text-amber-500 mt-0.5"></i>
            <span>{{ qualityResult.suggestions[0] || '照片不够清晰，AI 会尽力分析，您也可以稍后手动修正轮廓' }}</span>
          </div>
        </div>
        <button class="btn-primary w-full mt-4 py-3.5 text-base" :disabled="!uploadedImage || !selectedBodySite || isUploading" @click="submitAssessment">
          <span v-if="isUploading">
            <span class="inline-flex items-center gap-2"><svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> {{ uploadStage === 'uploading' ? '上传中...' : uploadStage === 'segmenting' ? (remainingSeconds > 0 ? `AI测评中，预计还需 ${remainingSeconds} 秒...` : 'AI仍在分析中，请耐心等待...') : '分析中...' }}</span>
          </span>
          <span v-else>开始评估</span>
        </button>
      </div>
    </div>

    <!-- Assessment History -->
    <div class="glass-card p-4 md:p-6 rounded-2xl">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-900">
          <i class="ri-line-chart-line"></i>
          <template v-if="selectedPart">{{ PART_LABELS[selectedPart] || selectedPart }} · </template>评估历史
        </h2>
        <div class="flex items-center gap-2">
          <template v-if="selectMode">
            <button
              class="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="selectedIds.size < 2"
              @click="compareSelected"
            ><i class="ri-arrow-left-right-line mr-0.5"></i>对比</button>
            <button class="text-sm text-red-500 hover:text-red-600 dark:text-red-400" @click="deleteSelected" :disabled="selectedIds.size === 0">删除({{ selectedIds.size }})</button>
            <button class="text-sm text-gray-500 " @click="toggleSelectMode">取消</button>
          </template>
          <button v-else-if="displayHistory.length" class="text-sm text-primary-600 dark:text-primary-400 hover:underline" @click="toggleSelectMode">多选</button>
        </div>
      </div>
      <div v-if="loadingHistory" class="text-center py-8 text-gray-400 ">
        <div class="text-4xl mb-3 animate-pulse"><i class="ri-bar-chart-2-line"></i></div>
        <p>加载评估记录中...</p>
      </div>
      <div v-else-if="displayHistory.length" class="space-y-2 overflow-hidden">
        <div v-for="record in displayHistory" :key="record.id" class="relative">
          <div class="flex items-center transition-transform duration-200" :class="selectMode ? '' : (isSwiped(record.id) ? '-translate-x-16' : 'translate-x-0')" @touchstart="onTouchStart($event)" @touchend="onTouchEnd($event, record.id)">
            <div v-if="selectMode" class="pr-3 shrink-0">
              <input type="checkbox" :checked="selectedIds.has(record.id)" @change="toggleSelect(record.id)" class="w-5 h-5 rounded border-gray-300 text-primary-500 focus:ring-primary-400" />
            </div>
            <div class="flex-1 min-w-0 flex items-center gap-3 py-3 px-3 rounded-xl bg-gray-50 cursor-pointer" @click="emit('view-detail', record.id)">
              <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0" :class="record.stage === '稳定期' || record.stage === '好转' ? 'bg-green-100 dark:bg-green-900/30' : 'bg-amber-100 dark:bg-amber-900/30'">
                <span class="text-xs font-bold">{{ record.vasiScore }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 text-sm">
                  <span class="font-medium text-gray-900">{{ PART_LABELS[record.bodySite] || record.bodySite }}</span>
                  <span class="text-gray-400 ">{{ record.date }}</span>
                </div>
                <div class="flex items-center gap-3 mt-0.5 text-xs text-gray-500 ">
                  <span>VASI <strong class="text-gray-700">{{ !privacyStore.privacyMode ? record.vasiScore : '**' }}</strong></span>
                  <span>面积 <strong class="text-gray-700">{{ !privacyStore.privacyMode ? record.areaPercentage + '%' : '**%' }}</strong></span>
                  <span class="badge text-[10px] px-1.5 py-0.5" :class="record.stage === '稳定期' || record.stage === '好转' ? 'badge-success' : 'badge bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'">{{ record.stage }}</span>
                </div>
              </div>
            </div>
          </div>
          <button v-if="!selectMode && isSwiped(record.id)" class="absolute right-0 top-0 bottom-0 w-16 flex items-center justify-center bg-red-500 text-white rounded-r-xl" @click="deleteSingle(record.id)" :disabled="deletingIds.has(record.id)">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          </button>
        </div>
        <div v-if="historyTotal > 0" class="flex items-center justify-between gap-2 pt-3 text-xs text-gray-600 dark:text-gray-400">
          <div class="flex items-center gap-1">
            <span>每页</span>
            <select
              :value="historyPageSize"
              @change="setHistoryPageSize(Number(($event.target as HTMLSelectElement).value))"
              class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary-400"
            >
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
            <span>条 / 共 {{ historyTotal }} 条</span>
          </div>
          <div class="flex items-center gap-1.5">
            <button
              class="px-2 py-0.5 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-800"
              :disabled="historyPage <= 1 || loadingHistory"
              @click="goToHistoryPage(historyPage - 1)"
            >上一页</button>
            <span class="px-1">{{ historyPage }} / {{ historyTotalPages }}</span>
            <button
              class="px-2 py-0.5 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-800"
              :disabled="historyPage >= historyTotalPages || loadingHistory"
              @click="goToHistoryPage(historyPage + 1)"
            >下一页</button>
          </div>
        </div>
      </div>
      <div v-else class="text-center py-8 text-gray-400 ">
        <div class="text-4xl mb-3"><i class="ri-bar-chart-2-line"></i></div><p>暂无评估记录</p><p class="text-xs">上传照片开始你的第一次评估</p>
      </div>
    </div>

    <section class="text-center text-xs text-gray-400  py-4 border-t border-gray-100 dark:border-gray-800">
      <i class="ri-error-warning-line"></i> VASI评估结果仅供参考，不构成医疗诊断建议
    </section>
  </div>
</template>

<style scoped>
.glass-card {
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 0 2px 20px rgba(100, 80, 60, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04);
}
:root.dark .glass-card,
.dark .glass-card {
  background: rgba(30, 30, 46, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.15), 0 1px 3px rgba(0, 0, 0, 0.1);
}
</style>
