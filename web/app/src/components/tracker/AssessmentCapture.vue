<script setup lang="ts">
import { computed, ref } from 'vue'
import BodyPartCamera from './BodyPartCamera.vue'
import AnalysisWaitStatus from './AnalysisWaitStatus.vue'
import DateWheelPicker from '@/components/common/DateWheelPicker.vue'
import ReferenceCalibration from './ReferenceCalibration.vue'
import { PART_LABELS } from '@/constants/bodySites'
import type { ObservationContext } from '@/types/assessment'
import type { QualityCheckResult } from '@/api/vasi'
const props = defineProps<{ context: ObservationContext; bodySite: string; preview: string | null; baselineUrl?: string | null; quality: QualityCheckResult | null; checking: boolean; busy: boolean; qualityError?: string; needsLogin?: boolean; dateNote?: string; stage?: string; fitScreen?: boolean }>()
const emit = defineEmits<{ 'update:context': [ObservationContext]; 'update:bodySite': [string]; file: [File, ('gallery' | 'camera')?]; date: [string]; 'retry-quality': []; remove: []; submit: []; cancel: [] }>()
const camera = ref(false)
const input = ref<HTMLInputElement | null>(null)
const stageLabels: Record<string, string> = { queued: '等待分析…', preprocessing: '准备照片…', quality_check: '检查照片…', segmenting: '识别范围…', validating: '核对测量…' }
const stageText = computed(() => stageLabels[props.stage || ''] || '分析中…')
function selected(event: Event) {
  const element = event.target as HTMLInputElement
  const file = element.files?.[0]
  if (file) { emit('file', file, 'gallery') }
  element.value = ''
}
function captured(file: File) { emit('file', file, 'camera'); camera.value = false }
function captureCalibration(value: ObservationContext['calibration']) { emit('update:context', { ...props.context, calibration: value }) }
const ready = computed(() => !!props.preview && !!props.bodySite && !!props.context.capture_date && !props.checking && !!props.quality && props.quality.overall !== 'poor' && !props.busy)
const qualityMessage = computed(() => props.checking ? '检查照片中…' : !props.quality ? props.qualityError || '照片检查尚未完成' : props.quality.overall === 'good' ? '' : props.quality.suggestions[0] || '请调整光照后重拍')
</script>
<template>
  <section aria-label="添加照片" class="capture-layout mx-auto grid w-full max-w-4xl items-start gap-3 lg:grid-cols-[minmax(0,1fr)_18rem] lg:gap-3" :class="fitScreen ? 'capture-layout--fit' : ''">
    <figure class="capture-photo min-w-0 overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <img v-if="preview" :src="preview" alt="本次记录照片" class="max-h-[56svh] min-h-[180px] w-full object-contain lg:max-h-[calc(100svh-13rem)]" />
      <div v-else class="flex h-48 items-center justify-center gap-3 text-gray-400"><i class="ri-camera-line text-4xl" aria-hidden="true"></i><span class="text-sm">添加照片</span></div>
      <figcaption class="border-t border-gray-100 px-3 dark:border-gray-700">
        <div class="flex min-h-[48px] items-center justify-between gap-2">
          <span class="min-w-0 truncate text-sm font-medium">{{ context.label || PART_LABELS[bodySite] || '白斑记录' }}</span>
          <div v-if="!busy" class="flex shrink-0 gap-1">
            <button class="min-h-[44px] rounded-lg px-3 text-sm text-primary-700 dark:text-primary-300" :disabled="!bodySite" @click="camera = true"><i class="ri-camera-line mr-1" aria-hidden="true"></i>{{ preview ? '重拍' : '拍照' }}</button>
            <button class="min-h-[44px] rounded-lg px-3 text-sm text-primary-700 dark:text-primary-300" :disabled="!bodySite" @click="input?.click()"><i class="ri-image-add-line mr-1" aria-hidden="true"></i>{{ preview ? '换图' : '相册' }}</button>
          </div>
        </div>
        <p v-if="preview && qualityMessage" id="capture-quality" role="status" class="pb-2 text-xs leading-5" :class="quality?.overall === 'poor' || qualityError ? 'text-amber-700 dark:text-amber-300' : 'text-gray-500 dark:text-gray-400'">{{ qualityMessage }}</p>
      </figcaption>
    </figure>
    <div class="capture-controls min-w-0 space-y-2">
      <fieldset :disabled="busy" aria-label="照片日期" class="flex min-w-0 items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-1 dark:border-gray-700 dark:bg-gray-800">
        <span class="shrink-0 text-xs text-gray-500 dark:text-gray-400">日期</span>
        <DateWheelPicker v-if="context.capture_date && !busy" class="min-w-0 flex-1" :model-value="context.capture_date" :min-year="1900" compact @update:model-value="emit('date', $event)" />
        <time v-else class="flex min-h-[44px] items-center text-sm" :datetime="context.capture_date">{{ context.capture_date || (preview ? '读取中…' : '—') }}</time>
      </fieldset>
      <ReferenceCalibration v-if="preview && !busy" :image="preview" @change="captureCalibration" />
      <AnalysisWaitStatus v-if="busy" :active="busy" :stage="stageText" @cancel="emit('cancel')" />
      <button v-if="preview && !checking && !quality && !busy" class="min-h-[44px] w-full rounded-xl border border-primary-300 text-sm text-primary-700 dark:border-primary-700 dark:text-primary-300" @click="emit('retry-quality')">{{ needsLogin ? '登录后继续检查' : '重新检查照片' }}</button>
      <button v-if="preview && !busy" :aria-describedby="qualityMessage ? 'capture-quality' : undefined" class="btn-primary min-h-[44px] w-full text-sm rounded-xl disabled:opacity-40" :disabled="!ready" @click="emit('submit')"><i class="ri-scan-line mr-2" aria-hidden="true"></i>开始分析</button>
    </div>
    <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="selected" />
    <BodyPartCamera v-model="camera" :body-part="bodySite" :baseline-url="baselineUrl" @captured="captured" />
  </section>
</template>

<style scoped>
.capture-layout--fit { flex: 1; min-height: 0; grid-template-rows: minmax(0, 1fr) auto; gap: 8px; align-items: stretch; }
.capture-layout--fit .capture-photo { display: flex; flex-direction: column; min-height: 0; }
.capture-layout--fit .capture-photo > img { flex: 1; min-height: 0; height: 0; max-height: none; }
.capture-layout--fit .capture-photo > figcaption { flex: none; }
.capture-layout--fit .capture-controls { min-height: 0; max-height: 100%; overflow-y: auto; }
.capture-layout--fit .capture-controls > :not([hidden]) ~ :not([hidden]) { margin-top: 8px; }
@media (min-width: 1024px), (max-height: 500px) and (min-width: 600px) {
  .capture-layout--fit { grid-template-columns: minmax(0, 1fr) minmax(220px, 18rem); grid-template-rows: minmax(0, 1fr); }
}
</style>
