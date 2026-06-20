/**
 * useVasiAssess — 评估提交与结果处理
 *
 * 职责：提交评估、AI分析状态、MaskEditor交互、结果管理
 * 拆分自 useVasiAssessment.ts（637行 → 本文件约180行）
 */
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { vasiApi } from '@/api/vasi'
import type { VisualFeatures } from '@/api/vasi'

export { getScoreInterpretation, getStageDescription } from './useVasiAssessment'

export function useVasiAssess() {
  const authStore = useAuthStore()
  const toast = useToast()

  // ── Upload progress ──
  const isUploading = ref(false)
  const uploadStage = ref<'uploading' | 'segmenting' | 'analyzing' | ''>('')

  // ── Assessment result ──
  const assessmentResult = ref<{
    id: number
    imageUrl: string | null
    vasiScore: number
    bodySite: string
    areaPercentage: number
    classification: string
    stage: string
    confidence?: number
    precisionLevel?: string
  } | null>(null)

  const lastAssessment = ref<{
    vasiScore: number
    bodySite: string
    areaPercentage: number
    classification: string
    stage: string
    imageUrl: string | null
    confidence?: number
    id?: number
  } | null>(null)

  // ── Mask editing ──
  const showContourEditor = ref(false)
  const highConfidence = ref(false)
  const isSubmittingContour = ref(false)
  const contourDiffResult = ref<{ match: boolean; avg_point_distance?: number; modified: boolean } | null>(null)
  const aiSkinLayerUrl = ref<string | null>(null)
  const aiLesionLayerUrl = ref<string | null>(null)

  // ── AI detection metadata ──
  const assessmentSource = ref<string | null>(null)
  const suspectedLesions = ref<any[] | null>(null)
  const visualFeatures = ref<VisualFeatures | null>(null)

  // ── Annotated composite image (original + skin/lesion layers) for sharing ──
  const annotatedImage = ref<string | null>(null)

  async function submitAssessment(
    image: File,
    bodySite: string,
    precision: string = 'quick',
    hasReferenceCard: boolean = false,
  ) {
    if (!authStore.isLoggedIn) { authStore.showLoginModal = true; return }
    isUploading.value = true
    uploadStage.value = 'uploading'
    try {
      uploadStage.value = 'segmenting'
      const data = await vasiApi.assess(image, bodySite, precision, { hasReferenceCard })
      uploadStage.value = 'analyzing'

      assessmentResult.value = {
        id: data.id,
        imageUrl: data.image_url || null,
        vasiScore: data.vasi_score,
        bodySite: data.body_site,
        areaPercentage: data.area_percentage,
        classification: data.classification,
        stage: data.stage,
        confidence: (data as any).confidence,
        precisionLevel: data.precision_level,
      }

      aiSkinLayerUrl.value = data.skin_layer_data_url ?? null
      aiLesionLayerUrl.value = data.lesion_layer_data_url ?? null
      assessmentSource.value = data.assessment_source ?? null
      suspectedLesions.value = data.suspected_lesions ?? null
      visualFeatures.value = data.visual_features ?? null
      highConfidence.value = ((data as any).confidence ?? 0) >= 0.8
      showContourEditor.value = true
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '评估提交失败，请稍后重试'
      toast.error(msg)
      throw e
    } finally {
      isUploading.value = false
      uploadStage.value = ''
    }
  }

  async function handleTwoLayerConfirm(skinMaskDataUrl: string, lesionMaskDataUrl: string) {
    if (!assessmentResult.value) return
    isSubmittingContour.value = true
    try {
      const result = await vasiApi.submitTwoLayerMask(
        assessmentResult.value.id, skinMaskDataUrl, lesionMaskDataUrl,
      )
      contourDiffResult.value = result.diff_summary
      if (result.diff_summary.modified) {
        toast.show(
          `已记录。AI与手动标注差异将用于提升模型准确率`,
          'info', 4000,
        )
      } else {
        toast.success('标注确认完成！')
      }
      if (result.final_vasi_score != null) {
        lastAssessment.value = {
          ...assessmentResult.value,
          vasiScore: result.final_vasi_score,
          areaPercentage: result.final_area_percentage ?? assessmentResult.value.areaPercentage,
        }
      } else {
        lastAssessment.value = assessmentResult.value
      }
      // Finalize
      const aid = assessmentResult.value.id
      cleanupState()
      if (aid) { try { await vasiApi.finalizeAssessment(aid) } catch {} }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '提交失败')
    } finally {
      isSubmittingContour.value = false
    }
  }

  async function skipContourEdit() {
    if (!assessmentResult.value) return
    lastAssessment.value = assessmentResult.value
    const aid = lastAssessment.value.id
    cleanupState()
    if (aid) { try { await vasiApi.finalizeAssessment(aid) } catch {} }
    toast.success(`评估成功！VASI评分: ${lastAssessment.value.vasiScore}`)
  }

  async function cancelAssessment() {
    if (!assessmentResult.value) return
    const aid = assessmentResult.value.id
    lastAssessment.value = null
    cleanupState()
    if (aid) { try { await vasiApi.abandonAssessment(aid) } catch {} }
    toast.show('已取消本次测评', 'info', 2000)
  }

  function cleanupState() {
    showContourEditor.value = false
    assessmentResult.value = null
    aiSkinLayerUrl.value = null
    aiLesionLayerUrl.value = null
    assessmentSource.value = null
    suspectedLesions.value = null
    visualFeatures.value = null
    contourDiffResult.value = null
  }

  return {
    // State
    isUploading, uploadStage,
    assessmentResult, lastAssessment,
    showContourEditor, highConfidence,
    isSubmittingContour, contourDiffResult,
    aiSkinLayerUrl, aiLesionLayerUrl,
    assessmentSource, suspectedLesions, visualFeatures,
    annotatedImage,
    // Methods
    submitAssessment, handleTwoLayerConfirm,
    skipContourEdit, cancelAssessment,
    cleanupState,
  }
}
