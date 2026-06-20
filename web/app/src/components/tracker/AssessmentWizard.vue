<script setup lang="ts">
/**
 * AssessmentWizard — Step-by-step guided VASI assessment flow.
 *
 * Layout: Step 1 uses the ReportPage pattern (fixed DigitalHuman background
 * + white card overlay with rounded top) for a clean, immersive experience.
 * Steps 2-5 use the standard scrollable layout with sticky progress bar.
 *
 * Steps:
 * 1. Select body part (DigitalHuman with interactive guide lines)
 * 2. Upload/photo (camera + quality check)
 * 3. AI analyzing (progress + features)
 * 4. Mask editing (drawing tools)
 * 5. Results (VASI score + interpretation + history)
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVasiAssessment, getScoreInterpretation, getStageDescription } from '@/composables/useVasiAssessment'
import { PART_LABELS } from '@/constants/bodySites'
import { usePrivacyStore } from '@/stores/privacy'
import { useToast } from '@/composables/useToast'
import DigitalHuman from '@/components/tracker/DigitalHuman.vue'
import BodyPartCamera from '@/components/tracker/BodyPartCamera.vue'
import MaskEditor from '@/components/tracker/MaskEditor.vue'
import PhotoGuideCard from '@/components/tracker/PhotoGuideCard.vue'
import VisualFeaturesCard from '@/components/tracker/VisualFeaturesCard.vue'
import FeedbackPrompt from '@/components/tracker/FeedbackPrompt.vue'

type Step = 1 | 2 | 3 | 4 | 5

const router = useRouter()
const privacyStore = usePrivacyStore()
const toast = useToast()

const {
  selectedBodySite, uploadedImage, imagePreview, isUploading, uploadStage,
  assessmentResult, lastAssessment, showContourEditor, highConfidence,
  isSubmittingContour, contourDiffResult,
  qualityResult, qualityChecking,
  recentAssessments, loadingHistory,
  historyPage, historyPageSize, historyTotal, historyTotalPages,
  selectMode, selectedIds, deletingIds,
  aiSkinLayerUrl, aiLesionLayerUrl,
  assessmentSource, suspectedLesions, visualFeatures,
  setBodySite, setHasReferenceCard, handleFileSelect, handleDrop, submitAssessment,
  removeImage, handleTwoLayerConfirm,
  skipContourEdit, cancelAssessment, loadAssessmentHistory,
  goToHistoryPage, setHistoryPageSize,
  toggleSelectMode, toggleSelect, isSwiped, onTouchStart, onTouchEnd,
  deleteSingle, deleteSelected, createAssessmentDraft,
} = useVasiAssessment()

// ── Wizard step state ──
const wizardStep = ref<Step>(1)
const showCamera = ref(false)
const fileInputEl = ref<HTMLInputElement | null>(null)
const showVisualFeaturesStep = ref(false)
const showDetailedHelp = ref(false)

// ── Assessment countdown timer ──
const estimatedSeconds = 80
const remainingSeconds = ref(estimatedSeconds)
let countdownTimer: ReturnType<typeof setInterval> | null = null

// ── Detection metadata ──
const detectionLabel = computed(() => {
  const s = assessmentSource.value
  if (!s) return null
  if (s.includes('vlm-guided') || s.includes('sam-vlm')) return { text: 'VLM 引导识别', color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300', icon: 'ri-brain-line' }
  if (s.includes('sam-only') || s.includes('auto')) return { text: 'SAM 自动识别', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300', icon: 'ri-scan-line' }
  if (s.includes('vlm-fallback')) return { text: 'VLM 降级识别', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300', icon: 'ri-alert-line' }
  if (s.includes('mock')) return { text: '模拟数据', color: 'bg-gray-100 text-gray-600', icon: 'ri-question-line' }
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

// Mini sparkline from history
const sparklineData = computed(() => {
  const items = recentAssessments.value
  if (items.length < 2) return null
  return items.slice(0, 7).reverse().map(r => r.vasiScore)
})

const partLabel = computed(() => {
  return selectedBodySite.value ? (PART_LABELS[selectedBodySite.value] || selectedBodySite.value) : ''
})

const displayHistory = computed(() => recentAssessments.value)

// Comparison with previous assessment
const compareWithPrevious = computed(() => {
  const items = displayHistory.value
  return items.map((item, idx) => {
    if (idx === items.length - 1) return { ...item, vasiDiff: null, areaDiff: null }
    const prev = items[idx + 1]
    return {
      ...item,
      vasiDiff: item.vasiScore - prev.vasiScore,
      areaDiff: item.areaPercentage - prev.areaPercentage,
    }
  })
})

// ── Step transitions ──
function onBodyPartSelect(bodySite: string) {
  setBodySite(bodySite)
  // Reload history filtered by this body site
  historyPage.value = 1
  loadAssessmentHistory(true, bodySite)
  wizardStep.value = 2
}

function goBack() {
  if (wizardStep.value === 1) {
    router.push({ name: 'assistant' })
  } else if (wizardStep.value === 2) {
    removeImage()
    wizardStep.value = 1
  } else if (wizardStep.value === 3) {
    // Can't go back during analysis
  } else if (wizardStep.value === 4) {
    cancelAssessment()
    wizardStep.value = 2
  } else if (wizardStep.value === 5) {
    wizardStep.value = 1
  }
}

function triggerUpload() {
  if (!selectedBodySite.value) {
    toast.warning('请先在数字人上点击选择身体部位，再上传照片')
    wizardStep.value = 1
    return
  }
  fileInputEl.value?.click()
}

function openCamera() {
  if (!selectedBodySite.value) {
    toast.warning('请先在数字人上点击选择身体部位，再拍照')
    wizardStep.value = 1
    return
  }
  showCamera.value = true
}

function handleCameraCapture(file: File, meta?: { hasReferenceCard?: boolean }) {
  if (meta?.hasReferenceCard) setHasReferenceCard(true)
  const fakeEvent = { target: { files: [file] } } as unknown as Event
  handleFileSelect(fakeEvent)
  showCamera.value = false
}

async function onSubmitAssessment() {
  await submitAssessment()
  // After submit, if we have visual features, show step 3; otherwise go to mask editor or results
  if (assessmentResult.value && visualFeatures.value) {
    showVisualFeaturesStep.value = true
    wizardStep.value = 3
  } else if (showContourEditor.value) {
    wizardStep.value = 4
  } else if (lastAssessment.value) {
    wizardStep.value = 5
  }
}

function onVisualFeaturesContinue() {
  showVisualFeaturesStep.value = false
  showContourEditor.value = true
  wizardStep.value = 4
}

async function onMaskConfirm(skinMaskDataUrl: string, lesionMaskDataUrl: string) {
  await handleTwoLayerConfirm(skinMaskDataUrl, lesionMaskDataUrl)
  wizardStep.value = 5
}

function onSkipContourEdit() {
  skipContourEdit()
  wizardStep.value = 5
}

function onCancelAssessment() {
  cancelAssessment()
  wizardStep.value = 2
}

function startNewAssessment() {
  wizardStep.value = 1
  // Reload all history (unfiltered) when starting fresh
  historyPage.value = 1
  loadAssessmentHistory(true)
}

function compareSelected() {
  if (selectedIds.value.size < 2) return
  const ids = Array.from(selectedIds.value).slice(0, 2).join(',')
  router.push({ name: 'vasi-compare', query: { ids } })
}

function viewDetail(id: number) {
  router.push({ name: 'vasi-detail', params: { id } })
}

// ── Auto-advance logic ──
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
onUnmounted(() => { if (countdownTimer) clearInterval(countdownTimer) })

// NOTE: Step routing is handled explicitly by onSubmitAssessment() and onVisualFeaturesContinue().
// No auto-advance watch needed — the wizard flow controls routing deliberately.
// (Removed watch(showContourEditor) that was causing step 3→4 race condition)

onMounted(() => {
  loadAssessmentHistory()
})

// Reload history when an assessment completes (so results appear in history)
watch(assessmentResult, (result) => {
  if (result) {
    historyPage.value = 1
    loadAssessmentHistory(true, selectedBodySite.value || undefined)
  }
})

// Step labels for the progress bar
const STEPS = [
  { num: 1, label: '选部位', icon: 'ri-body_scan-line' },
  { num: 2, label: '上传', icon: 'ri-camera-line' },
  { num: 3, label: '分析', icon: 'ri-brain-line' },
  { num: 4, label: '标注', icon: 'ri-brush-line' },
  { num: 5, label: '结果', icon: 'ri-line-chart-line' },
]
</script>

<template>
  <!-- ═══════════════════════════════════════════════════════════ -->
  <!-- Step 1: Select Body Part — ReportPage layout pattern       -->
  <!-- Fixed DigitalHuman (interactive) + white card overlay       -->
  <!-- ═══════════════════════════════════════════════════════════ -->
  <template v-if="wizardStep === 1">
    <div class="min-h-[100dvh] flex flex-col bg-[#F5F7FA] dark:bg-gray-900">
      <!-- DigitalHuman — fixed background, interactive with guide lines -->
      <div class="fixed top-[6vh] left-0 right-0 z-0 bg-[#F5F7FA] dark:bg-gray-900" style="height: 55vh; min-height: 360px">
        <div class="w-full max-w-md mx-auto h-full">
          <DigitalHuman mode="rain" :show-parts="true" :active-part="selectedBodySite" @select-part="onBodyPartSelect" />
        </div>
      </div>

      <!-- Card overlay — scrolls over DigitalHuman -->
      <div data-view-card class="relative z-10 bg-white dark:bg-gray-800 rounded-t-3xl shadow-[0_-8px_30px_rgba(0,0,0,0.08)]" style="margin-top: 55vh;">
        <div class="max-w-6xl mx-auto px-4 pt-3 pb-28 md:pb-8">
          <!-- Back/home button + title -->
          <div class="flex items-center justify-between mb-2">
            <div>
              <h1 class="text-xl font-bold text-gray-800 dark:text-gray-100">白斑测评</h1>
              <p class="text-sm text-gray-500 dark:text-gray-400">点击身体部位，上传照片，量化评估白斑面积</p>
            </div>
            <button class="w-10 h-10 flex items-center justify-center rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors min-h-[44px]" aria-label="返回" @click="goBack">
              <i class="ri-home-4-line text-xl text-gray-500"></i>
            </button>
          </div>

          <!-- Selected part indicator -->
          <div v-if="selectedBodySite" class="mb-4 flex items-center gap-3 px-5 py-3 rounded-2xl bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800 shadow-sm">
            <div class="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900/40 flex items-center justify-center shrink-0">
              <i class="ri-check-double-line text-primary-600 dark:text-primary-400 text-lg"></i>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-base font-semibold text-primary-700 dark:text-primary-300">{{ partLabel }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">已选择，点击下一步上传照片</p>
            </div>
            <button class="btn-primary px-4 py-2 text-sm min-h-[44px]" @click="wizardStep = 2">
              下一步 <i class="ri-arrow-right-s-line ml-1"></i>
            </button>
          </div>

          <!-- Recent assessments -->
          <div v-if="displayHistory.length > 0">
            <h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">最近评估</h3>
            <div class="space-y-2">
              <div
                v-for="item in displayHistory.slice(0, 5)"
                :key="item.id"
                class="flex items-center gap-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-700/50 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                @click="viewDetail(item.id)"
              >
                <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0" :class="item.stage === '稳定期' || item.stage === '好转' ? 'bg-green-100 dark:bg-green-900/30' : 'bg-amber-100 dark:bg-amber-900/30'">
                  <span class="text-xs font-bold">{{ item.vasiScore.toFixed(1) }}</span>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                    {{ PART_LABELS[item.bodySite] || item.bodySite }}
                  </p>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{{ item.date }}</p>
                </div>
                <div class="text-right">
                  <p class="text-sm font-bold text-primary-600 dark:text-primary-400">{{ item.vasiScore.toFixed(1) }}</p>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{{ item.areaPercentage.toFixed(1) }}%</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Camera Modal for step 1 -->
    <BodyPartCamera v-model="showCamera" :body-part="selectedBodySite" @captured="handleCameraCapture" />
  </template>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <!-- Steps 2-5: Standard layout with sticky progress bar        -->
  <!-- ═══════════════════════════════════════════════════════════ -->
  <template v-else>
    <div class="min-h-[100dvh] flex flex-col bg-[#F5F7FA] dark:bg-gray-900">
      <!-- Sticky step progress bar -->
      <nav class="sticky top-0 z-30 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md border-b border-gray-200 dark:border-gray-700 px-4 py-2">
        <div class="max-w-2xl mx-auto flex items-center gap-1">
          <button
            class="shrink-0 w-10 h-10 flex items-center justify-center rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors min-h-[44px]"
            aria-label="上一步"
            @click="goBack"
          >
            <i class="ri-arrow-left-s-line text-xl text-gray-500"></i>
          </button>
          <div class="flex-1 flex items-center justify-center gap-0.5 sm:gap-2 overflow-x-auto">
            <span class="sm:hidden text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap mr-1">
              {{ wizardStep }}/5 {{ STEPS.find(s => s.num === wizardStep)?.label }}
            </span>
            <template v-for="(step, idx) in STEPS" :key="step.num">
              <button
                class="hidden sm:flex items-center gap-1 px-2 py-1.5 rounded-lg transition-all text-xs whitespace-nowrap min-h-[36px]"
                :class="wizardStep === step.num ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-semibold' : wizardStep > step.num ? 'text-primary-500 dark:text-primary-400' : 'text-gray-400 dark:text-gray-500'"
                @click="wizardStep > step.num && (wizardStep = step.num as Step)"
              >
                <i :class="[step.icon, wizardStep >= step.num ? 'opacity-100' : 'opacity-40']" class="text-sm"></i>
                <span>{{ step.label }}</span>
                <i v-if="wizardStep > step.num" class="ri-check-line text-primary-500 text-xs"></i>
              </button>
              <div v-if="idx < STEPS.length - 1" class="w-4 sm:w-6 h-px" :class="wizardStep > step.num ? 'bg-primary-400' : 'bg-gray-200 dark:bg-gray-600'"></div>
            </template>
          </div>
        </div>
      </nav>

      <!-- Step Content -->
      <main class="flex-1 flex flex-col overflow-y-auto">

        <!-- ── Step 2: Upload Photo ── -->
        <section v-if="wizardStep === 2" class="flex-1 max-w-2xl mx-auto w-full px-4 pt-4 pb-24" aria-label="上传照片">
          <!-- Compact body part indicator -->
          <div v-if="selectedBodySite" class="mb-4 flex items-center justify-between p-3 rounded-xl bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800">
            <div class="flex items-center gap-2">
              <i class="ri-check-line text-primary-600 dark:text-primary-400"></i>
              <span class="text-sm font-medium text-primary-700 dark:text-primary-300">{{ partLabel }}</span>
            </div>
            <button class="text-xs text-primary-500 hover:text-primary-700 dark:hover:text-primary-300" @click="wizardStep = 1">
              更换
            </button>
          </div>

          <!-- Main action buttons - prominent at top -->
          <div class="mb-4 flex gap-3">
            <button class="flex-1 btn-primary py-4 text-base flex items-center justify-center gap-2 min-h-[56px] shadow-lg" @click="openCamera">
              <i class="ri-camera-line text-xl"></i>拍照
            </button>
            <button class="flex-1 btn-ghost py-4 text-base flex items-center justify-center gap-2 min-h-[56px]" @click="triggerUpload">
              <i class="ri-image-line text-xl"></i>相册
            </button>
          </div>

          <!-- Upload area (compact) -->
          <div
            class="relative border-2 border-dashed rounded-xl p-3 w-full text-center transition-all duration-200 cursor-pointer mb-4"
            :class="imagePreview ? 'border-primary-400 bg-primary-50/50 dark:bg-primary-900/10' : 'border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 hover:bg-gray-50/80 dark:hover:bg-gray-800/50'"
            @dragover.prevent @drop="handleDrop"
          >
            <input ref="fileInputEl" type="file" accept="image/*" class="hidden" aria-label="上传照片" @change="handleFileSelect" />
            <div v-if="imagePreview" class="relative inline-block">
              <img :src="imagePreview" alt="预览" class="max-h-40 rounded-lg mx-auto shadow-sm" :class="{ 'blur-lg': privacyStore.privacyMode }" />
              <button class="absolute top-2 right-2 w-8 h-8 bg-black/40 backdrop-blur-sm text-white rounded-full flex items-center justify-center hover:bg-red-500 transition-colors z-10 min-h-[44px] min-w-[44px]" @click.stop="removeImage" aria-label="移除照片">
                <i class="ri-close-line"></i>
              </button>
            </div>
            <div v-else class="flex items-center justify-center py-2" @click="triggerUpload">
              <i class="ri-upload-cloud-2-line text-gray-400 mr-2"></i>
              <span class="text-sm text-gray-500 dark:text-gray-400">或拖拽照片到此处</span>
            </div>
          </div>

          <!-- Photo guide tips - collapsed by default -->
          <PhotoGuideCard v-if="!imagePreview" class="mb-4" />

          <!-- Quality check result -->
          <div v-if="qualityChecking" class="mb-4 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            正在检查照片质量...
          </div>
          <div v-else-if="qualityResult && uploadedImage && qualityResult.overall !== 'good'" class="mb-4 p-3 rounded-xl border w-full border-amber-200 bg-amber-50/60 dark:bg-amber-900/10 dark:border-amber-800/60">
            <div class="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-300">
              <i class="ri-information-line text-amber-500 mt-0.5"></i>
              <span>{{ qualityResult.suggestions[0] || '照片不够清晰，AI 会尽力分析，您也可以稍后手动修正轮廓' }}</span>
            </div>
          </div>

          <!-- Submit button -->
          <button
            class="btn-primary w-full py-3.5 text-base min-h-[48px] shadow-md"
            :disabled="!uploadedImage || !selectedBodySite || isUploading"
            @click="onSubmitAssessment"
          >
            <span v-if="isUploading" class="inline-flex items-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              AI测评中{{ remainingSeconds > 0 ? `，预计还需 ${remainingSeconds} 秒...` : '...' }}
            </span>
            <span v-else>开始评估</span>
          </button>
        </section>

        <!-- ── Step 3: Visual Features (when available) ── -->
        <section v-else-if="wizardStep === 3 && showVisualFeaturesStep && visualFeatures" class="flex-1 max-w-2xl mx-auto w-full px-4 pt-4 pb-24" aria-label="特征分析">
          <div class="mb-3 flex items-center gap-2">
            <button class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 min-h-[44px]" @click="onCancelAssessment">
              <i class="ri-arrow-left-s-line text-xl"></i>
            </button>
            <span class="w-7 h-7 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center font-bold">3</span>
            <h2 class="text-lg font-bold text-gray-800 dark:text-gray-100">特征分析</h2>
          </div>
          <VisualFeaturesCard :visual-features="visualFeatures" @continue="onVisualFeaturesContinue" />
          <div class="text-center mt-4 flex items-center justify-center gap-4">
            <button class="text-xs text-red-400 hover:text-red-500 dark:hover:text-red-300 min-h-[44px]" @click="onCancelAssessment">取消测评</button>
            <button class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 min-h-[44px]" @click="onVisualFeaturesContinue">跳过，直接查看 VASI 测评结果 →</button>
          </div>
        </section>

        <!-- ── Step 3b: Analyzing spinner (during upload, no visual features yet) ── -->
        <section v-else-if="wizardStep === 3 && isUploading" class="flex-1 flex flex-col items-center justify-center px-4" aria-label="AI分析中">
          <div class="text-center max-w-sm">
            <div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center">
              <svg class="animate-spin w-10 h-10 text-primary-500" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            </div>
            <h2 class="text-xl font-bold text-gray-800 dark:text-gray-100 mb-2">
              {{ uploadStage === 'uploading' ? '上传中...' : uploadStage === 'segmenting' ? 'AI 识别中...' : '分析中...' }}
            </h2>
            <p class="text-sm text-gray-500 dark:text-gray-400 mb-1">
              正在分析您的{{ partLabel }}照片
            </p>
            <p v-if="remainingSeconds > 0" class="text-xs text-gray-400 dark:text-gray-500">
              预计还需 {{ remainingSeconds }} 秒
            </p>
          </div>
        </section>

        <!-- ── Step 4: Mask Editor ── -->
        <section v-else-if="wizardStep === 4 && showContourEditor && imagePreview && assessmentResult" class="flex-1 flex flex-col px-3 pt-3 pb-4" aria-label="标注白斑">
          <!-- Compact info bar -->
          <div class="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <span class="font-medium text-gray-700 dark:text-gray-300">VASI {{ assessmentResult.vasiScore }} · {{ assessmentResult.stage }}</span>
            <span v-if="detectionLabel" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full" :class="detectionLabel.color">
              <i :class="detectionLabel.icon"></i> {{ detectionLabel.text }}
            </span>
            <span class="text-gray-400 dark:text-gray-500">蓝色=皮肤 · 粉色=白斑</span>
            <button class="text-primary-500 hover:text-primary-700 dark:hover:text-primary-300 min-h-[44px] px-1" @click="showDetailedHelp=!showDetailedHelp">
              {{ showDetailedHelp ? '收起 ↑' : '详细说明 ↓' }}
            </button>
          </div>

          <!-- Detailed info (collapsible) -->
          <div v-if="showDetailedHelp" class="mb-2 p-2 rounded-lg bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800 text-xs space-y-1">
            <p v-if="lesionSummary" class="text-primary-600 dark:text-primary-400">
              <i class="ri-scan-line mr-1"></i>检测到 <strong>{{ lesionSummary.total }}</strong> 处疑似白斑
              <span v-if="lesionSummary.highConf > 0" class="text-green-600 dark:text-green-400 ml-2"><i class="ri-check-double-line mr-0.5"></i>{{ lesionSummary.highConf }} 处高置信</span>
              <span v-if="lesionSummary.highConf < lesionSummary.total" class="text-amber-600 dark:text-amber-400 ml-2"><i class="ri-error-warning-line mr-0.5"></i>{{ lesionSummary.total - lesionSummary.highConf }} 处需确认</span>
            </p>
            <p v-if="assessmentResult.confidence !== undefined" class="text-gray-500 dark:text-gray-400">
              AI 信心度 {{ Math.round(assessmentResult.confidence * 100) }}%
              <span v-if="needsCorrection" class="text-amber-600 dark:text-amber-400 ml-2">建议手动修正</span>
            </p>
            <p class="text-primary-600 dark:text-primary-400">白斑占比 = 粉色区域 ÷ (蓝色+粉色区域)</p>
          </div>

          <!-- Mask Editor -->
          <div class="flex-1 min-h-0">
            <MaskEditor
              :image-url="imagePreview"
              :editable="true"
              :initial-skin-layer-url="aiSkinLayerUrl"
              :initial-lesion-layer-url="aiLesionLayerUrl"
              @confirm="(p) => onMaskConfirm(p.skinMaskDataUrl, p.lesionMaskDataUrl)"
              @cancel="onCancelAssessment"
            />
          </div>

          <!-- Bottom actions -->
          <div class="mt-3 flex items-center justify-end gap-3">
            <span v-if="isSubmittingContour" class="flex items-center gap-2 text-sm text-primary-500">
              <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              提交中...
            </span>
            <button v-else class="min-h-[44px] px-3 rounded-lg text-sm transition-colors" :class="highConfidence ? 'bg-primary-500 text-white hover:bg-primary-600 shadow-sm font-medium' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'" :disabled="isSubmittingContour" @click="onSkipContourEdit">
              <template v-if="highConfidence">
                <i class="ri-check-line mr-1"></i>AI 识别准确，直接查看结果
              </template>
              <template v-else>
                跳过，直接查看结果 →
              </template>
            </button>
          </div>

          <!-- Diff result -->
          <div v-if="contourDiffResult" class="mt-3 p-3 rounded-xl border" :class="contourDiffResult.modified ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'">
            <div class="flex items-center gap-2">
              <i :class="contourDiffResult.modified ? 'ri-error-warning-line text-amber-500' : 'ri-check-double-line text-green-500'"></i>
              <span class="text-xs font-medium" :class="contourDiffResult.modified ? 'text-amber-700 dark:text-amber-300' : 'text-green-700 dark:text-green-300'">
                {{ contourDiffResult.modified ? `AI与手动标注存在差异（平均偏差: ${(contourDiffResult.avg_point_distance ?? 0).toFixed(3)}），已记录用于模型优化` : 'AI识别结果与您的标注一致！' }}
              </span>
            </div>
          </div>
        </section>

        <!-- ── Step 5: Results ── -->
        <section v-else-if="wizardStep === 5" class="flex-1 max-w-2xl mx-auto w-full px-4 pt-4 pb-24 space-y-4" aria-label="评估结果" style="padding-bottom: calc(4rem + env(safe-area-inset-bottom, 0px))">
          <template v-if="lastAssessment">
            <!-- Result Card -->
            <div class="card p-4 border-l-4" :class="{
              'border-green-500': lastAssessment.vasiScore < 10,
              'border-amber-500': lastAssessment.vasiScore >= 10 && lastAssessment.vasiScore < 25,
              'border-orange-500': lastAssessment.vasiScore >= 25 && lastAssessment.vasiScore < 50,
              'border-red-500': lastAssessment.vasiScore >= 50,
            }">
              <div class="flex items-start justify-between mb-3">
                <div>
                  <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100"><i class="ri-clipboard-line"></i> 评估结果</h2>
                  <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{{ partLabel }} · {{ lastAssessment.bodySite }}</p>
                </div>
                <button @click="startNewAssessment" class="text-sm text-primary-600 dark:text-primary-400 hover:underline min-h-[44px]">
                  <i class="ri-add-line mr-0.5"></i>新评估
                </button>
              </div>

              <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
                <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
                  <div class="text-2xl font-bold" :class="getScoreInterpretation(lastAssessment.vasiScore).color">{{ lastAssessment.vasiScore }}</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">VASI评分</div>
                </div>
                <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
                  <div class="text-2xl font-bold" :class="getScoreInterpretation(lastAssessment.vasiScore).color">{{ getScoreInterpretation(lastAssessment.vasiScore).level }}</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">严重程度</div>
                </div>
                <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
                  <div class="text-2xl font-bold text-gray-700 dark:text-gray-200">{{ lastAssessment.areaPercentage }}%</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400" title="白斑面积 ÷ 该部位皮肤区域面积">{{ !privacyStore.privacyMode ? '白斑占比' : '***' }}</div>
                </div>
                <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
                  <div class="text-2xl font-bold" :class="lastAssessment.stage === '好转' ? 'text-green-600' : lastAssessment.stage === '扩散' || lastAssessment.stage === '进展期' ? 'text-red-600' : 'text-amber-600'">{{ lastAssessment.stage }}</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">病情阶段</div>
                </div>
              </div>

              <!-- Sparkline trend -->
              <div v-if="sparklineData && sparklineData.length >= 2" class="mb-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-xs text-gray-500 dark:text-gray-400"><i class="ri-line-chart-line mr-1"></i>VASI 趋势</span>
                  <span class="text-xs font-medium" :class="sparklineData[sparklineData.length-1] < sparklineData[0] ? 'text-green-600 dark:text-green-400' : sparklineData[sparklineData.length-1] > sparklineData[0] ? 'text-red-600 dark:text-red-400' : 'text-gray-500'">
                    {{ sparklineData[sparklineData.length-1] < sparklineData[0] ? '↓ 改善' : sparklineData[sparklineData.length-1] > sparklineData[0] ? '↑ 需关注' : '→ 稳定' }}
                  </span>
                </div>
                <svg class="w-full h-10" viewBox="0 0 100 40" preserveAspectRatio="none">
                  <polyline
                    :points="sparklineData!.map((v, i) => `${(i / (sparklineData!.length - 1)) * 100},${40 - (v / Math.max(...sparklineData!)) * 35}`).join(' ')"
                    fill="none"
                    :stroke="sparklineData[sparklineData.length-1] < sparklineData[0] ? '#10b981' : sparklineData[sparklineData.length-1] > sparklineData[0] ? '#ef4444' : '#9ca3af'"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </div>

              <div v-if="lastAssessment.confidence !== undefined && lastAssessment.confidence < 0.5" class="text-xs text-amber-600 dark:text-amber-400 mb-2 p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20">
                <i class="ri-error-warning-line mr-1"></i>本次评估信心度较低（{{ Math.round(lastAssessment.confidence * 100) }}%），建议在更好的光照条件下重新拍照
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
                <div v-if="lastAssessment.classification" class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                  <h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"><i class="ri-price-tag-3-line"></i> 分型</h3>
                  <p class="text-sm text-gray-600 dark:text-gray-400">{{ lastAssessment.classification }}白癜风<span class="text-[10px] text-gray-400 dark:text-gray-500 ml-1">（仅供参考）</span></p>
                </div>
              </div>

              <button @click="createAssessmentDraft" class="btn-primary w-full mt-3 flex items-center justify-center gap-2 py-2.5 text-sm min-h-[44px]">
                <i class="ri-send-plane-line"></i>分享至发现
              </button>
              <p class="text-xs text-gray-400 dark:text-gray-500 mt-3 text-center"><i class="ri-error-warning-line"></i> 以上解读仅供参考，不构成医疗诊断建议。</p>
            </div>

            <!-- Feedback prompt -->
            <FeedbackPrompt v-if="lastAssessment.id" :assessment-id="lastAssessment.id" @dismiss="() => {}" />
          </template>

          <!-- Assessment History -->
          <div class="card p-4 md:p-6 rounded-2xl">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
                <i class="ri-line-chart-line"></i>
                <template v-if="selectedBodySite">{{ partLabel }} · </template>评估历史
              </h2>
              <div class="flex items-center gap-2">
                <template v-if="selectMode">
                  <button class="text-sm text-primary-600 dark:text-primary-400" :disabled="selectedIds.size < 2" @click="compareSelected"><i class="ri-arrow-left-right-line mr-0.5"></i>对比</button>
                  <button class="text-sm text-red-500 hover:text-red-600 dark:text-red-400" @click="deleteSelected" :disabled="selectedIds.size === 0">删除({{ selectedIds.size }})</button>
                  <button class="text-sm text-gray-500 dark:text-gray-400" @click="toggleSelectMode">取消</button>
                </template>
                <button v-else-if="displayHistory.length" class="text-sm text-primary-600 dark:text-primary-400 hover:underline" @click="toggleSelectMode">多选</button>
                <button v-if="displayHistory.length" class="text-sm text-primary-600 dark:text-primary-400 hover:underline" @click="startNewAssessment"><i class="ri-add-line mr-0.5"></i>新评估</button>
              </div>
            </div>
            <div v-if="loadingHistory" class="text-center py-8 text-gray-400 dark:text-gray-500">
              <div class="text-4xl mb-3 animate-pulse"><i class="ri-bar-chart-2-line"></i></div><p>加载中...</p>
            </div>
            <div v-else-if="compareWithPrevious.length" class="space-y-2 overflow-hidden">
              <div v-for="record in compareWithPrevious" :key="record.id" class="relative">
                <div class="flex items-center" :class="selectMode ? '' : (isSwiped(record.id) ? '-translate-x-16' : 'translate-x-0')" @touchstart="onTouchStart($event)" @touchend="onTouchEnd($event, record.id)">
                  <div v-if="selectMode" class="pr-3 shrink-0">
                    <input type="checkbox" :checked="selectedIds.has(record.id)" @change="toggleSelect(record.id)" class="w-5 h-5 rounded border-gray-300 text-primary-500 focus:ring-primary-400" />
                  </div>
                  <div class="flex-1 min-w-0 flex items-center gap-3 py-3 px-3 rounded-xl bg-gray-50 dark:bg-gray-800 cursor-pointer" @click="viewDetail(record.id)">
                    <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0 relative" :class="record.stage === '稳定期' || record.stage === '好转' ? 'bg-green-100 dark:bg-green-900/30' : 'bg-amber-100 dark:bg-amber-900/30'">
                      <span class="text-xs font-bold">{{ record.vasiScore }}</span>
                      <span v-if="record.vasiDiff !== null" class="absolute -top-1 -right-1 text-[9px] font-bold leading-none px-1 rounded-full" :class="record.vasiDiff < 0 ? 'bg-green-500 text-white' : record.vasiDiff > 0 ? 'bg-red-500 text-white' : 'bg-gray-400 text-white'">
                        {{ record.vasiDiff < 0 ? '↓' : record.vasiDiff > 0 ? '↑' : '=' }}
                      </span>
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 text-sm">
                        <span class="font-medium text-gray-900 dark:text-gray-100">{{ PART_LABELS[record.bodySite] || record.bodySite }}</span>
                        <span class="text-gray-400 dark:text-gray-500">{{ record.date }}</span>
                      </div>
                      <div class="flex items-center gap-3 mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                        <span>VASI <strong class="text-gray-700 dark:text-gray-200">{{ !privacyStore.privacyMode ? record.vasiScore : '**' }}</strong></span>
                        <span>面积 <strong class="text-gray-700 dark:text-gray-200">{{ !privacyStore.privacyMode ? record.areaPercentage + '%' : '**%' }}</strong></span>
                        <span v-if="record.vasiDiff !== null && record.vasiDiff !== 0" class="font-medium" :class="record.vasiDiff < 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                          {{ record.vasiDiff > 0 ? '+' : '' }}{{ record.vasiDiff.toFixed(1) }}
                        </span>
                        <span class="badge text-[10px] px-1.5 py-0.5" :class="record.stage === '稳定期' || record.stage === '好转' ? 'badge-success' : 'badge bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'">{{ record.stage }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <button v-if="!selectMode && isSwiped(record.id)" class="absolute right-0 top-0 bottom-0 w-16 flex items-center justify-center bg-red-500 text-white rounded-r-xl" @click="deleteSingle(record.id)" :disabled="deletingIds.has(record.id)">
                  <i class="ri-delete-bin-line"></i>
                </button>
              </div>
              <div v-if="historyTotal > 0" class="flex items-center justify-between gap-2 pt-3 text-xs text-gray-600 dark:text-gray-400">
                <div class="flex items-center gap-1">
                  <span>每页</span>
                  <select :value="historyPageSize" @change="setHistoryPageSize(Number(($event.target as HTMLSelectElement).value))" class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-1.5 py-0.5 text-xs">
                    <option :value="10">10</option>
                    <option :value="20">20</option>
                    <option :value="50">50</option>
                  </select>
                  <span>条 / 共 {{ historyTotal }} 条</span>
                </div>
                <div class="flex items-center gap-1.5">
                  <button class="px-2 py-0.5 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40" :disabled="historyPage <= 1 || loadingHistory" @click="goToHistoryPage(historyPage - 1)">上一页</button>
                  <span>{{ historyPage }} / {{ historyTotalPages }}</span>
                  <button class="px-2 py-0.5 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40" :disabled="historyPage >= historyTotalPages || loadingHistory" @click="goToHistoryPage(historyPage + 1)">下一页</button>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-8 text-gray-400 dark:text-gray-500">
              <div class="text-4xl mb-3"><i class="ri-bar-chart-2-line"></i></div><p>暂无评估记录</p>
            </div>
          </div>
        </section>

        <!-- Fallback -->
        <section v-else class="flex-1 flex flex-col items-center justify-center px-4 text-gray-400 dark:text-gray-500">
          <i class="ri-refresh-line text-4xl mb-3"></i>
          <p>正在准备...</p>
          <button class="btn-ghost mt-4" @click="wizardStep = 1">重新开始</button>
        </section>
      </main>
    </div>

    <!-- Camera Modal -->
    <BodyPartCamera v-model="showCamera" :body-part="selectedBodySite" @captured="handleCameraCapture" />
  </template>
</template>

<style scoped>
.card {
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 0 2px 20px rgba(100, 80, 60, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04);
}
:root.dark .card,
.dark .card {
  background: rgba(30, 30, 46, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.15), 0 1px 3px rgba(0, 0, 0, 0.1);
}
</style>