<template>
  <div class="training-page">
    <n-page-header title="训练数据管理" />
    <p class="page-desc">
      打标数据沉淀为训练样本 — 训练 U-Net 白斑识别模型，对比上线前后精度，持续优化测评与白斑报告
    </p>

    <!-- 统计卡片 -->
    <n-grid :cols="isMobile ? 2 : 4" :x-gap="12" :y-gap="12" style="margin-top: 20px" responsive="screen">
      <n-gi>
        <n-card size="small" class="stat-card"><n-statistic label="总样本" :value="stats?.total_samples ?? 0" /></n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card"><n-statistic label="有效样本（含管理员蒙层）" :value="stats?.usable_samples ?? 0" /></n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card"><n-statistic label="训练集" :value="stats?.train_count ?? 0" /></n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card"><n-statistic label="测试集" :value="stats?.test_count ?? 0" /></n-card>
      </n-gi>
    </n-grid>

    <!-- 训练控制 -->
    <n-card style="margin-top: 20px" :bordered="false" class="list-card">
      <template #header>
        <div class="card-header">
          <span><i class="ri-cpu-line" /> 模型训练</span>
          <n-space :size="8">
            <n-button size="small" :loading="syncing" @click="syncSamples">
              <template #icon><i class="ri-refresh-line" /></template>
              同步打标数据{{ stats && stats.pending_sync > 0 ? ` (${stats.pending_sync} 待同步)` : '' }}
            </n-button>
            <n-button size="small" type="primary" :disabled="trainingRunning" @click="showTrainConfirm = true">
              <template #icon><i class="ri-play-circle-line" /></template>
              训练模型
            </n-button>
          </n-space>
        </div>
      </template>

      <!-- 训练进行中：进度条 -->
      <div v-if="currentRun && (currentRun.status === 'running' || currentRun.status === 'pending')" class="train-progress">
        <div class="train-progress-info">
          <n-spin :size="16" />
          <span>{{ stageLabel(currentRun.stage) }} · {{ currentRun.progress }}%</span>
          <span class="muted">版本 {{ currentRun.version_tag || '生成中' }}</span>
        </div>
        <n-progress type="line" :percentage="currentRun.progress" :height="8" :show-indicator="false" />
        <div class="train-progress-hint">
          <i class="ri-information-line" /> 训练在后台执行（约 5-10 分钟），期间服务器 CPU 占用会上升；可离开本页，稍后回来查看结果。
        </div>
      </div>

      <!-- 训练失败 -->
      <div v-else-if="currentRun && currentRun.status === 'failed'" class="train-failed">
        <i class="ri-error-warning-line" />
        <div>
          <div class="train-failed-title">训练失败 ({{ currentRun.created_at || '' }})</div>
          <div class="train-failed-msg">{{ currentRun.error || '未知错误' }}</div>
        </div>
      </div>

      <!-- 最近一次完成：前后对比 + 上线 -->
      <div v-else-if="latestCompletedRun" class="train-result">
        <div class="train-result-header">
          <div class="train-result-title">
            <i class="ri-line-chart-line" />
            {{ latestCompletedRun.version_tag }} · 测试集 {{ latestCompletedRun.new_metrics?.test_size ?? latestCompletedRun.test_size ?? '-' }} 张
            <span class="muted">（{{ latestCompletedRun.finished_at || latestCompletedRun.created_at }}）</span>
          </div>
          <n-button
            v-if="pendingActivateVersionId"
            size="small"
            type="primary"
            :loading="activating"
            @click="activateVersion(pendingActivateVersionId)"
          >
            <template #icon><i class="ri-rocket-2-line" /></template>
            上线该模型
          </n-button>
          <n-tag v-else-if="latestCompletedRun.version_tag && isVersionActive(latestCompletedRun.version_tag)" size="small" type="success" :bordered="false">
            <i class="ri-check-line" /> 已上线
          </n-tag>
        </div>
        <div class="compare-metrics">
          <div class="metric-col">
            <div class="metric-col-title">训练前（当前线上）</div>
            <div class="metric-row"><span>Dice</span><b>{{ metricPct(latestCompletedRun.baseline_metrics?.dice) }}</b></div>
            <div class="metric-row"><span>IoU</span><b>{{ metricPct(latestCompletedRun.baseline_metrics?.iou) }}</b></div>
            <div class="metric-row"><span>面积误差</span><b>{{ areaPct(latestCompletedRun.baseline_metrics?.area_error_pct) }}</b></div>
          </div>
          <div class="metric-arrow"><i class="ri-arrow-right-line" /></div>
          <div class="metric-col new">
            <div class="metric-col-title">训练后（新模型）</div>
            <div class="metric-row"><span>Dice</span><b>{{ metricPct(latestCompletedRun.new_metrics?.dice) }}</b></div>
            <div class="metric-row"><span>IoU</span><b>{{ metricPct(latestCompletedRun.new_metrics?.iou) }}</b></div>
            <div class="metric-row"><span>面积误差</span><b>{{ areaPct(latestCompletedRun.new_metrics?.area_error_pct) }}</b></div>
          </div>
          <div class="metric-delta">
            <div :class="['delta-item', diceDelta > 0 ? 'up' : diceDelta < 0 ? 'down' : '']">
              <i :class="diceDelta > 0 ? 'ri-arrow-up-line' : diceDelta < 0 ? 'ri-arrow-down-line' : 'ri-subtract-line'" />
              Dice {{ diceDelta > 0 ? '+' : '' }}{{ diceDelta.toFixed(1) }}pt
            </div>
            <div :class="['delta-item', iouDelta > 0 ? 'up' : iouDelta < 0 ? 'down' : '']">
              <i :class="iouDelta > 0 ? 'ri-arrow-up-line' : iouDelta < 0 ? 'ri-arrow-down-line' : 'ri-subtract-line'" />
              IoU {{ iouDelta > 0 ? '+' : '' }}{{ iouDelta.toFixed(1) }}pt
            </div>
            <div class="delta-hint">确认新模型更优后再上线；上线后立即对测评 / 白斑报告生效</div>
          </div>
        </div>
      </div>

      <div v-else class="train-empty">
        <n-empty size="small" description="尚未训练过模型 — 完成打标并添加至训练样本后（需 ≥8 个有效样本），即可开始训练" />
      </div>
    </n-card>

    <!-- 训练样本列表 -->
    <n-card style="margin-top: 20px" :bordered="false" class="list-card">
      <template #header>
        <div class="card-header">
          <span><i class="ri-database-2-line" /> 训练样本 ({{ samplesTotal }})</span>
          <n-select
            v-model:value="sampleBodySite"
            :options="bodySiteOptions"
            size="small"
            clearable
            placeholder="身体部位"
            style="width: 140px"
            @update:value="applySampleFilter"
          />
        </div>
      </template>

      <n-spin :show="samplesLoading">
        <div v-if="samples.length === 0 && !samplesLoading" style="padding: 40px 0">
          <n-empty size="small" description="暂无训练样本 — 在图片打标页完成标注后点击「添加至训练样本」" />
        </div>
        <div v-else class="sample-rows">
          <div v-for="s in samples" :key="s.id" class="sample-row">
            <div class="sample-thumbs" @click="openCompare(s)">
              <div class="thumb-cell">
                <img v-if="s.image_label_id" :src="proxyImageUrl(s.image_label_id)" loading="lazy" alt="原图" @error="onThumbError" />
                <div v-else class="thumb-placeholder"><i class="ri-image-line" /></div>
                <span class="thumb-label">原图</span>
              </div>
              <div class="thumb-cell">
                <img
                  v-if="s.image_label_id && s.has_user_mask"
                  :src="userAnnotatedUrl(s.image_label_id)"
                  loading="lazy"
                  alt="用户标注"
                  @error="onAnnotatedError($event, '无用户标注')"
                />
                <div v-else class="thumb-placeholder"><i class="ri-user-line" /></div>
                <span class="thumb-label">用户标注</span>
              </div>
              <div class="thumb-cell">
                <img
                  v-if="s.image_label_id && s.has_admin_mask"
                  :src="adminAnnotatedUrl(s.image_label_id)"
                  loading="lazy"
                  alt="管理员标注"
                  @error="onAnnotatedError($event, '未标注')"
                />
                <div v-else class="thumb-placeholder"><i class="ri-edit-2-line" /></div>
                <span class="thumb-label">管理员标注</span>
              </div>
            </div>

            <div class="sample-body">
              <div class="sample-header">
                <span class="sample-id">样本 #{{ s.id }}</span>
                <n-tag v-if="s.body_site" size="tiny" :bordered="false">{{ s.body_site }}</n-tag>
                <n-tag v-if="s.vitiligo_type" size="tiny" :bordered="false" type="info">{{ s.vitiligo_type }}</n-tag>
                <n-tag v-if="s.stage" size="tiny" :bordered="false" type="warning">{{ s.stage }}</n-tag>
                <n-tag v-if="s.quality_level" size="tiny" :bordered="false" type="success">{{ s.quality_level }}</n-tag>
                <span v-if="s.dice_score != null" class="sample-dice">Dice {{ (s.dice_score * 100).toFixed(1) }}%</span>
              </div>
              <div class="sample-meta">
                <span v-if="s.username" class="sample-user"><i class="ri-user-line" /> {{ s.username }}（匿名）</span>
                <span v-else class="sample-user muted">管理员上传</span>
                <span v-if="s.sample_source" class="sample-source">{{ sourceLabel(s.sample_source) }}</span>
                <span class="sample-date">{{ formatShortDate(s.created_at) }}</span>
                <span v-if="!s.image_label_id" class="sample-unlinked"><i class="ri-error-warning-line" /> 未关联打标记录（重新同步可修复）</span>
              </div>
            </div>
          </div>
        </div>
      </n-spin>

      <n-space justify="end" style="margin-top: 16px">
        <n-pagination
          v-model:page="samplePage"
          :page-size="samplePageSize"
          :item-count="samplesTotal"
          @update:page="fetchSamples"
        />
      </n-space>
    </n-card>

    <!-- 模型版本 -->
    <n-card v-if="stats && stats.model_versions.length > 0" style="margin-top: 20px" :bordered="false" class="list-card">
      <template #header>
        <span><i class="ri-stack-line" /> 模型版本</span>
      </template>
      <div class="version-rows">
        <div
          v-for="mv in stats.model_versions"
          :key="mv.id"
          class="version-row"
          :class="{ active: mv.is_active }"
        >
          <div class="version-main">
            <span class="version-tag">{{ mv.version_tag }}</span>
            <n-tag v-if="mv.is_active" size="tiny" type="success" :bordered="false">当前线上</n-tag>
            <n-tag v-if="mv.evolution_layer && mv.evolution_layer !== 'model_weights'" size="tiny" :bordered="false">非权重版本</n-tag>
            <span v-if="mv.metrics?.dice != null" class="version-metric">Dice {{ metricPct(mv.metrics.dice) }}</span>
            <span v-if="mv.metrics?.iou != null" class="version-metric">IoU {{ metricPct(mv.metrics.iou) }}</span>
            <span class="version-meta">{{ mv.sample_count }} 测试样本 · {{ mv.deployed_at ? `上线 ${mv.deployed_at}` : `训练 ${mv.created_at || ''}` }}</span>
          </div>
          <n-button
            v-if="mv.evolution_layer === 'model_weights' && !mv.is_active"
            size="tiny"
            type="primary"
            ghost
            :loading="activating"
            @click="activateVersion(mv.id)"
          >
            上线
          </n-button>
          <n-popconfirm
            v-if="mv.evolution_layer === 'model_weights' && mv.is_active"
            positive-text="确认下线"
            negative-text="取消"
            @positive-click="deactivateVersion(mv.id)"
          >
            <template #trigger>
              <n-button size="tiny" type="warning" ghost :loading="activating">
                下线
              </n-button>
            </template>
            下线后识别将回退到 SAM→CV 链路，确认要下线 {{ mv.version_tag }} 吗？
          </n-popconfirm>
        </div>
      </div>
    </n-card>

    <!-- 训练历史 -->
    <n-card v-if="runs.length > 0" style="margin-top: 20px" :bordered="false" class="list-card">
      <template #header>
        <span><i class="ri-history-line" /> 训练历史</span>
      </template>
      <div class="run-rows">
        <div v-for="r in runs" :key="r.id" class="run-row">
          <span class="run-tag" :class="r.status">{{ r.version_tag || `run#${r.id}` }}</span>
          <n-tag size="tiny" :bordered="false" :type="runStatusType(r.status)">{{ runStatusLabel(r.status) }}</n-tag>
          <span class="run-metric">
            Dice {{ metricPct(r.baseline_metrics?.dice) }} → {{ metricPct(r.new_metrics?.dice) }}
          </span>
          <span class="run-meta">训练 {{ r.train_size ?? '-' }} / 测试 {{ r.test_size ?? '-' }}</span>
          <span class="run-time">{{ r.finished_at || r.created_at }}</span>
          <span v-if="r.error" class="run-error" :title="r.error"><i class="ri-error-warning-line" /></span>
        </div>
      </div>
    </n-card>

    <!-- 三图对比 Modal -->
    <n-modal
      v-model:show="compareVisible"
      preset="card"
      :bordered="false"
      style="width: 94vw; max-width: 1200px;"
      :title="compareSample ? `三图对比 · 样本 #${compareSample.id}${compareSample.username ? ' · ' + compareSample.username : ''}` : '三图对比'"
    >
      <div v-if="compareSample" class="compare-body">
        <div class="compare-grid">
          <div class="compare-cell">
            <img v-if="compareSample.image_label_id" :src="proxyImageUrl(compareSample.image_label_id)" alt="原图" @error="onThumbError" />
            <div v-else class="compare-empty"><i class="ri-image-line" /><span>未关联原图</span></div>
            <div class="compare-caption">原图</div>
          </div>
          <div class="compare-cell">
            <img
              v-if="compareSample.image_label_id && compareSample.has_user_mask"
              :src="userAnnotatedUrl(compareSample.image_label_id)"
              alt="用户标注"
              @error="onAnnotatedError($event, '无用户标注')"
            />
            <div v-else class="compare-empty"><i class="ri-user-line" /><span>无用户标注</span></div>
            <div class="compare-caption">用户标注（SubSkin 填涂）</div>
          </div>
          <div class="compare-cell">
            <img
              v-if="compareSample.image_label_id && compareSample.has_admin_mask"
              :src="adminAnnotatedUrl(compareSample.image_label_id)"
              alt="管理员标注"
              @error="onAnnotatedError($event, '未标注')"
            />
            <div v-else class="compare-empty"><i class="ri-edit-2-line" /><span>未标注</span></div>
            <div class="compare-caption">管理员标注</div>
          </div>
        </div>
        <div class="compare-summary">
          <n-tag v-if="compareSample.body_site" size="small" :bordered="false">{{ compareSample.body_site }}</n-tag>
          <n-tag v-if="compareSample.vitiligo_type" size="small" :bordered="false" type="info">{{ compareSample.vitiligo_type }}</n-tag>
          <span v-if="compareSample.dice_score != null" class="summary-item">Dice: {{ (compareSample.dice_score * 100).toFixed(1) }}%</span>
          <span class="summary-item muted">{{ formatShortDate(compareSample.created_at) }}</span>
        </div>
      </div>
    </n-modal>

    <!-- 训练确认 Modal -->
    <n-modal
      v-model:show="showTrainConfirm"
      preset="card"
      :bordered="false"
      title="开始训练模型"
      style="width: 520px; max-width: 94vw;"
    >
      <div class="confirm-body">
        <div class="confirm-row">
          <i class="ri-database-2-line" />
          <span>有效训练样本：<b>{{ stats?.usable_samples ?? 0 }}</b> 个（需 ≥ {{ MIN_SAMPLES }}，含管理员标注蒙层）</span>
        </div>
        <div class="confirm-row">
          <i class="ri-scales-3-line" />
          <span>随机抽取 20% 作为测试集（用于训练前后精度对比），其余作为训练集</span>
        </div>
        <div class="confirm-row">
          <i class="ri-time-line" />
          <span>CPU 训练轻量 U-Net，预计 5-10 分钟内完成</span>
        </div>
        <div class="confirm-warning">
          <i class="ri-alert-line" />
          训练期间服务器 CPU 占用会明显上升（后端为共享环境，测评等请求可能变慢）。训练完成后需手动确认上线，不会自动替换线上模型。
        </div>
      </div>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showTrainConfirm = false">取消</n-button>
          <n-button
            type="primary"
            :disabled="(stats?.usable_samples ?? 0) < MIN_SAMPLES"
            :loading="startingTrain"
            @click="startTraining"
          >
            <template #icon><i class="ri-play-circle-line" /></template>
            开始训练
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  NPageHeader, NGrid, NGi, NCard, NStatistic, NTag, NButton,
  NModal, NSpace, NEmpty, NSpin, NPagination, NSelect, NProgress,
  useMessage,
} from 'naive-ui'
import request from '@/api/request'

