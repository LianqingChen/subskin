<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { contentApi } from '@/api/content'
import type { TimelineItem } from '@/api/content'

const loading = ref(true)
const timeline = ref<TimelineItem[]>([])

function formatMonth(month: string): string {
  const [year, m] = month.split('-')
  return `${year}年${parseInt(m)}月`
}

function getSourceIcon(source: string): string {
  const s = source.toLowerCase()
  if (s.includes('pubmed')) return 'ri-file-text-line'
  if (s.includes('clinical')) return 'ri-capsule-line'
  if (s.includes('cma') || s.includes('中华')) return 'ri-hospital-line'
  if (s.includes('news')) return 'ri-newspaper-line'
  return 'ri-article-line'
}

onMounted(async () => {
  try {
    const res = await contentApi.getTimeline(12)
    timeline.value = res.timeline
  } catch {
    timeline.value = []
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="research-timeline">
    <div v-if="loading" class="text-center py-8 text-gray-400">
      <i class="ri-loader-4-line animate-spin text-2xl"></i>
      <p class="text-sm mt-2">加载中...</p>
    </div>

    <div v-else-if="timeline.length === 0" class="text-center py-8 text-gray-400">
      <i class="ri-time-line text-3xl"></i>
      <p class="text-sm mt-2">暂无研究进展数据</p>
    </div>

    <div v-else class="relative pl-6">
      <!-- Timeline line -->
      <div class="absolute left-2 top-0 bottom-0 w-0.5 bg-gradient-to-b from-primary-300 to-primary-100"></div>

      <!-- Timeline items -->
      <div v-for="item in timeline" :key="item.month" class="relative mb-6 last:mb-0">
        <!-- Dot -->
        <div class="absolute -left-4 top-1 w-3 h-3 rounded-full bg-primary-500 border-2 border-white shadow"></div>

        <!-- Content -->
        <div class="ml-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-sm font-semibold text-gray-900">{{ formatMonth(item.month) }}</span>
            <span class="px-2 py-0.5 text-xs bg-primary-50 text-primary-600 rounded-full">
              {{ item.count }} 篇
            </span>
          </div>

          <!-- Highlights -->
          <div class="space-y-2">
            <div
              v-for="highlight in item.highlights"
              :key="highlight.id"
              class="flex items-start gap-2 p-2 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
            >
              <i :class="getSourceIcon(highlight.source)" class="text-primary-500 mt-0.5"></i>
              <div class="flex-1 min-w-0">
                <p class="text-xs text-gray-700 line-clamp-2">{{ highlight.title }}</p>
                <span class="text-[10px] text-gray-400">{{ highlight.source }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
