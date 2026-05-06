<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { medicalReportApi } from '@/api/medical-report'
import type { MedicalReport, InterpretationResult } from '@/api/medical-report'
import ReportFileViewer from '@/components/tracker/ReportFileViewer.vue'
import ReportProfileConfirmation from '@/components/tracker/ReportProfileConfirmation.vue'
import ReportInterpretation from '@/components/tracker/ReportInterpretation.vue'

const route = useRoute()
const router = useRouter()

const reportId = computed(() => Number(route.params.id))
const loading = ref(true)
const report = ref<MedicalReport | null>(null)
const interpretation = ref<InterpretationResult | null>(null)

// Progress state
const interpreting = ref(false)
const progressStage = ref(0)
let pollingInterval: number | null = null

// Profile confirmation state
const skipProfileLink = ref(false)
const showProfileConfirmation = computed(() => {
  return report.value?.extracted_patient_info_json && 
         !report.value?.patient_profile_id && 
         !skipProfileLink.value
})

async function loadReport() {
  loading.value = true
  try {
    const r = await medicalReportApi.get(reportId.value)
    report.value = r
    interpretation.value = r.interpretation_json
    
    if (interpretation.value?.sections) {
      for (const s of interpretation.value.sections) {
        ;(s as any)._expanded = false
      }
    }
  } catch {
    // not found
  } finally {
    loading.value = false
  }
}

async function triggerInterpret() {
  interpreting.value = true
  progressStage.value = 1
  
  try {
    // Start interpretation in background
    medicalReportApi.interpret(reportId.value).catch(() => {})
    
    // Start polling
    startPolling()
  } catch {
    interpreting.value = false
  }
}

function startPolling() {
  if (pollingInterval) clearInterval(pollingInterval)
  
  // Simulate progress stages since we don't have real SSE
  const stageInterval = setInterval(() => {
    if (progressStage.value < 4) {
      progressStage.value++
    }
  }, 3000)
  
  pollingInterval = window.setInterval(async () => {
    try {
      const result = await medicalReportApi.getInterpretation(reportId.value)
      if (result.interpreted) {
        clearInterval(pollingInterval!)
        clearInterval(stageInterval)
        pollingInterval = null
        interpreting.value = false
        await loadReport()
      }
    } catch (e) {
      // ignore polling errors
    }
  }, 2000)
}

function handleProfileLinked(profileId: number) {
  if (report.value) {
    report.value.patient_profile_id = profileId
  }
}

function handleProfileSkipped() {
  skipProfileLink.value = true
}

onMounted(() => {
  loadReport()
})

onUnmounted(() => {
  if (pollingInterval) clearInterval(pollingInterval)
})

function formatDate(dateStr: string) {
  return dateStr?.slice(0, 10) || ''
}
</script>

