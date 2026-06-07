<script setup lang="ts">
/**
 * Unified loading indicator component.
 */
withDefaults(defineProps<{
  message?: string
  /** 'spinner' | 'pulse' | 'skeleton' */
  variant?: 'spinner' | 'pulse' | 'skeleton'
  /** Number of skeleton placeholders (only for variant='skeleton') */
  skeletonCount?: number
}>(), {
  message: '加载中...',
  variant: 'spinner',
  skeletonCount: 6,
})
</script>

<template>
  <!-- Spinner variant -->
  <div v-if="variant === 'spinner'" class="flex-1 flex items-center justify-center py-12">
    <div class="text-center">
      <div class="w-8 h-8 border-2 border-primary-200 border-t-primary-500 rounded-full animate-spin mx-auto"></div>
      <p v-if="message" class="text-sm text-gray-500  mt-3">{{ message }}</p>
    </div>
  </div>

  <!-- Pulse variant (icon pulse animation) -->
  <div v-else-if="variant === 'pulse'" class="text-center py-8 text-gray-400 ">
    <div class="text-4xl mb-3 animate-pulse"><i class="ri-bar-chart-2-line"></i></div>
    <p v-if="message">{{ message }}</p>
  </div>

  <!-- Skeleton cards -->
  <div v-else-if="variant === 'skeleton'" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
    <div
      v-for="i in skeletonCount"
      :key="i"
      class="rounded-xl overflow-hidden bg-white animate-pulse"
    >
      <div class="aspect-[3/4] bg-gray-200"></div>
      <div class="px-2.5 pt-2 pb-2 space-y-2">
        <div class="h-3 bg-gray-200 rounded w-4/5"></div>
        <div class="h-3 bg-gray-200 rounded w-3/5"></div>
      </div>
    </div>
  </div>
</template>
