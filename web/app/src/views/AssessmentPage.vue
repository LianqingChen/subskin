<script setup lang="ts">
/**
 * AssessmentPage — 白斑测评（重构版 v3）
 *
 * 3步流程：拍照评估 → AI分析+画布 → 结果+解读
 * 侧边栏（桌面端）/ 底部sheet（移动端）：评估历史
 *
 * 架构：3个独立 composable + 4个独立组件，全部符合行数规范。
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDrafts } from '@/composables/useDrafts'
import { useToast } from '@/composables/useToast'
import { useVasiUpload } from '@/composables/useVasiUpload'
import { useVasiAssess } from '@/composables/useVasiAssess'
import { useVasiHistory } from '@/composables/useVasiHistory'
import { communityApi } from '@/api/community'
import AssessmentStep1Capture from '@/components/tracker/AssessmentStep1Capture.vue'
import AssessmentStep2Analyze from '@/components/tracker/AssessmentStep2Analyze.vue'
import AssessmentStep3Result from '@/components/tracker/AssessmentStep3Result.vue'
import AssessmentHistoryPanel from '@/components/tracker/AssessmentHistoryPanel.vue'

type Step = 1 | 2 | 3

const router = useRouter()
const toast = useToast()
const isSubmittingPhoto = ref(false)
const { saveDraftWithSync } = useDrafts()

// ── Composables ──
const upload = useVasiUpload()
const assess = useVasiAssess()
const history = useVasiHistory()

// ── Wizard state ──
const wizardStep = ref<Step>(1)
const showHistory = ref(false)

// ── Step transitions ──
function onBodyPartSelect(site: string) {
  upload.setBodySite(site)
  history.loadHistory(true, site)
}

function onCameraCapture(file: File, meta?: { hasReferenceCard?: boolean }) {
  if (meta?.hasReferenceCard) upload.setHasReferenceCard(true)
  const dt = new DataTransfer()
  dt.items.add(file)
  upload.handleFileSelect({ target: { files: dt.files } } as unknown as Event)
}

async function onSubmitPhoto() {
  if (!upload.uploadedImage.value) {
    toast.show('请先拍照或选择照片', 'warning', 3000)
    return
  }
  if (!upload.selectedBodySite.value) {
    toast.show('请先选择评估部位', 'warning', 3000)
    return
  }
  isSubmittingPhoto.value = true
  try {
    await assess.submitAssessment(
      upload.uploadedImage.value,
      upload.selectedBodySite.value,
      'quick',
      upload.hasReferenceCard.value,
    )
    // submitAssessment sets showContourEditor=true on success
    // The watch below will handle step transition
  } catch {
    isSubmittingPhoto.value = false
    // stay on step 1, error already shown by useVasiAssess
  }
}

// Watch: when submit completes and contour editor is ready, go to step 2
// or if no editor needed, go directly to step 3
watch(() => assess.isUploading.value, (uploading) => {
  if (!uploading && isSubmittingPhoto.value) {
    // API call just finished
    isSubmittingPhoto.value = false
    if (assess.showContourEditor.value && upload.imagePreview.value) {
      // MaskEditor ready — go to step 2
      wizardStep.value = 2
    } else if (assess.assessmentResult.value) {
      // No contour editing needed — show result directly
      wizardStep.value = 3
    }
  }
})

async function onMaskConfirm(skinMaskDataUrl: string, lesionMaskDataUrl: string, annotatedImage: string | null) {
  try {
    await assess.handleTwoLayerConfirm(skinMaskDataUrl, lesionMaskDataUrl)
  } catch (e: any) {
    console.error('handleTwoLayerConfirm failed:', e)
    // Force completion even on error
    if (assess.assessmentResult.value) {
      assess.lastAssessment.value = assess.assessmentResult.value as any
    }
  }
  // Store annotated image for sharing (before cleanupState clears it)
  assess.annotatedImage.value = annotatedImage
  wizardStep.value = 3
  history.loadHistory(true)
}

async function onSkipContour() {
  // Generate annotated image from AI layers (no manual edits) for sharing
  if (assess.aiSkinLayerUrl.value && assess.aiLesionLayerUrl.value && upload.imagePreview.value) {
    assess.annotatedImage.value = await composeAnnotatedImage(
      upload.imagePreview.value,
      assess.aiSkinLayerUrl.value,
      assess.aiLesionLayerUrl.value,
    )
  }
  try {
    await assess.skipContourEdit()
    wizardStep.value = 3
    history.loadHistory(true)
  } catch (e: any) {
    console.error('skipContourEdit failed:', e)
    if (assess.assessmentResult.value) {
      assess.lastAssessment.value = assess.assessmentResult.value as any
    }
    wizardStep.value = 3
    history.loadHistory(true)
  }
}

async function composeAnnotatedImage(imageUrl: string, skinLayerUrl: string, lesionLayerUrl: string): Promise<string | null> {
  try {
    const loadImage = (src: string) => new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = src
    })
    const [baseImg, skinImg, lesionImg] = await Promise.all([loadImage(imageUrl), loadImage(skinLayerUrl), loadImage(lesionLayerUrl)])
    const w = skinImg.width || baseImg.naturalWidth
    const h = skinImg.height || baseImg.naturalHeight
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(baseImg, 0, 0, w, h)
    ctx.globalAlpha = 0.55
    ctx.drawImage(skinImg, 0, 0, w, h)
    ctx.drawImage(lesionImg, 0, 0, w, h)
    ctx.globalAlpha = 1
    return canvas.toDataURL('image/png')
  } catch {
    return null
  }
}

async function onCancelAssessment() {
  isSubmittingPhoto.value = false
  assess.isUploading.value = false
  wizardStep.value = 1
  if (assess.assessmentResult.value) {
    try { await assess.cancelAssessment() } catch {}
  }
}

function onNewAssessment() {
  assess.cleanupState()
  assess.annotatedImage.value = null
  upload.resetAll()
  wizardStep.value = 1
  history.loadHistory(true)
}

/**
 * Convert a data URL (base64) to a File object so it can be uploaded
 * via communityApi.uploadImage which expects a File/Blob.
 */
