<script setup lang="ts">
import type { TreatmentShare } from '@/types'

defineProps<{
  treatment: TreatmentShare
}>()

function formatScore(t: { vasi_score: number; final_vasi_score?: number | null }): string {
  const score = t.final_vasi_score ?? t.vasi_score
  return Number(score).toFixed(1)
}
</script>

<template>
  <!-- 详情页结构化信息卡 -->
  <div class="rounded-xl border border-blue-100 dark:border-blue-900/60 bg-blue-50/50 dark:bg-blue-900/20 overflow-hidden">
    <div class="flex items-center gap-2 px-4 py-2.5 bg-blue-100/60 dark:bg-blue-900/40">
      <i class="ri-capsule-line text-blue-600 dark:text-blue-300"></i>
      <span class="text-sm font-semibold text-blue-700 dark:text-blue-300">治疗方案信息</span>
      <span class="ml-auto text-[10px] text-blue-500/80 dark:text-blue-300/70">白友真实经验分享</span>
    </div>

    <div class="px-4 py-3 space-y-2.5">
      <!-- 治疗方案 -->
      <div class="flex items-start gap-2.5">
        <i class="ri-medicine-bottle-line text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0"></i>
        <div class="min-w-0">
          <div class="text-[11px] text-gray-400 dark:text-gray-500 mb-0.5">治疗方案</div>
          <div class="text-[13px] text-gray-800 dark:text-gray-200 leading-relaxed break-words">{{ treatment.method }}</div>
        </div>
      </div>

      <!-- 持续周期 / 费用区间 -->
      <div class="flex flex-wrap gap-x-6 gap-y-2.5">
        <div v-if="treatment.duration" class="flex items-start gap-2.5">
          <i class="ri-time-line text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0"></i>
          <div>
            <div class="text-[11px] text-gray-400 dark:text-gray-500 mb-0.5">持续周期</div>
            <div class="text-[13px] text-gray-800 dark:text-gray-200">{{ treatment.duration }}</div>
          </div>
        </div>
        <div v-if="treatment.cost_range" class="flex items-start gap-2.5">
          <i class="ri-money-cny-circle-line text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0"></i>
          <div>
            <div class="text-[11px] text-gray-400 dark:text-gray-500 mb-0.5">费用区间</div>
            <div class="text-[13px] text-gray-800 dark:text-gray-200">{{ treatment.cost_range }}</div>
          </div>
        </div>
      </div>

      <!-- 效果评价 -->
      <div v-if="treatment.effect_rating" class="flex items-start gap-2.5">
        <i class="ri-star-line text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0"></i>
        <div>
          <div class="text-[11px] text-gray-400 dark:text-gray-500 mb-0.5">效果自评</div>
          <div class="flex items-center gap-1">
            <i v-for="n in 5" :key="n"
              class="text-sm"
              :class="n <= (treatment.effect_rating || 0) ? 'ri-star-fill text-amber-400' : 'ri-star-line text-gray-300 dark:text-gray-600'"></i>
            <span class="text-[12px] text-gray-500 dark:text-gray-400 ml-1">{{ treatment.effect_rating }}/5</span>
          </div>
        </div>
      </div>

      <!-- 副作用 -->
      <div v-if="treatment.side_effects && treatment.side_effects.length > 0" class="flex items-start gap-2.5">
        <i class="ri-alert-line text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0"></i>
        <div class="min-w-0">
          <div class="text-[11px] text-gray-400 dark:text-gray-500 mb-1">副作用</div>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="s in treatment.side_effects" :key="s"
              class="text-[11px] px-2 py-0.5 rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300">
              {{ s }}
            </span>
          </div>
        </div>
      </div>

      <!-- VASI 前后对比 -->
      <div v-if="treatment.vasi_assessments && treatment.vasi_assessments.length > 0" class="flex items-start gap-2.5">
        <i class="ri-line-chart-line text-blue-500 dark:text-blue-400 mt-0.5 flex-shrink-0"></i>
        <div class="flex-1 min-w-0">
          <div class="text-[11px] text-gray-400 dark:text-gray-500 mb-1">VASI 评估对比</div>
          <div class="flex flex-wrap items-center gap-2">
            <template v-for="(v, idx) in treatment.vasi_assessments" :key="v.id">
              <div class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600">
                <div>
                  <div class="text-[10px] text-gray-400 dark:text-gray-500">{{ v.assessment_date || '未知日期' }}<template v-if="v.body_site"> · {{ v.body_site }}</template></div>
                  <div class="text-[13px] font-semibold text-gray-800 dark:text-gray-200">VASI {{ formatScore(v) }}</div>
                </div>
              </div>
              <i v-if="idx < (treatment.vasi_assessments.length - 1)" class="ri-arrow-right-line text-gray-400"></i>
            </template>
            <span v-if="treatment.vasi_assessments.length === 2" class="text-[11px] font-medium"
              :class="(treatment.vasi_assessments[1].final_vasi_score ?? treatment.vasi_assessments[1].vasi_score) <= (treatment.vasi_assessments[0].final_vasi_score ?? treatment.vasi_assessments[0].vasi_score) ? 'text-green-600 dark:text-green-400' : 'text-orange-500'">
              {{
                ((treatment.vasi_assessments[1].final_vasi_score ?? treatment.vasi_assessments[1].vasi_score) -
                 (treatment.vasi_assessments[0].final_vasi_score ?? treatment.vasi_assessments[0].vasi_score)).toFixed(1)
              }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
