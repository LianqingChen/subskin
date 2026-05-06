<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { medicalReportApi } from '@/api/medical-report'

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
  router.push(`/report/compare?ids=${selectedForCompare.value.join(',')}`)
}

function handleReportFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (!files) return
  for (const file of Array.from(files)) {
    if (file.size > 20 * 1024 * 1024) {
      toast.error(`${file.name} 超过20MB限制`)
      continue
    }
    reportFiles.value.push(file)
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (e) => { reportPreviews.value.push(e.target?.result as string) }
      reader.readAsDataURL(file)
    } else {
      reportPreviews.value.push('')
    }
  }
}

async function loadMedicalReports() {
  if (!authStore.isLoggedIn) return
  loadingReports.value = true
  try {
    const res = await medicalReportApi.list(50, 0)
    medicalReports.value = res.items
  } catch {
    // silent fail
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

async function deleteReport(reportId: number) {
  if (!confirm('确定要删除这份体检报告吗？')) return
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

async function getSecureFileUrl(fileId: number): Promise<string> {
  const token = authStore.token
  const response = await fetch(`/api/files/serve/${fileId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

async function handleFileClick(fileId: number) {
  try {
    const url = await getSecureFileUrl(fileId)
    window.open(url, '_blank')
  } catch (e) {
    toast.error('无法加载文件')
  }
}

function viewInterpretation(report: any) {
  router.push(`/tracker/report/${report.id}`)
}

onMounted(() => {
  loadMedicalReports()
})

defineExpose({ loadMedicalReports })
</script>

<template>
  <div class="space-y-4">
    <div class="card p-4">

      <!-- File upload box — prompt when empty, file list when selected -->
      <div
        class="relative border-2 border-dashed rounded-2xl p-4 text-center cursor-pointer transition-all duration-200"
        :class="reportFiles.length ? 'border-primary-400 bg-primary-50/50 dark:bg-primary-900/10' : 'border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 hover:bg-gray-50/80 dark:hover:bg-gray-800/50'"
        @dragover.prevent
        @drop.prevent="(e: DragEvent) => { const files = e.dataTransfer?.files; if (files) { for (const f of Array.from(files)) { reportFiles.push(f); } } }"
      >
        <input ref="reportFileInput" type="file" multiple accept="image/*,.pdf" class="hidden" @change="handleReportFileSelect" />

        <!-- Empty state: upload prompt -->
        <div v-if="!reportFiles.length" class="flex flex-col items-center" @click="($refs.reportFileInput as HTMLInputElement).click()">
          <div class="w-12 h-12 rounded-2xl bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center mb-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 text-amber-500 dark:text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
            </svg>
          </div>
          <p class="text-sm font-medium text-gray-600 dark:text-gray-300">点击或拖拽上传体检报告</p>
          <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">支持图片 / PDF，单个最大 20MB，标题自动生成</p>
        </div>

        <!-- Files selected: show file list inside the box -->
        <div v-else class="space-y-2 text-left">
          <div v-for="(file, idx) in reportFiles" :key="idx"
            class="flex items-center gap-3 p-2.5 rounded-lg bg-white/80 dark:bg-gray-800/80 border border-gray-100 dark:border-gray-700">
            <span class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              :class="file.type.startsWith('image/') ? 'bg-primary-50 dark:bg-primary-900/30' : 'bg-amber-50 dark:bg-amber-900/30'">
              <svg v-if="file.type.startsWith('image/')" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-primary-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clip-rule="evenodd" /></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-amber-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" /></svg>
            </span>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{{ file.name }}</div>
              <div class="text-xs text-gray-400 dark:text-gray-500">{{ (file.size / 1024).toFixed(1) }} KB</div>
            </div>
            <button class="p-1 text-gray-400 hover:text-red-500 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              @click="reportFiles.splice(idx, 1); reportPreviews.splice(idx, 1)">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
            </button>
          </div>
          <button class="flex items-center gap-1 text-xs text-primary-500 hover:text-primary-600 font-medium"
            @click="($refs.reportFileInput as HTMLInputElement).click()">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" /></svg>
            添加更多文件
          </button>
        </div>
      </div>

      <!-- Submit button -->
      <button v-if="reportFiles.length" class="btn-primary w-full py-3 text-base mt-3"
        :disabled="isUploadingReport"
        @click="submitReport">
        <span v-if="isUploadingReport">上传中...</span>
        <span v-else>上传并解读</span>
      </button>
    </div>

    <div class="card p-4">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100"><i class="ri-file-list-3-line mr-1"></i>历史报告</h2>
        <button v-if="medicalReports.length > 1" @click="toggleCompareMode" class="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 flex items-center gap-1">
          <i class="ri-scales-line"></i> {{ isCompareMode ? '取消对比' : '对比报告' }}
        </button>
      </div>
      
      <!-- Filters -->
      <div v-if="medicalReports.length > 0" class="flex gap-2 mb-4 overflow-x-auto pb-1 hide-scrollbar">
        <button class="px-3 py-1.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 whitespace-nowrap">全部</button>
        <button class="px-3 py-1.5 rounded-full text-xs font-medium bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 whitespace-nowrap flex items-center gap-1">按时间筛选 <i class="ri-arrow-down-s-line"></i></button>
        <button class="px-3 py-1.5 rounded-full text-xs font-medium bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 whitespace-nowrap flex items-center gap-1">按体检人筛选 <i class="ri-arrow-down-s-line"></i></button>
      </div>

      <div v-if="loadingReports" class="text-center py-8 text-gray-400 dark:text-gray-500">加载中...</div>
      <div v-else-if="medicalReports.length === 0" class="text-center py-8 text-gray-400 dark:text-gray-500">
        <div class="text-4xl mb-3"><i class="ri-file-list-3-line"></i></div>
        <p>暂无体检报告</p>
        <p class="text-xs mt-1">上传报告后，AI将自动提取关键指标</p>
      </div>
      <div v-else class="space-y-3">
        <div v-for="report in medicalReports" :key="report.id"
          class="p-4 rounded-xl border transition-all cursor-pointer relative"
          :class="[
            isCompareMode && selectedForCompare.includes(report.id) ? 'border-primary-500 bg-primary-50/30 dark:bg-primary-900/10' : 'border-gray-200 dark:border-gray-700 hover:shadow-md',
            isCompareMode && !selectedForCompare.includes(report.id) && selectedForCompare.length >= 3 ? 'opacity-50' : ''
          ]"
          @click="isCompareMode ? toggleReportSelection(report.id) : viewInterpretation(report)">
          
          <!-- Checkbox for compare mode -->
          <div v-if="isCompareMode" class="absolute top-4 right-4 text-xl" :class="selectedForCompare.includes(report.id) ? 'text-primary-500' : 'text-gray-300 dark:text-gray-600'">
            <i :class="selectedForCompare.includes(report.id) ? 'ri-checkbox-circle-fill' : 'ri-checkbox-blank-circle-line'"></i>
          </div>

          <!-- Row 1: title + delete -->
          <div class="flex items-center justify-between pr-8">
            <h3 class="font-medium text-gray-900 dark:text-gray-100 text-sm truncate flex-1 min-w-0">{{ report.title }}</h3>
            <button v-if="!isCompareMode" class="p-1.5 text-red-400 dark:text-red-400 hover:text-red-600 dark:hover:text-red-300 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors flex-shrink-0 ml-2"
              title="删除" @click.stop="deleteReport(report.id)"><i class="ri-delete-bin-line"></i></button>
          </div>
          <!-- Row 2: tags + date -->
          <div class="flex items-center gap-2 mt-1 flex-wrap">
            <span v-for="tag in (report.tags || '').split(',').filter(Boolean)" :key="tag"
              class="px-2 py-0.5 rounded-full text-xs bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300">{{ tag }}</span>
            <span class="text-xs text-gray-400 dark:text-gray-500">{{ formatDate(report.created_at) }}</span>
          </div>
          <!-- Row 3: files + AI badge -->
          <div class="flex items-center gap-2 mt-2">
            <button v-for="file in report.files" :key="file.id"
              @click.stop="handleFileClick(file.id)"
              class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs bg-gray-100 dark:bg-gray-700 text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors cursor-pointer">
              <i :class="file.file_type?.startsWith('image/') ? 'ri-image-line' : 'ri-file-text-line'"></i> {{ file.file_name }}
            </button>
            <button class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400 hover:bg-primary-100 dark:hover:bg-primary-900/50 transition-colors cursor-pointer"
              @click.stop="viewInterpretation(report)">
              <i class="ri-eye-line"></i> 查看报告
            </button>
            <button v-if="!report.interpretation_json"
              class="inline-flex items-center px-2.5 py-1.5 rounded-md text-xs bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-50 transition-colors flex-shrink-0 whitespace-nowrap"
              @click.stop="triggerInterpret(report.id)" :disabled="interpretLoading[report.id]">
              <i class="ri-robot-line mr-1" v-if="!interpretLoading[report.id]"></i>
              {{ interpretLoading[report.id] ? '解读中...' : 'AI解读' }}
            </button>
            <span v-else class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 flex-shrink-0 whitespace-nowrap"><i class="ri-robot-line text-xs"></i> AI解读</span>
          </div>
        </div>
      </div>
    </div>

    <section class="text-center text-xs text-gray-400 dark:text-gray-500 py-4 border-t border-gray-100 dark:border-gray-800">
      <i class="ri-error-warning-line"></i> 体检报告分析结果仅供参考，不构成医疗诊断建议
    </section>

    <!-- Compare Mode Sticky Bar -->
    <div v-if="isCompareMode" class="fixed bottom-0 left-0 right-0 bg-gray-900 dark:bg-gray-950 text-white p-4 shadow-[0_-8px_30px_rgba(0,0,0,0.12)] z-50 flex items-center justify-between" style="padding-bottom: calc(1rem + env(safe-area-inset-bottom));">
      <div class="text-sm">已选择 <span class="font-bold text-primary-400">{{ selectedForCompare.length }}</span>/3 份报告</div>
      <div class="flex gap-3">
        <button @click="toggleCompareMode" class="px-4 py-2 rounded-lg text-sm font-medium text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 transition-colors">取消</button>
        <button @click="startCompare" :disabled="selectedForCompare.length < 2" class="px-4 py-2 rounded-lg text-sm font-medium bg-primary-500 hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">开始对比</button>
      </div>
    </div>
  </div>
</template>
