<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useReportReanalysis } from '@/composables/useReportReanalysis'
import type { AlignmentTransform } from '@/types/comparison-alignment'
import { identityAlignment } from '@/utils/comparison-alignment'
import ComparisonAlignmentControls from './ComparisonAlignmentControls.vue'
const props = defineProps<{ beforeUrl: string; afterUrl: string; beforeLabel?: string; afterLabel?: string }>()
const emit = defineEmits<{ editing: [boolean] }>()
const report = useReportReanalysis(props), open = ref(false), ready = ref(false)
const alignment = ref<AlignmentTransform | null>(null)
watch(open, value => emit('editing', value), { immediate: true, flush: 'sync' })
onBeforeUnmount(() => emit('editing', false))
function toggle() {
  if (report.busy.value) return
  ready.value = false
  open.value = !open.value
  if (open.value) { alignment.value = identityAlignment(); void report.load() }
  else report.reset()
}
watch(() => [props.beforeUrl, props.afterUrl, props.beforeLabel, props.afterLabel, report.available.value], () => { open.value = false; alignment.value = null })
</script>
<template>
  <section v-if="report.available.value" aria-label="重新对齐并分析" data-html2canvas-ignore="true" class="space-y-3 print:hidden">
    <button type="button" class="min-h-[44px] rounded-lg border border-primary-200 px-3 text-sm text-primary-700 dark:border-primary-700 dark:text-primary-300" :aria-expanded="open" :disabled="report.busy.value" @click="toggle"><i class="ri-drag-move-line mr-1" aria-hidden="true"></i>{{ open ? '收起调整' : '调整并重新分析' }}</button>
    <template v-if="open">
      <p role="status" class="text-sm text-gray-600 dark:text-gray-300">{{ report.busy.value ? '正在根据本次设置重新分析，请等待新报告。' : '当前是调整预览，尚未重新分析。确认后将生成新报告。' }}</p>
      <button type="button" class="btn-primary min-h-[44px] w-full disabled:opacity-40" :disabled="!report.pair.value || !ready || report.loading.value || report.busy.value" @click="report.generate(alignment)">{{ report.busy.value ? '正在准备新报告…' : alignment ? '确认对齐并重新分析' : '重新分析' }}</button>
      <p v-if="report.loading.value || report.error.value" role="status" class="text-sm text-gray-500 dark:text-gray-400">{{ report.error.value || '正在读取这组照片…' }}</p>
      <ComparisonAlignmentControls v-if="report.pair.value" v-model="alignment" :before-url="report.pair.value.referenceUrl" :after-url="report.pair.value.movingUrl" :disabled="report.busy.value" @ready="ready = $event" />
    </template>
  </section>
</template>
