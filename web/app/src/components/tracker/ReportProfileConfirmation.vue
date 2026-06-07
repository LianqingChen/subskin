<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { medicalReportApi } from '@/api/medical-report'
import type { ExtractedPatientInfo } from '@/api/medical-report'
import apiClient from '@/api/client'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  reportId: number
  extractedInfo: ExtractedPatientInfo
}>()

const emit = defineEmits<{
  (e: 'linked', profileId: number): void
  (e: 'skipped'): void
}>()

const toast = useToast()
const profiles = ref<any[]>([])
const loading = ref(true)
const selectedProfileId = ref<number | null>(null)
const isCreating = ref(false)
const isLinking = ref(false)

async function loadProfiles() {
  try {
    const { data } = await apiClient.get('/patient-profiles/')
    profiles.value = data.items || data || []
    if (profiles.value.length > 0) {
      selectedProfileId.value = profiles.value[0].id
    }
  } catch (e) {
    console.error('Failed to load profiles', e)
  } finally {
    loading.value = false
  }
}

async function linkProfile() {
  if (!selectedProfileId.value) return
  isLinking.value = true
  try {
    await medicalReportApi.linkProfile(props.reportId, selectedProfileId.value)
    toast.success('已关联档案')
    emit('linked', selectedProfileId.value)
  } catch (e) {
    toast.error('关联失败')
  } finally {
    isLinking.value = false
  }
}

async function createProfile() {
  isCreating.value = true
  try {
    const { data } = await apiClient.post('/patient-profiles/', {
      name: props.extractedInfo.name || '未知',
      gender: props.extractedInfo.gender || 'unknown',
      birth_date: props.extractedInfo.age ? new Date(new Date().getFullYear() - props.extractedInfo.age, 0, 1).toISOString().split('T')[0] : null,
      relationship: 'self'
    })
    await medicalReportApi.linkProfile(props.reportId, data.id)
    toast.success('已创建并关联新档案')
    emit('linked', data.id)
  } catch (e) {
    toast.error('创建失败')
  } finally {
    isCreating.value = false
  }
}

onMounted(loadProfiles)
</script>

<template>
  <div class="card p-4 border-l-4 border-primary-500 bg-primary-50/30 dark:bg-primary-900/10">
    <div class="flex items-start gap-3">
      <div class="p-2 bg-primary-100 dark:bg-primary-900/50 rounded-full text-primary-600 dark:text-primary-400 shrink-0">
        <i class="ri-user-smile-line text-xl"></i>
      </div>
      <div class="flex-1 min-w-0">
        <h3 class="text-base font-semibold text-gray-900  mb-1">识别到患者信息</h3>
        <p class="text-sm text-gray-600  mb-3">报告中包含以下患者信息，是否关联到健康档案？</p>
        
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <div class="bg-white  p-2 rounded border border-gray-200 dark:border-gray-700">
            <div class="text-xs text-gray-400 mb-1">姓名 <span class="text-[10px] bg-gray-100  px-1 rounded ml-1">来自报告</span></div>
            <div class="font-medium text-gray-900 ">{{ extractedInfo.name || '-' }}</div>
          </div>
          <div class="bg-white  p-2 rounded border border-gray-200 dark:border-gray-700">
            <div class="text-xs text-gray-400 mb-1">性别 <span class="text-[10px] bg-gray-100  px-1 rounded ml-1">来自报告</span></div>
            <div class="font-medium text-gray-900 ">{{ extractedInfo.gender || '-' }}</div>
          </div>
          <div class="bg-white  p-2 rounded border border-gray-200 dark:border-gray-700">
            <div class="text-xs text-gray-400 mb-1">年龄 <span class="text-[10px] bg-gray-100  px-1 rounded ml-1">来自报告</span></div>
            <div class="font-medium text-gray-900 ">{{ extractedInfo.age ? `${extractedInfo.age}岁` : '-' }}</div>
          </div>
          <div class="bg-white  p-2 rounded border border-gray-200 dark:border-gray-700">
            <div class="text-xs text-gray-400 mb-1">体检日期 <span class="text-[10px] bg-gray-100  px-1 rounded ml-1">来自报告</span></div>
            <div class="font-medium text-gray-900 ">{{ extractedInfo.exam_date || '-' }}</div>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <template v-if="profiles.length > 0">
            <select v-model="selectedProfileId" class="text-sm border-gray-300 dark:border-gray-600 rounded-md bg-white  py-1.5 pl-3 pr-8">
              <option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
            <button @click="linkProfile" :disabled="isLinking" class="btn-primary py-1.5 px-3 text-sm">
              <i class="ri-user-line mr-1"></i> 关联已有档案
            </button>
          </template>
          <button @click="createProfile" :disabled="isCreating" class="btn-ghost py-1.5 px-3 text-sm border border-gray-200 dark:border-gray-700 bg-white ">
            <i class="ri-user-add-line mr-1"></i> 创建新档案
          </button>
          <button @click="$emit('skipped')" class="btn-ghost py-1.5 px-3 text-sm text-gray-500">
            <i class="ri-close-line mr-1"></i> 跳过
          </button>
        </div>
      </div>
    </div>
  </div>
</template>