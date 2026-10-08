<script setup lang="ts">
import { computed, ref } from 'vue'
import { compactContributionCount, contributionTiles } from '@/utils/contribution-charts'
import type { ContributionOverview, MyContributions } from '@/types/contribution'
const props = defineProps<{ overview: ContributionOverview | null; summary: MyContributions | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const highlight = ref(true)
const total = computed(() => props.overview?.images.status === 'available' ? props.overview.images.value : null)
const mine = computed(() => props.summary?.images.value ?? null)
const safeShare = computed(() => total.value !== null && mine.value !== null && mine.value <= total.value && (total.value - mine.value === 0 || total.value - mine.value >= 5))
const chart = computed(() => contributionTiles(total.value ?? 0, safeShare.value && highlight.value ? mine.value ?? 0 : 0))
const reading = computed(() => total.value === null ? '有效图片总量暂不公开，不推算个人占比' : `当前有效图片${total.value}张，每格最多${chart.value.unit}张${safeShare.value && mine.value !== null ? `，其中我的${mine.value}张` : ''}`)
const contributors = computed(() => props.overview?.contributors.status === 'available' ? `${props.overview.contributors.value} 位图片贡献者` : props.overview?.contributors.status === 'suppressed' ? '贡献者规模暂不公开' : '')
</script>

<template>
  <section id="community-results" class="card min-w-0 scroll-mt-24 p-5 dark:bg-gray-800 sm:p-6" aria-labelledby="waffle-title">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 id="waffle-title" class="text-lg font-semibold">我们共同积累</h2><span v-if="contributors" class="rounded-full bg-primary-50 px-3 py-1 text-xs text-primary-700 dark:bg-primary-900 dark:text-primary-300">{{ contributors }}</span></div>
    <div v-if="loading" role="status" class="h-64 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-700"><span class="sr-only">正在加载共同成果</span></div>
    <div v-else-if="error" role="alert" class="py-8 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">共同成果暂时没有加载成功</p><button type="button" class="btn-ghost mt-3 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else-if="overview">
      <div class="flex flex-wrap items-baseline gap-3"><strong class="text-4xl font-semibold tabular-nums">{{ total === null ? '暂不公开' : compactContributionCount(total) }}<span v-if="total !== null" class="ml-1 text-xs font-normal text-gray-500 dark:text-gray-400">张</span></strong><p class="text-sm text-gray-500 dark:text-gray-400">有效图片<span v-if="mine !== null" class="ml-1 text-primary-700 dark:text-primary-300">· {{ total !== null && mine <= total ? `其中有你的 ${mine} 张` : `我的有效图片 ${mine} 张` }}</span></p></div>
      <div v-if="chart.tiles.length" class="waffle mt-5" role="img" :aria-label="reading"><span v-for="(tile, index) in chart.tiles" :key="index" class="waffle-cell"><span class="waffle-community" :style="{ height: `${tile.fill * 100}%` }"></span><span v-if="tile.mine > 0" class="waffle-mine" :style="{ height: `${tile.mineFill * 100}%` }"></span></span></div>
      <div v-else class="mt-5 rounded-2xl bg-gray-50 px-4 py-7 dark:bg-gray-900" role="status"><div class="mx-auto flex max-w-44 flex-wrap justify-center gap-2" aria-hidden="true"><span v-for="n in 12" :key="n" class="h-4 w-4 rounded-sm bg-gray-200 dark:bg-gray-700"></span></div><p class="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">{{ total === null ? '积累图暂不公开' : '有效图片库正在积累' }}</p><p class="mt-2 text-center text-xs leading-6 text-gray-500 dark:text-gray-400">{{ total === null ? '小样本不公开，个人贡献仍可单独查看。' : '每份资料经过授权、去重与采纳后，才进入这里。' }}</p></div>
      <div v-if="total !== null && total > 0" class="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400"><span>每格最多 {{ chart.unit.toLocaleString('zh-CN') }} 张 · 尾格按实际数量填充</span><label v-if="safeShare" class="flex min-h-11 items-center gap-2"><input v-model="highlight" type="checkbox" class="accent-primary-600" />标出我的贡献</label></div>
      <div v-if="chart.tiles.length" class="mt-1 flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400"><span v-if="safeShare" class="inline-flex items-center gap-2"><b class="waffle-swatch waffle-mine"></b>我的贡献</span><span class="inline-flex items-center gap-2"><b class="waffle-swatch waffle-community"></b>{{ safeShare ? '其他有效图片' : '有效图片' }}</span></div>
      <p class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">格子代表图片，不代表人数；小份额按真实面积显示，个人数量始终单独标明。</p>
      <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-gray-100 pt-4 text-xs text-gray-500 dark:border-gray-700 dark:text-gray-400"><span><i class="ri-team-line mr-1 text-primary-600 dark:text-primary-400" aria-hidden="true"></i>{{ overview.users.value?.toLocaleString('zh-CN') }} 个有效注册账号</span><span>本人已核对：{{ overview.checked.status === 'available' ? `${overview.checked.value}张` : '暂不公开' }}</span></div>
      <details class="mt-2 text-xs text-gray-500 dark:text-gray-400"><summary class="min-h-11 cursor-pointer">查看统计口径与质量进度</summary><p class="leading-6">{{ overview.images.note }}。账号数量不等于独立病友数。</p><p class="mt-2 leading-6">医生参考：{{ overview.doctor_ratio.note }}。持续随访：{{ overview.followup.note }}。</p><p class="mt-2">更新时间：<time :datetime="overview.updated_at">{{ new Date(overview.updated_at).toLocaleString('zh-CN') }}</time></p></details>
    </template>
  </section>
</template>

<style scoped>
.waffle { display:grid; grid-template-columns:repeat(14,minmax(0,1fr)); gap:4px; }
.waffle-cell { position:relative; aspect-ratio:1; overflow:hidden; border-radius:3px; background:var(--color-surface); }
.waffle-community { background:var(--color-primary-200); }
.waffle-mine { background:var(--color-primary-700); }
.waffle-cell > span { position:absolute; bottom:0; left:0; width:100%; }
.waffle-swatch { position:static; display:inline-block; height:10px; width:10px; border-radius:2px; }
:global(html.dark .waffle-community) { background:var(--color-primary-600); }
:global(html.dark .waffle-mine) { background:var(--color-primary-300); }
@media(min-width:640px) { .waffle { grid-template-columns:repeat(20,minmax(0,1fr)); } }
</style>
