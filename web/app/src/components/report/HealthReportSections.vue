<script setup lang="ts">
/**
 * HealthReportSections — 综合健康报告的「心情/体检/问答/综合概览」区块
 * 渲染在报告文档（固定浅色）内，与 SkinReportViewPage 的白斑章节并排。
 */
import { computed } from 'vue'
import type { SkinReportMetrics } from '@/api/skin_report'

const props = defineProps<{
  metrics: SkinReportMetrics | null
}>()

const mood = computed(() => props.metrics?.mood ?? null)
const exam = computed(() => props.metrics?.exam ?? null)
const qa = computed(() => props.metrics?.qa ?? null)

const hasMood = computed(
  () => !!mood.value && (mood.value.post_count > 0 || mood.value.mood_positive + mood.value.mood_neutral + mood.value.mood_negative > 0),
)
const hasExam = computed(() => !!exam.value && exam.value.report_count > 0)
const hasQa = computed(() => !!qa.value && qa.value.question_count > 0)

const moodTotal = computed(() => {
  if (!mood.value) return 0
  return mood.value.mood_positive + mood.value.mood_neutral + mood.value.mood_negative
})

function pct(n: number) {
  if (!moodTotal.value) return 0
  return Math.round((n / moodTotal.value) * 100)
}

function riskStyle(risk?: string) {
  if (risk === '需关注') return { cls: 'hr-badge--bad', icon: 'ri-error-warning-line' }
  if (risk === '部分异常') return { cls: 'hr-badge--warn', icon: 'ri-alert-line' }
  if (risk === '良好') return { cls: 'hr-badge--good', icon: 'ri-shield-check-line' }
  return { cls: 'hr-badge--flat', icon: 'ri-question-line' }
}
</script>

<template>
  <div v-if="metrics">
    <!-- 综合概览 KPI 卡 -->
    <div class="hr-section">
      <h3 class="hr-title"><i class="ri-dashboard-line"></i> 本期概览</h3>
      <div class="hr-kpis">
        <div class="hr-kpi">
          <span class="hr-kpi__label">白斑趋势</span>
          <span class="hr-kpi__value">{{ metrics.trend || '待评估' }}</span>
        </div>
        <div class="hr-kpi">
          <span class="hr-kpi__label">追踪部位</span>
          <span class="hr-kpi__value">{{ metrics.site_count ?? 0 }}<em>个</em></span>
        </div>
        <div class="hr-kpi">
          <span class="hr-kpi__label">心情</span>
          <span class="hr-kpi__value">{{ mood?.mood_label || '暂无' }}</span>
        </div>
        <div class="hr-kpi">
          <span class="hr-kpi__label">体检</span>
          <span class="hr-kpi__value">{{ exam?.report_count ? exam.risk_label : '暂无' }}</span>
        </div>
        <div class="hr-kpi">
          <span class="hr-kpi__label">AI 问答</span>
          <span class="hr-kpi__value">{{ qa?.question_count ?? 0 }}<em>条</em></span>
        </div>
        <div class="hr-kpi">
          <span class="hr-kpi__label">记录 / 获赞</span>
          <span class="hr-kpi__value">{{ mood?.post_count ?? 0 }}<em>/</em>{{ mood?.like_received ?? 0 }}</span>
        </div>
      </div>
    </div>

    <!-- 心情变化 -->
    <div v-if="hasMood" class="hr-section">
      <h3 class="hr-title"><i class="ri-heart-3-line"></i> 心情变化</h3>
      <div class="hr-mood-head">
        <span class="hr-mood__label">本期整体心情：{{ mood?.mood_trend || mood?.mood_label }}</span>
        <span v-if="mood?.comfort_line" class="hr-mood__comfort">
          <i class="ri-double-quotes-l"></i>{{ mood.comfort_line }}
        </span>
      </div>
      <div v-if="moodTotal > 0" class="hr-mood-bar">
        <div class="hr-mood-bar__seg hr-mood-bar__seg--good" :style="{ width: pct(mood?.mood_positive ?? 0) + '%' }"></div>
        <div class="hr-mood-bar__seg hr-mood-bar__seg--flat" :style="{ width: pct(mood?.mood_neutral ?? 0) + '%' }"></div>
        <div class="hr-mood-bar__seg hr-mood-bar__seg--bad" :style="{ width: pct(mood?.mood_negative ?? 0) + '%' }"></div>
      </div>
      <div v-if="moodTotal > 0" class="hr-mood-legend">
        <span><i class="hr-dot hr-dot--good"></i>积极 {{ mood?.mood_positive ?? 0 }}</span>
        <span><i class="hr-dot hr-dot--flat"></i>平稳 {{ mood?.mood_neutral ?? 0 }}</span>
        <span><i class="hr-dot hr-dot--bad"></i>低落 {{ mood?.mood_negative ?? 0 }}</span>
      </div>
    </div>

    <!-- 体检要点 -->
    <div v-if="hasExam" class="hr-section">
      <h3 class="hr-title"><i class="ri-microscope-line"></i> 体检要点</h3>
      <div class="hr-exam-head">
        <span class="hr-badge" :class="riskStyle(exam?.risk_label).cls">
          <i :class="riskStyle(exam?.risk_label).icon"></i>{{ exam?.risk_label }}
        </span>
        <span class="hr-exam-count">本期上传 {{ exam?.report_count }} 份体检报告</span>
      </div>
      <ul v-if="exam?.abnormal_items?.length" class="hr-exam-list">
        <li v-for="(it, i) in exam.abnormal_items.slice(0, 4)" :key="i">
          <span class="hr-exam-list__name">{{ it.indicator }}</span>
          <span v-if="it.value" class="hr-exam-list__value">{{ it.value }}</span>
          <span v-if="it.interpretation" class="hr-exam-list__desc">{{ it.interpretation }}</span>
        </li>
      </ul>
      <div v-if="exam?.relevant_indicators?.length" class="hr-exam-rel">
        <i class="ri-flask-line"></i> 与白癜风相关的指标：{{ exam.relevant_indicators.join('、') }}
      </div>
      <p v-if="!exam?.abnormal_items?.length && !exam?.relevant_indicators?.length" class="hr-note">
        <i class="ri-shield-check-line"></i> 本期体检未见明显异常指标
      </p>
    </div>

    <!-- AI 问答洞察 -->
    <div v-if="hasQa" class="hr-section">
      <h3 class="hr-title"><i class="ri-chat-3-line"></i> 你关心的话题</h3>
      <p class="hr-qa-count">本期你在 AI 问答提了 {{ qa?.question_count }} 个问题</p>
      <div v-if="qa?.topics?.length" class="hr-qa-topics">
        <span v-for="(t, i) in qa.topics" :key="i" class="hr-topic">{{ t }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hr-section {
  padding: 20px 24px;
  border-top: 1px solid #f1f5f9;
}

.hr-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #0f766e;
  margin-bottom: 14px;
}

