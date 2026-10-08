<script setup lang="ts">
/**
 * SkinReportSharedPage — 白斑变化报告公开分享页（无需登录）
 *
 * 通过 share_token 访问，脱敏展示（不含原始图片），底部引导注册/登录。
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSharedReport } from '@/api/skin_report'
import type { SkinReport } from '@/api/skin_report'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const report = ref<SkinReport | null>(null)
const loading = ref(true)
const error = ref('')

const isPeriodic = computed(
  () => report.value?.report_type === 'weekly' || report.value?.report_type === 'monthly',
)

async function load() {
  const token = route.params.token as string
  if (!token) {
    error.value = '无效的分享链接'
    loading.value = false
    return
  }
  try {
    const { data } = await getSharedReport(token)
    report.value = data
  } catch {
    error.value = '报告不存在或已关闭分享'
  } finally {
    loading.value = false
  }
}

function trendStyle(trend: string) {
  if (trend === '好转')
    return { bg: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: 'ri-arrow-down-line', label: '好转' }
  if (trend === '加重')
    return { bg: 'bg-rose-50 text-rose-700 border-rose-200', icon: 'ri-arrow-up-line', label: '加重' }
  if (trend === '稳定')
    return { bg: 'bg-amber-50 text-amber-700 border-amber-200', icon: 'ri-subtract-line', label: '稳定' }
  return { bg: 'bg-slate-50 text-slate-600 border-slate-200', icon: 'ri-question-line', label: trend }
}

function fmtDate(d: string | null) {
  return d ? d.slice(0, 10) : ''
}

function goToApp() {
  if (authStore.isLoggedIn) {
    // 跳转分享并自动弹起记录分享面板
    router.push({ name: 'community', query: { create: '1' } })
  } else {
    authStore.showLoginModal = true
  }
}

onMounted(load)
</script>

<template>
  <div class="shared-page">
    <div v-if="loading" class="shared-loading">
      <i class="ri-loader-4-line shared-spin"></i>
      <p>报告加载中...</p>
    </div>

    <div v-else-if="error" class="shared-error">
      <i class="ri-file-damage-line"></i>
      <p>{{ error }}</p>
      <button class="shared-cta" @click="router.push({ name: 'community' })">返回 SubSkin</button>
    </div>

    <template v-else-if="report">
      <div class="shared-doc">
        <!-- 封面 -->
        <div class="shared-cover">
          <div class="shared-cover__brand">
            <i class="ri-leaf-line"></i>
            <span>SubSkin · 小白日记</span>
          </div>
          <h1 class="shared-cover__title">{{ report.title }}</h1>
          <p class="shared-cover__meta">
            {{ report.body_site_label }} · {{ fmtDate(report.period_start) }} ~
            {{ fmtDate(report.period_end) }}
          </p>
          <div
            v-if="report.metrics"
            class="shared-cover__trend"
            :class="trendStyle(report.metrics.trend).bg"
          >
            <i :class="trendStyle(report.metrics.trend).icon"></i>
            <span>{{ trendStyle(report.metrics.trend).label }}</span>
          </div>
        </div>

        <!-- 指标 -->
        <div v-if="report.metrics" class="shared-section">
          <h3 class="shared-section__title"><i class="ri-pie-chart-line"></i> 关键指标</h3>
          <div v-if="isPeriodic && report.metrics.sites_summary" class="shared-metrics">
            <div class="shared-metric">
              <span class="shared-metric__label">追踪部位</span>
              <span class="shared-metric__value">{{ report.metrics.sites_summary.total }}</span>
            </div>
            <div class="shared-metric">
              <span class="shared-metric__label">好转部位</span>
              <span class="shared-metric__value">{{ report.metrics.sites_summary.improving }}</span>
            </div>
            <div class="shared-metric">
              <span class="shared-metric__label">周期天数</span>
              <span class="shared-metric__value">{{ report.metrics.period_days }}</span>
            </div>
          </div>
          <div v-else class="shared-metrics">
            <div class="shared-metric">
              <span class="shared-metric__label">记录次数</span>
              <span class="shared-metric__value">{{ report.metrics.point_count }}</span>
            </div>
            <div class="shared-metric">
              <span class="shared-metric__label">追踪天数</span>
              <span class="shared-metric__value">{{ report.metrics.date_span_days }}</span>
            </div>
            <div v-if="report.metrics.has_vasi && report.metrics.vasi_change != null" class="shared-metric">
              <span class="shared-metric__label">VASI 变化</span>
              <span class="shared-metric__value">{{ report.metrics.vasi_change > 0 ? '+' : '' }}{{ report.metrics.vasi_change }}</span>
            </div>
          </div>
        </div>

        <!-- 变化摘要（对比报告：客观事实，每条一句话） -->
        <div v-if="!isPeriodic && report.metrics?.change_summary?.length" class="shared-section">
          <h3 class="shared-section__title"><i class="ri-file-list-3-line"></i> 变化摘要</h3>
          <ul class="shared-list">
            <li v-for="(line, i) in report.metrics.change_summary" :key="i">
              <i class="ri-checkbox-circle-line"></i><span>{{ line }}</span>
            </li>
          </ul>
        </div>

        <!-- AI 叙事 / 洞察 / 建议：仅周报月报保留 -->
        <template v-if="isPeriodic">
          <div v-if="report.narrative" class="shared-section">
            <h3 class="shared-section__title"><i class="ri-sparkling-2-line"></i> AI 分析</h3>
            <p class="shared-narrative">{{ report.narrative }}</p>
          </div>

          <div v-if="report.insights?.length" class="shared-section">
            <h3 class="shared-section__title"><i class="ri-lightbulb-line"></i> 关键洞察</h3>
            <ul class="shared-list">
              <li v-for="(ins, i) in report.insights" :key="i">
                <i class="ri-checkbox-circle-line"></i><span>{{ ins }}</span>
              </li>
            </ul>
          </div>

          <div v-if="report.recommendations?.length" class="shared-section">
            <h3 class="shared-section__title"><i class="ri-thumb-up-line"></i> 建议</h3>
            <ul class="shared-list">
              <li v-for="(rec, i) in report.recommendations" :key="i">
                <i class="ri-arrow-right-s-line"></i><span>{{ rec }}</span>
              </li>
            </ul>
          </div>
        </template>

        <div class="shared-disclaimer">
          <i class="ri-error-warning-line"></i>
          <span>本报告仅供参考，不构成医疗诊断建议。</span>
        </div>
      </div>

      <!-- 引导注册 -->
      <div class="shared-lead">
        <i class="ri-leaf-line shared-lead__icon"></i>
        <h2>用 SubSkin 追踪你的白斑变化</h2>
        <p>图文日记 · AI 深度分析 · 变化报告 — 白癜风病友的AI手帐和分享社区</p>
        <button class="shared-lead__btn" @click="goToApp">
          <i class="ri-arrow-right-line"></i>
          {{ authStore.isLoggedIn ? '开始记录' : '立即体验' }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.shared-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f5f7fa;
  padding: 16px 16px 40px;
}

.shared-loading,
.shared-error {
  text-align: center;
  padding: 80px 24px;
  color: #94a3b8;
}

.shared-loading i,
.shared-error i {
  font-size: 40px;
  display: block;
  margin-bottom: 12px;
}

.shared-spin {
  animation: s-spin 1s linear infinite;
}

@keyframes s-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.shared-doc {
  max-width: 600px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
  color: #1e293b;
}

.shared-cover {
  background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
  color: white;
  padding: 28px 24px;
}

.shared-cover__brand {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  opacity: 0.9;
  margin-bottom: 14px;
}

.shared-cover__title {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.4;
  margin-bottom: 8px;
}

.shared-cover__meta {
  font-size: 13px;
  opacity: 0.9;
  margin-bottom: 14px;
}

.shared-cover__trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid;
}

.shared-section {
  padding: 20px 24px;
  border-top: 1px solid #f1f5f9;
}

.shared-section__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #0f766e;
  margin-bottom: 14px;
}

.shared-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.shared-metric {
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px 8px;
  text-align: center;
}

.shared-metric__label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.shared-metric__value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.shared-narrative {
  font-size: 15px;
  line-height: 1.8;
  color: #334155;
  white-space: pre-wrap;
}

.shared-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.shared-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.shared-list li i {
  color: #0d9488;
  font-size: 16px;
  margin-top: 2px;
  flex-shrink: 0;
}

.shared-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 14px 24px;
  background: #fefce8;
  color: #92400e;
  font-size: 12px;
  line-height: 1.6;
}

.shared-lead {
  max-width: 600px;
  margin: 20px auto 0;
  text-align: center;
  background: white;
  border-radius: 16px;
  padding: 28px 24px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
}

.shared-lead__icon {
  font-size: 40px;
  color: var(--color-primary-500);
  margin-bottom: 10px;
  display: block;
}

.shared-lead h2 {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 8px;
}

.shared-lead p {
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  margin-bottom: 18px;
}

.shared-lead__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 12px 32px;
  border-radius: 24px;
  border: none;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(15, 118, 110, 0.3);
}

.shared-cta {
  margin-top: 16px;
  padding: 10px 28px;
  border-radius: 22px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
</style>
