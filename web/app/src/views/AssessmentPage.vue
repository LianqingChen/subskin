<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useVasiUpload } from '@/composables/useVasiUpload'
import { useVasiAssess } from '@/composables/useVasiAssess'
import { useVasiHistory } from '@/composables/useVasiHistory'
import { useVasiShare } from '@/composables/useVasiShare'
import { useComparisonHistory } from '@/composables/useComparisonHistory'
import siteModules from '../../../shared/site-modules.json'
import { BODY_SITES } from '@/constants/bodySites'
import type { ObservationContext } from '@/types/assessment'
import AssessmentCapture from '@/components/tracker/AssessmentCapture.vue'
import AssessmentObservationResult from '@/components/tracker/AssessmentObservationResult.vue'
import AssessmentRecords from '@/components/tracker/AssessmentRecords.vue'
import type { ObservationRecord } from '@/components/tracker/AssessmentRecords.vue'
import ComparisonHistoryPanel from '@/components/tracker/ComparisonHistoryPanel.vue'
import AnnotationReviewPanel from '@/components/tracker/AnnotationReviewPanel.vue'
import { defaultCaptureDate, localToday, type CaptureSource } from '@/utils/capture-date'
import { toProtectedFileUrl } from '@/utils/file-url'
import { vasiApi } from '@/api/vasi'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import AssessmentVisualHome from '@/components/tracker/AssessmentVisualHome.vue'
import AssessmentSectionNav from '@/components/tracker/AssessmentSectionNav.vue'
import BodyPartCamera from '@/components/tracker/BodyPartCamera.vue'
import { queueComparisonPhotos } from '@/composables/useQuickPhotoCompare'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()
const upload = useVasiUpload()
const assess = useVasiAssess()
const history = useVasiHistory()
const reports = useComparisonHistory()
const share = useVasiShare(assess)
type Screen = 'home' | 'capture' | 'result' | 'records'
const screen = ref<Screen>('home')
const pageRef = ref<HTMLElement | null>(null)
watch(screen, async () => { await nextTick(); pageRef.value?.scrollTo({ top: 0 }) })
const context = ref<ObservationContext>({ intent: 'discovery' })
const baselineUrl = ref<string | null>(null)
const editing = ref(false)
const recordTab = ref<'photos' | 'reports'>('photos')
const homeCamera = ref(false)
const pendingCapture = ref<{ record: ObservationRecord; site: string } | null>(null)
const dateNote = ref('')
// 追踪拍摄：编辑时把上次记录的白斑范围作为参考轮廓（构图可能不同，仅供参考，不会自动采用）。
const baselineMaskUrl = ref<string | null>(null)
watch(editing, async on => {
  baselineMaskUrl.value = null
  const id = context.value.baseline_id
  if (!on || !id) return
  try {
    const data = await vasiApi.getAssessment(id)
    if (editing.value && context.value.baseline_id === id) baselineMaskUrl.value = data.lesion_layer_data_url ?? null
  } catch { /* 参考层可缺省 */ }
})
let dateGeneration = 0
const assessmentLabel = siteModules.modules.find(m => m.path === '/assessment')?.label || '记录'
const result = computed(() => assess.lastAssessment.value)
const busy = computed(() => assess.isUploading.value || assess.isSubmittingContour.value)
const workScreen = computed(() => screen.value === 'capture' || (screen.value === 'result' && editing.value))
const pageTitle = computed(() => ({ home: assessmentLabel, capture: '添加照片', result: '本次记录', records: '我的记录' }[screen.value]))
watch(() => route.query.tab, tab => { if (tab === 'exam' || tab === 'report') router.replace({ name: 'assessment-exam' }) }, { immediate: true })
function requireLogin() { if (auth.isLoggedIn) return true; auth.showLoginModal = true; return false }
async function records() {
  if (!requireLogin()) return
  recordTab.value = 'photos'; screen.value = 'records'
  await router.replace({ path: '/assessment', query: { view: 'records' } })
  await Promise.all([history.loadHistory(true), reports.load(true)])
}
function startRecording() {
  pendingCapture.value = null
  const site = upload.selectedBodySite.value
  upload.resetAll(); upload.setBodySite(site)
  assess.cleanupState(); editing.value = false; baselineUrl.value = null
  context.value = { intent: 'discovery' }
}
function cameraFromHome() {
  if (!requireLogin()) return
  if (!upload.selectedBodySite.value) { toast.warning('先点选身体部位'); return }
  startRecording()
  homeCamera.value = true
}
function cameraCaptured(file: File) {
  const pending = pendingCapture.value
  pendingCapture.value = null
  if (pending) {
    upload.resetAll(); assess.cleanupState(); editing.value = false
    upload.setBodySite(pending.site)
    baselineUrl.value = pending.record.imageUrl || null
    context.value = { ...pending.record.observation, intent: 'tracking', baseline_id: pending.record.id, capture_date: '', label: pending.record.observation?.label || pending.record.bodySite }
    if (route.query.baseline || route.query.view) void router.replace({ path: '/assessment' })
  }
  void fileSelected(file, 'camera')
  homeCamera.value = false
  screen.value = 'capture'
}
function cameraCancelled() {
  const pending = pendingCapture.value
  pendingCapture.value = null
  if (!pending || Number(route.query.baseline) !== pending.record.id) return
  const destination = router.resolve({ name: 'vasi-detail', params: { id: pending.record.id } })
  if (window.history.state?.back === destination.fullPath) router.back()
  else void router.replace(destination.fullPath)
}
function galleryFromHome(files: File[]) {
  if (!requireLogin()) return
  if (!upload.selectedBodySite.value) { toast.warning('先点选身体部位'); return }
  const supported = files.every(file => ['image/jpeg', 'image/png', 'image/webp'].includes(file.type) && file.size <= 10 * 1024 * 1024)
  if (!supported) { toast.warning('请选择 10MB 以内的 JPG、PNG 或 WebP 照片'); return }
  if (files.length > 1) {
    if (files.length !== 2) { toast.warning('白斑对比请选择两张照片'); return }
    queueComparisonPhotos(files)
    photoCompare()
    return
  }
  if (files[0]) { startRecording(); fileSelected(files[0]); screen.value = 'capture' }
}
function photoCompare() {
  if (!requireLogin()) return
  if (!upload.selectedBodySite.value) { toast.warning('先点选身体部位'); return }
  router.push({ name: 'assessment-photo-compare', query: { site: upload.selectedBodySite.value } })
}
function continueRecord(record: ObservationRecord) {
  const site = Object.values(BODY_SITES).find(s => s.label === record.bodySite || s.id === record.bodySite || (s.id === 'neck' && record.bodySite === '颈部'))
  if (!site) { toast.warning('这条历史记录需要重新确认部位，请建立新的拍摄位置'); return }
  pendingCapture.value = { record, site: site.id }
  homeCamera.value = true
}
async function fileSelected(file: File, source: CaptureSource = 'gallery') {
  if (!upload.selectFile(file)) return
  const generation = ++dateGeneration
  const today = localToday()
  dateNote.value = source === 'camera' ? '已填写本次拍摄日期' : '正在读取照片日期…'
  context.value = { ...context.value, capture_date: source === 'camera' ? today : '', calibration: undefined }
  const defaults = await defaultCaptureDate(file, source, today)
  if (generation !== dateGeneration || upload.uploadedImage.value !== file) return
  context.value = { ...context.value, capture_date: defaults.date }
  dateNote.value = defaults.note
}
function changeDate(value: string) {
  dateGeneration++
  context.value = { ...context.value, capture_date: value }
  dateNote.value = '已手动修改照片日期'
}
function retryQuality() {
  if (upload.qualityNeedsLogin.value || !auth.isLoggedIn) { auth.showLoginModal = true; return }
  if (upload.uploadedImage.value) void upload.checkQuality(upload.uploadedImage.value)
}
watch(() => auth.token, (token, previous) => {
  if (token && token !== previous && upload.qualityNeedsLogin.value) {
    upload.qualityNeedsLogin.value = false
    upload.qualityError.value = '登录已更新，请重新检查照片'
  }
})
async function submit() {
  if (!requireLogin() || !upload.uploadedImage.value || busy.value) return
  if (upload.qualityChecking.value || !upload.qualityResult.value || upload.qualityResult.value.overall === 'poor') { toast.warning('请先完成照片质量检查'); return }
  if (!context.value.capture_date) { toast.warning('请确认照片日期'); return }
  try {
    await assess.submitAssessment(upload.uploadedImage.value, upload.selectedBodySite.value, 'quick', false, context.value)
    if (result.value) { editing.value = true; screen.value = 'result' }
  } catch { /* Error already shown by the composable; retain photograph for retry. */ }
}
async function save() { if (result.value?.measurement?.annotation?.review_state === 'pending') { editing.value = true; return } try { await assess.skipContourEdit(); await history.loadHistory(true, upload.selectedBodySite.value) } catch { /* Preserve retry state. */ } }
async function confirmMasks(payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string; uncertaintyReviewed: boolean; annotatedImageDataUrl?: string }) {
  try { await assess.handleTwoLayerConfirm(payload.skinMaskDataUrl, payload.lesionMaskDataUrl, payload.uncertaintyReviewed); assess.annotatedImage.value = payload.annotatedImageDataUrl || null; editing.value = false } catch { /* Preserve editor for retry. */ }
}
function compare(ids: number[]) { router.push({ name: 'vasi-compare', query: { ids: ids.join(',') } }) }
function compareBaseline() { if (result.value?.id && context.value.baseline_id) compare([context.value.baseline_id, result.value.id]) }
async function back() {
  if (busy.value) return
  if (editing.value && assess.autoFinalized.value) { editing.value = false; return }
  if (screen.value === 'result' && !assess.autoFinalized.value) {
    try { await assess.cancelAssessment() } catch { toast.error('退出未完成，请重试'); return }
  }
  editing.value = false
  screen.value = 'home'
  if (route.query.tab || route.query.view || route.query.baseline) router.replace({ path: '/assessment' })
}
onMounted(async () => {
  if (route.query.view === 'records') { await records(); return }
  if (auth.isLoggedIn) await history.loadHistory(true)
  const id = Number(route.query.baseline)
  if (Number.isInteger(id) && id > 0 && auth.isLoggedIn) {
    try {
      await assess.loadAssessment(id)
      const r = assess.lastAssessment.value
      if (r) continueRecord({ id:r.id, date:r.observation?.capture_date || '', bodySite:r.bodySite, imageUrl:r.imageUrl || undefined, observation:r.observation })
    } catch { toast.error('基线记录暂时无法加载') }
  }
})
watch(() => auth.user?.id, (owner, previous) => {
  if (previous != null && owner !== previous) {
    pendingCapture.value = null; assess.cancelPending(); upload.resetAll(); editing.value = false; homeCamera.value = false
    history.recentAssessments.value = []; reports.reports.value = []; screen.value = 'home'
  }
})
watch(() => auth.isLoggedIn, loggedIn => {
  if (loggedIn) history.loadHistory(true)
  else { pendingCapture.value = null; homeCamera.value = false; assess.cancelPending(); upload.resetAll(); history.recentAssessments.value = []; reports.reports.value = []; screen.value = 'home' }
})
</script>
<template>
  <div ref="pageRef" class="flex-1 min-h-0 bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100" :class="screen === 'home' ? 'assessment-home-shell' : workScreen ? 'assessment-work-shell' : 'overflow-y-auto'">
    <!-- 子工具条：手机端分段控件居中；平板/桌面与内容同宽左对齐，右侧「我的记录」带文字 -->
    <header class="assessment-toolbar sticky top-0 z-40 shrink-0 border-b border-gray-200/80 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div class="page grid min-h-[52px] grid-cols-[44px_minmax(0,1fr)_44px] items-center gap-1 md:flex md:gap-2">
        <button v-if="screen !== 'home'" class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800" aria-label="返回白斑记录" :disabled="busy" @click="back"><i class="ri-arrow-left-line text-xl" aria-hidden="true"></i></button>
        <span v-else class="md:hidden"></span>
        <div class="flex min-w-0 justify-center md:mr-auto md:justify-start"><AssessmentSectionNav active="skin" :locked="busy" @skin="back" /></div>
        <button class="flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-xl text-primary-700 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-gray-800 md:px-3" aria-label="我的记录" :disabled="busy" @click="records"><i class="ri-history-line text-xl md:text-lg" aria-hidden="true"></i><span class="hidden text-sm font-medium md:inline">我的记录</span></button>
      </div>
    </header>
    <div class="page flex gap-6" :class="screen === 'home' ? 'min-h-0 flex-1' : workScreen ? 'min-h-0 flex-1 py-2' : 'py-4 pb-[calc(4rem+env(safe-area-inset-bottom))] md:py-6 md:pb-10'">
      <section class="min-w-0 flex-1" :class="screen === 'home' ? 'min-h-0' : workScreen ? 'flex min-h-0 flex-col' : 'space-y-4'">
        <h1 class="sr-only">{{ pageTitle }}</h1>
        <AssessmentVisualHome v-if="screen === 'home'" :body-site="upload.selectedBodySite.value" :recent="history.recentAssessments.value" :logged-in="auth.isLoggedIn" :loading="history.loadingHistory.value" @select="upload.setBodySite" @camera="cameraFromHome" @files="galleryFromHome" @compare="photoCompare" @history="records" @continue="continueRecord" @need-part="toast.warning('先点选身体部位')" />
        <AssessmentCapture v-else-if="screen === 'capture'" fit-screen v-model:context="context" :body-site="upload.selectedBodySite.value" :preview="upload.imagePreview.value" :baseline-url="baselineUrl" :quality="upload.qualityResult.value" :checking="upload.qualityChecking.value" :quality-error="upload.qualityError.value" :needs-login="upload.qualityNeedsLogin.value" :date-note="dateNote" :busy="assess.isUploading.value" :stage="assess.uploadStage.value" @update:body-site="upload.setBodySite" @file="fileSelected" @date="changeDate" @retry-quality="retryQuality" @remove="upload.removeImage" @submit="submit" @cancel="assess.cancelPending" />
        <template v-else-if="screen === 'result' && result">
          <AnnotationReviewPanel v-if="editing" fit-screen :image="result.measurement?.annotation?.protocol === 'skin-seg-v2' ? toProtectedFileUrl(result.imageUrl) : upload.imagePreview.value || toProtectedFileUrl(result.imageUrl)" :skin="assess.aiSkinLayerUrl.value" :lesion="assess.aiLesionLayerUrl.value" :uncertain="result.measurement?.annotation?.uncertain_pixels ? result.measurement.annotation.uncertain_layer_data_url : null" :reference="baselineMaskUrl" :selector="result.measurement?.annotation?.protocol === 'skin-seg-v2' ? assess.selectRegion : undefined" :outline="result.measurement?.annotation?.protocol === 'skin-seg-v2' ? assess.outlineRegions : undefined" :busy="busy" @confirm="confirmMasks" @cancel="editing = false" />
          <AssessmentObservationResult v-else :result="result" :skin-layer="assess.aiSkinLayerUrl.value" :lesion-layer="assess.aiLesionLayerUrl.value" :visual-features="assess.visualFeatures.value" :saved="assess.autoFinalized.value" :busy="busy" :can-compare="!!context.baseline_id" @save="save" @adjust="editing = true" @compare="compareBaseline" @done="records" @share="share.shareResult" @retake="continueRecord({id:result.id,date:context.capture_date || '',bodySite:result.bodySite,imageUrl:result.imageUrl || undefined,observation:result.observation})" />
        </template>
        <template v-else-if="screen === 'records'">
          <nav aria-label="记录类型" class="inline-flex gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
            <button type="button" class="min-h-[40px] rounded-lg px-4 text-sm" :aria-pressed="recordTab === 'photos'" :class="recordTab === 'photos' ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-200' : 'text-gray-600 dark:text-gray-400'" @click="recordTab = 'photos'">白斑记录</button>
            <button type="button" class="min-h-[40px] rounded-lg px-4 text-sm" :aria-pressed="recordTab === 'reports'" :class="recordTab === 'reports' ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-200' : 'text-gray-600 dark:text-gray-400'" @click="recordTab = 'reports'">白斑对比</button>
          </nav>
          <AssessmentRecords v-if="recordTab === 'photos'" :items="history.recentAssessments.value" :loading="history.loadingHistory.value" :page="history.historyPage.value" :total-pages="history.historyTotalPages.value" @create="back" @continue="continueRecord" @page="history.goToPage" @compare="compare" />
          <ComparisonHistoryPanel v-else class="card overflow-hidden" :items="reports.reports.value" :loading="reports.loading.value" :total="reports.total.value" :page="reports.page.value" :page-size="reports.pageSize.value" :total-pages="reports.totalPages.value" :body-site-filter="null" @view-report="router.push({name:'skin-report-view',params:{id:$event}})" @go-to-page="reports.goToPage" @set-page-size="reports.setPageSize" />
        </template>
        <MedicalDisclaimer v-if="screen !== 'home' && !editing" :class="workScreen ? 'mt-1 shrink-0' : ''" variant="inline" message="照片记录仅供参考，不构成医疗建议" />
      </section>
    </div>
    <BodyPartCamera v-model="homeCamera" :body-part="pendingCapture?.site || upload.selectedBodySite.value" :baseline-url="pendingCapture ? pendingCapture.record.imageUrl || null : baselineUrl" @captured="cameraCaptured" @cancel="cameraCancelled" />
  </div>
</template>

<style scoped>
/* Reserve both navigation bars before distributing space between photo and actions. */
.assessment-work-shell {
  --work-top-padding: 0px;
  display: flex;
  flex: none;
  flex-direction: column;
  height: calc(100svh - 56px - 55px - env(safe-area-inset-bottom, 0px) - var(--work-top-padding));
  overflow: hidden;
}
:global(html[data-ios] .assessment-work-shell) { --work-top-padding: env(safe-area-inset-top, 0px); }
@media (min-width: 768px) {
  .assessment-work-shell { height: calc(100svh - 56px - var(--work-top-padding)); }
}

.assessment-home-shell {
  display: flex;
  flex-direction: column;
  flex: none;
  height: calc(100dvh - 56px);
  overflow: hidden;
}
@media (max-width: 767px) {
  .assessment-home-shell {
    height: calc(100dvh - 56px - 55px - env(safe-area-inset-bottom, 0px));
  }
}
@media (min-width: 768px), (max-height: 600px) {
  .assessment-home-shell { height: auto; min-height: 0; overflow: visible; flex: 1; }
  /* 首页此时随窗口滚动：工具条吸附在全站顶栏（56px）下方 */
  .assessment-home-shell > .assessment-toolbar { top: 56px; }
}
</style>
