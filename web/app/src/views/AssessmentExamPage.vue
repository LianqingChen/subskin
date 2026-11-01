<script setup lang="ts">
import { computed } from 'vue'
import siteModules from '../../../shared/site-modules.json'
import AssessmentToolbar from '@/components/tracker/AssessmentToolbar.vue'
import ReportUploader from '@/components/tracker/ReportUploader.vue'
const label = computed(() => siteModules.modules.find(item => item.path.includes('tab=exam'))?.label || '体检解读')
</script>
<template>
  <div class="min-w-0 flex-1 text-gray-900 dark:text-gray-100">
    <AssessmentToolbar active="exam" />
    <section class="page py-5 pb-[calc(4rem+env(safe-area-inset-bottom))] md:py-6 md:pb-10">
      <h1 class="sr-only">{{ label }}</h1>
      <ReportUploader />
    </section>
  </div>
</template>
