/**
 * useVasiUpload — 测评上传逻辑
 *
 * 职责：照片上传、相机捕获、照片质量检查、照片预览管理
 * 拆分自 useVasiAssessment.ts（637行 → 本文件约150行）
 */
import { ref } from 'vue'
import { isAxiosError } from 'axios'
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
  const qualityError = ref('')
  const qualityNeedsLogin = ref(false)
  const hasReferenceCard = ref(false)

  let qualityGeneration = 0

  // ── Helpers ──
  function loadImagePreview(file: File) {
    const reader = new FileReader()
    reader.onload = () => { if (uploadedImage.value === file) imagePreview.value = reader.result as string }
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
    selectFile(file)
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    const file = event.dataTransfer?.files[0]
    if (!file) return
    if (!ensureBodySiteSelected()) return
    if (!file.type.startsWith('image/')) { toast.error('请上传图片文件'); return }
    if (file.size > 10 * 1024 * 1024) { toast.error('图片大小不能超过10MB'); return }
    selectFile(file)
  }

  function selectFile(file: File): boolean {
    if (!ensureBodySiteSelected()) return false
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { toast.error('请选择 JPG、PNG 或 WebP 照片'); return false }
    if (file.size > 10 * 1024 * 1024) { toast.error('图片大小不能超过10MB'); return false }
    uploadedImage.value = file
    loadImagePreview(file)
    void checkQuality(file)
    return true
  }

  async function checkQuality(file: File) {
    const generation = ++qualityGeneration
    qualityResult.value = null
    qualityError.value = ''
    qualityNeedsLogin.value = false
    qualityChecking.value = true
    try {
      const result = await vasiApi.checkPhotoQuality(file)
      if (generation === qualityGeneration) qualityResult.value = result
    } catch (error) {
      if (generation !== qualityGeneration) return
      qualityResult.value = null
      const status = isAxiosError(error) ? error.response?.status : undefined
      qualityNeedsLogin.value = status === 401
      qualityError.value = status === 401 ? '登录已失效，请登录后重新检查照片'
        : status === 413 ? '照片过大，请选择10MB以内的图片'
        : status === 400 || status === 422 ? '照片无法读取，请换一张 JPG、PNG 或 WebP 图片'
        : status === 403 ? '暂时无法访问质检服务，请重新登录后重试'
        : isAxiosError(error) && error.code === 'ECONNABORTED' ? '照片检查超时，请重新检查'
        : '照片检查暂时失败，请检查网络后重试，无需重新选图'
    } finally {
      if (generation === qualityGeneration) qualityChecking.value = false
    }
  }

  function removeImage() {
    qualityGeneration++
    uploadedImage.value = null
    imagePreview.value = null
    qualityResult.value = null
    qualityChecking.value = false
    qualityError.value = ''
    qualityNeedsLogin.value = false
    hasReferenceCard.value = false
  }

  function resetAll() {
    removeImage()
    selectedBodySite.value = ''
  }

  return {
    // State
    selectedBodySite, uploadedImage, imagePreview,
    qualityResult, qualityChecking, qualityError, qualityNeedsLogin, hasReferenceCard,
    // Methods
    setBodySite, setHasReferenceCard,
    handleFileSelect, handleDrop, selectFile, checkQuality,
    removeImage, resetAll,
    loadImagePreview,
  }
}
