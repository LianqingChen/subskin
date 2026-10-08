<script setup lang="ts">
/**
 * Step 3: 评估结果 + 解读
 * 简洁结果卡片，底部按钮 sticky + safe-area
 */
import { computed } from 'vue'
import { getScoreInterpretation, getStageDescription } from '@/composables/useVasiAssessment'
import { PART_LABELS } from '@/constants/bodySites'

const props = defineProps<{
  lastAssessment: { vasiScore: number; bodySite: string; areaPercentage: number; classification: string; stage: string; imageUrl: string | null; confidence?: number; id?: number } | null
  sparklineData: number[] | null
  autoFinalized?: boolean
  patientModelVersion?: string | null
}>()

const emit = defineEmits<{ newAssessment: []; shareResult: [] }>()

const partLabel = computed(() => props.lastAssessment ? (PART_LABELS[props.lastAssessment.bodySite] || props.lastAssessment.bodySite) : '')
const interpretation = computed(() => props.lastAssessment ? getScoreInterpretation(props.lastAssessment.vasiScore) : null)
const stageDesc = computed(() => props.lastAssessment ? getStageDescription(props.lastAssessment.stage) : null)
const sparklinePoints = computed(() => {
  const d = props.sparklineData; if (!d || d.length < 2) return ''
  const maxVal = Math.max(...d)
  return d.map((v, i) => `${(i / (d.length - 1)) * 100},${30 - (v / maxVal) * 26}`).join(' ')
})
const sparklineColor = computed(() => {
  const d = props.sparklineData; if (!d || d.length < 2) return '#9ca3af'
  return d[d.length - 1] < d[0] ? '#10b981' : d[d.length - 1] > d[0] ? '#ef4444' : '#9ca3af'
})

// 评分卡左侧色条 + 病情阶段文字颜色（医学语义色，允许使用 green/red/amber）
const scoreBorderColor = computed(() => {
  const s = props.lastAssessment?.vasiScore ?? 0
  if (s < 10) return 'border-l-green-500'
  if (s < 25) return 'border-l-amber-500'
  if (s < 50) return 'border-l-orange-500'
  return 'border-l-red-500'
})

const stageColor = computed(() => {
  const st = props.lastAssessment?.stage ?? ''
  if (st === '好转') return 'text-green-600 dark:text-green-400'
  if (st === '扩散' || st === '进展期') return 'text-red-600 dark:text-red-400'
  return 'text-amber-600 dark:text-amber-400'
})
</script>

