<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePrivacyStore } from '@/stores/privacy'
import { useThemeStore } from '@/stores/theme'
import { useToast } from '@/composables/useToast'
import { vasiApi } from '@/api/vasi'

import VitiligoContour from '@/components/tracker/VitiligoContour.vue'
import BodyPartCamera from '@/components/tracker/BodyPartCamera.vue'
import ReportUploader from '@/components/tracker/ReportUploader.vue'
import DigitalHuman from '@/components/tracker/DigitalHuman.vue'
import BodyPartPanel from '@/components/tracker/BodyPartPanel.vue'
import ChatOverlay from '@/components/chat/ChatOverlay.vue'
import type { VasiHistoryItem, ContourRegion, QualityCheckResult } from '@/api/vasi'

const router = useRouter()
const authStore = useAuthStore()
const privacyStore = usePrivacyStore()
const themeStore = useThemeStore()
const toast = useToast()

// ── View State ──
type ViewType = 'home' | 'assessment' | 'chat' | 'report'
const activeView = ref<ViewType>('home')

const chatContextHint = computed(() => {
  if (!selectedPart.value) return ''
  const label = PART_LABELS[selectedPart.value] || selectedPart.value
  const a = activePartAssessment.value
  if (a) return `你正在查看${label}的情况（VASI ${a.vasiScore}，${a.stage}），有什么想问的吗？`
  return `你正在查看${label}，有什么想问的吗？`
})

const PART_LABELS: Record<string, string> = {
  face: '面部', neck: '颈部', hands: '手部',
  trunk: '躯干', arms: '上肢', legs: '下肢', feet: '足部',
}

// ── Visual Metaphor Transition ──
const metaphorType = ref<'none' | 'body-scan'>('none')
let metaphorTimeout: ReturnType<typeof setTimeout> | null = null

function playMetaphor(type: 'body-scan' | 'bubble-expand' | 'stethoscope-glow', targetView: ViewType) {
  if (type === 'body-scan') {
    // Body scan: show CSS ring overlay then transition
    metaphorType.value = type
    if (metaphorTimeout) clearTimeout(metaphorTimeout)
    metaphorTimeout = setTimeout(() => {
      metaphorType.value = 'none'
      activeView.value = targetView
    }, 600)
  } else {
    // Bubble/stethoscope: 3D object itself flashes (handled by DigitalHuman), just delay the view switch
    if (metaphorTimeout) clearTimeout(metaphorTimeout)
    metaphorTimeout = setTimeout(() => {
      activeView.value = targetView
    }, 500)
  }
}

function goHome() {
  activeView.value = 'home'
}



// ── Digital Human Event Handlers ──
const digitalHumanRef = ref<InstanceType<typeof DigitalHuman> | null>(null)

function onOpenChat() {
  playMetaphor('bubble-expand', 'chat')
}

// ── Tracker State ──
const selectedBodySite = ref('')
const uploadedImage = ref<File | null>(null)
const imagePreview = ref<string | null>(null)
const isUploading = ref(false)
const uploadStage = ref<'uploading' | 'segmenting' | 'analyzing' | ''>('')
const showCamera = ref(false)
const selectedPart = ref<string | null>(null)

// ── Digital Human: latest results (for potential future use) ──
const latestPerPart = ref<Record<string, { vasiScore: number; areaPercentage: number; stage: string; classification?: string }>>({})

const activePartAssessment = computed(() => {
  if (!selectedPart.value) return null
  return latestPerPart.value[selectedPart.value] || null
})

const partHistory = computed(() => {
  if (!selectedPart.value) return []
  return recentAssessments.value.filter(r => r.bodySite === selectedPart.value)
})

const displayHistory = computed(() => {
  if (selectedPart.value) {
    return recentAssessments.value.filter(r => r.bodySite === selectedPart.value)
  }
  return recentAssessments.value
})

const assessmentResult = ref<{
  id: number
  vasiScore: number
  bodySite: string
  areaPercentage: number
  classification: string
  stage: string
  confidence?: number
  precisionLevel?: string
} | null>(null)
const aiContours = ref<ContourRegion[]>([])
const editedContours = ref<ContourRegion[]>([])
const showContourEditor = ref(false)
const isSubmittingContour = ref(false)
const contourDiffResult = ref<{ match: boolean; avg_point_distance?: number; modified: boolean } | null>(null)

const preciseAvailable = ref(true)
const isPreciseAssessing = ref(false)
const preciseAssessmentDone = ref(false)

