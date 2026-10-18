<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { BODY_REGIONS, BODY_SILHOUETTE, BODY_VIEWBOX } from '@/utils/body-silhouette'
import { compactContributionCount, contributionParts } from '@/utils/contribution-charts'
import type { ContributionDistribution, ContributionPersonalVisuals } from '@/types/contribution'
const props = defineProps<{ distribution: ContributionDistribution | null; personal: ContributionPersonalVisuals | null; loading: boolean; error: boolean; personalError: boolean }>()
defineEmits<{ retry: [] }>()
const clipId = `body-${useId()}`
const mode = ref<'community' | 'mine'>('community')
const selected = ref<string | null>(null)
const parts = computed(() => contributionParts(props.distribution, props.personal, mode.value))
const maximum = computed(() => Math.max(1, ...parts.value.map(p => p.count ?? 0)))
const ownParts = computed(() => contributionParts(null, props.personal, 'mine'))
const selectedPart = computed(() => parts.value.find(p => p.code === selected.value))
const ownSelected = computed(() => ownParts.value.find(p => p.code === selected.value))
const hasData = computed(() => parts.value.some(p => (p.count ?? 0) > 0))
const visibleError = computed(() => mode.value === 'mine' ? props.personalError : props.error)
function count(code: string) { return parts.value.find(p => p.code === code)?.count ?? null }
function shade(code: string) { const value = count(code); return value !== null && value > 0 ? 0.2 + 0.8 * value / maximum.value : 1 }
function select(code: string) { selected.value = selected.value === code ? null : code }
watch(mode, () => { selected.value = null })
watch(() => props.personal, value => { if (!value) mode.value = 'community' })
</script>

