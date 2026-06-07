<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, remove } = useToast()

const typeStyles: Record<string, string> = {
  success: 'bg-green-50 border-green-200 text-green-700',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  error: 'bg-red-50 border-red-200 text-red-700',
  info: 'bg-blue-50 border-blue-200 text-blue-700',
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-[200] flex flex-col gap-2 max-w-sm">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="flex items-center justify-between px-4 py-3 rounded-lg shadow-lg border text-sm"
          :class="typeStyles[toast.type]"
        >
          <span>{{ toast.message }}</span>
          <button class="ml-3 opacity-60 hover:opacity-100" @click="remove(toast.id)">×</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.3s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>