const message = useMessage()

const MIN_SAMPLES = 8

const isMobile = ref(false)
function checkMobile() { isMobile.value = window.innerWidth <= 768 }

// ── 类型 ──

interface ModelVersion {
  id: number
  version_tag: string
  description: string | null
  evolution_layer: string | null
  metrics: Record<string, any>
  sample_count: number
  is_active: boolean
  deployed_at: string | null
  created_at: string | null
}

interface TrainingStats {
  total_samples: number
  usable_samples: number
  train_count: number
  test_count: number
  pending_sync: number
  training_running: boolean
  last_export_at: string | null
  model_versions: ModelVersion[]
}

interface TrainingRun {
  id: number
  status: string
  progress: number
  stage: string | null
  train_size: number | null
  test_size: number | null
  baseline_metrics: Record<string, any> | null
  new_metrics: Record<string, any> | null
  version_tag: string | null
  error: string | null
  started_by: number | null
  created_at: string | null
  finished_at: string | null
}

interface TrainingSample {
  id: number
  image_label_id: number | null
  image_hash: string | null
  body_site: string | null
  vitiligo_type: string | null
  stage: string | null
  quality_level: string | null
  sample_source: string | null
  dice_score: number | null
  has_user_mask: boolean
  has_admin_mask: boolean
  username: string | null
  created_at: string | null
}

