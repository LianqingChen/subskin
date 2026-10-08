<script setup lang="ts">
/**
 * 维度提及分布条 —— 替代医院级平均分（v3）。
 *
 * 为什么不用平均分：单一分数会被截图当作「医院得分」，构成事实上的评比与排名口实
 * （《广告法》第 16 条禁止医疗机构之间比较）。计数型分布 + 「没体验过」档既诚实，
 * 又天然抑制刷分（参考名医汇「暂未评价」档）。
 */
import { computed } from 'vue'
import { EXPERIENCE_DIMENSIONS } from '@/utils/reviewRiskRules'
import type { DimensionDistribution } from '@/types/hospital'

const props = defineProps<{
  items: DimensionDistribution[]
  /** 评价总数（用于标题文案；分布本身按维度各自计数） */
  reviewCount?: number
}>()

const QUESTION: Record<string, string> = Object.fromEntries(
  EXPERIENCE_DIMENSIONS.map(item => [item.key, item.question]),
)

const rows = computed(() => (props.items ?? [])
  .filter(item => item.total > 0)
  .map(item => {
    const answered = Math.max(item.satisfied + item.neutral + item.unsatisfied, 1)
    return {
      ...item,
      question: QUESTION[item.dimension] ?? '',
      satisfiedPct: Math.round((item.satisfied / answered) * 100),
      neutralPct: Math.round((item.neutral / answered) * 100),
      unsatisfiedPct: Math.round((item.unsatisfied / answered) * 100),
    }
  }))
</script>

<template>
  <section v-if="rows.length" aria-labelledby="hospital-dimension-title" class="rounded-2xl bg-gray-50 p-4 dark:bg-gray-800">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h3 id="hospital-dimension-title" class="text-sm font-medium">
        病友怎么说<template v-if="reviewCount"> · 共 {{ reviewCount }} 条评价</template>
      </h3>
      <span class="text-[11px] text-gray-400">按维度分别计数，不做合并评分</span>
    </div>

    <ul class="mt-3 space-y-3">
      <li v-for="row in rows" :key="row.dimension">
        <div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <span class="text-xs font-medium text-gray-700 dark:text-gray-200">{{ row.dimension }}</span>
          <span class="text-[11px] tabular-nums text-gray-500 dark:text-gray-400">
            满意 {{ row.satisfied }} · 一般 {{ row.neutral }} · 不满意 {{ row.unsatisfied }} · 没体验过 {{ row.na }}
          </span>
        </div>
        <div class="mt-1 flex h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700" role="img"
             :aria-label="`${row.dimension}：满意 ${row.satisfied} 条，一般 ${row.neutral} 条，不满意 ${row.unsatisfied} 条，没体验过 ${row.na} 条`">
          <span class="h-full bg-primary-500" :style="{ width: row.satisfiedPct + '%' }" />
          <span class="h-full bg-amber-400" :style="{ width: row.neutralPct + '%' }" />
          <span class="h-full bg-rose-400" :style="{ width: row.unsatisfiedPct + '%' }" />
        </div>
        <p v-if="row.question" class="mt-1 text-[11px] leading-5 text-gray-400">{{ row.question }}</p>
      </li>
    </ul>

    <p class="mt-3 text-[11px] leading-5 text-gray-400">
      以上为病友个人的就医体验计数，<strong>不代表医疗水平评价</strong>，也不算疗效；这里按历史评价条数展示；去重后的近一年单项分布与排序请查看「体验评价」。
    </p>
  </section>
</template>
