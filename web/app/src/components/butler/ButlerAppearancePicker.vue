<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useButlerStore, BUTLER_DEFAULT_PREFERENCE } from '@/stores/butler'
import { useToast } from '@/composables/useToast'
import ButlerCreature3D from '@/components/butler/ButlerCreature3D.vue'
import type { ButlerMascot, ButlerPosition, ButlerSize, ButlerStyle } from '@/types'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const butlerStore = useButlerStore()
const toast = useToast()

// 形象仅保留金斑蝶（默认）与梅花鹿，均由 ButlerCreature3D 程序化 3D 渲染
const MASCOT_OPTIONS: { value: ButlerMascot; label: string; creature: 'butterfly' | 'deer' }[] = [
  { value: 'real', label: '金斑蝶', creature: 'butterfly' },
  { value: 'deer', label: '梅花鹿', creature: 'deer' },
]
const STYLE_OPTIONS: { value: ButlerStyle; label: string }[] = [
  { value: 'circle', label: '圆形' },
  { value: 'rounded', label: '圆角' },
]
const SIZE_OPTIONS: { value: ButlerSize; label: string }[] = [
  { value: 'small', label: '小' },
  { value: 'medium', label: '中' },
  { value: 'large', label: '大' },
]
const POSITION_OPTIONS: { value: ButlerPosition; label: string }[] = [
  { value: 'right', label: '右下角' },
  { value: 'left', label: '左下角' },
]

const form = reactive({ ...BUTLER_DEFAULT_PREFERENCE })

watch(
  () => props.visible,
  (visible) => {
    if (visible) Object.assign(form, butlerStore.preference)
  },
)

const previewCreature = computed<'butterfly' | 'deer'>(() =>
  form.mascot === 'deer' ? 'deer' : 'butterfly',
)
const previewSize = computed(() => ({ small: 44, medium: 56, large: 64 })[form.size])

async function onSave() {
  if (form.greeting.length > 100) {
    toast.warning('问候语最多 100 字')
    return
  }
  await butlerStore.savePreference({ ...form })
  toast.success('小白管家外观已更新')
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="butler-pref-fade">
      <div v-if="visible" class="fixed inset-0 z-[90] bg-black/40 flex items-end md:items-center justify-center p-0 md:p-6 safe-bottom" role="dialog" aria-modal="true" aria-label="小白管家外观设置" @click.self="emit('close')">
        <div class="bg-white dark:bg-gray-900 w-full md:max-w-md rounded-t-2xl md:rounded-2xl shadow-2xl max-h-[85dvh] overflow-y-auto">
          <header class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800 sticky top-0 bg-white dark:bg-gray-900">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100"><i class="ri-robot-3-line"></i> 小白管家</h3>
            <button type="button" class="w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800" aria-label="关闭" @click="emit('close')">
              <i class="ri-close-line"></i>
            </button>
          </header>

          <div class="p-4 space-y-5">
            <!-- 实时预览 -->
            <div class="flex justify-center py-2">
              <div class="flex items-center justify-center overflow-visible transition-all"
                :class="form.style === 'circle' ? 'rounded-full' : 'rounded-2xl'"
                :style="{ width: previewSize + 'px', height: previewSize + 'px', boxShadow: '0 4px 14px rgba(0,0,0,0.15)' }">
                <ButlerCreature3D :creature="previewCreature" :size="previewSize" mood="greeting" />
              </div>
            </div>

            <fieldset>
              <legend class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">管家形象</legend>
              <div class="grid grid-cols-2 gap-2">
                <button v-for="opt in MASCOT_OPTIONS" :key="opt.value" type="button"
                  class="flex flex-col items-center gap-1 p-2 rounded-xl border transition-colors"
                  :class="form.mascot === opt.value ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-200 dark:border-gray-700 hover:border-primary-300'"
                  :aria-pressed="form.mascot === opt.value" @click="form.mascot = opt.value">
                  <ButlerCreature3D :creature="opt.creature" :size="40" />
                  <span class="text-[11px] text-gray-600 dark:text-gray-300">{{ opt.label }}</span>
                </button>
              </div>
            </fieldset>

            <div class="grid grid-cols-3 gap-4">
              <fieldset>
                <legend class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">风格</legend>
                <div class="space-y-1">
                  <button v-for="opt in STYLE_OPTIONS" :key="opt.value" type="button"
                    class="w-full px-2 py-1.5 min-h-[36px] rounded-lg text-xs transition-colors"
                    :class="form.style === opt.value ? 'bg-primary-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'"
                    :aria-pressed="form.style === opt.value" @click="form.style = opt.value">{{ opt.label }}</button>
                </div>
              </fieldset>
              <fieldset>
                <legend class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">大小</legend>
                <div class="space-y-1">
                  <button v-for="opt in SIZE_OPTIONS" :key="opt.value" type="button"
                    class="w-full px-2 py-1.5 min-h-[36px] rounded-lg text-xs transition-colors"
                    :class="form.size === opt.value ? 'bg-primary-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'"
                    :aria-pressed="form.size === opt.value" @click="form.size = opt.value">{{ opt.label }}</button>
                </div>
              </fieldset>
              <fieldset>
                <legend class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">位置</legend>
                <div class="space-y-1">
                  <button v-for="opt in POSITION_OPTIONS" :key="opt.value" type="button"
                    class="w-full px-2 py-1.5 min-h-[36px] rounded-lg text-xs transition-colors"
                    :class="form.position === opt.value ? 'bg-primary-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'"
                    :aria-pressed="form.position === opt.value" @click="form.position = opt.value">{{ opt.label }}</button>
                </div>
              </fieldset>
            </div>
            <p class="text-[10px] leading-relaxed text-gray-400">
              长按管家可直接拖动到页面任意位置；拖到屏幕左右边缘隐藏，拖回底部角落恢复默认位置。
            </p>

            <fieldset>
              <legend class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">开场问候</legend>
              <label for="butler-greeting" class="sr-only">开场问候</label>
              <input id="butler-greeting" v-model="form.greeting" type="text" maxlength="100"
                class="w-full min-w-0 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm text-gray-800 dark:text-gray-200 outline-none focus:ring-1 focus:ring-primary-400" />
            </fieldset>

            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-gray-800 dark:text-gray-200">在页面上显示小白管家</p>
                <p class="text-[11px] text-gray-400">关闭后漂浮按钮不再出现</p>
              </div>
              <button type="button" role="switch" :aria-checked="form.enabled"
                class="relative w-11 h-6 rounded-full transition-colors"
                :class="form.enabled ? 'bg-primary-500' : 'bg-gray-300 dark:bg-gray-600'"
                @click="form.enabled = !form.enabled">
                <span class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all" :class="form.enabled ? 'left-[22px]' : 'left-0.5'"></span>
              </button>
            </div>
          </div>

          <footer class="flex gap-2 px-4 py-3 border-t border-gray-100 dark:border-gray-800 sticky bottom-0 bg-white dark:bg-gray-900">
            <button type="button" class="flex-1 py-2.5 min-h-[44px] rounded-xl text-sm border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors" @click="emit('close')">取消</button>
            <button type="button" class="flex-1 py-2.5 min-h-[44px] rounded-xl text-sm bg-primary-500 text-white hover:bg-primary-600 transition-colors" @click="onSave">保存</button>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.butler-pref-fade-enter-active,
.butler-pref-fade-leave-active {
  transition: opacity 0.2s ease;
}
.butler-pref-fade-enter-from,
.butler-pref-fade-leave-to {
  opacity: 0;
}
</style>
