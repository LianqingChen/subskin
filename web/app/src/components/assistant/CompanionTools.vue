<script setup lang="ts">
/**
 * CompanionTools — 知心陪伴快捷工具（对话框上方）
 *
 * 两个工具：正念呼吸（全屏浮层）、用药提醒（底部抽屉面板，从个人中心迁移至此）。
 */
import { ref } from 'vue'
import BreathingExercise from '@/components/assistant/BreathingExercise.vue'
import MedicationReminderPanel from '@/components/assistant/MedicationReminderPanel.vue'

const showBreathing = ref(false)
const showMedication = ref(false)

function toggleBreathing() {
  showBreathing.value = !showBreathing.value
}
</script>

<template>
  <div class="flex items-center gap-2">
    <button
      type="button"
      class="inline-flex items-center gap-1.5 px-3 min-h-[40px] rounded-full text-xs font-medium transition-colors border"
      :class="showBreathing
        ? 'bg-primary-500 border-primary-500 text-white'
        : 'bg-white dark:bg-gray-800 border-primary-100 dark:border-primary-900 text-primary-600 dark:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900'"
      aria-label="正念呼吸"
      @click="toggleBreathing"
    >
      <i class="ri-leaf-line text-sm"></i>正念呼吸
    </button>

    <button
      type="button"
      class="inline-flex items-center gap-1.5 px-3 min-h-[40px] rounded-full text-xs font-medium transition-colors border"
      :class="showMedication
        ? 'bg-primary-500 border-primary-500 text-white'
        : 'bg-white dark:bg-gray-800 border-primary-100 dark:border-primary-900 text-primary-600 dark:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900'"
      aria-label="用药提醒"
      @click="showMedication = true"
    >
      <i class="ri-capsule-line text-sm"></i>用药提醒
    </button>

    <!-- Full-screen overlay for breathing -->
    <Teleport to="body">
      <Transition name="overlay-fade">
        <div v-if="showBreathing" class="fixed inset-0 z-[70] flex flex-col bg-white dark:bg-gray-950 safe-top safe-bottom">
          <div class="flex-1 overflow-y-auto px-3 py-6">
            <div class="max-w-md mx-auto">
              <BreathingExercise @close="showBreathing = false" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 用药提醒：底部抽屉 / 桌面居中弹层 -->
    <Teleport to="body">
      <Transition name="sheet-fade">
        <div
          v-if="showMedication"
          class="fixed inset-0 z-[90] flex items-end sm:items-center justify-center bg-black/50"
          @click.self="showMedication = false"
        >
          <div class="w-full sm:max-w-md bg-white dark:bg-gray-800 rounded-t-2xl sm:rounded-2xl p-5 pb-6 safe-bottom max-h-[88dvh] overflow-y-auto shadow-xl">
            <MedicationReminderPanel @close="showMedication = false" />
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
/* Overlay transitions */
.overlay-fade-enter-active,
.overlay-fade-leave-active,
.sheet-fade-enter-active,
.sheet-fade-leave-active {
  transition: all 0.25s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
.sheet-fade-enter-from,
.sheet-fade-leave-to {
  opacity: 0;
  transform: translateY(24px);
}
</style>