function dataUrlToFile(dataUrl: string, filename = 'annotated.png'): File {
  const [meta, base64] = dataUrl.split(',')
  const mime = meta.match(/:(.*?);/)?.[1] || 'image/png'
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new File([bytes], filename, { type: mime })
}

async function uploadAnnotatedImage(dataUrl: string): Promise<string | null> {
  try {
    const file = dataUrlToFile(dataUrl)
    const res = await communityApi.uploadImage(file)
    return res.image_url
  } catch (e) {
    console.error('Failed to upload annotated image:', e)
    return null
  }
}

async function onShareResult() {
  const a = assess.lastAssessment.value
  if (!a) return
  const today = new Date().toISOString().split('T')[0]
  const htmlContent =
    `<p>今天做了VASI评估：</p>` +
    `<ul>` +
    `<li>评估部位：${a.bodySite}</li>` +
    `<li>VASI评分：${a.vasiScore}</li>` +
    `<li>白斑占该部位皮肤：${a.areaPercentage}%</li>` +
    `<li>病情阶段：${a.stage}</li>` +
    `<li>分型：${a.classification || '未分型'}</li>` +
    `</ul>` +
    `<p></p><p>今日感受：</p>`

  // 1st cover: annotated image (original + AI skin/lesion layers) if available
  // 2nd cover: original uploaded photo
  // Must upload data URL to server first to get a real URL that the
  // backend and ImagePostEditor can handle (localStorage and API both
  // reject raw base64 data URLs).
  const images: string[] = []
  if (assess.annotatedImage.value) {
    const uploadedUrl = await uploadAnnotatedImage(assess.annotatedImage.value)
    if (uploadedUrl) images.push(uploadedUrl)
  }
  if (a.imageUrl) images.push(a.imageUrl)
  const draftKey = await saveDraftWithSync({
    type: 'image',
    title: `${today} 病情日记`,
    content: htmlContent,
    images,
    categoryId: null,
    mood: '💪坚持中',
    isPrivate: true,
  })
  toast.success('已生成草稿')
  router.push({ path: '/community/new', query: { type: 'image', draftKey } })
}

