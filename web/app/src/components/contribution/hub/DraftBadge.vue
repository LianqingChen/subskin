<script setup lang="ts">
defineProps<{ status?: string | null }>()
</script>

<template>
  <span v-if="status && status !== 'published'" class="inline-flex items-center gap-1 whitespace-nowrap rounded-md bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
    <i class="ri-eye-line" aria-hidden="true"></i>草稿预览 · 未发布
  </span>
</template>
