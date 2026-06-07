<script setup lang="ts">
import type { Source } from '@/types'

defineProps<{
  sources: Source[]
}>()
</script>

<template>
  <aside class="hidden lg:block w-72 border-l border-gray-200 bg-gray-50 overflow-y-auto">
    <div class="p-4 space-y-4">
      <div>
        <h3 class="text-sm font-semibold text-gray-700 mb-2"><i class="ri-book-3-line mr-1"></i>相关知识</h3>
        <div class="space-y-2">
          <div
            v-for="source in sources"
            :key="source.title"
            class="p-3 bg-white rounded-lg border border-gray-100 text-sm"
          >
            <div class="font-medium text-gray-800 mb-1">{{ source.title }}</div>
            <p v-if="source.snippet" class="text-gray-500 text-xs line-clamp-3">{{ source.snippet }}</p>
            <a
              v-if="source.url"
              :href="source.url"
              target="_blank"
              class="text-primary-500 text-xs hover:underline mt-1 inline-block"
            >
              查看原文 →
            </a>
          </div>
        </div>
        <div v-if="!sources.length" class="text-xs text-gray-400 text-center py-6">
          提问后将显示相关知识
        </div>
      </div>

      <div>
        <h3 class="text-sm font-semibold text-gray-700 mb-2"><i class="ri-chat-3-line mr-1"></i>发现相关</h3>
        <div class="space-y-2">
          <div class="p-3 bg-white rounded-lg border border-gray-100 text-sm">
            <p class="text-gray-500 text-xs">查看小白的真实经验分享</p>
            <router-link to="/community" class="text-primary-500 text-xs hover:underline mt-1 inline-block">
              前往发现 →
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
