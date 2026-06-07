<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const reportIds = computed(() => {
  const idsParam = route.query.ids as string
  if (!idsParam) return []
  return idsParam.split(',').map(id => Number(id)).filter(id => !isNaN(id))
})

// Mock data structure for comparison
interface CompareResult {
  overall_trend: 'improving' | 'stable' | 'worsening'
  counts: {
    improving: number
    worsening: number
    stable: number
    attention_needed: number
  }
  reports: {
    id: number
    date: string
    title: string
  }[]
  indicators: {
    name: string
    values: Record<number, { value: string, status: 'normal' | 'high' | 'low' | 'critical' | null }>
    delta: string
    delta_type: 'improving' | 'worsening' | 'neutral'
    trend: 'improving' | 'stable' | 'worsening'
    trend_interpretation: string
    _expanded?: boolean
  }[]
  assessment: {
    summary: string
    highlights: string[]
    concerns: string[]
    recommendations: string[]
  }
}

const compareData = ref<CompareResult | null>(null)
const activeFilter = ref<'all' | 'abnormal' | 'improving' | 'worsening'>('all')

async function loadComparison() {
  if (reportIds.value.length < 2) {
    loading.value = false
    return
  }
  
  loading.value = true
  try {
    // In a real app, we would call an API like:
    // const data = await medicalReportApi.compare(reportIds.value)
    
    // For now, we mock the response based on the requirements
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    compareData.value = {
      overall_trend: 'improving',
      counts: {
        improving: 2,
        worsening: 1,
        stable: 8,
        attention_needed: 3
      },
      reports: reportIds.value.map((id, index) => ({
        id,
        date: `2026-0${5 - index}-15`,
        title: `体检报告 ${id}`
      })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()),
      indicators: [
        {
          name: '白细胞计数 (WBC)',
          values: {
            [reportIds.value[0]]: { value: '9.5', status: 'high' },
            [reportIds.value[1]]: { value: '7.2', status: 'normal' }
          },
          delta: '▼-2.3',
          delta_type: 'improving',
          trend: 'improving',
          trend_interpretation: '白细胞计数已恢复到正常范围，提示体内炎症反应已消退。',
          _expanded: false
        },
        {
          name: '血红蛋白 (Hb)',
          values: {
            [reportIds.value[0]]: { value: '135', status: 'normal' },
            [reportIds.value[1]]: { value: '138', status: 'normal' }
          },
          delta: '▲+3',
          delta_type: 'neutral',
          trend: 'stable',
          trend_interpretation: '血红蛋白水平保持稳定，处于健康范围。',
          _expanded: false
        },
        {
          name: '谷丙转氨酶 (ALT)',
          values: {
            [reportIds.value[0]]: { value: '35', status: 'normal' },
            [reportIds.value[1]]: { value: '58', status: 'high' }
          },
          delta: '▲+23',
          delta_type: 'worsening',
          trend: 'worsening',
          trend_interpretation: '谷丙转氨酶出现升高，可能与近期饮食、饮酒或药物使用有关，建议关注肝功能。',
          _expanded: false
        },
        {
          name: '空腹血糖 (GLU)',
          values: {
            [reportIds.value[0]]: { value: '5.1', status: 'normal' },
            [reportIds.value[1]]: { value: '5.3', status: 'normal' }
          },
          delta: '▲+0.2',
          delta_type: 'neutral',
          trend: 'stable',
          trend_interpretation: '血糖水平稳定，继续保持良好的饮食习惯。',
          _expanded: false
        }
      ],
      assessment: {
        summary: '总体来看，您的健康状况较上次体检有所改善。炎症指标已恢复正常，但肝功能指标出现轻度异常，需要引起注意。',
        highlights: [
          '白细胞计数恢复正常，炎症消退',
          '血糖、血脂等代谢指标保持稳定'
        ],
        concerns: [
          '谷丙转氨酶 (ALT) 升高，提示肝脏可能存在轻度损伤'
        ],
        recommendations: [
          '建议清淡饮食，减少油腻食物摄入',
          '避免熬夜和饮酒，减轻肝脏负担',
          '建议1-2个月后复查肝功能'
        ]
      }
    }
  } catch (e) {
    console.error('Failed to load comparison', e)
  } finally {
    loading.value = false
  }
}

