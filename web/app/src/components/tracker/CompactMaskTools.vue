<script setup lang="ts">
import { ref } from 'vue'
import type { PhotoMaskTool } from '@/utils/photo-mask'
const props = defineProps<{ tool: PhotoMaskTool; brushSize: number; disabled?: boolean; refineAvailable?: boolean }>()
const emit = defineEmits<{ 'update:tool': [PhotoMaskTool]; 'update:brushSize': [number] }>()
const expanded = ref(false)
function closeOutside(event: FocusEvent) {
  if (event.relatedTarget instanceof Node && !(event.currentTarget as HTMLElement).contains(event.relatedTarget)) expanded.value = false
}
const tools = [{ key: 'skin', label: '正常皮肤', icon: 'ri-brush-line' }, { key: 'lesion', label: '白斑', icon: 'ri-brush-fill' }, { key: 'eraser', label: '排除', icon: 'ri-eraser-line' }, { key: 'refine', label: 'AI吸附', icon: 'ri-magic-line' }] as const
// 每个工具的实际作用：「正常皮肤」会把涂到的白斑改回正常皮肤；「排除」把区域移出皮肤范围（不计入占比）。
const hints: Record<PhotoMaskTool, string> = {
  lesion: '涂出白斑范围。双指可缩放、放大后画得更细',
  skin: '涂在误标为白斑的地方，即可擦掉白斑（改回正常皮肤）',
  eraser: '涂掉背景、衣物等不是皮肤的部分，它们不会计入占比',
  refine: '点一下白斑内部，AI 会自动贴合到边界',
}
</script>
<template>
  <div class="space-y-1">
  <div role="group" aria-label="调整范围工具" class="grid grid-cols-5 gap-1 rounded-2xl bg-white p-1 dark:bg-gray-800">
    <button v-for="item in tools" :key="item.key" type="button" :aria-pressed="tool === item.key" :disabled="disabled || (item.key === 'refine' && !refineAvailable)" class="flex min-h-[52px] min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-xs disabled:opacity-40" :class="tool === item.key ? 'bg-primary-50 text-primary-800 dark:bg-primary-900/40 dark:text-primary-200' : 'text-gray-600 dark:text-gray-300'" @click="emit('update:tool', item.key)">
      <i :class="[item.icon, item.key === 'skin' ? 'skin-icon' : item.key === 'lesion' ? 'lesion-icon' : item.key === 'refine' ? 'refine-icon' : '']" class="text-xl" aria-hidden="true"></i>{{ item.label }}
    </button>
    <div class="relative min-w-0" @keydown.esc="expanded = false" @focusout="closeOutside">
      <button type="button" aria-label="调节画笔和橡皮粗细" :aria-expanded="expanded" :disabled="disabled" class="flex min-h-[52px] w-full flex-col items-center justify-center gap-1 rounded-xl text-xs text-gray-600 disabled:opacity-40 dark:text-gray-300" @click="expanded = !expanded"><i class="ri-ruler-line text-xl" aria-hidden="true"></i>粗细</button>
      <div v-if="expanded" class="absolute bottom-full right-0 z-50 mb-2 flex w-16 flex-col items-center gap-2 rounded-2xl border border-gray-200 bg-white py-3 shadow-lg dark:border-gray-700 dark:bg-gray-800">
        <output class="text-xs tabular-nums">{{ props.brushSize }}</output>
        <input aria-label="画笔和橡皮粗细" aria-orientation="vertical" type="range" min="2" max="64" step="2" :value="brushSize" :disabled="disabled" class="brush-range accent-primary-600" @input="emit('update:brushSize', Number(($event.target as HTMLInputElement).value))" />
      </div>
    </div>
  </div>
  <p class="px-1 text-xs leading-4 text-gray-500 dark:text-gray-400" aria-live="polite">{{ hints[tool] }}</p>
  </div>
</template>
<style scoped>
.refine-icon { color: rgb(196, 181, 253); }
.skin-icon { color: rgb(147, 197, 253); }
.lesion-icon { color: rgb(249, 168, 212); }
.brush-range { writing-mode: vertical-lr; direction: rtl; width: 44px; height: 160px; touch-action: none; }
</style>