<template>
  <div class="min-h-dvh bg-gray-50 dark:bg-gray-900 pb-20 md:pb-8">
    <!-- Header -->
    <header class="sticky top-0 z-30 bg-white/80 dark:bg-gray-800/80 backdrop-blur border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-6xl mx-auto flex items-center gap-3 px-4 h-12">
        <button @click="router.back()" class="p-1 -ml-1 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
          <i class="ri-arrow-left-s-line text-xl"></i>
        </button>
        <h1 class="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">体检报告解读</h1>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-4">
      <!-- Loading -->
      <div v-if="loading" class="text-center py-16 text-gray-400 dark:text-gray-500">
        <div class="text-4xl mb-3 animate-pulse"><i class="ri-file-list-3-line"></i></div>
        <p>加载中...</p>
      </div>

      <template v-else-if="report">
        <div class="flex flex-col lg:flex-row gap-6">
          
          <!-- Left Column: File Viewer -->
          <div class="w-full lg:w-1/2 flex flex-col gap-4">
            <div class="card p-4">
              <h2 class="font-semibold text-gray-900 dark:text-gray-100">{{ report.title }}</h2>
              <div class="flex items-center gap-2 mt-1 flex-wrap">
                <span v-for="tag in (report.tags || '').split(',').filter(Boolean)" :key="tag"
                  class="px-2 py-0.5 rounded-full text-xs bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300">
                  {{ tag }}
                </span>
                <span class="text-xs text-gray-400 dark:text-gray-500">{{ formatDate(report.created_at) }}</span>
              </div>
            </div>
            
            <div class="flex-1 min-h-[500px]">
              <ReportFileViewer v-if="report.files?.length" :files="report.files" />
              <div v-else class="card h-full flex items-center justify-center text-gray-400">
                <div class="text-center">
                  <i class="ri-file-damage-line text-4xl mb-2"></i>
                  <p>无文件</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Right Column: Interpretation -->
          <div class="w-full lg:w-1/2 flex flex-col gap-4">
            
            <!-- Profile Confirmation -->
            <ReportProfileConfirmation 
              v-if="showProfileConfirmation"
              :report-id="report.id"
              :extracted-info="report.extracted_patient_info_json!"
              @linked="handleProfileLinked"
              @skipped="handleProfileSkipped"
            />

            <!-- Not yet interpreted -->
            <div v-if="!interpretation && !interpreting" class="card p-8 text-center flex-1 flex flex-col items-center justify-center">
              <div class="text-5xl mb-4 text-primary-500"><i class="ri-robot-line"></i></div>
              <p class="text-gray-900 dark:text-gray-100 font-medium mb-2 text-lg">还未进行AI解读</p>
              <p class="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-sm">AI将用通俗易懂的语言解读你的体检报告，提示风险项并给出建议</p>
              <button @click="triggerInterpret" class="btn-primary px-6 py-2.5">
                <i class="ri-magic-line mr-1"></i> 开始AI解读
              </button>
            </div>

            <!-- Interpreting Progress -->
            <div v-else-if="interpreting" class="card p-8 flex-1 flex flex-col items-center justify-center">
              <div class="w-full max-w-sm space-y-6">
                <div class="text-center mb-8">
                  <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-50 dark:bg-primary-900/30 text-primary-500 mb-4">
                    <i class="ri-loader-4-line text-3xl animate-spin"></i>
                  </div>
                  <h3 class="text-lg font-medium text-gray-900 dark:text-gray-100">AI正在解读报告</h3>
                  <p class="text-sm text-gray-500 mt-1">通常需要10-30秒，请耐心等待</p>
                </div>
                
                <div class="space-y-4">
                  <div class="flex items-center gap-3" :class="progressStage >= 1 ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'">
                    <i :class="progressStage > 1 ? 'ri-checkbox-circle-fill' : (progressStage === 1 ? 'ri-loader-4-line animate-spin' : 'ri-checkbox-blank-circle-line')" class="text-xl"></i>
                    <span class="font-medium">正在提取报告文本...</span>
                  </div>
                  <div class="flex items-center gap-3" :class="progressStage >= 2 ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'">
                    <i :class="progressStage > 2 ? 'ri-checkbox-circle-fill' : (progressStage === 2 ? 'ri-loader-4-line animate-spin' : 'ri-checkbox-blank-circle-line')" class="text-xl"></i>
                    <span class="font-medium">正在识别检查项目...</span>
                  </div>
                  <div class="flex items-center gap-3" :class="progressStage >= 3 ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'">
                    <i :class="progressStage > 3 ? 'ri-checkbox-circle-fill' : (progressStage === 3 ? 'ri-loader-4-line animate-spin' : 'ri-checkbox-blank-circle-line')" class="text-xl"></i>
                    <span class="font-medium">正在AI解读中...</span>
                  </div>
                  <div class="flex items-center gap-3" :class="progressStage >= 4 ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'">
                    <i :class="progressStage > 4 ? 'ri-checkbox-circle-fill' : (progressStage === 4 ? 'ri-loader-4-line animate-spin' : 'ri-checkbox-blank-circle-line')" class="text-xl"></i>
                    <span class="font-medium">正在生成报告...</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Interpretation Result -->
            <ReportInterpretation v-else-if="interpretation" :interpretation="interpretation" />
            
          </div>
        </div>
      </template>

      <!-- Report not found -->
      <div v-else class="text-center py-16 text-gray-400 dark:text-gray-500">
        <div class="text-4xl mb-3"><i class="ri-file-damage-line"></i></div>
        <p>报告不存在或已被删除</p>
        <button @click="router.push('/tracker')" class="mt-4 text-sm text-primary-500 hover:underline">返回健康手帐</button>
      </div>
    </main>
  </div>
</template>