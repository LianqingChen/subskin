<script setup lang="ts">
import { computed } from 'vue'
import type { InterpretationResult } from '@/api/medical-report'

const props = defineProps<{
  interpretation: InterpretationResult
}>()

const riskLabel = computed(() => {
  const map: Record<string, string> = { low: '低风险', medium: '中等风险', high: '高风险', critical: '危急' }
  return map[props.interpretation.risk_level] || '未知'
})

const riskClass = computed(() => {
  const map: Record<string, string> = {
    low: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  }
  return map[props.interpretation.risk_level] || ''
})

const riskIcon = computed(() => {
  const map: Record<string, string> = {
    low: 'ri-checkbox-circle-fill',
    medium: 'ri-error-warning-fill',
    high: 'ri-alert-fill',
    critical: 'ri-alert-fill',
  }
  return map[props.interpretation.risk_level] || 'ri-information-fill'
})

const totalIndicators = computed(() => {
  if (props.interpretation.sections?.length) {
    return props.interpretation.sections.reduce((sum, s) => sum + s.indicator_count, 0)
  }
  return props.interpretation.parsed_indicators?.length || 0
})

const totalAbnormal = computed(() => {
  if (props.interpretation.sections?.length) {
    return props.interpretation.sections.reduce((sum, s) => sum + s.abnormal_count, 0)
  }
  return props.interpretation.abnormal_items?.length || 0
})

const statusLabel = (s: string) => {
  const map: Record<string, string> = { high: '偏高', low: '偏低', critical: '显著异常' }
  return map[s] || s
}

function toggleSource(item: any) {
  item._showSource = !item._showSource
}
</script>