const qualityResult = ref<QualityCheckResult | null>(null)
const qualityChecking = ref(false)
const qualityIgnored = ref(false)
const showStandaloneChooser = ref(false)


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
const selectMode = ref(false)
const selectedIds = ref<Set<number>>(new Set())
const swipedId = ref<number | null>(null)
const deletingIds = ref<Set<number>>(new Set())
const touchStartX = ref(0)
const lastAssessment = ref<{
  vasiScore: number
  bodySite: string
  areaPercentage: number
  classification: string
  stage: string
  confidence?: number
} | null>(null)

const stats = computed(() => {
  if (recentAssessments.value.length === 0) return null
  const latest = recentAssessments.value[0]
  const improvement = recentAssessments.value.length >= 2
    ? (() => {
        const first = recentAssessments.value[recentAssessments.value.length - 1]
        if (first.vasiScore === 0) return '0.0'
        return ((first.vasiScore - latest.vasiScore) / first.vasiScore * 100).toFixed(1)
      })()
    : '0.0'
  return {
    latestScore: latest.vasiScore,
    improvement: Math.abs(parseFloat(improvement)),
    trend: parseFloat(improvement) > 0 ? '改善中 ↑' : (parseFloat(improvement) < 0 ? '需关注 ↓' : '首次评估'),
    totalAssessments: recentAssessments.value.length,
    sparkline: recentAssessments.value.slice(0, 7).reverse().map(r => r.vasiScore),
  }
})

async function loadAssessmentHistory() {
  if (!authStore.isLoggedIn) return
  loadingHistory.value = true
  try {
    const res = await vasiApi.getHistory(20, 0)
    recentAssessments.value = res.items.map((item: VasiHistoryItem) => ({
      id: item.id,
      date: item.assessment_date.split('T')[0],
      bodySite: item.body_site,
      vasiScore: item.vasi_score,
      areaPercentage: item.area_percentage,
      stage: item.stage,
      classification: item.classification,
    }))
    selectMode.value = false
    selectedIds.value.clear()
  } catch (err) {
    console.error('Failed to load VASI history:', err)
  } finally {
    loadingHistory.value = false
  }
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

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  const red = r / 255
  const green = g / 255
  const blue = b / 255

  const max = Math.max(red, green, blue)
  const min = Math.min(red, green, blue)
  const lightness = (max + min) / 2

  if (max === min) {
    return [0, 0, Math.round(lightness * 100)]
  }

  const delta = max - min
  const saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min)

  let hue = 0
  if (max === red) {
    hue = ((green - blue) / delta + (green < blue ? 6 : 0)) / 6
  } else if (max === green) {
    hue = ((blue - red) / delta + 2) / 6
  } else {
    hue = ((red - green) / delta + 4) / 6
  }

  return [Math.round(hue * 360), Math.round(saturation * 100), Math.round(lightness * 100)]
}

function extractSkinToneFromFile(file: File) {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const img = new Image()
  const url = URL.createObjectURL(file)

  img.onload = () => {
    const maxSize = 100
    const scale = Math.min(maxSize / img.width, maxSize / img.height, 1)
    canvas.width = Math.floor(img.width * scale)
    canvas.height = Math.floor(img.height * scale)

    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
    const pixels = imageData.data

    let hueSum = 0
    let skinPixelCount = 0

    for (let index = 0; index < pixels.length; index += 4) {
      const red = pixels[index]
      const green = pixels[index + 1]
      const blue = pixels[index + 2]

      const [hue, saturation, lightness] = rgbToHsl(red, green, blue)
      const isSkinColor = (
        hue >= 0 && hue <= 50 &&
        saturation >= 15 && saturation <= 80 &&
        lightness >= 20 && lightness <= 80
      )

      if (isSkinColor) {
        hueSum += hue
        skinPixelCount += 1
      }
    }

    URL.revokeObjectURL(url)

    if (skinPixelCount > 10) {
      const averageHue = Math.round(hueSum / skinPixelCount)
      themeStore.setCustomHue(averageHue)
      toast.show('网站主题已复色，祝您早日复色！如需变更，请到个人中心设置', 'success', 5000)
    }
  }

  img.onerror = () => {
    URL.revokeObjectURL(url)
  }

  img.src = url
}

function maybeExtractSkinTone(file: File) {
  if (themeStore.customHue === null) {
    extractSkinToneFromFile(file)
  }
}

