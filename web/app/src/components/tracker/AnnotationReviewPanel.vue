<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import PhotoMaskCanvas from './PhotoMaskCanvas.vue'
import CompactMaskTools from './CompactMaskTools.vue'
import type { PhotoMaskTool } from '@/utils/photo-mask'
import type { RGBSelector } from '@/api/rgb-segmentation'
import type { AssessmentFusionPreview, FusionLesionLayer } from '@/types/assessment'
const props = defineProps<{ image: string; fusionPreview?: AssessmentFusionPreview; fusionLayer?: (kind: FusionLesionLayer | 'lesion', signal: AbortSignal) => Promise<string>; skin?: string | null; lesion?: string | null; uncertain?: string | null; reference?: string | null; busy?: boolean; fitScreen?: boolean; creative?: boolean; selector?: RGBSelector; outline?: (signal: AbortSignal) => Promise<{ lesion: string; uncertain: string }>; snap?: (skin: string, target: string, signal: AbortSignal) => Promise<string> }>()
const emit = defineEmits<{ confirm: [payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string; uncertaintyReviewed: boolean; annotatedImageDataUrl?: string }]; cancel: [] }>()
const editor = ref<InstanceType<typeof PhotoMaskCanvas> | null>(null)
const tool = ref<PhotoMaskTool>('lesion'), brushSize = ref(12), ready = ref(false), refining = ref(false), hasCandidate = ref(false), more = ref(false)
const disabled = computed(() => !!props.busy || !ready.value || refining.value)
function runOutline() { if (!disabled.value) { more.value = false; void editor.value?.outline() } }
function adoptAll() { if (!disabled.value) editor.value?.adoptCandidates() }
function discardAll() { if (!disabled.value) editor.value?.discardCandidates() }
function snapEdges() { if (!disabled.value) { more.value = false; void editor.value?.snapEdges() } }
watch(() => props.selector, value => { if (!value && tool.value === 'refine') tool.value = 'lesion' })
function confirm() {
  if (disabled.value) return
  const masks = editor.value?.snapshot()
  if (masks) emit('confirm', { ...masks, uncertaintyReviewed: true })
}
const fusionOptions: { kind: FusionLesionLayer; label: string }[] = [
  { kind: 'boundary_lesion', label: '边界细化' },
  { kind: 'smallspot_lesion', label: '小斑补查' },
]
const fusionRows = computed(() => fusionOptions.flatMap(option => {
  const stats = props.fusionPreview?.variants[option.kind]
  return stats ? [{ ...option, ...stats }] : []
}))
function loadFusion(kind: FusionLesionLayer | 'lesion') {
  const fetchLayer = props.fusionLayer
  if (!fetchLayer || disabled.value) return
  more.value = false
  void editor.value?.loadLesionDraft(signal => fetchLayer(kind, signal))
}
function beforeUnload(event: BeforeUnloadEvent) { event.preventDefault(); event.returnValue = '' }
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(() => !props.busy && !refining.value && window.confirm('离开后，本次未保存的涂层修改将丢失。确定离开吗？'))
function cancel() {
  if (props.busy || refining.value) return
  if (window.confirm('退出后，本次未保存的涂层修改将丢失。确定退出吗？')) emit('cancel')
}
</script>
<template>
  <Teleport to="body">
    <section aria-label="核对并调整皮肤和白斑范围" class="annotation-workspace bg-white text-gray-900 dark:bg-gray-900 dark:text-gray-100">
      <header class="workspace-header flex shrink-0 items-center gap-2 border-b border-gray-200 px-2 dark:border-gray-700">
        <button type="button" class="flex h-11 w-11 items-center justify-center rounded-xl text-xl" aria-label="退出编辑" :disabled="busy || refining" @click="cancel"><i class="ri-arrow-left-line" aria-hidden="true"></i></button>
        <div class="min-w-0 flex-1"><h2 class="text-sm font-semibold">调整皮肤和白斑范围</h2><p class="text-xs text-gray-500 dark:text-gray-400">双指缩放 · 蓝色为皮肤 · 粉色为白斑</p></div>
      </header>
      <PhotoMaskCanvas ref="editor" fill :image="image" :skin="skin" :lesion="lesion" :candidate="uncertain" :reference="reference" editable :busy="busy" :tool="tool" :brush-size="brushSize" :refine="selector ?? null" :outline="outline ?? null" :snap="snap ?? null" @ready="ready = $event" @refining="refining = $event" @candidates="hasCandidate = $event" />
      <div class="workspace-controls relative shrink-0 border-t border-gray-200 bg-white px-2 pt-1 dark:border-gray-700 dark:bg-gray-900">
        <div v-if="more" class="absolute bottom-full left-2 right-2 z-40 mb-2 max-h-[45vh] overflow-y-auto rounded-2xl border border-gray-200 bg-white p-2 shadow-lg dark:border-gray-700 dark:bg-gray-800">
          <p v-if="hasCandidate" class="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">橙色为待核对区域，未计入占比</p>
          <div v-if="hasCandidate" class="grid grid-cols-2 gap-2 pb-2">
            <button type="button" class="min-h-[44px] rounded-xl bg-primary-50 px-2 text-sm text-primary-800 disabled:opacity-40 dark:bg-primary-900/40 dark:text-primary-200" :disabled="disabled" @click="adoptAll">全部当作白斑</button>
            <button type="button" class="min-h-[44px] rounded-xl border border-gray-300 px-2 text-sm disabled:opacity-40 dark:border-gray-600" :disabled="disabled" @click="discardAll">丢弃候选</button>
          </div>
          <div v-if="fusionPreview && fusionLayer" class="space-y-1 border-b border-gray-200 pb-2 dark:border-gray-700">
            <p class="px-2 text-xs font-medium">白斑初稿对照</p>
            <p class="px-2 text-xs text-gray-500 dark:text-gray-400">载入后替换当前白斑层，可撤销。</p>
            <button type="button" class="menu-action" :disabled="disabled" @click="loadFusion('lesion')">载入原辅助分割</button>
            <template v-for="option in fusionRows" :key="option.kind">
              <button v-if="option.added_pixels || option.removed_pixels" type="button" class="menu-action flex flex-wrap items-center justify-between gap-1" :disabled="disabled" @click="loadFusion(option.kind)">
                <span>{{ option.label }}</span><span class="text-xs tabular-nums text-gray-500 dark:text-gray-400">新增 {{ option.added_pixels }} · 移除 {{ option.removed_pixels }} 像素</span>
              </button>
              <p v-else class="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">{{ option.label }}与原辅助分割一致</p>
            </template>
            <p v-if="fusionPreview.smallspots.status === 'not_sparse'" class="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">本图未触发小斑补查</p>
            <p v-else-if="fusionPreview.smallspots.status === 'no_candidates'" class="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">未找到可补查的小斑候选</p>
            <p v-else-if="fusionPreview.smallspots.status === 'unavailable'" class="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">小斑补查未完成，可继续核对原辅助分割</p>
            <p v-else class="px-2 py-1 text-xs tabular-nums text-gray-500 dark:text-gray-400">已核对 {{ fusionPreview.smallspots.judged }} / {{ fusionPreview.smallspots.proposed }} 处小斑候选</p>
          </div>
          <button v-if="selector" type="button" class="menu-action" :disabled="disabled" @click="tool = 'refine'; more = false">智能点选白斑</button>
          <button type="button" class="menu-action" :disabled="disabled" @click="tool = 'remove'; more = false">整块去除误标</button>
          <button v-if="snap" type="button" class="menu-action" :disabled="disabled" @click="snapEdges">贴合边界</button>
          <button v-if="outline" type="button" class="menu-action" :disabled="disabled" @click="runOutline">AI 粗定位候选范围</button>
        </div>
        <CompactMaskTools v-model:tool="tool" v-model:brush-size="brushSize" :disabled="disabled" :refine-available="!!selector" />
        <div class="flex items-center gap-2 pb-1">
          <button type="button" class="relative min-h-[44px] rounded-xl border border-gray-200 px-3 text-sm dark:border-gray-700" :aria-expanded="more" @click="more = !more"><i class="ri-more-2-fill" aria-hidden="true"></i> 更多<span v-if="hasCandidate" class="ml-1 text-primary-700 dark:text-primary-300">· 待核对</span></button>
          <button type="button" class="btn-primary min-h-[44px] min-w-0 flex-1 rounded-xl disabled:opacity-40" :disabled="disabled" @click="confirm">{{ busy ? '保存中…' : creative ? '确认并创作' : '确认并保存' }}</button>
        </div>
      </div>
    </section>
  </Teleport>
</template>
<style scoped>
.annotation-workspace { position: fixed; inset: 0; z-index: 100; display: flex; flex-direction: column; width: 100%; height: 100vh; height: 100dvh; }
.workspace-header { padding-top: env(safe-area-inset-top, 0px); }
.workspace-controls { padding-bottom: max(0.25rem, env(safe-area-inset-bottom, 0px)); }
.menu-action { display: block; width: 100%; min-height: 44px; border-radius: 0.75rem; padding: 0.5rem; text-align: left; font-size: 0.875rem; }
.menu-action:disabled { opacity: 0.4; }
</style>
