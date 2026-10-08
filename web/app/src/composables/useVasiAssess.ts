import { ref, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { vasiApi } from '@/api/vasi'
import { rgbApi, RGBTaskError, type RGBSelection } from '@/api/rgb-segmentation'
import type { VasiAssessmentResponse, SuspectedLesion, VisualFeatures } from '@/api/vasi'
import type { AssessmentResult, ObservationContext } from '@/types/assessment'
import { useToast } from '@/composables/useToast'
import { assessmentError } from '@/utils/assessment-errors'

export { getScoreInterpretation, getStageDescription } from './useVasiAssessment'

export function useVasiAssess() {
  const toast = useToast()
  const auth = useAuthStore()
  const isUploading = ref(false)
  const uploadStage = ref('')
  const assessmentResult = ref<AssessmentResult | null>(null)
  const lastAssessment = ref<AssessmentResult | null>(null)
  const showContourEditor = ref(false)
  const highConfidence = ref(false)
  const isSubmittingContour = ref(false)
  const aiSkinLayerUrl = ref<string | null>(null)
  const aiLesionLayerUrl = ref<string | null>(null)
  const assessmentSource = ref<string | null>(null)
  const suspectedLesions = ref<SuspectedLesion[] | null>(null)
  const visualFeatures = ref<VisualFeatures | null>(null)
  const autoFinalized = ref(false)
  const patientModelVersion = ref<string | null>(null)
  const annotatedImage = ref<string | null>(null)
  const contourDiffResult = ref<{ modified?: boolean } | null>(null)
  let generation = 0
  let taskController: AbortController | null = null

  function mapResult(data: VasiAssessmentResponse): AssessmentResult {
    return { id: data.id, imageUrl: data.image_url, vasiScore: data.final_vasi_score ?? data.vasi_score,
      bodySite: data.body_site, areaPercentage: data.final_area_percentage ?? data.area_percentage,
      classification: data.classification, stage: data.stage, confidence: data.confidence,
      measurement: data.measurement, observation: data.observation }
  }
  async function loadAssessment(id: number) {
    const current = ++generation
    const owner = auth.user?.id
    const data = await vasiApi.getAssessment(id)
    if (current !== generation || !auth.isLoggedIn || auth.user?.id !== owner) return
    assessmentResult.value = mapResult(data)
    lastAssessment.value = assessmentResult.value
    aiSkinLayerUrl.value = data.skin_layer_data_url ?? null
    aiLesionLayerUrl.value = data.lesion_layer_data_url ?? null
    visualFeatures.value = data.visual_features ?? null
    autoFinalized.value = data.record_status ? data.record_status === 'active' : data.measurement?.annotation?.review_state !== 'pending'
  }
  async function submitAssessment(image: File, bodySite: string, _precision = 'quick', _hasReferenceCard = false, observation?: ObservationContext) {
    const current = ++generation
    const owner = auth.user?.id
    isUploading.value = true
    uploadStage.value = 'analyzing'
    lastAssessment.value = null
    assessmentResult.value = null
    try {
      taskController?.abort()
      taskController = new AbortController()
      const job = await rgbApi.assess(image, bodySite, observation, taskController.signal, stage => { if (current === generation) uploadStage.value = stage })
      if (current !== generation) { void rgbApi.cancel(job.jobId).catch(() => undefined); return }
      const data = await vasiApi.getAssessment(job.assessmentId)
      if (current !== generation || auth.user?.id !== owner || !auth.isLoggedIn) return
      if (data.assessment_source === 'quality-reject') throw new Error('quality-reject')
      assessmentResult.value = mapResult(data)
      aiSkinLayerUrl.value = data.skin_layer_data_url ?? null
      aiLesionLayerUrl.value = data.lesion_layer_data_url ?? null
      assessmentSource.value = data.assessment_source ?? null
      suspectedLesions.value = data.suspected_lesions ?? null
      visualFeatures.value = data.visual_features ?? null
      autoFinalized.value = !!data.auto_finalized
      patientModelVersion.value = data.patient_model_version ?? null
      highConfidence.value = data.measurement?.status === 'measured'
      showContourEditor.value = false
      // Automatic and manual paths share the same current-result snapshot.
      lastAssessment.value = assessmentResult.value
    } catch (error) {
      if (current !== generation) return
      toast.error(error instanceof RGBTaskError ? error.message : assessmentError(error, '照片暂不能完成分析，请重拍或稍后重试'))
      throw error
    } finally {
      if (current === generation) { isUploading.value = false; uploadStage.value = '' }
    }
  }
  async function skipContourEdit() {
    if (!assessmentResult.value) return
    isSubmittingContour.value = true
    try {
      await vasiApi.finalizeAssessment(assessmentResult.value.id)
      lastAssessment.value = { ...assessmentResult.value }
      autoFinalized.value = true
      showContourEditor.value = false
      toast.success('记录已保存')
    } catch (error) {
      toast.error(assessmentError(error, '记录尚未保存，请重试'))
      throw error
    } finally { isSubmittingContour.value = false }
  }
  async function handleTwoLayerConfirm(skin: string, lesion: string, uncertaintyReviewed = false) {
    if (!assessmentResult.value) return
    isSubmittingContour.value = true
    try {
      const annotation = assessmentResult.value.measurement?.annotation
      const response = annotation?.protocol === 'skin-seg-v2' && annotation.job_id && annotation.mask_revision
        ? await rgbApi.review(annotation.job_id, annotation.mask_revision, skin, lesion, uncertaintyReviewed)
        : await vasiApi.submitTwoLayerMask(assessmentResult.value.id, skin, lesion, uncertaintyReviewed)
      contourDiffResult.value = response.diff_summary
      assessmentResult.value = { ...assessmentResult.value,
        vasiScore: response.final_vasi_score ?? assessmentResult.value.vasiScore,
        areaPercentage: response.final_area_percentage ?? assessmentResult.value.areaPercentage,
        measurement: response.measurement ?? assessmentResult.value.measurement }
      aiSkinLayerUrl.value = 'skin_layer_data_url' in response && typeof response.skin_layer_data_url === 'string' ? response.skin_layer_data_url : skin
      aiLesionLayerUrl.value = 'lesion_layer_data_url' in response && typeof response.lesion_layer_data_url === 'string' ? response.lesion_layer_data_url : lesion
      visualFeatures.value = null
      lastAssessment.value = assessmentResult.value
      showContourEditor.value = false
      await skipContourEdit()
    } catch (error) {
      toast.error(assessmentError(error, '范围尚未保存，请重试'))
      throw error
    } finally { isSubmittingContour.value = false }
  }
  async function selectRegion(input: RGBSelection): Promise<string> {
    const annotation = assessmentResult.value?.measurement?.annotation
    if (!annotation?.job_id || !annotation.mask_revision) throw new RGBTaskError('REVISION_CONFLICT')
    return rgbApi.select(annotation.job_id, annotation.mask_revision, input)
  }
  async function outlineRegions(signal: AbortSignal): Promise<{ lesion: string; uncertain: string }> {
    const annotation = assessmentResult.value?.measurement?.annotation
    if (!annotation?.job_id || !annotation.mask_revision) throw new RGBTaskError('REVISION_CONFLICT')
    return rgbApi.outline(annotation.job_id, annotation.mask_revision, signal)
  }
  function cleanupState() {
    assessmentResult.value = null
    lastAssessment.value = null
    aiSkinLayerUrl.value = null
    aiLesionLayerUrl.value = null
    showContourEditor.value = false
    visualFeatures.value = null
    autoFinalized.value = false
    annotatedImage.value = null
  }
  async function cancelAssessment() {
    if (assessmentResult.value && !autoFinalized.value) await vasiApi.abandonAssessment(assessmentResult.value.id)
    cleanupState()
  }
  function cancelPending() { taskController?.abort(); taskController = null; generation++; isUploading.value = false; uploadStage.value = ''; cleanupState() }
  onBeforeUnmount(() => cancelPending())
  return { isUploading, uploadStage, assessmentResult, lastAssessment, showContourEditor, highConfidence,
    isSubmittingContour, aiSkinLayerUrl, aiLesionLayerUrl, assessmentSource, suspectedLesions,
    visualFeatures, autoFinalized, patientModelVersion, annotatedImage, contourDiffResult,
    loadAssessment, submitAssessment, selectRegion, outlineRegions, skipContourEdit, handleTwoLayerConfirm, cancelAssessment, cleanupState, cancelPending }
}
