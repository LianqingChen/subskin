<script setup lang="ts">
import { onMounted, nextTick } from 'vue'
import DigitalHuman from '@/components/tracker/DigitalHuman.vue'
import ReportUploader from '@/components/tracker/ReportUploader.vue'

// Auto-scroll card to panda chin level on mount
onMounted(() => {
  nextTick(() => {
    const card = document.querySelector('[data-view-card]')
    if (card) {
      const cardTop = card.getBoundingClientRect().top + window.scrollY
      window.scrollTo({ top: cardTop - window.innerHeight * 0.30, behavior: 'smooth' })
    }
  })
})
</script>

<template>
  <div class="bg-[#F5F7FA] dark:bg-gray-900">
    <!-- Panda — fixed, never moves -->
    <div class="fixed top-[6vh] left-0 right-0 z-0 bg-[#F5F7FA] dark:bg-gray-900" style="height: 55vh; min-height: 360px">
      <div class="w-full max-w-md mx-auto h-full">
        <DigitalHuman mode="wave" :show-parts="false" />
      </div>
    </div>

    <!-- Report section — starts below panda, scrolls up over it -->
    <div data-view-card class="relative z-10 bg-white dark:bg-gray-800 rounded-t-3xl shadow-[0_-8px_30px_rgba(0,0,0,0.08)]"
      style="margin-top: 55vh;">
      <div class="max-w-6xl mx-auto px-4 pt-3 pb-24 md:pb-8">
        <div class="flex items-center justify-between mb-2">
          <div>
            <h1 class="text-xl font-bold text-gray-800 dark:text-gray-100">体检解读</h1>
            <p class="text-sm text-gray-500 dark:text-gray-400">上传体检报告，AI 自动解读</p>
          </div>
        </div>
        <ReportUploader />
      </div>
    </div>
  </div>
</template>
