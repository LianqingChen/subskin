<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { vasiApi } from '@/api/vasi'
import type { VasiAssessmentResponse } from '@/api/vasi'
import { PART_LABELS } from '@/constants/bodySites'
import { usePrivacyStore } from '@/stores/privacy'
import BeforeAfterSlider from '@/components/tracker/BeforeAfterSlider.vue'
import { toProtectedFileUrl } from '@/utils/file-url'

const route = useRoute()
const router = useRouter()
const privacyStore = usePrivacyStore()

const loading = ref(true)
const errorMsg = ref('')
const before = ref<VasiAssessmentResponse | null>(null)
const after = ref<VasiAssessmentResponse | null>(null)

const ids = computed(() => {
  const raw = (route.query.ids as string) || ''
  return raw.split(',').map(s => Number(s)).filter(n => Number.isFinite(n) && n > 0)
})

async function load() {
  loading.value = true
  errorMsg.value = ''
  if (ids.value.length < 2) {
    errorMsg.value = '请至少选择 2 条评估记录进行对比'
    loading.value = false
    return
  }
  try {
    const [a, b] = await Promise.all([
      vasiApi.getAssessment(ids.value[0]),
      vasiApi.getAssessment(ids.value[1]),
    ])
    const ta = new Date(a.assessment_date).getTime()
    const tb = new Date(b.assessment_date).getTime()
    if (ta <= tb) {
      before.value = a
      after.value = b
    } else {
      before.value = b
      after.value = a
    }
  } catch {
    errorMsg.value = '加载评估记录失败'
  } finally {
    loading.value = false
  }
}

const dateDiffText = computed(() => {
  if (!before.value || !after.value) return ''
  const ms = new Date(after.value.assessment_date).getTime() - new Date(before.value.assessment_date).getTime()
  const days = Math.round(ms / 86400000)
  if (days === 0) return '同日'
  if (days < 30) return `相隔 ${days} 天`
  if (days < 365) return `相隔 ${Math.round(days / 30)} 个月`
  return `相隔 ${(days / 365).toFixed(1)} 年`
})

function displayScore(a: VasiAssessmentResponse | null) {
  if (!a) return 0
  return a.final_vasi_score != null ? a.final_vasi_score : a.vasi_score
}

function displayArea(a: VasiAssessmentResponse | null) {
  if (!a) return 0
  return a.final_area_percentage != null ? a.final_area_percentage : a.area_percentage
}

const scoreDelta = computed(() => {
  if (!before.value || !after.value) return 0
  return Math.round((displayScore(after.value) - displayScore(before.value)) * 10) / 10
})
const areaDelta = computed(() => {
  if (!before.value || !after.value) return 0
  return Math.round((displayArea(after.value) - displayArea(before.value)) * 10) / 10
})

function trendBadge(delta: number) {
  if (delta < -0.5) return { label: '改善', color: 'text-green-700 bg-green-100 dark:bg-green-900/30 dark:text-green-300', icon: 'ri-arrow-down-line' }
  if (delta > 0.5) return { label: '加重', color: 'text-red-700 bg-red-100 dark:bg-red-900/30 dark:text-red-300', icon: 'ri-arrow-up-line' }
  return { label: '稳定', color: 'text-amber-700 bg-amber-100 dark:bg-amber-900/30 dark:text-amber-300', icon: 'ri-subtract-line' }
}

const scoreTrend = computed(() => trendBadge(scoreDelta.value))
const areaTrend = computed(() => trendBadge(areaDelta.value))

function formatDate(d: string) {
  return d?.slice(0, 10) || ''
}

const authedBeforeUrl = computed(() => toProtectedFileUrl(before.value?.image_url))
const authedAfterUrl = computed(() => toProtectedFileUrl(after.value?.image_url))

onMounted(load)
</script>

