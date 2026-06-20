/**
 * useVasiUpload — 测评上传逻辑
 *
 * 职责：照片上传、相机捕获、照片质量检查、照片预览管理
 * 拆分自 useVasiAssessment.ts（637行 → 本文件约150行）
 */
import { ref } from 'vue'
import { useToast } from '@/composables/useToast'
import { vasiApi } from '@/api/vasi'
import type { QualityCheckResult } from '@/api/vasi'

export function useVasiUpload() {
  const toast = useToast()

  // ── State ──
  const selectedBodySite = ref('')
  const uploadedImage = ref<File | null>(null)
  const imagePreview = ref<string | null>(null)
  const qualityResult = ref<QualityCheckResult | null>(null)
  const qualityChecking = ref(false)
  const hasReferenceCard = ref(false)

  // ── Helpers ──
  function loadImagePreview(file: File) {
    const reader = new FileReader()
    reader.onload = () => { imagePreview.value = reader.result as string }
    reader.onerror = () => { imagePreview.value = null }
    reader.readAsDataURL(file)
  }

  function ensureBodySiteSelected(): boolean {
    if (!selectedBodySite.value) {
      toast.show('请先选择评估部位（在数字人上点击对应部位），再上传照片', 'warning', 4000)
      return false
    }
    return true
  }

  // ── Public API ──
  function setBodySite(site: string) {
    selectedBodySite.value = site
  }

  function setHasReferenceCard(value: boolean) {
    hasReferenceCard.value = value
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
  }

  async function checkQuality(file: File) {
    qualityResult.value = null
    qualityChecking.value = true
    try {
      qualityResult.value = await vasiApi.checkPhotoQuality(file)
    } catch {
      qualityResult.value = null
    } finally {
      qualityChecking.value = false
    }
  }

  function removeImage() {
    uploadedImage.value = null
    imagePreview.value = null
    qualityResult.value = null
    qualityChecking.value = false
    hasReferenceCard.value = false
  }

  function resetAll() {
    removeImage()
    selectedBodySite.value = ''
  }

  return {
    // State
    selectedBodySite, uploadedImage, imagePreview,
    qualityResult, qualityChecking, hasReferenceCard,
    // Methods
    setBodySite, setHasReferenceCard,
    handleFileSelect, handleDrop, checkQuality,
    removeImage, resetAll,
    loadImagePreview,
  }
}