<template>
  <div class="space-y-4">
    <!-- Layer 1: Top summary card -->
    <div class="card p-5">
      <div class="flex items-start justify-between mb-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-900  mb-1">总体评估</h2>
          <div class="flex items-center gap-3 text-sm">
            <span class="text-gray-500 ">共检测 <span class="font-medium text-gray-900 ">{{ totalIndicators }}</span> 项指标</span>
            <span class="text-gray-300 ">|</span>
            <span class="text-gray-500 ">发现 <span class="font-medium text-red-500">{{ totalAbnormal }}</span> 项异常</span>
          </div>
        </div>
        <div class="px-3 py-1.5 rounded-full flex items-center gap-1.5 font-medium text-sm" :class="riskClass">
          <i :class="riskIcon"></i> {{ riskLabel }}
        </div>
      </div>
      
      <!-- Extracted patient info -->
      <div v-if="interpretation.extracted_patient_info" class="flex flex-wrap items-center gap-x-4 gap-y-1 mb-3 text-xs text-gray-500  bg-gray-50  rounded-lg px-3 py-2">
        <template v-if="interpretation.extracted_patient_info.name">
          <span class="flex items-center gap-1">
            <i class="ri-user-line"></i> {{ interpretation.extracted_patient_info.name }}
          </span>
        </template>
        <template v-if="interpretation.extracted_patient_info.gender || interpretation.extracted_patient_info.age != null">
          <span>
            {{ interpretation.extracted_patient_info.gender ? (interpretation.extracted_patient_info.gender === '男' ? '男' : '女') : '' }}
            {{ interpretation.extracted_patient_info.age != null ? interpretation.extracted_patient_info.age + '岁' : '' }}
          </span>
        </template>
        <template v-if="interpretation.extracted_patient_info.exam_date">
          <span class="flex items-center gap-1">
            <i class="ri-calendar-line"></i> 体检日期: {{ interpretation.extracted_patient_info.exam_date }}
          </span>
        </template>
        <span v-if="interpretation.extracted_patient_info.confidence >= 0.8" class="px-1.5 py-0.5 rounded text-[10px] bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
          <i class="ri-check-line mr-0.5"></i>AI提取
        </span>
      </div>

      <p class="text-gray-700  leading-relaxed text-sm bg-gray-50  p-3 rounded-lg">
        {{ interpretation.summary }}
      </p>
    </div>

    <!-- Layer 2 & 3: Section cards -->
    <template v-if="interpretation.sections?.length">
      <div class="space-y-3">
        <div v-for="section in interpretation.sections" :key="section.section_name"
          class="card overflow-hidden transition-all"
          :class="{
            'border-l-4 border-l-red-500': section.risk === 'red',
            'border-l-4 border-l-yellow-500': section.risk === 'yellow',
            'border-l-4 border-l-green-500': section.risk === 'green',
          }"
        >
          <!-- Section header (Layer 2) -->
          <div class="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            @click="section._expanded = !section._expanded">
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-base font-semibold text-gray-900 ">{{ section.section_name }}</h3>
              <div class="flex items-center gap-3">
                <span class="text-sm text-gray-500 ">
                  {{ section.indicator_count }}项指标
                  <template v-if="section.abnormal_count > 0">
                    <span v-if="section.risk === 'red'" class="text-red-500 font-medium ml-1"><i class="ri-error-warning-fill"></i> {{ section.abnormal_count }}项异常</span>
                    <span v-else class="text-yellow-500 font-medium ml-1">{{ section.abnormal_count }}项异常</span>
                  </template>
                  <span v-else class="text-green-500 font-medium ml-1"><i class="ri-check-line"></i> 全部正常</span>
                </span>
                <i class="text-gray-400 transition-transform duration-200"
                  :class="section._expanded ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'"></i>
              </div>
            </div>
            <p class="text-sm text-gray-600 ">{{ section.section_summary }}</p>
          </div>

          <!-- Expanded detail (Layer 3) -->
          <div v-if="section._expanded" class="border-t border-gray-100 dark:border-gray-700 bg-gray-50/50 ">
            
            <!-- Abnormal items -->
            <div v-if="section.abnormal_items?.length" class="p-4 space-y-4">
              <h4 class="text-xs font-medium text-gray-400  uppercase tracking-wider">异常指标解读</h4>
              
              <div v-for="item in section.abnormal_items" :key="item.indicator_name"
                class="bg-white  rounded-lg p-4 shadow-sm border border-gray-100 dark:border-gray-700">
                
                <div class="flex items-center gap-3 flex-wrap mb-3">
                  <span class="font-semibold text-gray-900 ">{{ item.indicator_name }}</span>
                  <span class="text-sm text-gray-600 ">{{ item.value }}</span>
                  <span class="px-2 py-0.5 rounded text-xs font-medium"
                    :class="item.status === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'">
                    {{ statusLabel(item.status) }}
                  </span>
                </div>
                
                <p class="text-sm text-gray-700  leading-relaxed mb-3">{{ item.interpretation }}</p>
                
                <!-- Traceability -->
                <div v-if="item.source_indicators?.length || item.source_text_excerpt" class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                  <button @click="toggleSource(item)" class="flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 font-medium">
                    <i :class="(item as any)._showSource ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'"></i>
                    数据来源
                    <span v-if="item.confidence" class="ml-2 px-1.5 py-0.5 rounded text-[10px]"
                      :class="{
                        'bg-green-100 text-green-700': item.confidence >= 0.8,
                        'bg-yellow-100 text-yellow-700': item.confidence >= 0.6 && item.confidence < 0.8,
                        'bg-orange-100 text-orange-700': item.confidence < 0.6
                      }">
                      <i v-if="item.confidence < 0.6" class="ri-error-warning-line mr-0.5"></i>
                      {{ item.confidence >= 0.8 ? '高置信度' : (item.confidence >= 0.6 ? '中等置信度' : '低置信度，建议咨询医生核实') }}
                    </span>
                  </button>
                  
                  <div v-if="(item as any)._showSource" class="mt-2 p-3 bg-gray-50  rounded text-xs space-y-2">
                    <div v-if="item.source_indicators?.length">
                      <div class="text-gray-500 mb-1">提取的指标数据：</div>
                      <table class="w-full text-left">
                        <tr v-for="src in item.source_indicators" :key="src.indicator_name" class="border-b border-gray-200 dark:border-gray-700 last:border-0">
                          <td class="py-1 text-gray-700 ">{{ src.indicator_name }}</td>
                          <td class="py-1 font-medium">{{ src.value }}</td>
                          <td class="py-1 text-gray-500">{{ src.ref_range }}</td>
                        </tr>
                      </table>
                    </div>
                    <div v-if="item.source_text_excerpt">
                      <div class="text-gray-500 mb-1">报告原文片段：</div>
                      <blockquote class="border-l-2 border-gray-300 dark:border-gray-600 pl-2 text-gray-600  italic">
                        "{{ item.source_text_excerpt }}"
                      </blockquote>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Normal indicators -->
            <div v-if="section.indicators?.length" class="p-4 pt-0">
              <h4 class="text-xs font-medium text-gray-400  uppercase tracking-wider mb-2 mt-2">全部指标</h4>
              <div class="bg-white  rounded-lg border border-gray-100 dark:border-gray-700 overflow-hidden">
                <table class="w-full text-sm text-left">
                  <thead class="bg-gray-50  text-gray-500  text-xs">
                    <tr>
                      <th class="px-3 py-2 font-medium">指标名称</th>
                      <th class="px-3 py-2 font-medium">结果</th>
                      <th class="px-3 py-2 font-medium">参考值</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
                    <tr v-for="ind in section.indicators" :key="ind.name" class="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                      <td class="px-3 py-2 text-gray-700 ">
                        <span class="inline-block w-1.5 h-1.5 rounded-full mr-1.5"
                          :class="{
                            'bg-red-500': ind.status === 'high' || ind.status === 'low' || ind.status === 'critical',
                            'bg-green-400': ind.status === 'normal',
                            'bg-gray-300': !ind.status,
                          }"></span>
                        {{ ind.name }}
                      </td>
                      <td class="px-3 py-2 font-medium" :class="ind.status !== 'normal' && ind.status ? 'text-red-500' : 'text-gray-900 '">
                        {{ ind.value }} {{ ind.unit }}
                      </td>
                      <td class="px-3 py-2 text-gray-500">{{ ind.ref_range }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Recommendations -->
    <div v-if="interpretation.recommendations?.length" class="card p-5">
      <div class="flex items-center gap-2 mb-4">
        <i class="ri-lightbulb-line text-primary-500 text-lg"></i>
        <h3 class="text-base font-semibold text-gray-900 ">改善建议</h3>
      </div>
      <div class="space-y-3">
        <div v-for="(rec, idx) in interpretation.recommendations" :key="idx"
          class="flex items-start gap-3 p-3 rounded-lg bg-primary-50/50 dark:bg-primary-900/10">
          <span class="w-6 h-6 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 flex items-center justify-center text-xs font-medium shrink-0 mt-0.5">{{ idx + 1 }}</span>
          <p class="text-sm text-gray-700  leading-relaxed">{{ rec.content || rec }}</p>
        </div>
      </div>
    </div>

    <!-- Disclaimer -->
    <div class="text-center text-xs text-gray-400  py-4">
      <i class="ri-error-warning-line"></i> {{ interpretation.disclaimer || '本解读仅供参考，不构成医疗诊断建议。如有异常指标，请咨询专业医生。' }}
    </div>
  </div>
</template>