<template>
  <div class="min-h-dvh bg-[#F5F7FA] pb-20 md:pb-8">
    <header class="sticky top-0 z-30 bg-[#F5F7FA]/80  backdrop-blur border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-6xl mx-auto flex items-center gap-3 px-4 h-12">
        <button @click="router.back()" class="p-1 -ml-1 text-gray-600 hover:text-gray-900 dark:hover:text-gray-100">
          <i class="ri-arrow-left-s-line text-xl"></i>
        </button>
        <h1 class="text-base font-semibold text-gray-900 truncate">评估对比</h1>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-4">
      <div v-if="loading" class="text-center py-16 text-gray-400 ">
        <div class="text-4xl mb-3 animate-pulse"><i class="ri-image-2-line"></i></div>
        <p>加载中...</p>
      </div>

      <div v-else-if="errorMsg" class="text-center py-16 text-gray-400 ">
        <div class="text-4xl mb-3"><i class="ri-file-damage-line"></i></div>
        <p>{{ errorMsg }}</p>
        <button @click="router.push({ name: 'assessment' })" class="mt-4 text-sm text-primary-500 hover:underline">返回测评</button>
      </div>

      <template v-else-if="before && after">
        <div class="flex flex-col lg:flex-row gap-6 lg:items-start">
          <div class="w-full lg:w-1/2 flex flex-col gap-3">
            <BeforeAfterSlider
              :before-url="authedBeforeUrl"
              :after-url="authedAfterUrl"
              :before-label="formatDate(before.assessment_date)"
              :after-label="formatDate(after.assessment_date)"
            />
            <p class="text-xs text-gray-500  text-center">
              <i class="ri-information-line"></i> 拖动中间滑块对比两次评估的差异
            </p>
          </div>

          <div class="w-full lg:w-1/2 flex flex-col gap-4">
            <div class="card p-4">
              <div class="flex items-center justify-between">
                <h2 class="font-semibold text-gray-900">
                  {{ PART_LABELS[after.body_site] || after.body_site }} · 趋势对比
                </h2>
                <span class="text-xs text-gray-500 ">{{ dateDiffText }}</span>
              </div>
            </div>

            <div class="card p-4">
              <div class="grid grid-cols-3 gap-3">
                <div class="text-center">
                  <div class="text-xs text-gray-500  mb-1">VASI 评分</div>
                  <div class="flex items-baseline justify-center gap-2">
                    <span class="text-sm text-gray-400 line-through">
                      {{ privacyStore.privacyMode ? displayScore(before) : '**' }}
                    </span>
                    <span class="text-xl font-bold text-gray-900">
                      {{ privacyStore.privacyMode ? displayScore(after) : '**' }}
                    </span>
                  </div>
                </div>
                <div class="text-center">
                  <div class="text-xs text-gray-500  mb-1">变化</div>
                  <span class="badge inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded-full" :class="scoreTrend.color">
                    <i :class="scoreTrend.icon"></i>
                    <template v-if="privacyStore.privacyMode">
                      {{ scoreDelta > 0 ? '+' : '' }}{{ scoreDelta }}
                    </template>
                    <template v-else>**</template>
                  </span>
                </div>
                <div class="text-center">
                  <div class="text-xs text-gray-500  mb-1">趋势</div>
                  <div class="text-sm font-semibold" :class="scoreTrend.color.split(' ')[0]">{{ scoreTrend.label }}</div>
                </div>
              </div>
              <div class="border-t border-gray-100 dark:border-gray-800 my-3"></div>
              <div class="grid grid-cols-3 gap-3">
                <div class="text-center">
                  <div class="text-xs text-gray-500  mb-1">白斑面积</div>
                  <div class="flex items-baseline justify-center gap-2">
                    <span class="text-sm text-gray-400 line-through">
                      {{ privacyStore.privacyMode ? displayArea(before) + '%' : '**%' }}
                    </span>
                    <span class="text-xl font-bold text-gray-900">
                      {{ privacyStore.privacyMode ? displayArea(after) + '%' : '**%' }}
                    </span>
                  </div>
                </div>
                <div class="text-center">
                  <div class="text-xs text-gray-500  mb-1">变化</div>
                  <span class="badge inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded-full" :class="areaTrend.color">
                    <i :class="areaTrend.icon"></i>
                    <template v-if="privacyStore.privacyMode">
                      {{ areaDelta > 0 ? '+' : '' }}{{ areaDelta }}%
                    </template>
                    <template v-else>**</template>
                  </span>
                </div>
                <div class="text-center">
                  <div class="text-xs text-gray-500  mb-1">趋势</div>
                  <div class="text-sm font-semibold" :class="areaTrend.color.split(' ')[0]">{{ areaTrend.label }}</div>
                </div>
              </div>
            </div>

            <div class="card p-4 text-sm text-gray-600 space-y-1">
<div><i class="ri-history-line text-primary-500"></i> <strong>之前</strong>：{{ formatDate(before.assessment_date) }} · {{ before.stage }} · {{ before.classification || '未分型' }}</div>
<div><i class="ri-time-line text-primary-500"></i> <strong>现在</strong>：{{ formatDate(after.assessment_date) }} · {{ after.stage }} · {{ after.classification || '未分型' }}</div>
            </div>

            <p class="text-xs text-gray-400  text-center">
              <i class="ri-error-warning-line"></i> 以上对比仅供参考，不构成医疗诊断建议
            </p>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>
