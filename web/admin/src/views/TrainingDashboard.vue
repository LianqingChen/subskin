<script setup lang="ts">
/**
 * TrainingDashboard — VASI training data & model metrics dashboard.
 *
 * M3 will add: dataset stats, train/val/test split management,
 * model version metrics, retrain trigger, export pipeline.
 */

import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import request from '@/api/request'

const message = useMessage()

interface TrainingStats {
  total_samples: number
  train_count: number
  val_count: number
  test_count: number
  pending_sync: number
  last_export_at: string | null
  model_versions: Array<{
    version_tag: string
    metrics: Record<string, number>
    sample_count: number
    is_active: boolean
    created_at: string
  }>
}

const stats = ref<TrainingStats | null>(null)
const loading = ref(true)
const syncing = ref(false)

async function fetchStats() {
  loading.value = true
  try {
    const { data } = await request.get<TrainingStats>('/vasi/admin/training/dashboard')
    stats.value = data
  } catch (err: any) {
    if (err?.response?.status !== 404) {
      message.error('加载训练数据失败')
    }
  } finally {
    loading.value = false
  }
}

async function syncSamples() {
  syncing.value = true
  try {
    const { data } = await request.post<{ synced: number }>('/vasi/admin/training/sync-samples')
    message.success(`同步完成: ${data.synced} 条样本`)
    fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '同步失败')
  } finally {
    syncing.value = false
  }
}

onMounted(() => fetchStats())
</script>

<template>
  <div :style="{ padding: '0', color: '#e2e8f0' }">
    <div :style="{ marginBottom: '20px' }">
      <h2 :style="{ fontSize: '18px', fontWeight: 600, margin: 0 }">训练数据管理</h2>
      <p :style="{ color: '#94a3b8', marginTop: '4px', fontSize: '13px' }">管理 VASI 模型训练数据集和模型版本</p>
    </div>

    <div v-if="loading" :style="{ padding: '40px', textAlign: 'center', color: '#64748b' }">
      加载中...
    </div>

    <div v-else-if="!stats" :style="{ padding: '40px', textAlign: 'center' }">
      <p :style="{ color: '#64748b', fontSize: '13px' }">训练数据服务未就绪。完成图片打标后，标记为"训练就绪"的数据将自动同步到这里。</p>
    </div>

    <div v-else :style="{ display: 'flex', flexDirection: 'column', gap: '16px' }">
      <!-- Stats cards -->
      <div :style="{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }">
        <div :style="statCardStyle">
          <div :style="{ fontSize: '11px', color: '#94a3b8' }">总样本</div>
          <div :style="{ fontSize: '22px', fontWeight: 700, color: '#cbd5e1' }">{{ stats.total_samples }}</div>
        </div>
        <div :style="statCardStyle">
          <div :style="{ fontSize: '11px', color: '#93c5fd' }">训练集</div>
          <div :style="{ fontSize: '22px', fontWeight: 700, color: '#60a5fa' }">{{ stats.train_count }}</div>
        </div>
        <div :style="statCardStyle">
          <div :style="{ fontSize: '11px', color: '#f9a8d4' }">验证集</div>
          <div :style="{ fontSize: '22px', fontWeight: 700, color: '#f472b6' }">{{ stats.val_count }}</div>
        </div>
        <div :style="statCardStyle">
          <div :style="{ fontSize: '11px', color: '#6ee7b7' }">测试集</div>
          <div :style="{ fontSize: '22px', fontWeight: 700, color: '#34d399' }">{{ stats.test_count }}</div>
        </div>
      </div>

      <!-- Actions -->
      <div :style="{ display: 'flex', gap: '8px' }">
        <button
          :disabled="syncing"
          :style="{ padding: '8px 16px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }"
          @click="syncSamples"
        >
          <i :class="syncing ? 'ri-loader-4-line ri-spin' : 'ri-refresh-line'"></i>
          同步打标数据 ({{ stats.pending_sync }} 待同步)
        </button>
      </div>

      <!-- Model versions -->
      <div v-if="stats.model_versions.length > 0" :style="{ background: '#1e293b', borderRadius: '8px', padding: '16px', border: '1px solid rgba(148,163,184,0.12)' }">
        <div :style="{ fontSize: '13px', fontWeight: 600, color: '#cbd5e1', marginBottom: '12px' }">模型版本</div>
        <div :style="{ display: 'flex', flexDirection: 'column', gap: '8px' }">
          <div v-for="mv in stats.model_versions" :key="mv.version_tag"
            :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px', borderRadius: '6px', background: mv.is_active ? 'rgba(16,185,129,0.08)' : 'transparent', border: mv.is_active ? '1px solid rgba(16,185,129,0.2)' : '1px solid transparent' }">
            <div>
              <span :style="{ fontSize: '13px', fontWeight: 500, color: '#e2e8f0' }">{{ mv.version_tag }}</span>
              <span v-if="mv.is_active" :style="{ marginLeft: '8px', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(16,185,129,0.2)', color: '#6ee7b7' }">当前</span>
            </div>
            <div :style="{ fontSize: '11px', color: '#64748b' }">
              {{ mv.sample_count }} 样本 · {{ new Date(mv.created_at).toLocaleDateString('zh-CN') }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
.ri-spin { animation: spin 1s linear infinite; }
</style>

<script lang="ts">
const statCardStyle = {
  background: 'rgba(30,41,59,0.6)',
  border: '1px solid rgba(148,163,184,0.1)',
  borderRadius: '8px',
  padding: '14px',
}
</script>
