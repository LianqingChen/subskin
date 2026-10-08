<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AssessmentResult } from '@/types/assessment'
import type { VisualFeatures } from '@/api/vasi'
import { toProtectedFileUrl } from '@/utils/file-url'
import { journalSummary } from '@/utils/assessment-story/summary'
import AnnotationEvidence from './AnnotationEvidence.vue'
import AssessmentStoryCard from './AssessmentStoryCard.vue'
import MicroAskCard from '@/components/contribution/MicroAskCard.vue'
const props = defineProps<{ result: AssessmentResult; skinLayer?: string | null; lesionLayer?: string | null; visualFeatures?: VisualFeatures | null; saved?: boolean; busy?: boolean; canCompare?: boolean; readonly?: boolean }>()
const emit = defineEmits<{ save: []; adjust: []; compare: []; done: []; share: []; retake: [] }>()
const showOriginal = ref(false), showDetails = ref(false)
const summary = computed(() => journalSummary(props.result))
const measure = computed(() => props.result.measurement)
</script>
<template>
  <article class="mx-auto w-full max-w-4xl space-y-4">
    <header class="flex items-center justify-between gap-3">
      <div><h2 class="whitespace-nowrap text-lg font-semibold">本次记录</h2><p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{{ summary.site }}<template v-if="summary.date"> · {{ summary.date }}</template></p></div>
      <span v-if="saved" class="shrink-0 text-xs text-primary-700 dark:text-primary-300"><i class="ri-check-line mr-1" aria-hidden="true"></i>已保存</span>
    </header>
    <div class="grid items-start gap-4" :class="saved && !readonly ? 'md:grid-cols-2' : ''">
      <section aria-label="照片记录结果" class="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
        <div v-if="result.imageUrl" class="flex items-center justify-between gap-2 px-3">
          <div class="flex gap-1" role="group" aria-label="照片显示方式"><button type="button" :aria-pressed="!showOriginal" class="min-h-[44px] px-2 text-xs" :class="!showOriginal ? 'text-primary-700 dark:text-primary-300' : 'text-gray-500'" @click="showOriginal = false">标注</button><button type="button" :aria-pressed="showOriginal" class="min-h-[44px] px-2 text-xs" :class="showOriginal ? 'text-primary-700 dark:text-primary-300' : 'text-gray-500'" @click="showOriginal = true">原图</button></div>
          <button v-if="!readonly" type="button" class="min-h-[44px] px-2 text-xs text-gray-500 dark:text-gray-400" :disabled="busy" @click="emit('adjust')"><i class="ri-edit-line mr-1" aria-hidden="true"></i>调整范围</button>
        </div>
        <div class="result-photo">
          <img v-if="result.imageUrl && showOriginal" :src="toProtectedFileUrl(result.imageUrl)" alt="本次记录的原始皮肤照片" class="h-full w-full object-contain" />
          <AnnotationEvidence v-else-if="result.imageUrl" :image="toProtectedFileUrl(result.imageUrl)" :skin="skinLayer" :lesion="lesionLayer" :uncertain="summary.reviewed ? null : measure?.annotation?.uncertain_layer_data_url" />
        </div>
        <div class="p-4">
          <p v-if="!showOriginal" class="mb-3 text-xs text-gray-400">浅粉为白斑 · 浅蓝为皮肤</p>
          <div class="flex items-baseline justify-between gap-2"><h3 class="whitespace-nowrap text-sm font-medium">照片内白斑占比</h3><strong class="text-2xl font-semibold tabular-nums text-primary-700 dark:text-primary-300">{{ summary.measurable ? summary.label : '—' }}</strong></div>
          <div v-if="summary.measurable && measure?.region_count != null" class="mt-2 flex justify-between text-xs text-gray-500 dark:text-gray-400"><span>可见标注区域</span><span>{{ measure.region_count }} 处</span></div>
          <p class="mt-3 text-xs text-gray-400">仅限本张照片中的可见皮肤</p>
          <p v-if="summary.notice" role="status" class="mt-2 text-xs leading-5 text-primary-800 dark:text-primary-200">{{ summary.notice }}</p>
          <button v-if="!saved && !readonly" class="btn-primary mt-3 min-h-[44px] w-full rounded-xl text-sm" :disabled="busy" @click="emit('save')">{{ busy ? '保存中…' : summary.reviewed ? '保存记录' : '核对范围后保存' }}</button>
          <button type="button" class="mt-1 min-h-[44px] text-xs text-gray-500 dark:text-gray-400" :aria-expanded="showDetails" @click="showDetails = !showDetails">测量说明<i :class="showDetails ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'" aria-hidden="true"></i></button>
          <div v-if="showDetails" class="space-y-2 border-t border-gray-100 pt-3 text-xs leading-5 text-gray-500 dark:border-gray-700 dark:text-gray-400">
            <p>占比＝白斑÷（正常皮肤＋白斑）。照片占比不是全身面积或临床 VASI，不同取景不宜直接比较。</p>
            <p v-for="reason in measure?.reasons || []" :key="reason">{{ reason }}</p>
            <p v-if="summary.measurable && measure?.lesion_pixels != null">白斑 {{ measure.lesion_pixels }} 像素，皮肤 {{ measure.skin_pixels }} 像素。</p>
            <p v-if="summary.measurable && measure?.area_cm2 != null">参照物估算 {{ measure.area_cm2 }} cm²，仅为二维投影面积。</p>
          </div>
        </div>
      </section>
      <AssessmentStoryCard v-if="saved && !readonly" :key="result.id" :result="result" :skin="skinLayer" :lesion="lesionLayer" :saved="saved" />
    </div>
    <MicroAskCard v-if="saved && !readonly" :key="'ask-' + result.id" trigger="record_saved" :body-site="result.bodySite" />
    <footer v-if="saved && !readonly" class="flex justify-end gap-3 text-xs text-gray-500 dark:text-gray-400"><button class="min-h-[44px]" @click="emit('retake')">继续拍</button><button v-if="canCompare" class="min-h-[44px]" @click="emit('compare')">与上次对比</button><button class="min-h-[44px]" @click="emit('done')">查看记录</button></footer>
  </article>
</template>
<style scoped>
.result-photo { height: clamp(200px, 38svh, 380px); }
.result-photo :deep(.photo-mask-stage) { height: 100%; border-radius: 0; }
@media (min-width: 768px) { .result-photo { height: 380px; } }
</style>