const filteredIndicators = computed(() => {
  if (!compareData.value) return []
  
  return compareData.value.indicators.filter(ind => {
    if (activeFilter.value === 'all') return true
    if (activeFilter.value === 'abnormal') {
      return Object.values(ind.values).some(v => v.status !== 'normal' && v.status !== null)
    }
    if (activeFilter.value === 'improving') return ind.trend === 'improving'
    if (activeFilter.value === 'worsening') return ind.trend === 'worsening'
    return true
  })
})

function getStatusColor(status: string | null) {
  if (status === 'normal') return 'text-green-600 dark:text-green-400'
  if (status === 'high' || status === 'critical') return 'text-red-600 dark:text-red-400'
  if (status === 'low') return 'text-blue-600 dark:text-blue-400'
  return 'text-gray-400  italic'
}

function getTrendIcon(trend: string) {
  if (trend === 'improving') return 'ri-trending-up-line text-green-500'
  if (trend === 'worsening') return 'ri-trending-down-line text-red-500'
  return 'ri-swap-line text-gray-400'
}

function getTrendLabel(trend: string) {
  if (trend === 'improving') return '改善'
  if (trend === 'worsening') return '恶化'
  return '稳定'
}

function getDeltaColor(type: string) {
  if (type === 'improving') return 'text-green-600 dark:text-green-400'
  if (type === 'worsening') return 'text-red-600 dark:text-red-400'
  return 'text-gray-500 '
}

onMounted(() => {
  loadComparison()
})
</script>