function loadImagePreview(file: File) {
  const reader = new FileReader()
  reader.onload = (event) => {
    imagePreview.value = event.target?.result as string
  }
  reader.readAsDataURL(file)
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) { toast.error('请上传图片文件'); return }
  if (file.size > 10 * 1024 * 1024) { toast.error('图片大小不能超过10MB'); return }
  uploadedImage.value = file
  maybeExtractSkinTone(file)
  loadImagePreview(file)
  checkQuality(file)
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  const file = event.dataTransfer?.files[0]
  if (!file) return
  if (!file.type.startsWith('image/')) { toast.error('请上传图片文件'); return }
  if (file.size > 10 * 1024 * 1024) { toast.error('图片大小不能超过10MB'); return }
  uploadedImage.value = file
  maybeExtractSkinTone(file)
  loadImagePreview(file)
  checkQuality(file)
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
    const data = await vasiApi.assess(uploadedImage.value, selectedBodySite.value)

    uploadStage.value = 'analyzing'
    assessmentResult.value = {
      id: data.id,
      vasiScore: data.vasi_score,
      bodySite: data.body_site,
      areaPercentage: data.area_percentage,
      classification: data.classification,
      stage: data.stage,
      confidence: (data as any).confidence,
      precisionLevel: data.precision_level,
    }
    // Update digital human
    latestPerPart.value = {
      ...latestPerPart.value,
      [selectedBodySite.value]: {
        vasiScore: data.vasi_score,
        areaPercentage: data.area_percentage,
        stage: data.stage,
        classification: data.classification,
      },
    }
    preciseAvailable.value = data.precise_available !== false

    if (data.contours && data.contours.length > 0) {
      aiContours.value = data.contours
      editedContours.value = data.contours.map(c => ({ ...c, polygon: c.polygon.map(p => [...p] as [number, number]) }))
      showContourEditor.value = true
    } else {
      aiContours.value = []
      editedContours.value = []
      lastAssessment.value = {
        vasiScore: data.vasi_score,
        bodySite: data.body_site,
        areaPercentage: data.area_percentage,
        classification: data.classification,
        stage: data.stage,
        confidence: (data as any).confidence,
      }
      uploadedImage.value = null
      imagePreview.value = null
      selectedBodySite.value = ''
      await loadAssessmentHistory()
      toast.success(`评估成功！VASI评分: ${data.vasi_score}`)
    }
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '评估提交失败，请稍后重试'
    toast.error(msg)
  } finally {
    isUploading.value = false
    uploadStage.value = ''
  }
}

function removeImage() {
  uploadedImage.value = null
  imagePreview.value = null
  qualityResult.value = null
  qualityChecking.value = false
  qualityIgnored.value = false
  preciseAssessmentDone.value = false
}

function openCamera() {
  if (!selectedPart.value && !selectedBodySite.value) {
    toast.warning('请先在数字人上点击选择评估部位')
    return
  }
  showCamera.value = true
}

function triggerUpload() {
  const input = document.querySelector<HTMLInputElement>('#tracker-file-input')
  input?.click()
}

function handleCameraCapture(file: File) {
  uploadedImage.value = file
  loadImagePreview(file)
  checkQuality(file)
  showCamera.value = false
}

async function startPreciseAssessment() {
  if (!uploadedImage.value || !selectedBodySite.value) return
  isPreciseAssessing.value = true
  try {
    const data = await vasiApi.assess(uploadedImage.value, selectedBodySite.value, 'precise')
    assessmentResult.value = {
      id: data.id,
      vasiScore: data.vasi_score,
      bodySite: data.body_site,
      areaPercentage: data.area_percentage,
      classification: data.classification,
      stage: data.stage,
      confidence: (data as any).confidence,
      precisionLevel: data.precision_level,
    }
    if (data.contours && data.contours.length > 0) {
      aiContours.value = data.contours
      editedContours.value = data.contours.map(c => ({ ...c, polygon: c.polygon.map(p => [...p] as [number, number]) }))
    }
    // Update digital human with precise results
    latestPerPart.value = {
      ...latestPerPart.value,
      [selectedBodySite.value]: {
        vasiScore: data.vasi_score,
        areaPercentage: data.area_percentage,
        stage: data.stage,
        classification: data.classification,
      },
    }
    preciseAssessmentDone.value = true
    toast.success('精确分析完成！轮廓已更新')
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '精确分析失败，请稍后重试'
    toast.error(msg)
  } finally {
    isPreciseAssessing.value = false
  }
}

