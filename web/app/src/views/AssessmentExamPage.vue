<script setup lang="ts">
import { computed } from 'vue'
import siteModules from '../../../shared/site-modules.json'
import AssessmentSectionNav from '@/components/tracker/AssessmentSectionNav.vue'
import ReportUploader from '@/components/tracker/ReportUploader.vue'
const label = computed(() => siteModules.modules.find(item => item.path.includes('tab=exam'))?.label || '体检解读')
</script>
<template>
  <div class="flex-1 bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100">
    <!-- 子工具条与「白斑记录」页同宽同样式：手机居中，平板/桌面左对齐 -->
    <header class="sticky top-14 z-30 border-b border-gray-200/80 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div class="page flex min-h-[52px] items-center justify-center md:justify-start"><AssessmentSectionNav active="exam" /></div>
    </header>
    <section class="page py-5 pb-8 md:py-6 md:pb-10">
      <h1 class="sr-only">{{ label }}</h1>
      <ReportUploader />
    </section>
  </div>
</template>
