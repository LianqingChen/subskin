<script setup lang="ts">
/**
 * Unified empty state component.
 * Provides consistent blank-slate UI across all pages.
 */
withDefaults(defineProps<{
  icon?: string
  title?: string
  description?: string
  actionLabel?: string
}>(), {
  icon: 'ri-file-edit-line',
  title: '暂无内容',
  description: '',
  actionLabel: '',
})

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="text-center py-8 md:py-12">
    <div class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-gray-100 text-2xl text-gray-400 dark:bg-gray-800 dark:text-gray-500"><i :class="icon" aria-hidden="true"></i></div>
    <p class="text-sm text-gray-500 dark:text-gray-400">{{ title }}</p>
    <p v-if="description" class="mt-1 text-xs text-gray-400 dark:text-gray-500">{{ description }}</p>
    <button
      v-if="actionLabel"
      class="btn-primary text-sm mt-4"
      @click="emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
