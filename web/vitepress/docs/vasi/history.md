---
title: VASI历史记录
---

<ClientOnly>
  <VASIHistory />
</ClientOnly>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getHistory } from '/.vitepress/theme/utils/vasi-api.js'

const BODY_SITES = {
  face: { label: '面部', icon: '😊' },
  neck: { label: '颈部', icon: '🦒' },
  trunk: { label: '躯干', icon: '👕' },
  upper_limb: { label: '上肢', icon: '💪' },
  lower_limb: { label: '下肢', icon: '🦵' },
  other: { label: '其他', icon: '📷' },
}

const DISEASE_STAGES = {
  improving: { label: '好转', color: '#2f855a', icon: '✅' },
  stable: { label: '稳定', color: '#d69e2e', icon: '⏸️' },
  spreading: { label: '扩散', color: '#e53e3e', icon: '⚠️' },
}

const assessments = ref([])
const isLoading = ref(true)
const errorMessage = ref('')
const selectedBodySite = ref('all')
const currentPage = ref(1)
const pageSize = ref(10)
const totalPages = ref(1)

const bodySiteOptions = computed(() => {
  const sites = typeof BODY_SITES === 'object' ? BODY_SITES : {}
  return [
    { value: 'all', label: '全部部位' },
    ...Object.entries(sites).map(([key, value]) => ({
      value: key,
      label: value?.label || key,
      icon: value?.icon || '📋'
    }))
  ]
})

async function loadHistory() {
  isLoading.value = true
  errorMessage.value = ''
  
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ...(selectedBodySite.value !== 'all' && { body_site: selectedBodySite.value })
    }
    
    const response = await getHistory(params)
    assessments.value = response.assessments || []
    totalPages.value = Math.ceil((response.total || 0) / pageSize.value)
  } catch (error) {
    errorMessage.value = error.message || '加载历史记录失败'
    assessments.value = []
  } finally {
    isLoading.value = false
  }
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

function goToDetail(assessmentId) {
  window.location.href = `/vasi/report?id=${assessmentId}`
}

function changePage(page) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    loadHistory()
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<template>
  <div class="vasi-page">
    <div class="vasi-header">
      <h1 class="vasi-title">📜 历史记录</h1>
      <p class="vasi-subtitle">
        查看您的VASI评估历史，追踪病情变化趋势
      </p>
    </div>
    
    <div class="vasi-nav">
      <a href="/vasi/" class="vasi-nav-link">
        📊 开始评估
      </a>
      <a href="/vasi/trend" class="vasi-nav-link">
        📈 趋势图
      </a>
    </div>
    
    <div class="filter-section">
      <div class="filter-label">筛选部位：</div>
      <div class="filter-buttons">
        <button
          v-for="site in bodySiteOptions"
          :key="site.value"
          @click="selectedBodySite = site.value; currentPage = 1; loadHistory()"
          :class="['filter-button', { 'is-active': selectedBodySite === site.value }]"
        >
          {{ site.label }}
        </button>
      </div>
    </div>
    
    <div class="vasi-loading" v-if="isLoading">
      <div class="vasi-spinner"></div>
      <p>加载中...</p>
    </div>
    
    <div class="error-message" v-else-if="errorMessage">
      ⚠️ {{ errorMessage }}
      <button @click="loadHistory" class="retry-button">重试</button>
    </div>
    
    <div class="vasi-empty-state" v-else-if="assessments.length === 0">
      <div class="vasi-empty-icon">📭</div>
      <p class="vasi-empty-text">暂无评估记录</p>
      <p class="vasi-empty-subtext">开始您的第一次VASI评估</p>
      <a href="/vasi/" class="start-assessment-button">开始评估</a>
    </div>
    
    <div class="history-list" v-else>
      <div 
        v-for="assessment in assessments"
        :key="assessment.id"
        @click="goToDetail(assessment.id)"
        class="history-card"
      >
        <div class="card-image" v-if="assessment.image_url">
          <img 
            :src="assessment.image_url" 
            :alt="`评估图片 - ${formatDate(assessment.created_at)}`"
            class="history-thumbnail"
          >
        </div>
        <div class="card-image placeholder" v-else>
          <div class="placeholder-icon">📷</div>
        </div>
        
        <div class="card-content">
          <div class="card-header">
            <span class="card-date">{{ formatDate(assessment.created_at) }}</span>
            <span 
              :class="['vasi-badge', `stage-${assessment.disease_stage || 'stable'}`]"
            >
              {{ DISEASE_STAGES[assessment.disease_stage]?.icon || '⏸️' }}
              {{ DISEASE_STAGES[assessment.disease_stage]?.label || assessment.disease_stage || '稳定' }}
            </span>
          </div>
          
          <div class="card-body">
            <div class="card-score">
              <span class="score-label">VASI</span>
              <span class="score-value">{{ assessment.vasi_score.toFixed(1) }}</span>
            </div>
            
            <div class="card-info">
              <div class="info-item">
                <span class="info-label">部位：</span>
                <span class="info-value">
                  {{ BODY_SITES[assessment.body_site]?.label || assessment.body_site || '未知' }}
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">面积：</span>
                <span class="info-value">{{ assessment.affected_area_percent }}%</span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="card-arrow">
          →
        </div>
      </div>
      
      <div class="pagination" v-if="totalPages > 1">
        <button
          @click="changePage(currentPage - 1)"
          :disabled="currentPage === 1"
          class="pagination-button"
        >
          ← 上一页
        </button>
        
        <span class="pagination-info">
          第 {{ currentPage }} / {{ totalPages }} 页
        </span>
        
        <button
          @click="changePage(currentPage + 1)"
          :disabled="currentPage === totalPages"
          class="pagination-button"
        >
          下一页 →
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import '/.vitepress/theme/styles/vasi.css';

