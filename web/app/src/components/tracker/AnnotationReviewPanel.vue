<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PhotoMaskCanvas from './PhotoMaskCanvas.vue'
import CompactMaskTools from './CompactMaskTools.vue'
import type { PhotoMaskTool } from '@/utils/photo-mask'
import type { RGBSelector } from '@/api/rgb-segmentation'
const props = defineProps<{ image: string; skin?: string | null; lesion?: string | null; uncertain?: string | null; reference?: string | null; busy?: boolean; fitScreen?: boolean; selector?: RGBSelector; outline?: (signal: AbortSignal) => Promise<{ lesion: string; uncertain: string }> }>()
const emit = defineEmits<{ confirm: [payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string; uncertaintyReviewed: boolean; annotatedImageDataUrl?: string }]; cancel: [] }>()
const editor = ref<InstanceType<typeof PhotoMaskCanvas> | null>(null)
const tool = ref<PhotoMaskTool>('lesion'), brushSize = ref(12), ready = ref(false), refining = ref(false)
const refineAvailable = computed(() => !!props.selector)
const outlineAvailable = computed(() => !!props.outline)
function runOutline() {
  if (props.busy || !ready.value || refining.value) return
  void editor.value?.outline()
}
watch(() => props.selector, value => { if (!value && tool.value === 'refine') tool.value = 'lesion' })
function confirm() {
  if (!ready.value || props.busy || refining.value) return
  const masks = editor.value?.snapshot()
  if (masks) emit('confirm', { ...masks, uncertaintyReviewed: true })
}
</script>
<template>
  <section aria-label="核对并调整皮肤和白斑范围" class="mx-auto w-full max-w-3xl" :class="fitScreen ? 'flex min-h-0 flex-1 flex-col gap-2' : 'space-y-2'">
    <PhotoMaskCanvas ref="editor" :fill="fitScreen" :image="image" :skin="skin" :lesion="lesion" :candidate="uncertain" :reference="reference" editable :busy="busy" :tool="tool" :brush-size="brushSize" :refine="selector ?? null" :outline="outline ?? null" @ready="ready = $event" @refining="refining = $event" />
    <div class="z-30 shrink-0 space-y-2 bg-gray-50 dark:bg-gray-900" :class="fitScreen ? '' : 'sticky bottom-0 pb-2'">
      <button v-if="outlineAvailable" type="button" class="min-h-[44px] w-full rounded-xl border border-primary-300 text-sm font-medium text-primary-700 disabled:opacity-40 dark:border-primary-700 dark:text-primary-300" :disabled="busy || !ready || refining" @click="runOutline">AI 粗定位，自动圈出候选范围</button>
      <CompactMaskTools v-model:tool="tool" v-model:brush-size="brushSize" :disabled="busy || !ready || refining" :refine-available="refineAvailable" />
      <button class="btn-primary min-h-[48px] w-full rounded-xl disabled:opacity-40" :disabled="!ready || busy || refining" aria-label="确认已核对当前皮肤和白斑范围，生成评估结果" @click="confirm">{{ busy ? '保存中…' : '确认' }}</button>
    </div>
  </section>
</template>
