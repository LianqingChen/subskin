---
title: VASI评估报告
---

<ClientOnly>
  <VASIReport />
</ClientOnly>

<script setup>
import { ref, onMounted } from 'vue'
import { getAssessment } from '/.vitepress/theme/utils/vasi-api.js'

const BODY_SITES = {
  face: { label: '面部', icon: '😊' },
  neck: { label: '颈部', icon: '🦒' },
  trunk: { label: '躯干', icon: '👕' },
  upper_limb: { label: '上肢', icon: '💪' },
  lower_limb: { label: '下肢', icon: '🦵' },
  other: { label: '其他', icon: '📷' },
}

const DISEASE_TYPES = {
  segmental: { label: '节段型', description: '局限于一个皮节区域' },
  non_segmental: { label: '非节段型', description: '对称或广泛分布' },
  mixed: { label: '混合型', description: '同时具备节段型和非节段型特征' },
}

const DISEASE_STAGES = {
  improving: { label: '好转', color: '#2f855a', icon: '✅' },
  stable: { label: '稳定', color: '#d69e2e', icon: '⏸️' },
  spreading: { label: '扩散', color: '#e53e3e', icon: '⚠️' },
}

const assessment = ref(null)
const isLoading = ref(true)
const errorMessage = ref('')

function getAssessmentId() {
  const urlParams = new URLSearchParams(window.location.search)
  return urlParams.get('id')
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(async () => {
  const assessmentId = getAssessmentId()
  
  if (!assessmentId) {
    errorMessage.value = '未找到评估记录'
    isLoading.value = false
    return
  }
  
  try {
    assessment.value = await getAssessment(assessmentId)
  } catch (error) {
    errorMessage.value = error.message || '获取评估数据失败'
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div class="vasi-page" v-if="!isLoading">
    <div class="vasi-header">
      <h1 class="vasi-title">📊 VASI评估报告</h1>
    </div>
    
    <div class="error-message" v-if="errorMessage">
      ⚠️ {{ errorMessage }}
      <div class="back-link">
        <a href="/vasi/">← 返回评估首页</a>
      </div>
    </div>
    
    <div v-else-if="assessment">
      <div class="vasi-score-display">
        <div class="vasi-score-label">VASI评分</div>
        <div class="vasi-score-value">{{ assessment.vasi_score.toFixed(1) }}</div>
        <div class="vasi-score-unit">满分100分</div>
      </div>
      
      <div class="vasi-card">
        <h2 class="vasi-card-title">📋 基本信息</h2>
        <div class="vasi-info-grid">
          <div class="vasi-info-item">
            <div class="vasi-info-label">评估日期</div>
            <div class="vasi-info-value">{{ formatDate(assessment.created_at) }}</div>
          </div>
          <div class="vasi-info-item">
            <div class="vasi-info-label">评估部位</div>
            <div class="vasi-info-value">
              {{ BODY_SITES[assessment.body_site]?.label || assessment.body_site || '未知' }}
            </div>
          </div>
          <div class="vasi-info-item">
            <div class="vasi-info-label">病情分型</div>
            <div class="vasi-info-value">
              {{ DISEASE_TYPES[assessment.disease_type]?.label || assessment.disease_type }}
            </div>
          </div>
          <div class="vasi-info-item">
            <div class="vasi-info-label">白斑面积</div>
            <div class="vasi-info-value">
              {{ assessment.affected_area_percent }}%
            </div>
          </div>
        </div>
      </div>
      
      <div class="vasi-card">
        <h2 class="vasi-card-title">📈 病情阶段</h2>
        <div class="stage-display">
          <span 
            :class="['vasi-badge', `stage-${assessment.disease_stage}`]"
          >
            {{ DISEASE_STAGES[assessment.disease_stage]?.icon }} 
            {{ DISEASE_STAGES[assessment.disease_stage]?.label || assessment.disease_stage }}
          </span>
        </div>
        <p class="stage-description">
          {{ assessment.disease_stage === 'improving' 
            ? '您的病情正在好转，白斑面积和色素脱失程度都在下降。请继续保持现有治疗方案。'
            : assessment.disease_stage === 'stable'
            ? '您的病情处于稳定状态，白斑面积和色素脱失程度保持不变。建议定期复查。'
            : '您的病情有扩散趋势，白斑面积或色素脱失程度有所增加。建议及时就医调整治疗方案。'
          }}
        </p>
      </div>
      
      <div class="vasi-card" v-if="assessment.image_url">
        <h2 class="vasi-card-title">🖼️ 评估图片</h2>
        <div class="image-container">
          <img 
            :src="assessment.image_url" 
            alt="评估图片"
            class="assessment-image"
          >
        </div>
      </div>
      
      <div class="vasi-card">
        <h2 class="vasi-card-title">⚠️ 免责声明</h2>
        <p class="disclaimer-text">
          本评估报告仅供参考，不构成医疗建议。VASI评分由AI算法生成，结果仅供参考。如需专业医疗建议，请咨询执业医师。
        </p>
      </div>
      
      <div class="action-section">
        <button @click="window.print()" class="action-button primary">
          🖨️ 打印报告
        </button>
        <a href="/vasi/history" class="action-button secondary">
          📜 查看历史记录
        </a>
        <a href="/vasi/trend" class="action-button secondary">
          📈 查看趋势图
        </a>
        <a href="/vasi/" class="action-button secondary">
          🔄 新增评估
        </a>
      </div>
    </div>
  </div>
  
  <div class="vasi-loading" v-else>
    <div class="vasi-spinner"></div>
    <p>加载中...</p>
  </div>
</template>

<style scoped>
@import '/.vitepress/theme/styles/vasi.css';

.stage-display {
  margin-bottom: 1rem;
}

.stage-description {
  font-size: 1rem;
  line-height: 1.6;
  color: var(--subskin-color-text-light);
  margin: 0;
}

.image-container {
  text-align: center;
}

.assessment-image {
  max-width: 100%;
  max-height: 400px;
  border-radius: var(--subskin-radius-md);
  object-fit: contain;
}

.disclaimer-text {
  font-size: 0.875rem;
  color: var(--subskin-color-text-muted);
  line-height: 1.6;
  margin: 0;
}

.action-section {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin: 2rem 0;
  flex-wrap: wrap;
}

.action-button {
  padding: 0.75rem 1.5rem;
  border-radius: var(--subskin-radius-md);
  font-weight: 500;
  text-decoration: none;
  transition: all 0.3s ease;
  display: inline-block;
}

.action-button.primary {
  background-color: var(--subskin-color-primary);
  color: white;
  border: none;
}

.action-button.primary:hover {
  background-color: var(--subskin-color-primary-dark);
}

.action-button.secondary {
  background-color: transparent;
  color: var(--subskin-color-text);
  border: 2px solid var(--subskin-color-border);
}

.action-button.secondary:hover {
  border-color: var(--subskin-color-primary);
  color: var(--subskin-color-primary);
}

.error-message {
  text-align: center;
  padding: 2rem;
  color: var(--subskin-color-danger);
}

.back-link {
  margin-top: 1rem;
}

.back-link a {
  color: var(--subskin-color-primary);
  text-decoration: none;
  font-weight: 500;
}

.back-link a:hover {
  text-decoration: underline;
}

@media (max-width: 640px) {
  .action-section {
    flex-direction: column;
  }
  
  .action-button {
    width: 100%;
  }
}
</style>
