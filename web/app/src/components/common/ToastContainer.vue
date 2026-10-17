<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, remove } = useToast()

const typeStyles: Record<string, string> = {
  success: 'bg-emerald-50 border-emerald-200/90 text-emerald-800 dark:bg-emerald-950/90 dark:border-emerald-800/80 dark:text-emerald-200',
  warning: 'bg-amber-50 border-amber-200/90 text-amber-800 dark:bg-amber-950/90 dark:border-amber-800/80 dark:text-amber-200',
  error: 'bg-red-50 border-red-200/90 text-red-800 dark:bg-red-950/90 dark:border-red-800/80 dark:text-red-200',
  info: 'bg-slate-900 border-slate-800 text-slate-100 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100',
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
          class="pointer-events-auto flex items-center justify-between px-3.5 py-2.5 rounded-xl shadow-lg border text-[13px] font-medium backdrop-blur-md"
          :class="typeStyles[toast.type]"
        >
          <span>{{ toast.message }}</span>
          <button type="button" class="ml-3 min-h-0 opacity-60 hover:opacity-100" aria-label="关闭提示" @click="remove(toast.id)">
            <i class="ri-close-line text-sm" aria-hidden="true"></i>
          </button>
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