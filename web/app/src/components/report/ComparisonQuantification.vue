<script setup lang="ts">
import { computed } from 'vue'
import type { PairMetrics } from '@/api/skin_report'
const props = defineProps<{ metrics?: PairMetrics | null }>()
const measured = computed(() => props.metrics?.comparison_status === 'measured' && !props.metrics?.duplicate && !props.metrics?.evidence?.duplicate)
const evidence = computed(() => props.metrics?.evidence)
const photos = computed(() => props.metrics?.photo_measurements)
function number(value: number | null | undefined, digits = 2) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('zh-CN', { maximumFractionDigits: digits }) : '—'
}
const rows = computed(() => [
  { label: '白斑占可见皮肤', unit: '%', before: photos.value?.before.area_percentage, after: photos.value?.after.area_percentage },
  { label: '白斑标注像素', unit: 'px', before: photos.value?.before.lesion_pixels, after: photos.value?.after.lesion_pixels },
  { label: '可见皮肤像素', unit: 'px', before: photos.value?.before.skin_pixels, after: photos.value?.after.skin_pixels },
  { label: '相对正常皮肤亮度', unit: 'L*', before: photos.value?.before.relative_lightness, after: photos.value?.after.relative_lightness },
  ...(photos.value?.before.area_cm2 != null || photos.value?.after.area_cm2 != null ? [{ label: '标尺投影面积', unit: 'cm²', before: photos.value?.before.area_cm2, after: photos.value?.after.area_cm2 }] : []),
])
const reasons = computed(() => [...new Set([
  ...(props.metrics?.reasons || []), ...(evidence.value?.reasons || []),
  ...(!measured.value && props.metrics?.capture_note ? [props.metrics.capture_note] : []),
])])
const sources = computed(() => [
  { label: '前', value: photos.value?.before }, { label: '后', value: photos.value?.after },
])
function assessmentId(ref?: string | null) { return /^va:\d+$/.test(ref || '') ? ref?.slice(3) : undefined }
</script>
<template>
  <section class="quant" aria-label="量化分析">
    <h4 class="quant__title"><i class="ri-bar-chart-box-line" aria-hidden="true" />量化分析</h4>
    <template v-if="measured">
      <p class="quant__scope">两张照片的共同可见皮肤范围</p>
      <dl class="quant__grid">
        <div><dt>前 · 白斑像素</dt><dd>{{ number(evidence?.area_a_px, 0) }} <small>px</small></dd></div>
        <div><dt>后 · 白斑像素</dt><dd>{{ number(evidence?.area_b_px, 0) }} <small>px</small></dd></div>
        <div><dt>相对面积变化</dt><dd>{{ metrics?.size_change_percent != null ? `${metrics.size_change_percent > 0 ? '+' : ''}${number(metrics.size_change_percent, 1)}%` : '不计算' }}</dd></div>
      </dl>
      <p class="quant__note">共同皮肤 {{ number(evidence?.common_pixels, 0) }} px · 覆盖率 {{ evidence?.common_coverage != null ? number(evidence.common_coverage * 100, 1) + '%' : '—' }} · 对齐误差 {{ number(evidence?.alignment_error_px) }} px</p>
      <p v-if="metrics?.size_change_percent == null" class="quant__note">基线白斑过小或为零，不能计算相对变化率；零值与未测得的数据分别显示。</p>
      <p v-if="evidence?.relative_lightness_change != null" class="quant__note">相对亮度变化：{{ number(evidence.relative_lightness_change, 1) }} L*（正值更亮、负值更暗，仅描述照片）</p>
    </template>
    <p v-else class="quant__note">这组照片暂不能可靠计算共同范围的变化率。下面保留各张照片已有的测量结果；“—”表示该项未测得，不是 0。</p>
    <table class="quant__table"><caption>单张照片的量化数据</caption><thead><tr><th scope="col">指标</th><th scope="col">前</th><th scope="col">后</th></tr></thead><tbody><tr v-for="row in rows" :key="row.label"><th scope="row">{{ row.label }} <small>({{ row.unit }})</small></th><td>{{ number(row.before) }}</td><td>{{ number(row.after) }}</td></tr></tbody></table>
    <p class="quant__note">单图占比使用各自的可见皮肤作分母，拍摄范围与尺寸可能不同，不能直接用两列相减判断增减；像素不是实际平方厘米。</p>
    <p v-if="metrics?.photo_measurement_source === 'latest_source_records'" class="quant__note">此旧报告的单图数据按来源记录当前标注补充，原报告的变化结论未改写。</p>
    <ul v-if="reasons.length" class="quant__reasons"><li v-for="reason in reasons" :key="reason">{{ reason }}</li></ul>
    <div v-for="source in sources" :key="source.label" class="quant__note">
      <p v-if="source.value?.status === 'partial'">{{ source.label }}：白斑可能未拍全，数据仅代表照片内已标注范围。</p>
      <p v-for="reason in source.value?.reasons || []" :key="reason">{{ source.label }}：{{ reason }}</p>
      <RouterLink v-if="assessmentId(source.value?.source_ref)" class="quant__link" :to="{ name: 'vasi-detail', params: { id: assessmentId(source.value?.source_ref) } }">查看{{ source.label }}记录并核对范围</RouterLink>
    </div>
    <p class="quant__note">本文不构成医疗建议。局部照片面积和颜色变化不等于全身 VASI、治疗效果或病情分期。</p>
  </section>
</template>
<style scoped>
.quant { border: 1px solid var(--color-primary-200); border-radius: 12px; padding: 16px; @apply bg-white text-slate-700; }
.quant__title { display: flex; gap: 6px; font-weight: 600; font-size: 15px; margin-bottom: 12px; }
.quant__scope { font-size: 12px; margin-bottom: 8px; @apply text-slate-500; }
.quant__grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 8px; }
.quant__grid div { padding: 12px 8px; border-radius: 8px; background: var(--color-primary-50); }
.quant__grid dt { font-size: 11px; @apply text-slate-500; }
.quant__grid dd { margin-top: 6px; font-size: 17px; font-weight: 600; overflow-wrap: anywhere; }
.quant small { font-size: 10px; font-weight: 400; }
.quant__table { width: 100%; table-layout: fixed; font-size: 12px; margin-top: 14px; border-collapse: collapse; }
.quant__table caption { text-align: left; font-weight: 500; margin-bottom: 8px; }
.quant__table th,.quant__table td { padding: 10px 4px; @apply border-b border-slate-200; text-align: right; overflow-wrap: anywhere; }
.quant__table th:first-child { text-align: left; width: 46%; font-weight: 400; }
.quant__note,.quant__reasons { margin-top: 10px; font-size: 11px; line-height: 1.8; @apply text-slate-500; }
.quant__reasons { padding-left: 16px; list-style: disc; }
.quant__link { display: inline-flex; min-height: 44px; align-items: center; text-decoration: underline; color: var(--color-primary-700); }
</style>
