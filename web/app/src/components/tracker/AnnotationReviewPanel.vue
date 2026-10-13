<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PhotoMaskCanvas from './PhotoMaskCanvas.vue'
import CompactMaskTools from './CompactMaskTools.vue'
import type { PhotoMaskTool } from '@/utils/photo-mask'
import type { RGBSelector } from '@/api/rgb-segmentation'
const props = defineProps<{ image: string; skin?: string | null; lesion?: string | null; uncertain?: string | null; reference?: string | null; busy?: boolean; fitScreen?: boolean; selector?: RGBSelector; outline?: (signal: AbortSignal) => Promise<{ lesion: string; uncertain: string }>; snap?: (skin: string, target: string, signal: AbortSignal) => Promise<string> }>()
const emit = defineEmits<{ confirm: [payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string; uncertaintyReviewed: boolean; annotatedImageDataUrl?: string }]; cancel: [] }>()
const editor = ref<InstanceType<typeof PhotoMaskCanvas> | null>(null)
const tool = ref<PhotoMaskTool>('lesion'), brushSize = ref(12), ready = ref(false), refining = ref(false), hasCandidate = ref(false)
const refineAvailable = computed(() => !!props.selector)
const outlineAvailable = computed(() => !!props.outline)
const snapAvailable = computed(() => !!props.snap)
function runOutline() {
  if (props.busy || !ready.value || refining.value) return
  void editor.value?.outline()
}
function adoptAll() { if (!props.busy && ready.value && !refining.value) editor.value?.adoptCandidates() }
function discardAll() { if (!props.busy && ready.value && !refining.value) editor.value?.discardCandidates() }
function snapEdges() { if (!props.busy && ready.value && !refining.value) void editor.value?.snapEdges() }
watch(() => props.selector, value => { if (!value && tool.value === 'refine') tool.value = 'lesion' })
function confirm() {
  if (!ready.value || props.busy || refining.value) return
  const masks = editor.value?.snapshot()
  if (masks) emit('confirm', { ...masks, uncertaintyReviewed: true })
}
</script>
<template>
  <section aria-label="核对并调整皮肤和白斑范围" class="mx-auto w-full max-w-3xl" :class="fitScreen ? 'flex min-h-0 flex-1 flex-col gap-2' : 'space-y-2'">
    <PhotoMaskCanvas ref="editor" :fill="fitScreen" :image="image" :skin="skin" :lesion="lesion" :candidate="uncertain" :reference="reference" editable :busy="busy" :tool="tool" :brush-size="brushSize" :refine="selector ?? null" :outline="outline ?? null" :snap="snap ?? null" @ready="ready = $event" @refining="refining = $event" @candidates="hasCandidate = $event" />
    <div class="z-30 shrink-0 space-y-2 bg-gray-50 dark:bg-gray-900" :class="fitScreen ? '' : 'sticky bottom-0 pb-2'">
      <p class="px-1 text-xs leading-4 text-gray-500 dark:text-gray-400">浅橙是待核对范围。确认后只保留浅粉白斑，浅橙不计入占比。</p>
      <div class="grid grid-cols-2 gap-2">
        <button type="button" class="min-h-[44px] rounded-xl bg-primary-50 text-sm font-medium text-primary-800 disabled:opacity-40 dark:bg-primary-900/40 dark:text-primary-200" :disabled="busy || !ready || refining || !hasCandidate" @click="adoptAll">全部当作白斑</button>
        <button type="button" class="min-h-[44px] rounded-xl border border-gray-300 text-sm text-gray-700 disabled:opacity-40 dark:border-gray-600 dark:text-gray-200" :disabled="busy || !ready || refining || !hasCandidate" @click="discardAll">丢弃候选</button>
      </div>
      <button v-if="snapAvailable" type="button" class="min-h-[44px] w-full rounded-xl border border-primary-300 text-sm font-medium text-primary-700 disabled:opacity-40 dark:border-primary-700 dark:text-primary-300" :disabled="busy || !ready || refining" @click="snapEdges">贴合边界</button>
      <button v-if="outlineAvailable" type="button" class="min-h-[44px] w-full rounded-xl border border-primary-300 text-sm font-medium text-primary-700 disabled:opacity-40 dark:border-primary-700 dark:text-primary-300" :disabled="busy || !ready || refining" @click="runOutline">AI 粗定位，自动圈出候选范围</button>
      <CompactMaskTools v-model:tool="tool" v-model:brush-size="brushSize" :disabled="busy || !ready || refining" :refine-available="refineAvailable" />
      <button class="btn-primary min-h-[48px] w-full rounded-xl disabled:opacity-40" :disabled="!ready || busy || refining" aria-label="确认已核对当前皮肤和白斑范围，生成评估结果" @click="confirm">{{ busy ? '保存中…' : '确认' }}</button>
    </div>
  </section>
</template>
