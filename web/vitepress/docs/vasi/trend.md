---
title: VASI趋势图
---

<ClientOnly>
  <VASITrend />
</ClientOnly>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { getTrend } from '/.vitepress/theme/utils/vasi-api.js'

const BODY_SITES = {
  face: { label: '面部', icon: '😊' },
  neck: { label: '颈部', icon: '🦒' },
  trunk: { label: '躯干', icon: '👕' },
  upper_limb: { label: '上肢', icon: '💪' },
  lower_limb: { label: '下肢', icon: '🦵' },
  other: { label: '其他', icon: '📷' },
}

const TIME_RANGES = [
  { value: 7, label: '7天' },
  { value: 30, label: '30天' },
  { value: 90, label: '90天' },
  { value: 180, label: '180天' },
  { value: 365, label: '365天' },
]

const trendData = ref([])
const isLoading = ref(true)
const errorMessage = ref('')
const selectedTimeRange = ref(30)
const selectedBodySite = ref('all')
const chartInstance = ref(null)
const chartContainer = ref(null)

const bodySiteOptions = computed(() => {
  const sites = typeof BODY_SITES === 'object' ? BODY_SITES : {}
  return [
    { value: 'all', label: '全部部位' },
    ...Object.entries(sites).map(([key, value]) => ({
    value: key,
    label: value.label
  }))
])

const summaryData = computed(() => {
  if (trendData.value.length === 0) return null
  
  const scores = trendData.value.map(d => d.vasi_score)
  const firstScore = scores[scores.length - 1]
  const lastScore = scores[0]
  const change = lastScore - firstScore
  const changePercent = firstScore > 0 ? (change / firstScore * 100).toFixed(1) : 0
  
  let trend = 'stable'
  if (change > 1) trend = 'spreading'
  else if (change < -1) trend = 'improving'
  
  return {
    firstScore: firstScore.toFixed(1),
    lastScore: lastScore.toFixed(1),
    change: change.toFixed(1),
    changePercent: changePercent,
    trend
  }
})

async function loadTrendData() {
  isLoading.value = true
  errorMessage.value = ''
  
  try {
    const params = {
      days: selectedTimeRange.value,
      ...(selectedBodySite.value !== 'all' && { body_site: selectedBodySite.value })
    }
    
    const response = await getTrend(params)
    trendData.value = response.trend || []
    
    if (chartInstance.value) {
      updateChart()
    }
  } catch (error) {
    errorMessage.value = error.message || '加载趋势数据失败'
    trendData.value = []
  } finally {
    isLoading.value = false
  }
}

function initChart() {
  if (!chartContainer.value) return
  
  chartInstance.value = echarts.init(chartContainer.value)
  updateChart()
  
  window.addEventListener('resize', handleResize)
}

function updateChart() {
  if (!chartInstance.value || trendData.value.length === 0) return
  
  const dates = trendData.value.map(d => 
    new Date(d.created_at).toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric'
    })
  )
  
  const scores = trendData.value.map(d => d.vasi_score)
  const stages = trendData.value.map(d => d.disease_stage)
  
  const colors = {
    improving: '#2f855a',
    stable: '#d69e2e',
    spreading: '#e53e3e'
  }
  
  const option = {
    title: {
      text: 'VASI评分趋势',
      left: 'center',
      textStyle: {
        fontSize: 18,
        color: '#2d3748'
      }
    },
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        const date = new Date(trendData.value[params[0].dataIndex].created_at)
        const formattedDate = date.toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        })
        const stage = stages[params[0].dataIndex]
        const stageLabel = stage === 'improving' ? '好转' 
          : stage === 'stable' ? '稳定' : '扩散'
        
        return `
          <div style="padding: 8px;">
            <div style="margin-bottom: 4px; font-weight: 600;">${formattedDate}</div>
            <div>VASI评分: <span style="font-weight: 600;">${params[0].value.toFixed(1)}</span></div>
            <div>病情阶段: <span style="color: ${colors[stage]};">${stageLabel}</span></div>
          </div>
        `
      }
    },
    grid: {
      left: '10%',
      right: '5%',
      bottom: '15%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: '#e2e8f0'
        }
      },
      axisLabel: {
        color: '#718096'
      }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLine: {
        lineStyle: {
          color: '#e2e8f0'
        }
      },
      axisLabel: {
        color: '#718096'
      },
      splitLine: {
        lineStyle: {
          color: '#e2e8f0',
          type: 'dashed'
        }
      }
    },
    series: [{
      name: 'VASI评分',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      data: scores,
      itemStyle: {
        color: function(params) {
          return colors[stages[params.dataIndex]]
        }
      },
      lineStyle: {
        width: 3,
        color: '#2b6cb0'
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [{
            offset: 0,
            color: 'rgba(43, 108, 176, 0.3)'
          }, {
            offset: 1,
            color: 'rgba(43, 108, 176, 0.05)'
          }]
        }
      },
      markPoint: {
        symbol: 'pin',
        symbolSize: 30,
        label: {
          show: false
        },
        data: stages.map((stage, index) => {
          if (stage === 'spreading') {
            return {
              name: '扩散',
              coord: [index, scores[index]],
              itemStyle: {
                color: '#e53e3e'
              }
            }
          } else if (stage === 'improving' && index === scores.length - 1) {
            return {
              name: '最新',
              coord: [index, scores[index]],
              itemStyle: {
                color: '#2f855a'
              }
            }
          }
          return null
        }).filter(Boolean)
      }
    }]
  }
  
  chartInstance.value.setOption(option)
}

