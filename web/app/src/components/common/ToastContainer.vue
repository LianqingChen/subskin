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
    <!-- 顶栏下方：手机端居中，桌面端靠右，不遮挡顶栏按钮 -->
    <div class="pointer-events-none fixed inset-x-4 top-[calc(3.5rem+env(safe-area-inset-top,0px)+0.5rem)] z-[200] flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:max-w-xs sm:items-end">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto flex items-center justify-between px-3.5 py-2.5 rounded-xl shadow-lg border text-[13px]"
          :class="typeStyles[toast.type]"
        >
          <span>{{ toast.message }}</span>
          <button type="button" class="ml-3 min-h-0 opacity-60 hover:opacity-100" aria-label="关闭提示" @click="remove(toast.id)">×</button>
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