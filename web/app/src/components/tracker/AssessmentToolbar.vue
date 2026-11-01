<script setup lang="ts">
import AssessmentSectionNav from './AssessmentSectionNav.vue'
defineProps<{ active: 'skin' | 'exam'; locked?: boolean; working?: boolean; narrow?: boolean; canBack?: boolean; showHistory?: boolean }>()
const emit = defineEmits<{ back: []; history: [] }>()
</script>
<template>
  <header class="assessment-toolbar border-b border-gray-200/80 bg-white dark:border-gray-800 dark:bg-gray-900" :class="working ? 'shrink-0' : 'sticky top-14 z-30'">
    <div :class="[narrow ? 'page-narrow' : 'page', 'flex min-h-[56px] items-center gap-2']">
      <button v-if="canBack" type="button" class="flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-lg text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800" :disabled="locked" aria-label="返回白斑记录" @click="emit('back')"><i class="ri-arrow-left-line text-xl" aria-hidden="true"></i></button>
      <div class="min-w-0 flex-1"><AssessmentSectionNav :active="active" :locked="locked" @skin="emit('back')" /></div>
      <button v-if="showHistory" type="button" class="flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-lg text-primary-700 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-gray-800" :disabled="locked" aria-label="我的记录" @click="emit('history')"><i class="ri-history-line text-xl" aria-hidden="true"></i></button>
    </div>
  </header>
</template>
