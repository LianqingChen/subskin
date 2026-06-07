<script setup lang="ts">
import { ref } from 'vue'
import { DEFAULT_THEME_HUE, useThemeStore } from '@/stores/theme'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const themeStore = useThemeStore()
const themeHue = ref(themeStore.customHue ?? DEFAULT_THEME_HUE)

function resetThemeColor() {
  themeHue.value = DEFAULT_THEME_HUE
  themeStore.setCustomHue(null)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center"
      @click.self="emit('update:modelValue', false)"
    >
      <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-semibold text-gray-900"><i class="ri-palette-line"></i> 网站主题</h2>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="emit('update:modelValue', false)">&times;</button>
        </div>
        <div class="p-6 space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-3">显示模式</label>
            <div class="flex gap-3">
              <button type="button"
                class="flex-1 py-2.5 rounded-lg border-2 text-sm font-medium transition-colors"
                :class="themeStore.mode === 'light' ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300' : 'border-gray-200 dark:border-gray-600 text-gray-600 '"
                @click="themeStore.setMode('light')"><i class="ri-sun-line"></i> 浅色</button>
              <button type="button"
                class="flex-1 py-2.5 rounded-lg border-2 text-sm font-medium transition-colors"
                :class="themeStore.mode === 'dark' ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300' : 'border-gray-200 dark:border-gray-600 text-gray-600 '"
                @click="themeStore.setMode('dark')">🌙 深色</button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-3">主题色</label>
            <div class="space-y-3">
              <input v-model.number="themeHue" type="range" min="0" max="360" step="1"
                class="theme-hue-slider"
                :style="{ accentColor: `hsl(${themeHue}, 70%, 62%)` }"
                @input="themeStore.setCustomHue(themeHue)" />
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg shadow-inner" :style="{ backgroundColor: `hsl(${themeHue}, 68%, 62%)` }"></div>
                <div>
                  <div class="text-sm font-medium text-gray-700">当前主题色</div>
                  <div class="text-xs text-gray-400">色相值: {{ themeHue }}°</div>
                </div>
              </div>
            </div>
          </div>
          <button type="button"
            class="w-full py-2.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm font-medium text-gray-600  hover:bg-gray-50 dark:hover:bg-gray-300 transition-colors"
            @click="resetThemeColor"><i class="ri-refresh-line"></i> 恢复默认主题</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