// ── 统计 ──

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
    await Promise.all([fetchStats(), fetchSamples()])
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '同步失败')
  } finally {
    syncing.value = false
  }
}

// ── 训练状态与轮询 ──

const currentRun = ref<TrainingRun | null>(null)
const runs = ref<TrainingRun[]>([])
const trainingRunning = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const latestCompletedRun = computed(() => {
  if (currentRun.value && currentRun.value.status === 'completed') return currentRun.value
  return runs.value.find(r => r.status === 'completed') || null
})

const diceDelta = computed(() => {
  const run = latestCompletedRun.value
  if (!run) return 0
  const b = Number(run.baseline_metrics?.dice)
  const n = Number(run.new_metrics?.dice)
  if (!isFinite(b) || !isFinite(n)) return 0
  return (n - b) * 100
})

const iouDelta = computed(() => {
  const run = latestCompletedRun.value
  if (!run) return 0
  const b = Number(run.baseline_metrics?.iou)
  const n = Number(run.new_metrics?.iou)
  if (!isFinite(b) || !isFinite(n)) return 0
  return (n - b) * 100
})

// 已完成但尚未上线的最新版本 → 显示「上线」按钮
const pendingActivateVersionId = computed(() => {
  const run = latestCompletedRun.value
  if (!run || !run.version_tag) return null
  const version = stats.value?.model_versions.find(mv => mv.version_tag === run.version_tag)
  if (!version || version.is_active) return null
  return version.id
})