<template>
  <div class="min-h-dvh bg-gray-50  pb-20 md:pb-8">
    <!-- Header -->
    <header class="sticky top-0 z-30 bg-white/80  backdrop-blur border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-6xl mx-auto flex items-center gap-3 px-4 h-14">
        <button @click="router.push('/report')" class="p-2 -ml-2 text-gray-600  hover:text-gray-900 dark:hover:text-gray-100 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
          <i class="ri-arrow-left-line text-xl"></i>
        </button>
        <h1 class="text-lg font-semibold text-gray-900  truncate">报告对比</h1>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <!-- Loading State -->
      <div v-if="loading" class="text-center py-20 text-gray-400 ">
        <div class="text-4xl mb-4 animate-pulse"><i class="ri-scales-line"></i></div>
        <p>正在生成对比分析...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="!compareData" class="text-center py-20 text-gray-400 ">
        <div class="text-4xl mb-4"><i class="ri-error-warning-line"></i></div>
        <p>无法加载对比数据，请确保选择了至少两份报告</p>
        <button @click="router.push('/report')" class="mt-4 btn-primary px-6 py-2">返回</button>
      </div>

      <template v-else>
        <!-- Summary Cards Row -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Card 1: Overall Trend -->
          <div class="card p-5 flex items-center gap-4">
            <div class="w-12 h-12 rounded-full flex items-center justify-center shrink-0"
              :class="{
                'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400': compareData.overall_trend === 'improving',
                'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400': compareData.overall_trend === 'worsening',
                'bg-gray-100 text-gray-600  ': compareData.overall_trend === 'stable'
              }">
              <i class="text-2xl" :class="getTrendIcon(compareData.overall_trend).split(' ')[0]"></i>
            </div>
            <div>
              <p class="text-sm text-gray-500  mb-1">总体趋势</p>
              <p class="text-lg font-bold text-gray-900 ">{{ getTrendLabel(compareData.overall_trend) }}</p>
            </div>
          </div>

          <!-- Card 2: Counts -->
          <div class="card p-5 flex flex-col justify-center">
            <p class="text-sm text-gray-500  mb-2">指标变化统计</p>
            <div class="flex items-center gap-3 text-sm font-medium">
              <span class="text-green-600 dark:text-green-400">{{ compareData.counts.improving }}项改善</span>
              <span class="text-gray-300 ">|</span>
              <span class="text-red-600 dark:text-red-400">{{ compareData.counts.worsening }}项恶化</span>
              <span class="text-gray-300 ">|</span>
              <span class="text-gray-600 ">{{ compareData.counts.stable }}项稳定</span>
            </div>
          </div>

          <!-- Card 3: Attention Needed -->
          <div class="card p-5 flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400 flex items-center justify-center shrink-0">
              <i class="ri-error-warning-fill text-2xl"></i>
            </div>
            <div>
              <p class="text-sm text-gray-500  mb-1">必看项</p>
              <p class="text-lg font-bold text-gray-900 ">
                <span v-if="compareData.counts.attention_needed > 0" class="text-yellow-600 dark:text-yellow-500">{{ compareData.counts.attention_needed }}项需关注</span>
                <span v-else class="text-green-600 dark:text-green-500">全部良好</span>
              </p>
            </div>
          </div>
        </div>

        <!-- Indicator Comparison Table Section -->
        <div class="card overflow-hidden">
          <!-- Filter Tabs -->
          <div class="border-b border-gray-100 dark:border-gray-800 px-4 py-3 overflow-x-auto hide-scrollbar flex gap-2">
            <button @click="activeFilter = 'all'" class="px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors"
              :class="activeFilter === 'all' ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400' : 'text-gray-600  hover:bg-gray-50 dark:hover:bg-gray-800'">
              全部指标
            </button>
            <button @click="activeFilter = 'abnormal'" class="px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors"
              :class="activeFilter === 'abnormal' ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400' : 'text-gray-600  hover:bg-gray-50 dark:hover:bg-gray-800'">
              异常项
            </button>
            <button @click="activeFilter = 'improving'" class="px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors"
              :class="activeFilter === 'improving' ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400' : 'text-gray-600  hover:bg-gray-50 dark:hover:bg-gray-800'">
              改善项
            </button>
            <button @click="activeFilter = 'worsening'" class="px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors"
              :class="activeFilter === 'worsening' ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400' : 'text-gray-600  hover:bg-gray-50 dark:hover:bg-gray-800'">
              恶化项
            </button>
          </div>

          <!-- Table -->
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse min-w-[600px]">
              <thead>
                <tr class="bg-gray-50  text-xs text-gray-500  uppercase tracking-wider">
                  <th class="p-4 font-medium">指标名称</th>
                  <th v-for="report in compareData.reports" :key="report.id" class="p-4 font-medium">{{ report.date }}</th>
                  <th class="p-4 font-medium">变化</th>
                  <th class="p-4 font-medium">趋势</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
                <template v-for="(ind, idx) in filteredIndicators" :key="idx">
                  <!-- Main Row -->
                  <tr class="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 cursor-pointer transition-colors group"
                    @click="ind._expanded = !ind._expanded">
                    <td class="p-4">
                      <div class="flex items-center gap-2">
                        <i class="ri-arrow-right-s-line text-gray-400 transition-transform duration-200" :class="{ 'rotate-90': ind._expanded }"></i>
                        <span class="font-medium text-gray-900  text-sm">{{ ind.name }}</span>
                      </div>
                    </td>
                    <td v-for="report in compareData.reports" :key="report.id" class="p-4">
                      <span class="text-sm font-medium" :class="getStatusColor(ind.values[report.id]?.status)">
                        {{ ind.values[report.id]?.value || '未检测' }}
                      </span>
                    </td>
                    <td class="p-4">
                      <span class="text-sm font-medium" :class="getDeltaColor(ind.delta_type)">{{ ind.delta }}</span>
                    </td>
                    <td class="p-4">
                      <div class="flex items-center gap-1.5">
                        <i :class="getTrendIcon(ind.trend)"></i>
                        <span class="text-sm text-gray-700 ">{{ getTrendLabel(ind.trend) }}</span>
                      </div>
                    </td>
                  </tr>
                  <!-- Expanded Interpretation Row -->
                  <tr v-if="ind._expanded" class="bg-gray-50/50 ">
                    <td :colspan="compareData.reports.length + 3" class="p-4 pt-0">
                      <div class="ml-6 p-4 bg-white  rounded-lg border border-gray-100 dark:border-gray-700 shadow-sm flex items-start gap-3">
                        <i class="ri-robot-line text-primary-500 text-lg mt-0.5"></i>
                        <div>
                          <p class="text-xs font-medium text-gray-500  mb-1">AI 趋势解读</p>
                          <p class="text-sm text-gray-700  leading-relaxed">{{ ind.trend_interpretation }}</p>
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
                <tr v-if="filteredIndicators.length === 0">
                  <td :colspan="compareData.reports.length + 3" class="p-8 text-center text-gray-500  text-sm">
                    没有找到符合条件的指标
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Overall Assessment Section -->
        <div class="card p-6 border-t-4"
          :class="{
            'border-t-green-500': compareData.overall_trend === 'improving',
            'border-t-red-500': compareData.overall_trend === 'worsening',
            'border-t-gray-400': compareData.overall_trend === 'stable'
          }">
          <div class="flex items-center gap-2 mb-4">
            <i class="ri-file-list-3-line text-xl text-gray-700 "></i>
            <h2 class="text-lg font-bold text-gray-900 ">综合评估报告</h2>
          </div>
          
          <p class="text-gray-700  leading-relaxed mb-6 text-sm md:text-base">
            {{ compareData.assessment.summary }}
          </p>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Highlights & Concerns -->
            <div class="space-y-6">
              <div v-if="compareData.assessment.highlights.length > 0">
                <h3 class="text-sm font-semibold text-green-600 dark:text-green-400 mb-3 flex items-center gap-1.5">
                  <i class="ri-thumb-up-line"></i> 改善亮点
                </h3>
                <ul class="space-y-2">
                  <li v-for="(item, idx) in compareData.assessment.highlights" :key="idx" class="flex items-start gap-2 text-sm text-gray-700 ">
                    <i class="ri-checkbox-circle-fill text-green-500 mt-0.5 shrink-0"></i>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>

              <div v-if="compareData.assessment.concerns.length > 0">
                <h3 class="text-sm font-semibold text-red-600 dark:text-red-400 mb-3 flex items-center gap-1.5">
                  <i class="ri-error-warning-line"></i> 需关注项
                </h3>
                <ul class="space-y-2">
                  <li v-for="(item, idx) in compareData.assessment.concerns" :key="idx" class="flex items-start gap-2 text-sm text-gray-700 ">
                    <i class="ri-error-warning-fill text-red-500 mt-0.5 shrink-0"></i>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
            </div>

            <!-- Recommendations -->
            <div v-if="compareData.assessment.recommendations.length > 0" class="bg-primary-50/50 dark:bg-primary-900/10 rounded-xl p-5 border border-primary-100 dark:border-primary-900/30">
              <h3 class="text-sm font-semibold text-primary-700 dark:text-primary-400 mb-3 flex items-center gap-1.5">
                <i class="ri-lightbulb-line"></i> 下一步建议
              </h3>
              <ul class="space-y-3">
                <li v-for="(item, idx) in compareData.assessment.recommendations" :key="idx" class="flex items-start gap-2 text-sm text-gray-700 ">
                  <span class="w-5 h-5 rounded-full bg-primary-100 dark:bg-primary-900/50 text-primary-600 dark:text-primary-400 flex items-center justify-center text-xs font-medium shrink-0 mt-0.5">{{ idx + 1 }}</span>
                  <span class="leading-relaxed">{{ item }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>
