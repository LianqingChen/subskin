import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePrivacyStore } from '@/stores/privacy'
import { useToast } from '@/composables/useToast'
import { vasiApi } from '@/api/vasi'
import type { VasiHistoryItem, ContourRegion, QualityCheckResult, VisualFeatures } from '@/api/vasi'
import { PART_LABELS } from '@/constants/bodySites'
import { useDrafts } from '@/composables/useDrafts'

export { PART_LABELS }

export function getScoreInterpretation(score: number): { level: string; color: string; description: string } {
  if (score < 10) {
    return {
      level: '轻度',
      color: 'text-green-600 dark:text-green-400',
      description: '白斑面积较小，色素脱失程度较轻。此时是治疗的黄金时期，建议尽早咨询皮肤科医生，制定个性化治疗方案。保持良好心态，避免精神压力。',
    }
  } else if (score < 25) {
    return {
      level: '中度',
      color: 'text-amber-600 dark:text-amber-400',
      description: '白斑面积和脱失程度中等。建议定期随访，配合医生进行系统性治疗。注意防晒，避免皮肤外伤。保持规律作息和均衡饮食有助于病情控制。',
    }
  } else if (score < 50) {
    return {
      level: '中重度',
      color: 'text-orange-600 dark:text-orange-400',
      description: '白斑面积较大，可能处于进展期。建议积极就医，考虑联合治疗方案（如光疗+药物）。密切监测病情变化，记录白斑发展情况。心理支持同样重要。',
    }
  }
  return {
    level: '重度',
    color: 'text-red-600 dark:text-red-400',
    description: '白斑面积广泛，需要积极综合治疗。建议在专业医生指导下制定系统治疗方案。注意心理健康，寻求家人和朋友的支持。坚持治疗，很多白友仍可获得改善。',
  }
}

export function getStageDescription(stage: string): string {
  const descriptions: Record<string, string> = {
    好转: '白斑面积在缩小或出现色素恢复，治疗正在发挥作用。继续保持当前治疗方案。',
    稳定: '白斑面积近期无明显变化，病情处于稳定期。这是进行干预治疗的好时机。',
    扩散: '白斑面积在扩大或出现新白斑，病情处于进展期。建议尽快就医，调整治疗方案。',
    稳定期: '白斑面积近期无明显变化，病情处于稳定期。这是进行干预治疗的好时机。',
    进展期: '白斑面积在扩大或出现新白斑，病情处于进展期。建议尽快就医，调整治疗方案。',
  }
  return descriptions[stage] || '请咨询专业医生了解病情阶段和治疗方案。'
}

