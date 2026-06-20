<script setup lang="ts">
/**
 * TrackerPage — Legacy redirect view.
 *
 * The /tracker route now redirects to /assessment in the router.
 * This component exists as a safety net in case any deep links
 * still reference TrackerPage directly.
 *
 * ALL assessment functionality has been moved to:
 * - AssessmentPage.vue (main page)
 * - AssessmentSection.vue (assessment workflow)
 * - components/tracker/* (sub-components)
 */
import { useRouter } from 'vue-router'

const router = useRouter()
router.replace({ name: 'assessment' })
</script>

<template>
  <div class="flex items-center justify-center min-h-[60vh]">
    <div class="text-center text-gray-400">
      <div class="text-4xl mb-3 animate-pulse"><i class="ri-bar-chart-2-line"></i></div>
      <p>正在跳转到测评页面...</p>
    </div>
  </div>
</template>