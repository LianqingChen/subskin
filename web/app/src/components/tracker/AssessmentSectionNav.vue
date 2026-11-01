<script setup lang="ts">
import siteModules from '../../../../shared/site-modules.json'
defineProps<{ active: 'skin' | 'exam'; locked?: boolean }>()
const emit = defineEmits<{ skin: [] }>()
const diary = siteModules.modules.find(item => item.path === '/assessment')
const exam = siteModules.modules.find(item => item.path.includes('tab=exam'))
const sections = [
  { key: 'skin', label: '白斑记录', icon: diary?.icon || 'ri-booklet-line', to: { name: 'assessment' } },
  { key: 'exam', label: exam?.label || '体检解读', icon: exam?.icon || 'ri-microscope-line', to: { name: 'assessment-exam' } },
]
// Visible 44px targets avoid overlapping pseudo-element hit areas on small screens.
const ITEM_CLASS = 'flex min-h-[44px] min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-2 text-[13px] sm:px-3'
</script>
<template>
  <nav aria-label="记录功能" class="grid w-full grid-cols-2 gap-0.5 rounded-xl bg-gray-100 p-0.5 sm:inline-flex sm:w-auto dark:bg-gray-800">
    <template v-for="section in sections" :key="section.key">
      <span v-if="locked" :class="ITEM_CLASS" aria-disabled="true" class="font-medium opacity-50">
        <i :class="section.icon" class="hidden sm:inline" aria-hidden="true"></i>{{ section.label }}
      </span>
      <router-link v-else :to="section.to" @click="section.key === 'skin' && active === 'skin' && emit('skin')" :aria-current="active === section.key ? 'page' : undefined"
        :class="[ITEM_CLASS, 'font-medium transition-colors', active === section.key ? 'bg-white text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 hover:text-primary-700 dark:text-gray-400 dark:hover:text-primary-200']">
        <i :class="section.icon" class="hidden sm:inline" aria-hidden="true"></i>{{ section.label }}
      </router-link>
    </template>
  </nav>
</template>