.filter-section {
  background-color: var(--subskin-color-bg);
  border: 1px solid var(--subskin-color-border);
  border-radius: var(--subskin-radius-lg);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.filter-label {
  font-size: 1rem;
  font-weight: 500;
  color: var(--subskin-color-text);
  margin-bottom: 1rem;
}

.filter-buttons {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.filter-button {
  padding: 0.5rem 1rem;
  background-color: var(--subskin-color-bg);
  color: var(--subskin-color-text);
  border: 1px solid var(--subskin-color-border);
  border-radius: var(--subskin-radius-sm);
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.filter-button:hover {
  border-color: var(--subskin-color-primary);
  color: var(--subskin-color-primary);
}

.filter-button.is-active {
  background-color: var(--subskin-color-primary);
  color: white;
  border-color: var(--subskin-color-primary);
}

.filter-icon {
  font-size: 1rem;
}

.filter-label-text {
  font-weight: 500;
}

.history-list {
  max-width: 800px;
  margin: 0 auto;
}

.history-card {
  background-color: var(--subskin-color-bg);
  border: 1px solid var(--subskin-color-border);
  border-radius: var(--subskin-radius-lg);
  padding: 1.5rem;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.history-card:hover {
  border-color: var(--subskin-color-primary);
  box-shadow: var(--subskin-shadow-md);
  transform: translateY(-2px);
}

.card-image {
  width: 100px;
  height: 100px;
  flex-shrink: 0;
  border-radius: var(--subskin-radius-md);
  overflow: hidden;
}

.history-thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-image.placeholder {
  background-color: var(--subskin-color-bg-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-icon {
  font-size: 2.5rem;
  opacity: 0.3;
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.card-date {
  font-size: 1rem;
  font-weight: 500;
  color: var(--subskin-color-text);
}

.card-body {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.card-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.score-label {
  font-size: 0.75rem;
  color: var(--subskin-color-text-muted);
}

.score-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--subskin-color-primary);
}

.card-info {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.info-item {
  font-size: 0.875rem;
}

.info-label {
  color: var(--subskin-color-text-muted);
}

.info-value {
  color: var(--subskin-color-text);
  font-weight: 500;
}

.card-arrow {
  font-size: 1.5rem;
  color: var(--subskin-color-text-muted);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.history-card:hover .card-arrow {
  opacity: 1;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1.5rem;
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--subskin-color-border);
}

.pagination-button {
  padding: 0.5rem 1rem;
  background-color: var(--subskin-color-bg);
  color: var(--subskin-color-text);
  border: 1px solid var(--subskin-color-border);
  border-radius: var(--subskin-radius-sm);
  cursor: pointer;
  transition: all 0.3s ease;
}

.pagination-button:hover:not(:disabled) {
  border-color: var(--subskin-color-primary);
  color: var(--subskin-color-primary);
}

.pagination-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-info {
  font-size: 0.875rem;
  color: var(--subskin-color-text-light);
}

.start-assessment-button {
  display: inline-block;
  margin-top: 1rem;
  padding: 0.75rem 2rem;
  background-color: var(--subskin-color-primary);
  color: white;
  border-radius: var(--subskin-radius-md);
  text-decoration: none;
  font-weight: 500;
  transition: background-color 0.3s ease;
}

.start-assessment-button:hover {
  background-color: var(--subskin-color-primary-dark);
}

.retry-button {
  margin-left: 1rem;
  padding: 0.5rem 1rem;
  background-color: var(--subskin-color-primary);
  color: white;
  border: none;
  border-radius: var(--subskin-radius-sm);
  cursor: pointer;
}

@media (max-width: 640px) {
  .filter-buttons {
    flex-direction: column;
  }
  
  .filter-button {
    width: 100%;
    justify-content: center;
  }
  
  .history-card {
    flex-direction: column;
    text-align: center;
  }
  
  .card-image {
    width: 150px;
    height: 150px;
  }
  
  .card-header {
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .card-body {
    flex-direction: column;
    gap: 1rem;
  }
  
  .pagination {
    flex-direction: column;
    gap: 1rem;
  }
}
</style>