function isVersionActive(versionTag: string): boolean {
  return !!stats.value?.model_versions.some(mv => mv.version_tag === versionTag && mv.is_active)
}

async function fetchStatus() {
  try {
    const { data } = await request.get<{ running: boolean; run: TrainingRun | null }>('/vasi/admin/training/train/status')
    trainingRunning.value = data.running
    currentRun.value = data.run
    if (data.running && !pollTimer) startPolling()
    if (!data.running && pollTimer) {
      // 训练刚结束：刷新全部数据
      stopPolling()
      await refreshAll()
      if (data.run?.status === 'completed') message.success('模型训练完成，请查看前后对比指标')
      else if (data.run?.status === 'failed') message.error('模型训练失败：' + (data.run.error || '未知错误'))
    }
  } catch { /* 轮询失败静默 */ }
}

async function fetchRuns() {
  try {
    const { data } = await request.get<{ items: TrainingRun[] }>('/vasi/admin/training/runs', { params: { limit: 10 } })
    runs.value = data.items
  } catch { /* 静默 */ }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(fetchStatus, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function refreshAll() {
  await Promise.all([fetchStats(), fetchSamples(), fetchRuns()])
}

// ── 触发训练 ──

const showTrainConfirm = ref(false)
const startingTrain = ref(false)

async function startTraining() {
  startingTrain.value = true
  try {
    const { data } = await request.post<{ status: string; run_id: number }>('/vasi/admin/training/train')
    if (data.status === 'ok') {
      message.success('训练已启动')
      showTrainConfirm.value = false
      await fetchStatus()
      startPolling()
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '启动训练失败')
  } finally {
    startingTrain.value = false
  }
}

// ── 模型上线 ──

const activating = ref(false)

async function activateVersion(versionId: number) {
  activating.value = true
  try {
    const { data } = await request.post<{ status: string; version_tag: string }>(`/vasi/admin/training/models/${versionId}/activate`)
    if (data.status === 'already_active') {
      message.info(`版本 ${data.version_tag} 已是当前线上版本`)
    } else {
      message.success(`版本 ${data.version_tag} 已上线，测评/白斑报告即刻生效`)
    }
    await fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '上线失败')
  } finally {
    activating.value = false
  }
}

async function deactivateVersion(versionId: number) {
  activating.value = true
  try {
    const { data } = await request.post<{ status: string; version_tag: string }>(`/vasi/admin/training/models/${versionId}/deactivate`)
    if (data.status === 'already_inactive') {
      message.info(`版本 ${data.version_tag} 当前未上线`)
    } else {
      message.success(`版本 ${data.version_tag} 已下线，识别回退到 SAM→CV 链路`)
    }
    await fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '下线失败')
  } finally {
    activating.value = false
  }
}

