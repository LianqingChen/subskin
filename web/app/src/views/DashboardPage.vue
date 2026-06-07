<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import AnalyticsDashboard from '@/components/analytics/AnalyticsDashboard.vue'
import ModerationPanel from '@/components/moderation/ModerationPanel.vue'
import ImageLabelingPanel from '@/components/image-label/ImageLabelingPanel.vue'

const authStore = useAuthStore()
const router = useRouter()
const activeTab = ref<'analytics' | 'moderation' | 'image-label'>('analytics')

if (!authStore.user?.is_admin) {
  router.replace('/')
}

const tabs = [
  { key: 'analytics' as const, label: '增长' },
  { key: 'moderation' as const, label: '风控' },
  { key: 'image-label' as const, label: '图片打标' },
]
</script>

<template>
  <div v-if="authStore.user?.is_admin" class="min-h-[calc(100dvh-3.5rem)]">
    <div class="max-w-6xl mx-auto px-4 pt-4 md:pt-6">
      <div class="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit mb-4">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          class="px-5 py-2 rounded-lg text-sm font-medium transition-all"
          :class="activeTab === tab.key
            ? 'bg-white text-gray-900 dark:text-white shadow-sm'
            : 'text-gray-500  hover:text-gray-700 dark:hover:text-gray-300'"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>
    <AnalyticsDashboard v-if="activeTab === 'analytics'" />
    <ModerationPanel v-else-if="activeTab === 'moderation'" />
    <ImageLabelingPanel v-else-if="activeTab === 'image-label'" />
  </div>
</template>