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
    <div class="text-4xl mb-3"><i :class="icon"></i></div>
    <p class="text-gray-400  text-sm">{{ title }}</p>
    <p v-if="description" class="text-xs text-gray-400  mt-1">{{ description }}</p>
    <button
      v-if="actionLabel"
      class="btn-primary text-sm mt-4"
      @click="emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
