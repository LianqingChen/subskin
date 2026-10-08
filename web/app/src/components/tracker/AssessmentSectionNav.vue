<script setup lang="ts">
import siteModules from '../../../../shared/site-modules.json'
defineProps<{ active: 'skin' | 'exam'; locked?: boolean }>()
const emit = defineEmits<{ skin: [] }>()
const exam = siteModules.modules.find(item => item.path.includes('tab=exam'))
const sections = [
  { key: 'skin', label: '白斑记录', icon: 'ri-focus-3-line', to: { name: 'assessment' } },
  { key: 'exam', label: exam?.label || '体检解读', icon: exam?.icon || 'ri-microscope-line', to: { name: 'assessment-exam' } },
]
// 视觉高度收紧到 34px（原 44px），同时用 after 伪元素把实际可点区域向上下各扩 6px，
// 保证触摸目标仍有 46px ≥ 44px（AGENTS.md 触摸规范），顶部不再占用过宽空间。
const ITEM_CLASS = 'relative flex min-h-[34px] items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-3 text-[13px] after:absolute after:inset-x-0 after:-inset-y-1.5 after:content-[\'\'] sm:px-4'
</script>
<template>
  <nav aria-label="记录功能" class="inline-flex max-w-full gap-0.5 rounded-xl bg-gray-100 p-0.5 dark:bg-gray-800">
    <template v-for="section in sections" :key="section.key">
      <span v-if="locked" :class="ITEM_CLASS" aria-disabled="true" class="font-medium opacity-50">
        <i :class="section.icon" aria-hidden="true"></i>{{ section.label }}
      </span>
      <router-link v-else :to="section.to" @click="section.key === 'skin' && active === 'skin' && emit('skin')" :aria-current="active === section.key ? 'page' : undefined"
        :class="[ITEM_CLASS, 'font-medium transition-colors', active === section.key ? 'bg-white text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-200' : 'text-gray-500 hover:text-primary-700 dark:text-gray-400 dark:hover:text-primary-200']">
        <i :class="section.icon" aria-hidden="true"></i>{{ section.label }}
      </router-link>
    </template>
  </nav>
</template>
