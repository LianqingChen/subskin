<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useToast } from '@/composables/useToast'
import { HealthConsentDeclined } from '@/composables/useHealthConsent'
import { getFileViewUrl, medicalReportApi } from '@/api/medical-report'

const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()

const reportFiles = ref<File[]>([])
const reportPreviews = ref<string[]>([])
const reportTags = ref<string[]>([])
const isUploadingReport = ref(false)
const medicalReports = ref<any[]>([])
const loadingReports = ref(false)
const interpretLoading = ref<Record<number, boolean>>({})

const isCompareMode = ref(false)
const selectedForCompare = ref<number[]>([])

// ── 历史报告筛选（按时间 / 按体检人）──
const timeFilter = ref<'all' | 'week' | 'month' | 'year'>('all')
const personFilter = ref('')
const showTimeMenu = ref(false)
const showPersonMenu = ref(false)

const TIME_OPTIONS = [
  { value: 'all', label: '全部时间' },
  { value: 'week', label: '最近7天' },
  { value: 'month', label: '最近30天' },
  { value: 'year', label: '最近一年' },
] as const

const timeFilterLabel = computed(() => {
  const opt = TIME_OPTIONS.find(o => o.value === timeFilter.value)
  if (!opt || timeFilter.value === 'all') return '时间'
  return `时间：${opt.label}`
})

const patientNames = computed(() => {
  const names = new Set<string>()
  for (const r of medicalReports.value) {
    const n = r.extracted_patient_info_json?.name
    if (n) names.add(n)
  }
  return Array.from(names).sort()
})

const filteredReports = computed(() => {
  let list = medicalReports.value
  if (timeFilter.value !== 'all') {
    const days = { week: 7, month: 30, year: 365 }[timeFilter.value]
    const cutoff = Date.now() - days * 86400000
    list = list.filter(r => new Date(r.created_at).getTime() >= cutoff)
  }
  if (personFilter.value) {
    list = list.filter(r => r.extracted_patient_info_json?.name === personFilter.value)
  }
  return list
})

function setTimeFilter(v: 'all' | 'week' | 'month' | 'year') {
  timeFilter.value = v
  showTimeMenu.value = false
}

function setPersonFilter(name: string) {
  personFilter.value = name
  showPersonMenu.value = false
}

function resetFilters() {
  timeFilter.value = 'all'
  personFilter.value = ''
  showTimeMenu.value = false
  showPersonMenu.value = false
}

function toggleCompareMode() {
  isCompareMode.value = !isCompareMode.value
  if (!isCompareMode.value) {
    selectedForCompare.value = []
  }
}

function toggleReportSelection(reportId: number) {
  const idx = selectedForCompare.value.indexOf(reportId)
  if (idx > -1) {
    selectedForCompare.value.splice(idx, 1)
  } else {
    if (selectedForCompare.value.length < 3) {
      selectedForCompare.value.push(reportId)
    } else {
      toast.warning('最多只能选择3份报告进行对比')
    }
  }
}

function startCompare() {
  if (selectedForCompare.value.length < 2) return
  router.push(`/assessment/report-compare?ids=${selectedForCompare.value.join(',')}`)
}

const REPORT_MAX_SIZE = 20 * 1024 * 1024
const REPORT_TYPES: Record<string, boolean> = {
  'image/jpeg': true,
  'image/png': true,
  'image/webp': true,
  'image/gif': true,
  'application/pdf': true,
}

function isSupportedReportFile(file: File): boolean {
  return REPORT_TYPES[file.type] || /\.(jpe?g|png|webp|gif|pdf)$/i.test(file.name)
}

function addReportFiles(fileList: FileList | File[]) {
  let rejectedType = false
  let rejectedSize = false

  for (const file of Array.from(fileList)) {
    if (!isSupportedReportFile(file)) {
      rejectedType = true
      continue
    }
    if (file.size > REPORT_MAX_SIZE) {
      rejectedSize = true
      continue
    }

    reportFiles.value.push(file)
    const reader = new FileReader()
    reader.onload = (event) => {
      if (!reportFiles.value.includes(file)) return
      reportPreviews.value.push(
        file.type.startsWith('image/') ? event.target?.result as string : '',
      )
    }
    reader.onerror = () => reportPreviews.value.push('')
    reader.readAsDataURL(file)
  }

  if (rejectedType) toast.error('存在不支持的文件，仅支持图片或 PDF')
  if (rejectedSize) toast.error('存在超过 20MB 的文件')
}

function handleReportFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files) return
  addReportFiles(target.files)
  // Allow selecting the same file again after it is removed.
  target.value = ''
}

function handleReportFileDrop(event: DragEvent) {
  const files = event.dataTransfer?.files
  if (files) addReportFiles(files)
}

function removeReportFile(index: number) {
  reportFiles.value.splice(index, 1)
  reportPreviews.value.splice(index, 1)
}

function handleFileClick(fileId: number) {
  // A direct authenticated view URL avoids blob lifecycle issues and keeps PDF
  // viewing working in mobile and WeChat browsers, where asynchronous popups
  // are often blocked.
  window.open(getFileViewUrl(fileId, authStore.token), '_blank', 'noopener')
}

async function loadMedicalReports() {
  if (!authStore.isLoggedIn) return
  loadingReports.value = true
  try {
    const res = await medicalReportApi.list(50, 0)
    medicalReports.value = res.items
  } catch {
    medicalReports.value = []
  } finally {
    loadingReports.value = false
  }
}

async function submitReport() {
  if (!authStore.isLoggedIn) { authStore.showLoginModal = true; return }
  if (reportFiles.value.length === 0) { toast.warning('请至少上传一个文件'); return }
  isUploadingReport.value = true
  try {
    // Auto-generate title: username + report type
    const userName = authStore.user?.username || '用户'
    const autoTitle = `${userName} 综合体检报告`
    const tagsStr = reportTags.value.join(',')
    const report = await medicalReportApi.create(autoTitle, tagsStr || null, reportFiles.value)
    toast.success('体检报告上传成功，正在AI解读...')
    reportFiles.value = []
    reportPreviews.value = []
    reportTags.value = []
    await loadMedicalReports()
    if (report.id) triggerInterpret(report.id)
  } catch (err: any) {
    if (err instanceof HealthConsentDeclined) { toast.warning(err.message); return }
    const detail = err?.response?.data?.detail
    toast.error(typeof detail === 'string' ? detail : '上传失败，请稍后重试')
  } finally {
    isUploadingReport.value = false
  }
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const confirmDeleteVisible = ref(false)
const pendingDeleteId = ref<number | null>(null)

function deleteReport(reportId: number) {
  pendingDeleteId.value = reportId
  confirmDeleteVisible.value = true
}

async function onConfirmDelete() {
  const reportId = pendingDeleteId.value
  confirmDeleteVisible.value = false
  pendingDeleteId.value = null
  if (reportId === null) return
  try {
    await medicalReportApi.delete(reportId)
    toast.success('删除成功')
    await loadMedicalReports()
  } catch {
    toast.error('删除失败')
  }
}

async function triggerInterpret(reportId: number) {
  interpretLoading.value[reportId] = true
  try {
    await medicalReportApi.interpret(reportId)
    await loadMedicalReports()
    toast.success('AI解读完成！')
    router.push(`/tracker/report/${reportId}`)
  } catch (err: any) {
    const detail = err?.response?.data?.detail
    toast.error(detail || '解读失败，请稍后重试')
  } finally {
    interpretLoading.value[reportId] = false
  }
}

function viewInterpretation(report: any) {
  router.push(`/tracker/report/${report.id}`)
}

// ── 历史入口：滚动定位到「历史报告」卡片并短暂高亮 ──
const historyCardRef = ref<HTMLElement | null>(null)
const historyHighlighted = ref(false)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

function scrollToHistory() {
  historyCardRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  historyHighlighted.value = false
  requestAnimationFrame(() => {
    historyHighlighted.value = true
    if (highlightTimer) clearTimeout(highlightTimer)
    highlightTimer = setTimeout(() => { historyHighlighted.value = false }, 1800)
  })
}

onUnmounted(() => {
  if (highlightTimer) clearTimeout(highlightTimer)
})

onMounted(() => {
  loadMedicalReports()
})

defineExpose({ loadMedicalReports })
</script>

<template>
  <!-- 桌面端两栏：左侧上传，右侧历史报告；手机/平板单栏 -->
  <div class="grid gap-4 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)] lg:items-start lg:gap-6" :class="isCompareMode ? 'pb-36 md:pb-24' : ''">
  <ConfirmDialog
    :visible="confirmDeleteVisible"
    title="删除确认"
    message="确定要删除这份体检报告吗？"
    confirm-text="删除"
    @confirm="onConfirmDelete"
    @cancel="confirmDeleteVisible = false"
  />

    <div class="card min-w-0 p-4 relative lg:p-5">
      <!-- File upload box — prompt when empty, file list when selected -->
      <div
        class="relative border border-dashed rounded-xl p-5 lg:py-10 text-center cursor-pointer transition-all duration-200"
        :class="reportFiles.length ? 'border-primary-500/50 bg-primary-50/40 dark:bg-primary-900/20' : 'border-gray-300/90 dark:border-gray-700 bg-gray-50/60 dark:bg-gray-800/40 hover:border-primary-400 dark:hover:border-primary-600 hover:bg-primary-50/30 dark:hover:bg-primary-900/20'"
        @dragover.prevent
        @drop.prevent="handleReportFileDrop"
      >
        <input
          ref="reportFileInput"
          type="file"
          multiple
          accept=".jpg,.jpeg,.png,.webp,.gif,.pdf,image/jpeg,image/png,image/webp,image/gif,application/pdf"
          class="hidden"
          @change="handleReportFileSelect"
        />

        <!-- Empty state: upload prompt -->
        <button type="button" v-if="!reportFiles.length" class="flex min-h-[120px] w-full flex-col items-center justify-center" @click="($refs.reportFileInput as HTMLInputElement).click()">
          <div class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-900/40 border border-primary-200/60 dark:border-primary-700/40 flex items-center justify-center mb-2.5 text-primary-600 dark:text-primary-400">
            <i class="ri-file-upload-line text-2xl" aria-hidden="true"></i>
          </div>
          <span class="text-sm font-medium text-gray-700 dark:text-gray-200">上传体检报告，查看解读</span>
          <span class="mt-1 text-xs text-gray-500 dark:text-gray-400">支持图片或 PDF · 单个文件最大 20MB</span>
        </button>

        <!-- Files selected: show file list inside the box -->
        <div v-else class="space-y-2 text-left">
          <div v-for="(file, idx) in reportFiles" :key="idx"
            class="flex items-center gap-3 p-2.5 rounded-lg bg-white/90 dark:bg-gray-800/90 border border-gray-200/80 dark:border-gray-700">
            <span class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              :class="file.type.startsWith('image/') ? 'bg-primary-50 dark:bg-primary-900 text-primary-600 dark:text-primary-400' : 'bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'">
              <i :class="file.type.startsWith('image/') ? 'ri-image-line' : 'ri-file-text-line'" class="text-base" aria-hidden="true"></i>
            </span>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{{ file.name }}</div>
              <div class="text-xs text-gray-400 dark:text-gray-500 tabular-nums">{{ (file.size / 1024).toFixed(1) }} KB</div>
            </div>
            <button
              type="button"
              class="w-9 h-9 flex items-center justify-center text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              :aria-label="`移除 ${file.name}`"
              @click="removeReportFile(idx)"
            >
              <i class="ri-close-line text-lg" aria-hidden="true"></i>
            </button>
          </div>
          <button type="button" class="min-h-[44px] flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 font-medium"
            @click="($refs.reportFileInput as HTMLInputElement).click()">
            <i class="ri-add-line text-sm" aria-hidden="true"></i>
            添加更多文件
          </button>
        </div>
      </div>

      <button type="button" class="mt-2 min-h-[44px] w-full text-xs text-gray-500 lg:hidden dark:text-gray-400" data-track-id="report_history_btn" @click="scrollToHistory">查看历史报告<i class="ri-arrow-down-line ml-1" aria-hidden="true"></i></button>
      <!-- Submit button -->
      <button v-if="reportFiles.length" class="btn-primary w-full py-3 text-base mt-3"
        :disabled="isUploadingReport"
        @click="submitReport">
        <span v-if="isUploadingReport">上传中...</span>
        <span v-else>上传并解读</span>
      </button>
    </div>

    <div ref="historyCardRef" class="card min-w-0 p-4 scroll-mt-32 lg:p-5 transition-all duration-500" :class="historyHighlighted ? 'ring-2 ring-primary-300 bg-primary-50 dark:bg-primary-900' : ''">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100"><i class="ri-file-list-3-line mr-1"></i>历史报告</h2>
        <button v-if="medicalReports.length > 1" type="button" @click="toggleCompareMode" class="min-h-[44px] text-[13px] text-primary-600 dark:text-primary-400 hover:text-primary-700 flex items-center gap-1">
          <i class="ri-scales-line"></i> {{ isCompareMode ? '取消对比' : '对比报告' }}
        </button>
      </div>
      
      <!-- Filters -->
      <div v-if="medicalReports.length > 0" class="flex flex-wrap gap-2 mb-4">
        <button type="button" @click="resetFilters"
          class="control-slim min-h-[44px]"
          :class="timeFilter === 'all' && !personFilter ? 'control-slim-active' : ''">
          全部
        </button>
        <div class="relative">
          <button type="button" @click="showTimeMenu = !showTimeMenu; showPersonMenu = false"
            class="control-slim min-h-[44px]"
            :class="timeFilter !== 'all' ? 'control-slim-active' : ''">
            {{ timeFilterLabel }} <i class="ri-arrow-down-s-line"></i>
          </button>
          <div v-if="showTimeMenu" class="menu-slim min-w-[130px]">
            <button v-for="opt in TIME_OPTIONS" :key="opt.value" type="button" @click="setTimeFilter(opt.value)"
              class="menu-slim-item min-h-[44px]"
              :class="timeFilter === opt.value ? 'text-primary-600 dark:text-primary-400 font-medium' : 'text-gray-700 dark:text-gray-300'">
              {{ opt.label }}
            </button>
          </div>
        </div>
        <div class="relative">
          <button type="button" @click="showPersonMenu = !showPersonMenu; showTimeMenu = false"
            class="control-slim min-h-[44px]"
            :class="personFilter ? 'control-slim-active' : ''">
            {{ personFilter ? '体检人：' + personFilter : '体检人' }} <i class="ri-arrow-down-s-line"></i>
          </button>
          <div v-if="showPersonMenu" class="menu-slim min-w-[160px] max-h-56 overflow-y-auto">
            <button type="button" @click="setPersonFilter('')"
              class="menu-slim-item min-h-[44px]"
              :class="!personFilter ? 'text-primary-600 dark:text-primary-400 font-medium' : 'text-gray-700 dark:text-gray-300'">
              全部体检人
            </button>
            <button v-for="name in patientNames" :key="name" type="button" @click="setPersonFilter(name)"
              class="menu-slim-item min-h-[44px]"
              :class="personFilter === name ? 'text-primary-600 dark:text-primary-400 font-medium' : 'text-gray-700 dark:text-gray-300'">
              {{ name }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="loadingReports" class="text-center py-8 text-gray-400 dark:text-gray-500">加载中...</div>
      <div v-else-if="medicalReports.length === 0" class="text-center py-8 text-gray-400 dark:text-gray-500">
        <div class="text-4xl mb-3"><i class="ri-file-list-3-line"></i></div>
        <p>暂无体检报告</p>
      </div>
      <div v-else-if="filteredReports.length === 0" class="text-center py-8 text-gray-400 dark:text-gray-500">
        <p>无符合条件的报告</p>
      </div>
      <div v-else class="space-y-3">
        <div v-for="report in filteredReports" :key="report.id"
          class="p-4 rounded-xl border transition-all cursor-pointer relative"
          :class="[
            isCompareMode && selectedForCompare.includes(report.id) ? 'border-primary-500 bg-primary-50 dark:bg-primary-900' : 'border-gray-200 dark:border-gray-700 hover:shadow-md',
            isCompareMode && !selectedForCompare.includes(report.id) && selectedForCompare.length >= 3 ? 'opacity-50' : ''
          ]"
          @click="isCompareMode ? toggleReportSelection(report.id) : viewInterpretation(report)">
          
          <!-- Checkbox for compare mode -->
          <div v-if="isCompareMode" class="absolute top-4 right-4 text-xl" :class="selectedForCompare.includes(report.id) ? 'text-primary-500' : 'text-gray-300 '">
            <i :class="selectedForCompare.includes(report.id) ? 'ri-checkbox-circle-fill' : 'ri-checkbox-blank-circle-line'"></i>
          </div>

          <!-- Row 1: title + delete -->
          <div class="flex items-center justify-between pr-8">
            <h3 class="min-w-0 flex-1 text-sm font-medium text-gray-900 dark:text-gray-100"><button type="button" class="min-h-[44px] w-full truncate text-left" @click.stop="isCompareMode ? toggleReportSelection(report.id) : viewInterpretation(report)">{{ report.title }}</button></h3>
            <button v-if="!isCompareMode" class="min-h-[44px] min-w-[44px] p-1.5 text-red-400 dark:text-red-400 hover:text-red-600 dark:hover:text-red-300 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors flex-shrink-0 ml-2"
              title="删除" @click.stop="deleteReport(report.id)"><i class="ri-delete-bin-line"></i></button>
          </div>
          <!-- Row 2: tags + date -->
          <div class="flex items-center gap-2 mt-1 flex-wrap">
            <span v-for="tag in (report.tags || '').split(',').filter(Boolean)" :key="tag"
              class="min-w-0 max-w-full break-all px-2 py-0.5 rounded-full text-xs bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300">{{ tag }}</span>
            <span class="text-xs text-gray-400 dark:text-gray-500">{{ formatDate(report.created_at) }}</span>
          </div>
          <!-- Row 3: filenames truncate within the card; multiple files wrap. -->
          <div class="mt-2 flex min-w-0 flex-wrap items-center gap-2">
            <button v-for="file in report.files" :key="file.id"
              @click.stop="handleFileClick(file.id)"
              class="inline-flex min-h-[44px] min-w-0 max-w-full items-center gap-1 px-2.5 py-1.5 rounded-md text-xs bg-gray-100 dark:bg-gray-700 text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors cursor-pointer">
              <i :class="file.file_type?.startsWith('image/') ? 'ri-image-line' : 'ri-file-text-line'" class="shrink-0" aria-hidden="true"></i><span class="truncate" :title="file.file_name">{{ file.file_name }}</span>
            </button>
            <button v-if="!report.interpretation_json"
              class="inline-flex min-h-[44px] items-center px-2.5 py-1.5 rounded-md text-xs bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-50 transition-colors flex-shrink-0 whitespace-nowrap"
              @click.stop="triggerInterpret(report.id)" :disabled="interpretLoading[report.id]">
              <i class="ri-robot-line mr-1" v-if="!interpretLoading[report.id]"></i>
              {{ interpretLoading[report.id] ? '解读中...' : 'AI解读' }}
            </button>
            <span v-else class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 flex-shrink-0 whitespace-nowrap"><i class="ri-robot-line text-xs"></i> AI解读</span>
          </div>
        </div>
      </div>
    </div>

    <section class="text-center text-xs text-gray-400 dark:text-gray-500 py-4 border-t border-gray-100 dark:border-gray-800 lg:col-span-2">
      <i class="ri-error-warning-line"></i> 体检报告分析结果仅供参考，不构成医疗诊断建议
    </section>

    <!-- Compare Mode Sticky Bar -->
    <div v-if="isCompareMode" class="app-fixed-x fixed bottom-[calc(55px+env(safe-area-inset-bottom,0px))] z-40 flex flex-wrap items-center justify-between gap-3 bg-gray-900 p-4 text-white shadow-sm md:bottom-0">
      <div class="text-sm">已选择 <span class="font-bold text-primary-400">{{ selectedForCompare.length }}</span>/3 份报告</div>
      <div class="flex w-full gap-3 sm:w-auto">
        <button @click="toggleCompareMode" class="min-h-[44px] flex-1 px-4 py-2 rounded-lg text-sm font-medium text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 transition-colors">取消</button>
        <button @click="startCompare" :disabled="selectedForCompare.length < 2" class="min-h-[44px] flex-1 whitespace-nowrap px-4 py-2 rounded-lg text-sm font-medium bg-primary-500 hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">开始对比</button>
      </div>
    </div>
  </div>
</template>