// ── 训练样本列表 ──

const samples = ref<TrainingSample[]>([])
const samplesTotal = ref(0)
const samplesLoading = ref(false)
const samplePage = ref(1)
const samplePageSize = 20
const sampleBodySite = ref<string | null>(null)

const bodySiteOptions = [
  '面部', '颈部', '头皮', '躯干前面', '躯干后面', '上肢近端', '上肢远端',
  '手部', '下肢近端', '下肢远端', '足部', '生殖器', '其他',
].map(s => ({ label: s, value: s }))

function applySampleFilter() {
  samplePage.value = 1
  fetchSamples()
}

async function fetchSamples() {
  samplesLoading.value = true
  try {
    const params: Record<string, any> = {
      limit: samplePageSize,
      offset: (samplePage.value - 1) * samplePageSize,
    }
    if (sampleBodySite.value) params.body_site = sampleBodySite.value
    const { data } = await request.get<{ total: number; items: TrainingSample[] }>('/vasi/admin/training/samples', { params })
    samples.value = data.items
    samplesTotal.value = data.total
  } catch {
    message.error('加载训练样本失败')
  } finally {
    samplesLoading.value = false
  }
}

// ── 三图对比 Modal ──

const compareVisible = ref(false)
const compareSample = ref<TrainingSample | null>(null)