.hr-title i {
  font-size: 18px;
}

.hr-kpis {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

@media (min-width: 640px) {
  .hr-kpis {
    grid-template-columns: repeat(6, 1fr);
  }
}

.hr-kpi {
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px 8px;
  text-align: center;
}

.hr-kpi__label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.hr-kpi__value {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.hr-kpi__value em {
  font-style: normal;
  font-size: 12px;
  font-weight: 500;
  color: #94a3b8;
}

.hr-mood-head {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hr-mood__label {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.hr-mood__comfort {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 13px;
  color: #0f766e;
  background: #ecfdf5;
  border-radius: 10px;
  padding: 8px 10px;
  line-height: 1.6;
}

.hr-mood__comfort i {
  flex-shrink: 0;
  margin-top: 1px;
}

.hr-mood-bar {
  display: flex;
  height: 10px;
  border-radius: 6px;
  overflow: hidden;
  background: #f1f5f9;
  margin: 12px 0 8px;
}

.hr-mood-bar__seg--good { background: #10b981; }
.hr-mood-bar__seg--flat { background: #cbd5e1; }
.hr-mood-bar__seg--bad { background: #f43f5e; }

.hr-mood-legend {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: #64748b;
}

.hr-mood-legend span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.hr-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.hr-dot--good { background: #10b981; }
.hr-dot--flat { background: #cbd5e1; }
.hr-dot--bad { background: #f43f5e; }

.hr-exam-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.hr-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.hr-badge--good { background: #ecfdf5; color: #047857; }
.hr-badge--warn { background: #fffbeb; color: #b45309; }
.hr-badge--bad { background: #fef2f2; color: #b91c1c; }
.hr-badge--flat { background: #f1f5f9; color: #475569; }

.hr-exam-count {
  font-size: 12px;
  color: #94a3b8;
}

.hr-exam-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hr-exam-list li {
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  align-items: baseline;
  font-size: 13px;
  line-height: 1.6;
}

.hr-exam-list__name {
  font-weight: 600;
  color: #334155;
}

.hr-exam-list__value {
  color: #b91c1c;
  font-weight: 600;
}

.hr-exam-list__desc {
  color: #64748b;
  width: 100%;
}

.hr-exam-rel {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 10px;
  padding: 10px 12px;
  background: #eff6ff;
  border-radius: 10px;
  font-size: 13px;
  color: #1d4ed8;
  line-height: 1.6;
}

.hr-exam-rel i {
  flex-shrink: 0;
  margin-top: 1px;
}

.hr-note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748b;
}

.hr-qa-count {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 10px;
}

.hr-qa-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hr-topic {
  padding: 6px 14px;
  border-radius: 16px;
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  color: #0f766e;
  font-size: 13px;
  font-weight: 500;
}
</style>
