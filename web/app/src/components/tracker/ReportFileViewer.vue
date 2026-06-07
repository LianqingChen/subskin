<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import type { MedicalReportFile } from '@/api/medical-report'

const props = defineProps<{
  files: MedicalReportFile[]
}>()

const authStore = useAuthStore()
const toast = useToast()

const activeFileIndex = ref(0)
const activeFile = computed(() => props.files[activeFileIndex.value])

const isPdf = computed(() => activeFile.value?.file_type === 'application/pdf' || activeFile.value?.file_name.toLowerCase().endsWith('.pdf'))
const isImage = computed(() => activeFile.value?.file_type?.startsWith('image/') || /\.(jpg|jpeg|png|gif|webp)$/i.test(activeFile.value?.file_name || ''))

const currentPage = ref(1)
const totalPages = ref(1)
const currentImageUrl = ref<string>('')
const loading = ref(false)

async function fetchImage(url: string) {
  loading.value = true
  try {
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${authStore.token}` }
    })
    if (!response.ok) {
      if (response.status === 404) {
        return false
      }
      throw new Error('Failed to load image')
    }
    const blob = await response.blob()
    if (currentImageUrl.value) {
      URL.revokeObjectURL(currentImageUrl.value)
    }
    currentImageUrl.value = URL.createObjectURL(blob)
    return true
  } catch (e) {
    toast.error('无法加载文件')
    return false
  } finally {
    loading.value = false
  }
}

async function loadCurrentFile() {
  if (!activeFile.value) return
  
  if (isPdf.value) {
    currentPage.value = 1
    await loadPdfPage(1)
  } else if (isImage.value) {
    await fetchImage(`/api/files/serve/${activeFile.value.id}`)
  }
}

async function loadPdfPage(page: number) {
  const success = await fetchImage(`/api/files/serve/${activeFile.value.id}?page=${page}`)
  if (success) {
    currentPage.value = page
    if (page > totalPages.value) {
      totalPages.value = page
    }
  } else if (page > 1) {
    toast.show('已经是最后一页了')
    totalPages.value = currentPage.value
  }
}

async function nextPage() {
  await loadPdfPage(currentPage.value + 1)
}

async function prevPage() {
  if (currentPage.value > 1) {
    await loadPdfPage(currentPage.value - 1)
  }
}

watch(() => activeFileIndex.value, loadCurrentFile)

onMounted(() => {
  if (props.files.length > 0) {
    loadCurrentFile()
  }
})
</script>

<template>
  <div class="card overflow-hidden flex flex-col bg-gray-100  h-full">
    <div v-if="files.length > 1" class="flex overflow-x-auto border-b border-gray-200 dark:border-gray-700 bg-white ">
      <button v-for="(file, idx) in files" :key="file.id"
        @click="activeFileIndex = idx"
        class="px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors"
        :class="activeFileIndex === idx ? 'border-primary-500 text-primary-600 dark:text-primary-400' : 'border-transparent text-gray-500 hover:text-gray-700  dark:hover:text-gray-200'">
        <i :class="file.file_type?.startsWith('image/') ? 'ri-image-line' : 'ri-file-text-line'" class="mr-1"></i>
        {{ file.file_name }}
      </button>
    </div>

    <div class="relative flex-1 min-h-[400px] flex items-center justify-center p-4">
      <div v-if="loading && !currentImageUrl" class="absolute inset-0 flex items-center justify-center bg-white/50  z-10">
        <i class="ri-loader-4-line animate-spin text-3xl text-primary-500"></i>
      </div>
      
      <img v-if="currentImageUrl" :src="currentImageUrl" class="max-w-full max-h-[70vh] object-contain shadow-sm rounded bg-white " />
      
      <div v-else-if="!loading" class="text-gray-400 flex flex-col items-center">
        <i class="ri-file-damage-line text-4xl mb-2"></i>
        <p>无法预览此文件</p>
      </div>
    </div>

    <div v-if="isPdf" class="flex items-center justify-center gap-4 p-3 bg-white  border-t border-gray-200 dark:border-gray-700">
      <button @click="prevPage" :disabled="currentPage <= 1 || loading" class="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors">
        <i class="ri-arrow-left-s-line text-xl"></i>
      </button>
      <span class="text-sm font-medium text-gray-600 ">第 {{ currentPage }} 页</span>
      <button @click="nextPage" :disabled="loading" class="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors">
        <i class="ri-arrow-right-s-line text-xl"></i>
      </button>
    </div>
  </div>
</template>