function openCompare(s: TrainingSample) {
  compareSample.value = s
  compareVisible.value = true
}

// ── 图片 URL（query token 鉴权，走 image_label 三图端点） ──

function adminToken(): string {
  return localStorage.getItem('admin_token') || ''
}

function proxyImageUrl(labelId: number): string {
  return `/api/vasi/admin/image-labels/${labelId}/image?access_token=${encodeURIComponent(adminToken())}`
}

function userAnnotatedUrl(labelId: number): string {
  return `/api/vasi/admin/image-labels/${labelId}/user-annotated-image?access_token=${encodeURIComponent(adminToken())}`
}

function adminAnnotatedUrl(labelId: number): string {
  return `/api/vasi/admin/image-labels/${labelId}/annotated-image?access_token=${encodeURIComponent(adminToken())}`
}

function onThumbError(event: Event) {
  const img = event.target as HTMLImageElement
  if (img.dataset.fallback === '1') return
  img.dataset.fallback = '1'
  img.src = placeholderSvg('图加载失败')
}

// 404（无该来源标注）时显示语义化占位而非“加载失败”
function onAnnotatedError(event: Event, text: string) {
  const img = event.target as HTMLImageElement
  if (img.dataset.fallback === '1') return
  img.dataset.fallback = '1'
  img.src = placeholderSvg(text)
}

