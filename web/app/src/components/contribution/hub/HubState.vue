<script setup lang="ts">
withDefaults(defineProps<{ loading: boolean; error: boolean; empty: boolean; emptyText?: string; skeleton?: number }>(), {
  emptyText: '内容正在医学审核，通过后上线', skeleton: 3,
})
defineEmits<{ retry: [] }>()
</script>

<template>
  <div v-if="loading" role="status" class="space-y-3">
    <div v-for="n in skeleton" :key="n" class="h-28 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800"></div>
    <span class="sr-only">正在加载</span>
  </div>
  <div v-else-if="error" role="alert" class="card py-8 text-center dark:bg-gray-800">
    <i class="ri-wifi-off-line text-2xl text-gray-400" aria-hidden="true"></i>
    <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">加载失败，请检查网络后重试</p>
    <button type="button" class="btn-ghost mt-2 min-h-11 px-4" @click="$emit('retry')">重新加载</button>
  </div>
  <div v-else-if="empty" role="status" class="card py-10 text-center dark:bg-gray-800">
    <i class="ri-stethoscope-line text-2xl text-primary-600 dark:text-primary-400" aria-hidden="true"></i>
    <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ emptyText }}</p>
  </div>
  <slot v-else />
</template>