<template>
  <section id="body-distribution" class="card min-w-0 p-4 dark:bg-gray-800 sm:p-5" aria-labelledby="body-title">
    <div class="mb-3 flex items-center justify-between gap-2"><h2 id="body-title" class="text-base font-semibold">部位分布</h2><div class="flex rounded-xl bg-gray-100 p-1 dark:bg-gray-900" role="group" aria-label="部位图统计范围"><button type="button" class="min-h-9 rounded-lg px-3 text-xs" :class="mode === 'community' ? 'bg-white font-medium text-primary-700 dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" :aria-pressed="mode === 'community'" @click="mode = 'community'">大家</button><button type="button" class="min-h-9 rounded-lg px-3 text-xs disabled:opacity-40" :class="mode === 'mine' ? 'bg-white font-medium text-primary-700 dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" :disabled="!personal && !personalError" :aria-pressed="mode === 'mine'" @click="mode = 'mine'">我的</button></div></div>
    <div v-if="loading" role="status" class="h-56 animate-pulse rounded-xl bg-gray-100 motion-reduce:animate-none dark:bg-gray-700"><span class="sr-only">正在加载部位图</span></div>
    <div v-else-if="visibleError" role="alert" class="py-6 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">部位数据加载失败</p><button type="button" class="btn-ghost mt-2 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else>
      <p v-if="!hasData" class="mb-3 text-xs text-gray-500 dark:text-gray-400">{{ parts.some(p => p.count === null) ? '部位数量暂不公开' : '有效资料正在积累' }}</p>
      <div class="body-layout">
        <figure class="body-figure"><svg class="body-plot" :viewBox="BODY_VIEWBOX" role="img" :aria-label="`${mode === 'mine' ? '本人' : '社区'}有效图片部位示意，深浅表示资料数量，左右为合计，并非病情图`">
          <defs><clipPath :id="clipId"><path :d="BODY_SILHOUETTE" /></clipPath></defs>
          <path :d="BODY_SILHOUETTE" class="body-empty" />
          <path v-for="(d, region) in BODY_REGIONS" :key="region" :d="d" :data-part="region" :clip-path="`url(#${clipId})`" :class="[count(region) !== null && (count(region) ?? 0) > 0 ? 'body-region' : 'body-empty', selected === region && 'body-selected']" :fill-opacity="selected === region ? 1 : shade(region)" />
          <path :d="BODY_SILHOUETTE" class="body-outline" />
        </svg><figcaption class="mt-1 text-center text-[11px] text-gray-500 dark:text-gray-400">左右合计</figcaption></figure>
        <div class="min-w-0 flex-1"><button v-for="part in parts" :key="part.code" type="button" class="part-button w-full rounded-lg px-1.5 py-1.5 text-left focus-visible:ring-2 focus-visible:ring-primary-500" :aria-pressed="selected === part.code" :aria-label="`${part.label}，${part.count === null ? '暂不公开' : `${part.count}张`}，查看详情`" @click="select(part.code)"><span class="mb-1 flex justify-between gap-2 text-xs"><span :class="selected === part.code ? 'font-semibold text-primary-700 dark:text-primary-300' : 'text-gray-600 dark:text-gray-300'">{{ part.label }}</span><span class="shrink-0 tabular-nums text-gray-500 dark:text-gray-400">{{ part.count === null ? '未公开' : compactContributionCount(part.count) }}</span></span><span class="block h-1.5 rounded-full bg-gray-100 dark:bg-gray-700"><span class="block h-full rounded-full bg-primary-500 dark:bg-primary-400" :style="{ width: `${100 * (part.count ?? 0) / maximum}%` }"></span></span></button></div>
      </div>
      <p v-if="selectedPart" class="mt-3 rounded-xl bg-primary-50 p-3 text-xs leading-6 text-primary-700 dark:bg-primary-900 dark:text-primary-300" aria-live="polite">{{ selectedPart.label }}：{{ selectedPart.count === null ? '公共数量暂不公开' : `${selectedPart.count} 张有效图片` }}<span v-if="mode === 'community' && ownSelected?.count !== null && ownSelected?.count !== undefined">；我的有效贡献 {{ ownSelected.count }} 张（单独统计）</span>。</p>
      <p class="mt-3 text-xs text-gray-500 dark:text-gray-400">颜色深浅表示资料多少，非病情严重度</p>
      <details v-if="distribution" class="mt-1 text-xs text-gray-500 dark:text-gray-400"><summary class="min-h-10 cursor-pointer py-2.5">细分部位与口径</summary><p class="leading-5">{{ distribution.note }} 大类合并时不猜测左右或精细部位。</p><ul class="mt-2 grid grid-cols-2 gap-1.5"><li v-for="row in distribution.rows" :key="row.code">{{ row.label }}：{{ row.count === null ? '未公开' : `${row.count}张` }}</li></ul><ul class="mt-3 flex flex-wrap gap-1.5"><li v-for="dimension in distribution.dimensions" :key="dimension.name" class="rounded-full bg-gray-50 px-2.5 py-1 dark:bg-gray-900"><i :class="dimension.status === 'available' ? 'ri-checkbox-circle-line' : 'ri-time-line'" class="mr-1" aria-hidden="true"></i>{{ dimension.name }} · {{ dimension.status === 'available' ? '已有' : '待补充' }}</li></ul><p class="mt-2 leading-5">{{ distribution.types.note }}</p><p class="mt-1.5 leading-5">{{ distribution.coverage.note }}</p></details>
    </template>
  </section>
</template>

<style scoped>
.body-layout { display:flex; align-items:center; gap:16px; }
.body-figure { width:118px; flex-shrink:0; margin:0; }
.body-plot { width:100%; height:auto; }
.body-region { fill:var(--color-primary-600); }
.body-empty { fill:var(--color-border); }
:global(html.dark .body-region) { fill:var(--color-primary-400); }
:global(html.dark .body-empty) { fill:var(--color-border-strong); }
.body-selected { fill:var(--color-primary-700); }
:global(html.dark .body-selected) { fill:var(--color-primary-300); }
.body-outline { fill:none; stroke:var(--color-border-strong); stroke-width:1; }
.part-button[aria-pressed="true"] { background:var(--color-primary-50); }
:global(html.dark .part-button[aria-pressed="true"]) { background:var(--color-primary-900); }
@media(pointer:coarse) { .part-button { min-height:40px; } }
@media(max-width:374px) { .body-figure { width:96px; } .body-layout { gap:10px; } }
</style>