function handleResize() {
  if (chartInstance.value) {
    chartInstance.value.resize()
  }
}

onMounted(async () => {
  await loadTrendData()
  
  if (trendData.value.length > 0) {
    setTimeout(() => initChart(), 100)
  }
})

onBeforeUnmount(() => {
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="vasi-page">
    <div class="vasi-header">
      <h1 class="vasi-title">📈 VASI趋势图</h1>
      <p class="vasi-subtitle">
        可视化展示您的病情变化趋势
      </p>
    </div>
    
    <div class="vasi-nav">
      <a href="/vasi/" class="vasi-nav-link">
        📊 开始评估
      </a>
      <a href="/vasi/history" class="vasi-nav-link">
        📜 历史记录
      </a>
    </div>
    
    <div class="filter-section">
      <div class="filter-group">
        <div class="filter-label">时间范围：</div>
        <div class="filter-buttons">
          <button
            v-for="range in TIME_RANGES"
            :key="range.value"
            @click="selectedTimeRange = range.value; loadTrendData()"
            :class="['filter-button', { 'is-active': selectedTimeRange === range.value }]"
          >
            {{ range.label }}
          </button>
        </div>
      </div>
      
      <div class="filter-group" style="margin-top: 1rem;">
        <div class="filter-label">筛选部位：</div>
        <div class="filter-buttons">
          <button
            v-for="site in bodySiteOptions"
            :key="site.value"
            @click="selectedBodySite = site.value; loadTrendData()"
            :class="['filter-button', { 'is-active': selectedBodySite === site.value }]"
          >
            {{ site.label }}
          </button>
        </div>
      </div>
    </div>
    
    <div class="vasi-loading" v-if="isLoading">
      <div class="vasi-spinner"></div>
      <p>加载中...</p>
    </div>
    
    <div class="error-message" v-else-if="errorMessage">
      ⚠️ {{ errorMessage }}
      <button @click="loadTrendData" class="retry-button">重试</button>
    </div>
    
    <div class="vasi-empty-state" v-else-if="trendData.length === 0">
      <div class="vasi-empty-icon">📉</div>
      <p class="vasi-empty-text">暂无趋势数据</p>
      <p class="vasi-empty-subtext">完成至少两次评估后可查看趋势图</p>
      <a href="/vasi/" class="start-assessment-button">开始评估</a>
    </div>
    
    <div v-else>
      <div class="vasi-summary-card" v-if="summaryData">
        <h2 class="summary-title">趋势总结</h2>
        <div class="vasi-summary-grid">
          <div class="vasi-summary-item">
            <div class="vasi-summary-label">首次评分</div>
            <div class="vasi-summary-value">{{ summaryData.firstScore }}</div>
          </div>
          <div class="vasi-summary-item">
            <div class="vasi-summary-label">最新评分</div>
            <div class="vasi-summary-value">{{ summaryData.lastScore }}</div>
          </div>
          <div class="vasi-summary-item">
            <div class="vasi-summary-label">变化量</div>
            <div 
              :class="['vasi-summary-value', summaryData.change > 0 ? 'negative' : 'positive']"
            >
              {{ summaryData.change > 0 ? '+' : '' }}{{ summaryData.change }}
            </div>
          </div>
          <div class="vasi-summary-item">
            <div class="vasi-summary-label">变化百分比</div>
            <div 
              :class="['vasi-summary-value', summaryData.change > 0 ? 'negative' : 'positive']"
            >
              {{ summaryData.change > 0 ? '+' : '' }}{{ summaryData.changePercent }}%
            </div>
          </div>
          <div class="vasi-summary-item">
            <div class="vasi-summary-label">趋势</div>
            <div class="vasi-summary-value">
              <span class="vasi-trend-indicator" :class="summaryData.trend">
                <template v-if="summaryData.trend === 'improving'">
                  ✅ 好转
                </template>
                <template v-else-if="summaryData.trend === 'stable'">
                  ⏸️ 稳定
                </template>
                <template v-else>
                  ⚠️ 扩散
                </template>
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="vasi-card">
        <div class="chart-header">
          <h2 class="vasi-card-title">趋势图表</h2>
          <div class="chart-legend">
            <span class="legend-item">
              <span class="legend-dot" style="background-color: #2f855a;"></span>
              好转
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background-color: #d69e2e;"></span>
              稳定
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background-color: #e53e3e;"></span>
              扩散
            </span>
          </div>
        </div>
        <div 
          ref="chartContainer" 
          class="vasi-chart-container"
        ></div>
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

.filter-group {
  display: flex;
  flex-direction: column;
}

.filter-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--subskin-color-text-light);
  margin-bottom: 0.75rem;
}

.filter-buttons {
  display: flex;
  gap: 0.5rem;
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

.summary-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: white;
  margin-bottom: 1.5rem;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.chart-legend {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--subskin-color-text-light);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.vasi-trend-indicator.up::before {
  content: '📈 ';
}

.vasi-trend-indicator.down::before {
  content: '📉 ';
}

.vasi-trend-indicator.neutral::before {
  content: '➡️ ';
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

@media (max-width: 640px) {
  .filter-buttons {
    flex-direction: column;
  }
  
  .filter-button {
    width: 100%;
  }
  
  .chart-legend {
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .vasi-summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