<template>
  <div class="flex flex-col min-h-0 h-full bg-gray-50 dark:bg-gray-900">

    <!-- Scrollable content -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="lastAssessment" class="px-4 pt-4 pb-2 space-y-4 max-w-lg mx-auto w-full">

        <!-- Score card -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 border-l-4 shadow-sm p-5 text-center" :class="scoreBorderColor">
          <p class="text-sm text-gray-500 dark:text-gray-400 mb-1">{{ partLabel }}</p>
          <div class="text-5xl font-bold mb-1" :class="interpretation?.color">{{ lastAssessment.vasiScore }}</div>
          <p class="text-sm font-medium" :class="interpretation?.color">VASI 评分 · {{ interpretation?.level }}</p>

          <div class="grid grid-cols-3 gap-2 mt-4">
            <div class="bg-gray-50 dark:bg-gray-800/60 rounded-lg p-2">
              <div class="text-lg font-bold text-gray-800 dark:text-gray-200">{{ lastAssessment.areaPercentage }}%</div>
              <div class="text-[10px] text-gray-400">白斑占比</div>
            </div>
            <div class="bg-gray-50 dark:bg-gray-800/60 rounded-lg p-2">
              <div class="text-lg font-bold" :class="stageColor">{{ lastAssessment.stage }}</div>
              <div class="text-[10px] text-gray-400">病情阶段</div>
            </div>
            <div class="bg-gray-50 dark:bg-gray-800/60 rounded-lg p-2">
              <div class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ lastAssessment.classification || '未分型' }}</div>
              <div class="text-[10px] text-gray-400">分型</div>
            </div>
          </div>

          <div v-if="props.sparklineData && props.sparklineData.length >= 2" class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs text-gray-400"><i class="ri-line-chart-line mr-1"></i>VASI 趋势</span>
              <span class="text-xs font-medium" :class="(props.sparklineData[props.sparklineData.length-1] < props.sparklineData[0]) ? 'text-green-600' : (props.sparklineData[props.sparklineData.length-1] > props.sparklineData[0]) ? 'text-red-600' : 'text-gray-500'">
                {{ props.sparklineData[props.sparklineData.length-1] < props.sparklineData[0] ? '↓ 改善' : props.sparklineData[props.sparklineData.length-1] > props.sparklineData[0] ? '↑ 需关注' : '→ 稳定' }}
              </span>
            </div>
            <svg class="w-full h-8" viewBox="0 0 100 30" preserveAspectRatio="none">
              <polyline :points="sparklinePoints" fill="none" :stroke="sparklineColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <p class="mt-1 text-[10px] leading-4 text-gray-400">
              <i class="ri-information-line mr-0.5" aria-hidden="true" />面积已升级为逐像素测量，与更早记录的对比仅供参考
            </p>
          </div>
        </div>

        <!-- AI interpretation -->
        <div class="space-y-2">
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
            <h3 class="text-sm font-medium text-gray-800 dark:text-gray-200 mb-0.5 flex items-center gap-1.5">
              <i class="ri-microscope-line text-primary-500"></i>评分含义
            </h3>
            <p class="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">{{ interpretation?.description }}</p>
          </div>
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
            <h3 class="text-sm font-medium text-gray-800 dark:text-gray-200 mb-0.5 flex items-center gap-1.5">
              <i class="ri-bar-chart-2-line text-primary-500"></i>阶段说明
            </h3>
            <p class="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">{{ stageDesc }}</p>
          </div>
          <div v-if="lastAssessment.confidence !== undefined && lastAssessment.confidence < 0.5" class="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-2.5 flex items-start gap-2">
            <i class="ri-error-warning-line text-amber-500 mt-0.5"></i>
            <p class="text-xs text-amber-600 dark:text-amber-400">本次评估信心度较低（{{ Math.round(lastAssessment.confidence * 100) }}%），建议在更好光照下重新拍照</p>
          </div>
          <div v-if="props.autoFinalized" class="bg-primary-50 dark:bg-primary-900 rounded-xl p-2.5 flex items-start gap-2 border border-primary-100 dark:border-primary-900">
            <i class="ri-sparkling-2-line text-primary-500 mt-0.5"></i>
            <div class="text-xs text-primary-700 dark:text-primary-300 leading-relaxed">
              <p>本次白斑识别已由 AI 共识自动确认（无需手动核对轮廓）。</p>
              <p v-if="props.patientModelVersion" class="mt-0.5 text-primary-600 dark:text-primary-400">
                患者专属识别模型 {{ props.patientModelVersion }} 参与判断，后续测评会持续自动学习提升。
              </p>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="flex flex-col items-center justify-center py-20 text-gray-400">
        <i class="ri-emotion-sad-line text-4xl mb-3"></i>
        <p>暂无评估结果</p>
        <button class="btn-ghost mt-4" @click="emit('newAssessment')">开始测评</button>
      </div>
    </div>

    <!-- Bottom actions — sticky -->
    <div v-if="lastAssessment" class="shrink-0 px-4 py-2.5 flex gap-3 bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700" style="padding-bottom: calc(0.625rem + env(safe-area-inset-bottom, 0px))">
      <button class="flex-1 btn-primary py-2.5 flex items-center justify-center gap-1.5 min-h-[44px] rounded-xl text-sm" @click="emit('shareResult')">
        <i class="ri-send-plane-line"></i>分享
      </button>
      <button class="flex-1 btn-ghost py-2.5 flex items-center justify-center gap-1.5 min-h-[44px] rounded-xl border border-gray-200 dark:border-gray-700 text-sm" @click="emit('newAssessment')">
        <i class="ri-add-line"></i>继续测评
      </button>
    </div>
  </div>
</template>