async function handleContourConfirm(contours: ContourRegion[]) {
  if (!assessmentResult.value) return
  isSubmittingContour.value = true
  try {
    const result = await vasiApi.submitContour(assessmentResult.value.id, contours)
    contourDiffResult.value = result.diff_summary

    if (result.diff_summary.modified) {
      toast.show(`轮廓已记录。AI与手动标注差异距离: ${(result.diff_summary.avg_point_distance ?? 0).toFixed(3)}，将用于提升模型准确率`, 'info', 5000)
    } else {
      toast.success('轮廓确认完成，AI识别结果与您的标注一致！')
    }

    lastAssessment.value = assessmentResult.value
    showContourEditor.value = false
    uploadedImage.value = null
    imagePreview.value = null
    selectedBodySite.value = ''
    assessmentResult.value = null
    aiContours.value = []
    editedContours.value = []
    preciseAssessmentDone.value = false
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

function skipContourEdit() {
  if (!assessmentResult.value) return
  lastAssessment.value = assessmentResult.value
  showContourEditor.value = false
  uploadedImage.value = null
  imagePreview.value = null
  selectedBodySite.value = ''
  assessmentResult.value = null
  aiContours.value = []
  editedContours.value = []
  preciseAssessmentDone.value = false
  loadAssessmentHistory()
  toast.success(`评估成功！VASI评分: ${lastAssessment.value.vasiScore}`)
}

function getScoreInterpretation(score: number): { level: string; color: string; description: string } {
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

function getStageDescription(stage: string): string {
  const descriptions: Record<string, string> = {
    好转: '白斑面积在缩小或出现色素恢复，治疗正在发挥作用。继续保持当前治疗方案。',
    稳定: '白斑面积近期无明显变化，病情处于稳定期。这是进行干预治疗的好时机。',
    扩散: '白斑面积在扩大或出现新白斑，病情处于进展期。建议尽快就医，调整治疗方案。',
    稳定期: '白斑面积近期无明显变化，病情处于稳定期。这是进行干预治疗的好时机。',
    进展期: '白斑面积在扩大或出现新白斑，病情处于进展期。建议尽快就医，调整治疗方案。',
  }
  return descriptions[stage] || '请咨询专业医生了解病情阶段和治疗方案。'
}

function writeDiaryFromAssessment() {
  if (!lastAssessment.value) return

  const assessment = lastAssessment.value
  const today = new Date().toISOString().split('T')[0]

  router.push({
    name: 'community-new',
    query: {
      mode: 'diary',
      prefill_title: `${today} 病情日记`,
      prefill_content:
        `<p>今天做了VASI评估：</p>` +
        `<ul>` +
        `<li>评估部位：${assessment.bodySite}</li>` +
        `<li>VASI评分：${assessment.vasiScore}</li>` +
        `<li>白斑面积：${assessment.areaPercentage}%</li>` +
        `<li>病情阶段：${assessment.stage}</li>` +
        `<li>分型：${assessment.classification}型</li>` +
        `</ul>` +
        `<p></p><p>今日感受：</p>`,
    },
  })
}

onMounted(async () => {
  await loadAssessmentHistory()
})

onUnmounted(() => {
  if (metaphorTimeout) clearTimeout(metaphorTimeout)
})
</script>

<template>
  <!-- ━━━ HOME VIEW: 3D Human Hub ━━━ -->
  <div v-if="activeView === 'home'" class="flex flex-col items-center px-4 pt-2 pb-6 min-h-[80vh]">
    <p class="text-sm text-gray-500  mb-3">点击部位评估 · 点击气泡问AI · 点击听诊器解读体检</p>

    <!-- 3D Digital Human (full width, tall) -->
    <div class="w-full max-w-lg h-[65vh] min-h-[400px] rounded-2xl overflow-hidden relative" data-swipe-ignore @touchstart.stop @touchmove.stop @touchend.stop>
      <DigitalHuman
        ref="digitalHumanRef"
        @open-chat="onOpenChat"
      />

      <!-- Visual metaphor overlay (body-scan only) -->
      <Transition name="metaphor-fade">
        <div v-if="metaphorType === 'body-scan'" class="absolute inset-0 z-30 flex items-center justify-center pointer-events-none">
          <div class="w-48 h-48 rounded-full border-4 border-primary-400 animate-ping opacity-60"></div>
        </div>
      </Transition>
    </div>

    <!-- Stats cards below model -->
    <div v-if="stats" class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 w-full max-w-lg">
      <div class="glass-card p-4 text-center rounded-2xl">
        <div class="text-2xl font-bold text-primary-600 dark:text-primary-400">{{ privacyStore.privacyMode ? stats.latestScore : '****' }}</div>
        <div class="text-xs text-gray-400  mt-1 font-medium">VASI 评分</div>
      </div>
      <div class="glass-card p-4 text-center rounded-2xl">
        <div class="text-2xl font-bold text-success-500 dark:text-green-400">{{ privacyStore.privacyMode ? stats.improvement + '%' : '****' }}</div>
        <div class="text-xs text-gray-400  mt-1 font-medium">累计改善</div>
      </div>
      <div class="glass-card p-4 text-center rounded-2xl">
        <div class="text-2xl font-bold text-gray-700 ">{{ stats.totalAssessments }}</div>
        <div class="text-xs text-gray-400  mt-1 font-medium">评估次数</div>
      </div>
      <div class="glass-card p-4 text-center rounded-2xl">
        <svg class="w-full h-10" viewBox="0 0 100 40" preserveAspectRatio="none">
          <polyline
            v-if="stats && stats.sparkline.length > 1"
            :points="stats?.sparkline.map((v, i) => `${(i / (stats!.sparkline.length - 1)) * 100},${40 - (v / Math.max(...stats!.sparkline)) * 35}`).join(' ')"
            fill="none"
            stroke="currentColor"
            :class="stats?.trend.includes('改善') ? 'text-green-500' : 'text-amber-500'"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <div class="text-xs text-gray-400  mt-1 font-medium">趋势</div>
      </div>
    </div>
  </div>

  <!-- ━━━ ASSESSMENT VIEW (full-screen, back button) ━━━ -->
  <div v-else-if="activeView === 'assessment'" class="max-w-6xl mx-auto px-4 pt-2 pb-6 space-y-6">
    <!-- Back button -->
    <button class="flex items-center gap-1 text-gray-600  hover:text-primary-500 dark:hover:text-primary-400 transition-colors mb-2" @click="goHome">
      <i class="ri-arrow-left-s-line text-xl"></i>
      <span class="text-sm">返回</span>
    </button>

    <!-- Last Assessment Result -->
    <div v-if="lastAssessment" class="card p-6 border-l-4" :class="{
      'border-green-500': lastAssessment.vasiScore < 10,
      'border-amber-500': lastAssessment.vasiScore >= 10 && lastAssessment.vasiScore < 25,
      'border-orange-500': lastAssessment.vasiScore >= 25 && lastAssessment.vasiScore < 50,
      'border-red-500': lastAssessment.vasiScore >= 50,
    }">
      <div class="flex items-start justify-between mb-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-900 "><i class="ri-clipboard-line"></i> 评估结果解读</h2>
          <p class="text-sm text-gray-500  mt-1">最新评估于刚刚完成</p>
        </div>
        <button @click="lastAssessment = null" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl">&times;</button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div class="bg-gray-50  rounded-lg p-3 text-center">
          <div class="text-xl font-bold" :class="getScoreInterpretation(lastAssessment.vasiScore).color">{{ lastAssessment.vasiScore }}</div>
          <div class="text-xs text-gray-500 ">VASI评分</div>
        </div>
        <div class="bg-gray-50  rounded-lg p-3 text-center">
          <div class="text-xl font-bold" :class="getScoreInterpretation(lastAssessment.vasiScore).color">{{ getScoreInterpretation(lastAssessment.vasiScore).level }}</div>
          <div class="text-xs text-gray-500 ">严重程度</div>
        </div>
        <div class="bg-gray-50  rounded-lg p-3 text-center">
          <div class="text-xl font-bold text-gray-700 ">{{ lastAssessment.areaPercentage }}%</div>
          <div class="text-xs text-gray-500 ">白斑面积占比</div>
        </div>
        <div class="bg-gray-50  rounded-lg p-3 text-center">
          <div class="text-xl font-bold" :class="lastAssessment.stage === '好转' ? 'text-green-600' : lastAssessment.stage === '扩散' || lastAssessment.stage === '进展期' ? 'text-red-600' : 'text-amber-600'">{{ lastAssessment.stage }}</div>
          <div class="text-xs text-gray-500 ">病情阶段</div>
        </div>
      </div>
      <div v-if="lastAssessment.confidence !== undefined" class="flex items-center gap-2 mt-3">
        <span class="text-sm text-gray-500">AI信心度:</span>
        <span v-if="lastAssessment.confidence >= 0.7" class="text-green-500">● 高 ({{ Math.round(lastAssessment.confidence * 100) }}%)</span>
        <span v-else-if="lastAssessment.confidence >= 0.4" class="text-amber-500">● 中 ({{ Math.round(lastAssessment.confidence * 100) }}%)</span>
        <span v-else class="text-red-500">● 低 ({{ Math.round(lastAssessment.confidence * 100) }}%)</span>
      </div>
      <div v-if="lastAssessment.confidence !== undefined && lastAssessment.confidence < 0.5" class="text-xs text-amber-600 dark:text-amber-400 mt-1">
        ⚠️ 本次评估信心度较低，建议在更好的光照条件下重新拍照
      </div>
      <div class="space-y-3">
        <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
          <h3 class="text-sm font-medium text-blue-700 dark:text-blue-300 mb-1"><i class="ri-microscope-line"></i> 评分含义</h3>
          <p class="text-sm text-blue-600 dark:text-blue-400">{{ getScoreInterpretation(lastAssessment.vasiScore).description }}</p>
        </div>
        <div class="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4">
          <h3 class="text-sm font-medium text-purple-700 dark:text-purple-300 mb-1"><i class="ri-bar-chart-2-line"></i> 阶段说明</h3>
          <p class="text-sm text-purple-600 dark:text-purple-400">{{ getStageDescription(lastAssessment.stage) }}</p>
        </div>
        <div v-if="lastAssessment.classification" class="bg-gray-50  rounded-lg p-4">
          <h3 class="text-sm font-medium text-gray-700  mb-1"><i class="ri-price-tag-3-line"></i> 分型</h3>
          <p class="text-sm text-gray-600 ">{{ lastAssessment.classification }}型白癜风</p>
        </div>
      </div>
      <button @click="writeDiaryFromAssessment" class="btn-primary mt-4 flex w-full items-center justify-center gap-2 py-2.5">
        <i class="ri-book-3-line mr-1"></i>写日记记录今天
      </button>
      <p class="text-xs text-gray-400  mt-4"><i class="ri-error-warning-line"></i> 以上解读仅供参考，不构成医疗诊断建议。</p>
    </div>

    <!-- Assessment Section -->
    <div class="flex flex-col lg:flex-row gap-4">
      <div class="lg:w-1/2">
        <!-- Contour Editor -->
        <template v-if="showContourEditor && imagePreview && assessmentResult">
          <div class="mb-4 p-3 rounded-xl bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800">
            <div class="flex items-center gap-2 mb-2">
              <i class="ri-information-line text-primary-500"></i>
              <span class="text-sm font-medium text-primary-700 dark:text-primary-300">VASI评分: {{ assessmentResult.vasiScore }} · 请调整白斑轮廓</span>
            </div>
            <p class="text-xs text-primary-600 dark:text-primary-400">AI已识别白斑区域（虚线圈定），您可以拖拽控制点、手绘新区域或整体移动来修正。</p>
          </div>
          <VitiligoContour :image-url="imagePreview" :contours="aiContours" :editable="true" @update="handleContourUpdate" @confirm="handleContourConfirm" />
          <div class="mt-4 flex items-center justify-between">
            <div v-if="isSubmittingContour" class="flex items-center gap-2 text-sm text-primary-500">
              <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> 提交中...
            </div>
            <button class="text-xs text-gray-400  hover:text-gray-600 dark:hover:text-gray-300 transition-colors" :disabled="isSubmittingContour" @click="skipContourEdit">跳过，直接查看结果 →</button>
          </div>
          <div v-if="contourDiffResult" class="mt-4 p-3 rounded-xl border" :class="contourDiffResult.modified ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'">
            <div class="flex items-center gap-2">
              <i :class="contourDiffResult.modified ? 'ri-error-warning-line text-amber-500' : 'ri-check-double-line text-green-500'"></i>
              <span class="text-xs font-medium" :class="contourDiffResult.modified ? 'text-amber-700 dark:text-amber-300' : 'text-green-700 dark:text-green-300'">
                {{ contourDiffResult.modified ? `AI与手动标注存在差异（平均偏差: ${(contourDiffResult.avg_point_distance ?? 0).toFixed(3)}），已记录用于模型优化` : 'AI识别结果与您的标注一致！' }}
              </span>
            </div>
          </div>
          <div v-if="preciseAvailable && !isPreciseAssessing && !preciseAssessmentDone && assessmentResult?.precisionLevel !== 'precise'" class="mt-4 p-3 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
            <div class="flex items-center gap-2 mb-1"><i class="ri-focus-3-line text-blue-500"></i><span class="text-sm font-medium text-blue-700 dark:text-blue-300">需要更精确的评估？</span></div>
            <p class="text-xs text-blue-600 dark:text-blue-400 mb-2">精确分析使用更高精度的AI模型，需要约1-2分钟</p>
            <button class="btn-ghost text-xs px-3 py-1.5" @click="startPreciseAssessment">开始精确分析</button>
          </div>
          <div v-if="isPreciseAssessing" class="mt-4 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 flex flex-col items-center">
            <svg class="animate-spin w-6 h-6 text-blue-500 mb-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            <span class="text-sm text-blue-600 dark:text-blue-400">精确分析中，请稍候...</span>
            <span class="text-xs text-gray-400 mt-1">预计需要1-2分钟</span>
          </div>
          <div v-if="preciseAssessmentDone" class="mt-4 p-3 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
            <div class="flex items-center gap-2"><i class="ri-check-double-line text-green-500"></i><span class="text-xs font-medium text-green-700 dark:text-green-300">精确分析已完成，轮廓已更新为高精度结果</span></div>
          </div>
        </template>

        <!-- Body Part Panel -->
        <BodyPartPanel
          v-else-if="selectedPart"
          :part="selectedPart"
          :assessment="activePartAssessment"
          :history="partHistory"
          @take-photo="openCamera"
          @upload-photo="triggerUpload"
          @close="selectedPart = null; selectedBodySite = ''"
        />
      </div>

      <!-- Upload Section -->
      <div class="lg:w-1/2">
        <div v-if="!showContourEditor && !selectedPart" class="card p-5 h-full flex flex-col min-h-[340px]">
          <div class="flex-1 flex flex-col items-center justify-center">
            <div class="relative border-2 border-dashed rounded-2xl p-6 w-full text-center cursor-pointer transition-all duration-200"
              :class="imagePreview ? 'border-primary-400 bg-primary-50/50 dark:bg-primary-900/10' : 'border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 hover:bg-gray-50/80 dark:hover:bg-gray-800/50'"
              @dragover.prevent @drop="handleDrop">
              <input id="tracker-file-input" ref="fileInput" type="file" accept="image/*" class="hidden" @change="handleFileSelect" />
              <div v-if="imagePreview" class="relative inline-block">
                <img :src="imagePreview" alt="预览" class="max-h-48 rounded-xl mx-auto shadow-sm" :class="{ 'blur-lg': !privacyStore.privacyMode }" />
                <button class="absolute top-2 right-2 w-8 h-8 bg-black/40 backdrop-blur-sm text-white rounded-full flex items-center justify-center hover:bg-red-500 transition-colors z-10" @click.stop="removeImage"><i class="ri-close-line"></i></button>
              </div>
              <div v-else class="flex flex-col items-center">
                <div class="w-12 h-12 rounded-2xl bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center mb-3">
                  <i class="ri-image-add-line text-2xl text-primary-500 dark:text-primary-400"></i>
                </div>
                <p class="text-sm font-medium text-gray-600 ">点击或拖拽上传白斑照片</p>
                <p class="text-xs text-gray-400  mt-1">支持 JPG / PNG，最大 10MB</p>
              </div>
            </div>
            <div class="relative mt-3 w-full">
              <button class="btn-primary w-full py-3 text-base flex items-center justify-center gap-2 min-h-[48px]" @click="showStandaloneChooser = !showStandaloneChooser">
                <i class="ri-camera-line text-lg"></i> 拍照评估
              </button>
              <div v-if="showStandaloneChooser" class="absolute left-0 right-0 top-full mt-2 p-3 rounded-xl bg-white  shadow-xl border border-gray-200 dark:border-gray-700 z-20 flex gap-2">
                <button class="flex-1 flex flex-col items-center gap-2 p-4 rounded-xl hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors border border-transparent hover:border-primary-200 dark:hover:border-primary-800" @click="showStandaloneChooser = false; openCamera()">
                  <div class="w-12 h-12 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center"><i class="ri-camera-line text-2xl text-primary-600 dark:text-primary-400"></i></div>
                  <span class="text-sm font-medium text-gray-700 ">拍照</span>
                </button>
                <button class="flex-1 flex flex-col items-center gap-2 p-4 rounded-xl hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors border border-transparent hover:border-primary-200 dark:hover:border-primary-800" @click="showStandaloneChooser = false; triggerUpload()">
                  <div class="w-12 h-12 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center"><i class="ri-image-line text-2xl text-primary-600 dark:text-primary-400"></i></div>
                  <span class="text-sm font-medium text-gray-700 ">相册选择</span>
                </button>
              </div>
            </div>
            <div v-if="qualityChecking" class="mt-3 flex items-center gap-2 text-sm text-gray-500 ">
              <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> 正在检查照片质量...
            </div>
            <div v-else-if="qualityResult && uploadedImage" class="mt-3 p-3 rounded-xl border w-full"
              :class="{ 'border-green-300 bg-green-50 dark:bg-green-900/20 dark:border-green-800': qualityResult.overall === 'good', 'border-amber-300 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800': qualityResult.overall === 'acceptable', 'border-red-300 bg-red-50 dark:bg-red-900/20 dark:border-red-800': qualityResult.overall === 'poor' }">
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium" :class="{'text-green-700 dark:text-green-300': qualityResult.overall === 'good', 'text-amber-700 dark:text-amber-300': qualityResult.overall === 'acceptable', 'text-red-700 dark:text-red-300': qualityResult.overall === 'poor'}">
                  <template v-if="qualityResult.overall === 'good'">✅ 照片质量良好</template>
                  <template v-else-if="qualityResult.overall === 'acceptable'">⚠️ {{ qualityResult.suggestions[0] || '照片质量一般' }}</template>
                  <template v-else>❌ 建议重新拍摄</template>
                </span>
              </div>
              <div v-if="qualityResult.overall !== 'good'" class="mt-2 flex items-center gap-2">
                <button class="text-xs px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-600  hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" @click="qualityIgnored = true">仍要评估</button>
                <button class="text-xs px-3 py-1.5 rounded-lg border border-primary-300 dark:border-primary-600 text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors" @click="removeImage">重新选择</button>
              </div>
            </div>
            <button class="btn-primary w-full mt-4 py-3 text-base" :disabled="!uploadedImage || !selectedBodySite || isUploading || (qualityResult?.overall === 'poor' && !qualityIgnored)" @click="submitAssessment">
              <span v-if="isUploading">
                <span class="inline-flex items-center gap-2"><svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> {{ uploadStage === 'uploading' ? '上传中...' : uploadStage === 'segmenting' ? 'AI识别中...' : '分析中...' }}</span>
              </span>
              <span v-else>开始评估</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Assessment History -->
    <div class="glass-card p-4 md:p-6 rounded-2xl">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-900 ">
          <i class="ri-line-chart-line"></i>
          <template v-if="selectedPart">{{ PART_LABELS[selectedPart] || selectedPart }} · </template>评估历史
        </h2>
        <div class="flex items-center gap-2">
          <template v-if="selectMode">
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
            <div class="flex-1 min-w-0 flex items-center gap-3 py-3 px-3 rounded-xl bg-gray-50 ">
              <div class="w-10 h-10 rounded-full flex items-center justify-center text-lg shrink-0" :class="record.stage === '稳定期' ? 'bg-green-100 dark:bg-green-900/30' : 'bg-amber-100 dark:bg-amber-900/30'">
                {{ record.stage === '稳定期' ? '✓' : '!' }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 text-sm">
                  <span class="font-medium text-gray-900 ">{{ record.bodySite }}</span>
                  <span class="text-gray-400 ">{{ record.date }}</span>
                </div>
                <div class="flex items-center gap-3 mt-0.5 text-xs text-gray-500 ">
                  <span>VASI <strong class="text-gray-700 ">{{ privacyStore.privacyMode ? record.vasiScore : '****' }}</strong></span>
                  <span>面积 <strong class="text-gray-700 ">{{ privacyStore.privacyMode ? record.areaPercentage + '%' : '****' }}</strong></span>
                  <span class="badge text-[10px] px-1.5 py-0.5" :class="record.stage === '稳定期' ? 'badge-success' : 'badge bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'">{{ record.stage }}</span>
                </div>
              </div>
            </div>
          </div>
          <button v-if="!selectMode && isSwiped(record.id)" class="absolute right-0 top-0 bottom-0 w-16 flex items-center justify-center bg-red-500 text-white rounded-r-xl" @click="deleteSingle(record.id)" :disabled="deletingIds.has(record.id)">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          </button>
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

  <!-- ━━━ CHAT VIEW (full-screen) ━━━ -->
  <ChatOverlay v-else-if="activeView === 'chat'" :show="true" :context-hint="chatContextHint" @close="goHome" />

  <!-- ━━━ REPORT VIEW (full-screen, back button) ━━━ -->
  <div v-else-if="activeView === 'report'" class="max-w-6xl mx-auto px-4 pt-2 pb-6">
    <button class="flex items-center gap-1 text-gray-600  hover:text-primary-500 dark:hover:text-primary-400 transition-colors mb-4" @click="goHome">
      <i class="ri-arrow-left-s-line text-xl"></i>
      <span class="text-sm">返回</span>
    </button>
    <ReportUploader />
  </div>

  <!-- Camera Modal (global) -->
  <BodyPartCamera
    v-model="showCamera"
    :body-part="selectedBodySite"
    @captured="handleCameraCapture"
  />
</template>

<!-- 全局样式：磨砂玻璃卡片 -->
<style>
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

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.metaphor-fade-enter-active { transition: opacity 0.3s ease; }
.metaphor-fade-leave-active { transition: opacity 0.2s ease; }
.metaphor-fade-enter-from,
.metaphor-fade-leave-to { opacity: 0; }
</style>