function placeholderSvg(text: string): string {
  return 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120" viewBox="0 0 160 120">' +
      '<rect width="160" height="120" fill="#1e293b"/>' +
      `<text x="80" y="65" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#64748b">${text}</text>` +
      '</svg>',
  )
}

// ── 格式化 ──

function metricPct(v: any): string {
  const n = Number(v)
  if (!isFinite(n)) return '-'
  return (n * 100).toFixed(1) + '%'
}

function areaPct(v: any): string {
  const n = Number(v)
  if (!isFinite(n)) return '-'
  return n.toFixed(1) + '%'
}

function formatShortDate(dateStr?: string | null) {
  if (!dateStr) return '-'
  return dateStr
}

function stageLabel(stage?: string | null): string {
  const labels: Record<string, string> = {
    collect: '收集样本',
    split: '划分数据集',
    baseline: '基线评估（当前模型）',
    train: '训练 U-Net',
    eval: '评估新模型',
    done: '完成',
  }
  return stage ? (labels[stage] || stage) : '准备中'
}

function runStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '等待中',
    running: '训练中',
    completed: '已完成',
    failed: '失败',
  }
  return labels[status] || status
}

function runStatusType(status: string): 'default' | 'info' | 'success' | 'error' | 'warning' {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'info'
    case 'failed': return 'error'
    default: return 'default'
  }
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    admin_label: '管理员打标',
    user_correction: '用户修正',
    ai_prediction: 'AI 预测',
  }
  return labels[source] || source
}

// ── 生命周期 ──

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  await Promise.all([fetchStats(), fetchSamples(), fetchRuns(), fetchStatus()])
})