function onNewAssessmentHideHistory() {
  onNewAssessment()
  showHistory.value = false
}

function goBack() {
  if (wizardStep.value === 1) {
    router.push({ name: 'assistant' })
  } else if (wizardStep.value === 2) {
    // Cancel assessment and return to step 1
    onCancelAssessment()
    // onCancelAssessment already calls wizardStep.value = 1 via cancelAssessment
  } else if (wizardStep.value === 3) {
    // From results, go back to step 1 for new assessment
    onNewAssessment()
  }
}

function onHistoryViewDetail(id: number) {
  showHistory.value = false
  router.push({ name: 'vasi-detail', params: { id } })
}

function onHistoryCompare() {
  if (history.selectedIds.value.size < 2) return
  showHistory.value = false
  const ids = Array.from(history.selectedIds.value).slice(0, 2).join(',')
  router.push({ name: 'vasi-compare', query: { ids } })
}

const stepLabel = computed(() => {
  switch (wizardStep.value) {
    case 1: return '拍照评估'
    case 2: return assess.isUploading.value ? 'AI 分析中...' : '标注确认'
    case 3: return '评估结果'
    default: return '白斑测评'
  }
})

onMounted(() => history.loadHistory(true))
</script>

<template>
  <div class="min-h-[100dvh] flex flex-col bg-[#F5F7FA] dark:bg-gray-900">
    <!-- ═══ Sticky Header ═══ -->
    <header class="sticky top-0 z-30 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md border-b border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between px-4 py-2.5">
        <button
          class="w-10 h-10 flex items-center justify-center rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors min-h-[44px]"
          aria-label="返回"
          @click="goBack"
        >
          <i class="ri-arrow-left-s-line text-xl text-gray-500"></i>
        </button>

        <div class="flex items-center gap-3">
          <div class="flex items-center gap-1.5">
            <span
              v-for="s in 3" :key="s"
              class="h-2 rounded-full transition-all duration-300"
              :class="wizardStep === s
                ? 'bg-primary-500 w-6'
                : wizardStep > s
                  ? 'bg-primary-300 w-2'
                  : 'bg-gray-200 dark:bg-gray-600 w-2'"
            ></span>
          </div>
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ stepLabel }}</span>
        </div>

        <button
          class="w-10 h-10 flex items-center justify-center rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors min-h-[44px] lg:hidden"
          aria-label="评估历史"
          @click="showHistory = !showHistory"
        >
          <i :class="showHistory ? 'ri-close-line' : 'ri-history-line'" class="text-xl text-gray-500"></i>
        </button>
        <div class="w-10 hidden lg:block"></div>
      </div>
    </header>

    <!-- ═══ Main Content ═══ -->
    <div class="flex-1 flex">
      <!-- Desktop: History sidebar -->
      <aside class="hidden lg:block w-52 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0">
        <AssessmentHistoryPanel
          :items="history.recentAssessments.value"
          :loading="history.loadingHistory.value"
          :total="history.historyTotal.value"
          :page="history.historyPage.value"
          :page-size="history.historyPageSize.value"
          :total-pages="history.historyTotalPages.value"
          :select-mode="history.selectMode.value"
          :selected-ids="history.selectedIds.value"
          :swiped-id="history.swipedId.value"
          :deleting-ids="history.deletingIds.value"
          @view-detail="onHistoryViewDetail"
          @compare-selected="onHistoryCompare"
          @new-assessment="onNewAssessmentHideHistory"
          @toggle-select-mode="history.toggleSelectMode"
          @toggle-select="history.toggleSelect"
          @delete-single="history.deleteSingle"
          @delete-selected="history.deleteSelected"
          @go-to-page="history.goToPage"
          @set-page-size="history.setPageSize"
          @touch-start="history.onTouchStart"
          @touch-end="history.onTouchEnd"
        />
      </aside>

      <!-- Step content -->
      <main class="flex-1 flex flex-col overflow-y-auto">
        <AssessmentStep1Capture
          v-if="wizardStep === 1"
          :selected-body-site="upload.selectedBodySite.value"
          :image-preview="upload.imagePreview.value"
          :quality-result="upload.qualityResult.value"
          :quality-checking="upload.qualityChecking.value"
          @select-part="onBodyPartSelect"
          @upload-file="upload.handleFileSelect"
          :is-submitting="isSubmittingPhoto"
          :upload-stage="assess.uploadStage.value"
          @open-camera="() => {}"
          @camera-capture="onCameraCapture"
          @remove-image="upload.removeImage"
          @submit="onSubmitPhoto"
        />

        <AssessmentStep2Analyze
          v-else-if="wizardStep === 2"
          :is-uploading="assess.isUploading.value"
          :upload-stage="assess.uploadStage.value"
          :image-preview="upload.imagePreview.value"
          :show-contour-editor="assess.showContourEditor.value"
          :ai-skin-layer-url="assess.aiSkinLayerUrl.value"
          :ai-lesion-layer-url="assess.aiLesionLayerUrl.value"
          :assessment-source="assess.assessmentSource.value"
          :suspected-lesions="assess.suspectedLesions.value"
          :visual-features="assess.visualFeatures.value"
          :high-confidence="assess.highConfidence.value"
          :is-submitting-contour="assess.isSubmittingContour.value"
          :assessment-result="assess.assessmentResult.value"
          @mask-confirm="onMaskConfirm"
          @skip-contour-edit="onSkipContour"
          @cancel-assessment="onCancelAssessment"
        />

        <AssessmentStep3Result
          v-else-if="wizardStep === 3"
          :last-assessment="assess.lastAssessment.value"
          :sparkline-data="history.sparklineData.value"
          @new-assessment="onNewAssessment"
          @share-result="onShareResult"
        />

        <div v-else class="flex-1 flex flex-col items-center justify-center px-4 text-gray-400">
          <i class="ri-refresh-line text-3xl mb-2"></i>
          <p>正在准备...</p>
        </div>
      </main>
    </div>



    <!-- ═══ Mobile: History bottom sheet ═══ -->
    <Transition name="slide-up">
      <div v-if="showHistory" class="fixed inset-0 z-40 lg:hidden">
        <div class="absolute inset-0 bg-black/30" @click="showHistory = false"></div>
        <div class="absolute bottom-0 left-0 right-0 bg-white dark:bg-gray-800 rounded-t-2xl max-h-[70vh] flex flex-col shadow-xl">
          <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
            <span class="text-sm font-semibold text-gray-700 dark:text-gray-300">评估历史</span>
            <button class="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 dark:hover:bg-gray-700" @click="showHistory = false">
              <i class="ri-close-line text-gray-500"></i>
            </button>
          </div>
          <div class="flex-1 overflow-y-auto">
            <AssessmentHistoryPanel
              :items="history.recentAssessments.value"
              :loading="history.loadingHistory.value"
              :total="history.historyTotal.value"
              :page="history.historyPage.value"
              :page-size="history.historyPageSize.value"
              :total-pages="history.historyTotalPages.value"
              :select-mode="history.selectMode.value"
              :selected-ids="history.selectedIds.value"
              :swiped-id="history.swipedId.value"
              :deleting-ids="history.deletingIds.value"
              @view-detail="onHistoryViewDetail"
              @compare-selected="onHistoryCompare"
              @new-assessment="onNewAssessmentHideHistory"
              @toggle-select-mode="history.toggleSelectMode"
              @toggle-select="history.toggleSelect"
              @delete-single="history.deleteSingle"
              @delete-selected="history.deleteSelected"
              @go-to-page="history.goToPage"
              @set-page-size="history.setPageSize"
              @touch-start="history.onTouchStart"
              @touch-end="history.onTouchEnd"
            />
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: opacity 0.25s ease;
}
.slide-up-enter-active > div:last-child,
.slide-up-leave-active > div:last-child {
  transition: transform 0.25s ease;
}
.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
}
.slide-up-enter-from > div:last-child,
.slide-up-leave-to > div:last-child {
  transform: translateY(100%);
}
</style>