export function useVasiAssessment() {
  const router = useRouter()
  const authStore = useAuthStore()
  const privacyStore = usePrivacyStore()
const toast = useToast()

  // ── Upload state ──
  const selectedBodySite = ref('')
  const uploadedImage = ref<File | null>(null)
  const imagePreview = ref<string | null>(null)
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

  const aiContours = ref<ContourRegion[]>([])
  const editedContours = ref<ContourRegion[]>([])
  const showContourEditor = ref(false)
  const isSubmittingContour = ref(false)
  const contourDiffResult = ref<{ match: boolean; avg_point_distance?: number; modified: boolean } | null>(null)
  const aiSkinLayerUrl = ref<string | null>(null)
  const aiLesionLayerUrl = ref<string | null>(null)

  // ── Phase A — VLM detection info ──
  const assessmentSource = ref<string | null>(null)    // e.g. "sam-vlm-guided", "sam-only-auto", "mock"
  const suspectedLesions = ref<any[] | null>(null)      // VLM-detected lesions with confidence
  const visualFeatures = ref<VisualFeatures | null>(null) // 6-dimension visual feature analysis
  const skinRegionRatio = ref<number | null>(null)      // skin area / image area %

  // ── Precise assessment ──
  const preciseAvailable = ref(true)
  const isPreciseAssessing = ref(false)
  const preciseAssessmentDone = ref(false)

  // ── Quality check ──
  const qualityResult = ref<QualityCheckResult | null>(null)
  const qualityChecking = ref(false)
  const qualityIgnored = ref(false)
  const hasReferenceCard = ref(false)

  function setHasReferenceCard(value: boolean) {
    hasReferenceCard.value = value
  }

  // ── Step guidance ──
  const currentStep = ref(1)

  // ── History ──
  const recentAssessments = ref<Array<{
    id: number
    date: string
    bodySite: string
    vasiScore: number
    areaPercentage: number
    stage: string
    classification?: string
  }>>([])
  const loadingHistory = ref(false)
  const historyOffset = ref(0)
  const historyHasMore = ref(false)
  const selectMode = ref(false)
  const selectedIds = ref<Set<number>>(new Set())
  const swipedId = ref<number | null>(null)
  const deletingIds = ref<Set<number>>(new Set())
  const touchStartX = ref(0)
  const loadingMore = ref(false)
  const currentBodySiteFilter = ref<string | null>(null)

  // ── Upload + Assessment ──
  function loadImagePreview(file: File) {
    const url = URL.createObjectURL(file)
    imagePreview.value = url
  }

  function ensureBodySiteSelected(): boolean {
    if (!selectedBodySite.value) {
      toast.show('请先选择评估部位（在数字人上点击对应部位），再上传照片', 'warning', 4000)
      return false
    }
    return true
  }

  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement
    const file = target.files?.[0]
    if (!file) return
    if (!ensureBodySiteSelected()) {
      if (target) target.value = ''
      return
    }
    if (!file.type.startsWith('image/')) { toast.error('请上传图片文件'); return }
    if (file.size > 10 * 1024 * 1024) { toast.error('图片大小不能超过10MB'); return }
    uploadedImage.value = file
    loadImagePreview(file)
    checkQuality(file)
    currentStep.value = 2
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    const file = event.dataTransfer?.files[0]
    if (!file) return
    if (!ensureBodySiteSelected()) return
    if (!file.type.startsWith('image/')) { toast.error('请上传图片文件'); return }
    if (file.size > 10 * 1024 * 1024) { toast.error('图片大小不能超过10MB'); return }
    uploadedImage.value = file
    loadImagePreview(file)
    checkQuality(file)
    currentStep.value = 2
  }

  async function checkQuality(file: File) {
    qualityResult.value = null
    qualityIgnored.value = false
    qualityChecking.value = true
    try {
      qualityResult.value = await vasiApi.checkPhotoQuality(file)
    } catch {
      qualityResult.value = null
    } finally {
      qualityChecking.value = false
    }
  }

  function setBodySite(site: string) {
    selectedBodySite.value = site
    currentStep.value = 1
  }

  async function submitAssessment() {
    if (!authStore.isLoggedIn) { authStore.showLoginModal = true; return }
    if (!uploadedImage.value) { toast.warning('请先上传白斑照片'); return }
    if (!selectedBodySite.value) { toast.warning('请选择评估部位'); return }
    isUploading.value = true
    uploadStage.value = 'uploading'
    preciseAssessmentDone.value = false
    preciseAvailable.value = true
    try {
      uploadStage.value = 'segmenting'
      const data = await vasiApi.assess(uploadedImage.value, selectedBodySite.value, 'quick', {
        hasReferenceCard: hasReferenceCard.value,
      })
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
      preciseAvailable.value = data.precise_available !== false
      currentStep.value = 3

      aiContours.value = data.contours || []
      editedContours.value = (data.contours || []).map(c => ({ ...c, polygon: c.polygon.map(p => [...p] as [number, number]) }))
      aiSkinLayerUrl.value = data.skin_layer_data_url ?? null
      aiLesionLayerUrl.value = data.lesion_layer_data_url ?? null
      assessmentSource.value = data.assessment_source ?? null
      suspectedLesions.value = data.suspected_lesions ?? null
      skinRegionRatio.value = data.skin_region_ratio ?? null
      visualFeatures.value = data.visual_features ?? null
      showContourEditor.value = true
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '评估提交失败，请稍后重试'
      toast.error(msg)
    } finally {
      isUploading.value = false
      uploadStage.value = ''
    }
  }

  async function removeImage() {
    uploadedImage.value = null
    imagePreview.value = null
    qualityResult.value = null
    qualityChecking.value = false
    qualityIgnored.value = false
    hasReferenceCard.value = false
    preciseAssessmentDone.value = false
    assessmentSource.value = null
    suspectedLesions.value = null
    skinRegionRatio.value = null
    currentStep.value = selectedBodySite.value ? 1 : 1
  // Phase 1: Abandon draft assessment if one exists
  if (assessmentResult.value?.id) {
    try { await vasiApi.abandonAssessment(assessmentResult.value.id) } catch {}
    assessmentResult.value = null
  }
  }

  // ── Precise assessment ──
  async function startPreciseAssessment() {
    if (!uploadedImage.value || !selectedBodySite.value) return
    isPreciseAssessing.value = true
    try {
      const data = await vasiApi.assess(uploadedImage.value, selectedBodySite.value, 'precise', {
        hasReferenceCard: hasReferenceCard.value,
      })
      assessmentResult.value = {
        id: data.id, imageUrl: data.image_url || null, vasiScore: data.vasi_score, bodySite: data.body_site,
        areaPercentage: data.area_percentage, classification: data.classification,
        stage: data.stage, confidence: (data as any).confidence, precisionLevel: data.precision_level,
      }
      if (data.contours && data.contours.length > 0) {
        aiContours.value = data.contours
        editedContours.value = data.contours.map(c => ({ ...c, polygon: c.polygon.map(p => [...p] as [number, number]) }))
      }
      preciseAssessmentDone.value = true
      toast.success('精确分析完成！轮廓已更新')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '精确分析失败，请稍后重试')
    } finally {
      isPreciseAssessing.value = false
    }
  }

  async function handleTwoLayerConfirm(skinMaskDataUrl: string, lesionMaskDataUrl: string) {
    if (!assessmentResult.value) return
    isSubmittingContour.value = true
    try {
      const result = await vasiApi.submitTwoLayerMask(assessmentResult.value.id, skinMaskDataUrl, lesionMaskDataUrl)
      contourDiffResult.value = result.diff_summary
      if (result.diff_summary.modified) {
        toast.show(`图层已记录。AI与手动标注差异距离: ${(result.diff_summary.avg_point_distance ?? 0).toFixed(3)}，将用于提升模型准确率`, 'info', 5000)
      } else {
        toast.success('图层确认完成，AI识别结果与您的标注一致！')
      }
      if (result.final_vasi_score != null) lastAssessment.value = { ...assessmentResult.value, vasiScore: result.final_vasi_score, areaPercentage: result.final_area_percentage ?? assessmentResult.value.areaPercentage }
      else lastAssessment.value = assessmentResult.value
      const aid = assessmentResult.value.id
      showContourEditor.value = false
      uploadedImage.value = null; imagePreview.value = null; selectedBodySite.value = ''
      assessmentResult.value = null; aiContours.value = []; editedContours.value = []
      aiSkinLayerUrl.value = null; aiLesionLayerUrl.value = null
      assessmentSource.value = null; suspectedLesions.value = null; skinRegionRatio.value = null
      preciseAssessmentDone.value = false; currentStep.value = 1
      if (aid) { try { await vasiApi.finalizeAssessment(aid) } catch {} }
      await loadAssessmentHistory()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '图层提交失败')
    } finally {
      isSubmittingContour.value = false
    }
  }

  async function handleContourConfirm(contours: ContourRegion[], maskDataUrl?: string | null) {
    if (!assessmentResult.value) return
    isSubmittingContour.value = true
    try {
      const result = await vasiApi.submitContour(assessmentResult.value.id, contours, maskDataUrl ?? null)
      contourDiffResult.value = result.diff_summary
      if (result.diff_summary.modified) {
        toast.show(`轮廓已记录。AI与手动标注差异距离: ${(result.diff_summary.avg_point_distance ?? 0).toFixed(3)}，将用于提升模型准确率`, 'info', 5000)
      } else {
        toast.success('轮廓确认完成，AI识别结果与您的标注一致！')
      }
      lastAssessment.value = assessmentResult.value
      const aid = assessmentResult.value.id
      showContourEditor.value = false
      uploadedImage.value = null; imagePreview.value = null; selectedBodySite.value = ''
      assessmentResult.value = null; aiContours.value = []; editedContours.value = []
      assessmentSource.value = null; suspectedLesions.value = null; skinRegionRatio.value = null
      preciseAssessmentDone.value = false; currentStep.value = 1
      if (aid) { try { await vasiApi.finalizeAssessment(aid) } catch {} }
      await loadAssessmentHistory()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '轮廓提交失败')
    } finally {
      isSubmittingContour.value = false
    }
  }

  function handleContourUpdate(contours: ContourRegion[]) {
    editedContours.value = contours
  }

  async function skipContourEdit() {
    if (!assessmentResult.value) return
    lastAssessment.value = assessmentResult.value
    // Finalize the draft assessment
    const aid = lastAssessment.value.id
    showContourEditor.value = false
    uploadedImage.value = null; imagePreview.value = null; selectedBodySite.value = ''
    assessmentResult.value = null; aiContours.value = []; editedContours.value = []
    aiSkinLayerUrl.value = null; aiLesionLayerUrl.value = null
    assessmentSource.value = null; suspectedLesions.value = null; skinRegionRatio.value = null
    preciseAssessmentDone.value = false; currentStep.value = 1
    if (aid) { try { await vasiApi.finalizeAssessment(aid) } catch {} }
    loadAssessmentHistory()
    toast.success(`评估成功！VASI评分: ${lastAssessment.value.vasiScore}`)
  }

  // ── History ──
  async function loadAssessmentHistory(reset = true, bodySite?: string) {
    if (!authStore.isLoggedIn) return
    if (reset) {
      loadingHistory.value = true
      historyOffset.value = 0
      currentBodySiteFilter.value = bodySite ?? null
    } else {
      loadingMore.value = true
    }
    try {
      const res = await vasiApi.getHistory(20, reset ? 0 : historyOffset.value, currentBodySiteFilter.value || undefined)
      const items = res.items.map((item: VasiHistoryItem) => ({
        id: item.id,
        date: item.assessment_date.split('T')[0],
        bodySite: item.body_site,
        vasiScore: item.final_vasi_score ?? item.vasi_score,
        areaPercentage: item.final_area_percentage ?? item.area_percentage,
        stage: item.stage,
        classification: item.classification,
      }))
      if (reset) {
        recentAssessments.value = items
      } else {
        recentAssessments.value.push(...items)
      }
      historyHasMore.value = items.length === 20
      historyOffset.value = recentAssessments.value.length
      selectMode.value = false
      selectedIds.value.clear()
    } catch (err) {
      console.error('Failed to load VASI history:', err)
    } finally {
      loadingHistory.value = false
      loadingMore.value = false
    }
  }

  async function loadMoreHistory() {
    if (loadingMore.value || !historyHasMore.value) return
    await loadAssessmentHistory(false)
  }

  function toggleSelectMode() {
    selectMode.value = !selectMode.value
    if (!selectMode.value) selectedIds.value.clear()
  }

  function toggleSelect(id: number) {
    if (selectedIds.value.has(id)) selectedIds.value.delete(id)
    else selectedIds.value.add(id)
  }

  function isSwiped(id: number) { return swipedId.value === id }

  function onTouchStart(e: TouchEvent) {
    if (selectMode.value) return
    touchStartX.value = e.touches[0].clientX
  }

  function onTouchEnd(e: TouchEvent, id: number) {
    if (selectMode.value) return
    const deltaX = e.changedTouches[0].clientX - touchStartX.value
    if (deltaX < -50) swipedId.value = id
    else if (deltaX > 30) swipedId.value = null
  }

  async function deleteSingle(id: number) {
    if (deletingIds.value.has(id)) return
    deletingIds.value.add(id)
    try {
      await vasiApi.deleteAssessment(id)
      recentAssessments.value = recentAssessments.value.filter(r => r.id !== id)
      swipedId.value = null
      toast.success('已删除')
    } catch {
      toast.error('删除失败')
    } finally {
      deletingIds.value.delete(id)
    }
  }

  async function deleteSelected() {
    if (selectedIds.value.size === 0) return
    deletingIds.value = new Set(selectedIds.value)
    try {
      await vasiApi.deleteAssessmentsBatch([...selectedIds.value])
      recentAssessments.value = recentAssessments.value.filter(r => !selectedIds.value.has(r.id))
      toast.success(`已删除 ${selectedIds.value.size} 条记录`)
      selectMode.value = false
      selectedIds.value.clear()
    } catch {
      toast.error('批量删除失败')
    } finally {
      deletingIds.value.clear()
    }
  }

  const { saveDraftWithSync } = useDrafts()

  async function createAssessmentDraft(): Promise<string | null> {
    if (!lastAssessment.value) return null
    const a = lastAssessment.value
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

    const images: string[] = a.imageUrl ? [a.imageUrl] : []

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
    await router.push({ path: '/community/new', query: { type: 'image', draftKey } })
    return draftKey
  }

  function writeDiaryFromAssessment() {
    if (!lastAssessment.value) return
    const a = lastAssessment.value
    const today = new Date().toISOString().split('T')[0]
    router.push({
      name: 'community-new',
      query: {
        mode: 'diary',
        prefill_title: `${today} 病情日记`,
        prefill_content:
          `<p>今天做了VASI评估：</p>` +
          `<ul>` +
          `<li>评估部位：${a.bodySite}</li>` +
          `<li>VASI评分：${a.vasiScore}</li>` +
          `<li>白斑占该部位皮肤：${a.areaPercentage}%</li>` +
          `<li>病情阶段：${a.stage}</li>` +
          `<li>分型：${a.classification || '未分型'}</li>` +
          `</ul>` +
          `<p></p><p>今日感受：</p>`,
      },
    })
  }

  // ── Privacy helper ──
  function privacyMask(value: number | string, suffix = ''): string {
    if (privacyStore.privacyMode) return String(value) + suffix
    return '****'
  }

  return {
    // State
    selectedBodySite, uploadedImage, imagePreview, isUploading, uploadStage,
    assessmentResult, lastAssessment, aiContours, editedContours, showContourEditor,
    isSubmittingContour, contourDiffResult, preciseAvailable, isPreciseAssessing,
    preciseAssessmentDone, qualityResult, qualityChecking, qualityIgnored,
    aiSkinLayerUrl, aiLesionLayerUrl,
    assessmentSource, suspectedLesions, skinRegionRatio, visualFeatures,
    recentAssessments, loadingHistory, loadingMore, historyHasMore,
    selectMode, selectedIds, swipedId, deletingIds, currentStep,
    hasReferenceCard,
    // Methods
    setBodySite, setHasReferenceCard,
    handleFileSelect, handleDrop, checkQuality, submitAssessment,
    removeImage, startPreciseAssessment, handleTwoLayerConfirm, handleContourConfirm, handleContourUpdate,
    skipContourEdit, loadAssessmentHistory, loadMoreHistory,
    toggleSelectMode, toggleSelect, isSwiped, onTouchStart, onTouchEnd,
    deleteSingle, deleteSelected, writeDiaryFromAssessment, createAssessmentDraft,
    privacyMask,
  }
}
