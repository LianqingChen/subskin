<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ContributionDistribution } from '@/types/contribution'
const props = defineProps<{ distribution: ContributionDistribution | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const mode = ref<'parts' | 'matrix'>('parts')
const maximum = computed(() => Math.max(1, ...(props.distribution?.rows.map(x => x.count ?? 0) ?? [])))
const hasData = computed(() => props.distribution?.rows.some(x => (x.count ?? 0) > 0) ?? false)
</script>

<template>
  <section class="card p-5 dark:bg-gray-800 md:p-6" aria-labelledby="matrix-title">
    <div class="flex flex-wrap items-start justify-between gap-3"><div><h2 id="matrix-title" class="text-lg font-semibold md:text-xl">每一种情况，都值得被看见</h2><p class="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400">不仅积累数量，也逐步补齐不同部位、类型和拍摄条件。</p></div><div class="flex rounded-xl bg-gray-100 p-1 dark:bg-gray-900" role="group" aria-label="数据分布展示方式"><button v-for="item in ([{ value: 'parts', label: '部位分布' }, { value: 'matrix', label: '覆盖矩阵' }] as const)" :key="item.value" type="button" class="min-h-11 rounded-lg px-3 text-xs transition-colors" :class="mode === item.value ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'" :aria-pressed="mode === item.value" @click="mode = item.value">{{ item.label }}</button></div></div>
    <div v-if="loading" role="status" class="mt-5 h-40 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-700"><span class="sr-only">加载分布中</span></div>
    <div v-else-if="error" role="alert" class="mt-5 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">分布数据加载失败</p><button type="button" class="btn-ghost mt-2 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else-if="distribution">
      <p v-if="distribution.status === 'suppressed'" role="note" class="mt-5 rounded-xl bg-gray-50 p-4 text-xs leading-6 text-gray-500 dark:bg-gray-900/40 dark:text-gray-400"><i class="ri-shield-keyhole-line mr-1" aria-hidden="true"></i>当前分布含小样本，为保护贡献者，暂不公开各部位数量。随着更多有效贡献积累，分布将逐步开放。</p>
      <p v-else-if="!hasData" class="mt-5 rounded-xl bg-primary-50 p-4 text-xs leading-6 text-primary-700 dark:bg-primary-900/20 dark:text-primary-300">当前有效授权库正在积累。已有上传资料通过授权与采纳后，才会进入这里的分布。</p>
      <ul v-if="mode === 'parts'" class="mt-5 grid gap-x-8 gap-y-4 md:grid-cols-2"><li v-for="row in distribution.rows" :key="row.code"><div class="mb-1.5 flex items-center justify-between gap-2 text-xs"><span class="text-gray-600 dark:text-gray-300">{{ row.label }}</span><span class="tabular-nums text-gray-400">{{ row.count === null ? '暂不公开' : `${row.count} 张` }}</span></div><div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-700"><div class="h-full rounded-full bg-primary-400 dark:bg-primary-500" :style="{ width: `${100 * (row.count ?? 0) / maximum}%` }"></div></div></li></ul>
      <div v-else class="mt-5 overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-700" tabindex="0" aria-label="部位和医生分型矩阵，可横向滚动">
        <table class="w-full min-w-[540px] border-collapse text-xs"><caption class="sr-only">按主部位与医生分型统计的有效图片；尚无临床参考的格显示未统计。</caption><thead><tr class="bg-gray-50 dark:bg-gray-900/50"><th scope="col" class="px-3 py-4 text-left font-medium">主部位</th><th v-for="column in distribution.types.columns" :key="column" scope="col" class="px-3 py-4 text-center font-medium">{{ column }}</th></tr></thead><tbody><tr v-for="row in distribution.rows" :key="row.code" class="border-t border-gray-100 dark:border-gray-700"><th scope="row" class="px-3 py-3 text-left font-normal text-gray-600 dark:text-gray-300">{{ row.label }}</th><td v-for="column in distribution.types.columns" :key="column" class="px-3 py-3 text-center" :class="column === '待医生分型' ? 'text-primary-700 dark:text-primary-300' : 'text-gray-400 dark:text-gray-500'">{{ column === '待医生分型' ? row.count === null ? '暂不公开' : row.count : '未统计' }}</td></tr></tbody></table>
      </div>
      <p class="mt-4 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ mode === 'matrix' ? distribution.types.note : distribution.note }} 正常皮肤与相似疾病将使用独立对照分类。</p>
      <details class="mt-5 border-t border-gray-100 pt-4 dark:border-gray-700"><summary class="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 text-sm font-medium">五维覆盖进度<i class="ri-arrow-down-s-line" aria-hidden="true"></i></summary><div class="mt-3 flex flex-wrap gap-2"><span v-for="dimension in distribution.dimensions" :key="dimension.name" class="rounded-full bg-gray-50 px-3 py-2 text-xs text-gray-500 dark:bg-gray-900/40 dark:text-gray-400">{{ dimension.name }} · {{ dimension.status === 'available' ? '已有维度' : '待补充' }}</span></div><p class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ distribution.coverage.note }}。每个未知值都会保留，不用猜测填补缺口。</p></details>
    </template>
  </section>
</template>