onUnmounted(() => {
  stopPolling()
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.training-page { padding: 0; }
.page-desc {
  color: #94a3b8;
  margin: 6px 0 0;
  font-size: 13px;
}
.stat-card { background-color: #1e293b; }
.list-card { background-color: #1e293b; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 8px;
}
.card-header > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
}

/* ── 训练进度 ── */
.train-progress { display: flex; flex-direction: column; gap: 10px; padding: 4px 0; }
.train-progress-info { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #e2e8f0; }
.train-progress-info .muted { color: #64748b; font-size: 12px; }
.train-progress-hint {
  font-size: 11px;
  color: #64748b;
  display: flex;
  gap: 4px;
  align-items: center;
}

.train-failed {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #f87171;
  font-size: 20px;
  align-items: flex-start;
}
.train-failed-title { font-size: 13px; font-weight: 600; color: #fca5a5; }
.train-failed-msg { font-size: 12px; color: #f87171; margin-top: 4px; }

/* ── 训练结果对比 ── */
.train-result { display: flex; flex-direction: column; gap: 14px; }
.train-result-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.train-result-title {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.train-result-title .muted { color: #64748b; font-weight: 400; font-size: 11px; }

.compare-metrics {
  display: flex;
  gap: 14px;
  align-items: stretch;
  flex-wrap: wrap;
}
.metric-col {
  flex: 1;
  min-width: 180px;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.metric-col.new { border-color: rgba(99, 102, 241, 0.35); }
.metric-col-title { font-size: 11px; color: #64748b; }
.metric-row { display: flex; justify-content: space-between; font-size: 12px; color: #94a3b8; }
.metric-row b { color: #e2e8f0; font-variant-numeric: tabular-nums; }
.metric-col.new .metric-row b { color: #a5b4fc; }

.metric-arrow {
  display: flex;
  align-items: center;
  color: #475569;
  font-size: 18px;
}

.metric-delta {
  flex: 1;
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
}
.delta-item { font-size: 13px; color: #94a3b8; display: flex; align-items: center; gap: 4px; font-variant-numeric: tabular-nums; }
.delta-item.up { color: #34d399; }
.delta-item.down { color: #f87171; }
.delta-hint { font-size: 11px; color: #64748b; margin-top: 4px; line-height: 1.5; }

.train-empty { padding: 20px 0; }

/* ── 样本列表 ── */
.sample-rows { display: flex; flex-direction: column; gap: 10px; }
.sample-row {
  display: flex;
  gap: 14px;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.08);
  transition: border-color 0.15s;
}
.sample-row:hover { border-color: rgba(99, 102, 241, 0.3); }

.sample-thumbs { display: flex; gap: 6px; flex-shrink: 0; cursor: pointer; }
.thumb-cell {
  position: relative;
  width: 72px;
  height: 92px;
  border-radius: 6px;
  overflow: hidden;
  background: #1e293b;
  border: 1px solid rgba(148, 163, 184, 0.12);
}
.thumb-cell img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #475569;
  font-size: 18px;
}
.thumb-label {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 1px 2px;
  font-size: 10px;
  text-align: center;
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.72);
  white-space: nowrap;
  overflow: hidden;
}

.sample-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; justify-content: center; }
.sample-header { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.sample-id { font-size: 12px; color: #94a3b8; font-weight: 600; }
.sample-dice { font-size: 11px; color: #6ee7b7; margin-left: auto; font-variant-numeric: tabular-nums; }
.sample-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 11px; }
.sample-user { color: #a5b4fc; display: inline-flex; align-items: center; gap: 3px; }
.sample-user.muted { color: #64748b; }
.sample-source { color: #64748b; }
.sample-date { color: #475569; margin-left: auto; }
.sample-unlinked { color: #fbbf24; display: inline-flex; align-items: center; gap: 3px; }

/* ── 模型版本 ── */
.version-rows { display: flex; flex-direction: column; gap: 8px; }
.version-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.08);
  background: #0f172a;
}
.version-row.active { background: rgba(16, 185, 129, 0.06); border-color: rgba(16, 185, 129, 0.25); }
.version-main { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.version-tag { font-size: 13px; font-weight: 500; color: #e2e8f0; }
.version-metric { font-size: 11px; color: #6ee7b7; font-variant-numeric: tabular-nums; }
.version-meta { font-size: 11px; color: #64748b; }

/* ── 训练历史 ── */
.run-rows { display: flex; flex-direction: column; gap: 6px; }
.run-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.06);
  font-size: 12px;
}
.run-tag { font-weight: 600; color: #cbd5e1; min-width: 120px; }
.run-metric { color: #94a3b8; font-variant-numeric: tabular-nums; }
.run-meta { color: #64748b; }
.run-time { color: #475569; margin-left: auto; }
.run-error { color: #f87171; }

/* ── 三图对比 Modal ── */
.compare-body { display: flex; flex-direction: column; gap: 14px; }
.compare-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.compare-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 8px;
  padding: 8px;
}
.compare-cell img { width: 100%; height: 280px; object-fit: contain; display: block; border-radius: 4px; }
.compare-empty {
  height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #475569;
  font-size: 28px;
}
.compare-empty span { font-size: 12px; color: #64748b; }
.compare-caption { font-size: 12px; color: #94a3b8; text-align: center; }
.compare-summary { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.summary-item { font-size: 12px; color: #94a3b8; }
.summary-item.muted { color: #64748b; }

/* ── 训练确认 Modal ── */
.confirm-body { display: flex; flex-direction: column; gap: 10px; }
.confirm-row { display: flex; align-items: flex-start; gap: 8px; font-size: 13px; color: #cbd5e1; }
.confirm-row i { color: #64748b; font-size: 15px; margin-top: 1px; }
.confirm-row b { color: #e2e8f0; }
.confirm-warning {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(234, 179, 8, 0.08);
  border: 1px solid rgba(234, 179, 8, 0.25);
  font-size: 12px;
  color: #fbbf24;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .compare-grid { grid-template-columns: 1fr; }
  .compare-cell img, .compare-empty { height: 200px; }
  .sample-row { flex-direction: column; }
  .metric-arrow { display: none; }
}
</style>
