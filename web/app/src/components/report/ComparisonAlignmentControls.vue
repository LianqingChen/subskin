<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AlignmentTransform } from '@/types/comparison-alignment'
import { identityAlignment } from '@/utils/comparison-alignment'
import { useManualComparisonSupport } from '@/composables/useManualComparisonSupport'
import ManualAlignmentPanel from './ManualAlignmentPanel.vue'
const props = defineProps<{ beforeUrl: string; afterUrl: string; modelValue: AlignmentTransform | null; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [AlignmentTransform | null]; ready: [boolean] }>()
const support = useManualComparisonSupport(), previewReady = ref(false)
const canAnalyze = computed(() => !props.modelValue || (previewReady.value && support.supported.value))
watch(canAnalyze, value => emit('ready', value), { immediate: true })
watch(() => !!props.modelValue, value => { if (value && !support.checked.value && !support.loading.value) void support.load() }, { immediate: true })
watch(() => [props.beforeUrl, props.afterUrl], () => { emit('update:modelValue', null); previewReady.value = false })
function manual() { if (props.modelValue) return; emit('update:modelValue', identityAlignment()) }
</script>
<template>
  <section aria-label="照片对齐方式" class="space-y-3 rounded-2xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
    <div role="group" aria-label="对齐方式" class="flex flex-wrap gap-2">
      <button type="button" :disabled="disabled" :aria-pressed="!modelValue" class="min-h-[44px] rounded-lg px-3 text-sm" :class="!modelValue ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" @click="emit('update:modelValue', null)">自动对齐</button>
      <button type="button" :disabled="disabled" :aria-pressed="!!modelValue" class="min-h-[44px] rounded-lg px-3 text-sm" :class="modelValue ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" @click="manual">手动调整</button>
    </div>
    <p v-if="!modelValue" class="text-xs text-gray-500 dark:text-gray-400">开始分析时尝试自动对齐，也可以先手动调整画面。</p>
    <template v-else>
      <ManualAlignmentPanel :model-value="modelValue" :before-url="beforeUrl" :after-url="afterUrl" :disabled="disabled" @update:model-value="emit('update:modelValue', $event)" @ready="previewReady = $event" />
      <p v-if="!support.supported.value" role="status" class="text-xs text-gray-500 dark:text-gray-400">{{ support.loading.value ? '正在准备手动分析…' : '手动对齐分析尚未启用，可先预览调整。' }}<button v-if="!support.loading.value" type="button" class="min-h-[44px] px-2 text-primary-700 dark:text-primary-300" @click="support.load">重试</button></p>
    </template>
  </section>
</template>
