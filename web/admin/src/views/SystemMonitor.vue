<template>
  <div class="system-monitor-page">
    <n-page-header title="系统监控" />
    <p class="page-desc">实时监控系统资源与服务状态，支持服务启停操作</p>

    <!-- 统计卡片 -->
    <n-grid :cols="isMobile ? 2 : 4" :x-gap="16" :y-gap="16" style="margin-top: 24px" responsive="screen">
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="CPU 使用率">
            <template #prefix>
              <i class="ri-cpu-line stat-icon" style="color: #6366f1;" />
            </template>
            <span :style="{ color: getUsageColor(resources.cpu) }">{{ resources.cpu }}%</span>
          </n-statistic>
          <n-progress
            type="line"
            :percentage="resources.cpu"
            color="#6366f1"
            style="margin-top: 8px"
            :show-indicator="false"
          />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="内存使用率">
            <template #prefix>
              <i class="ri-database-2-line stat-icon" style="color: #10b981;" />
            </template>
            <span :style="{ color: getUsageColor(resources.memory) }">{{ resources.memory }}%</span>
          </n-statistic>
          <n-progress
            type="line"
            :percentage="resources.memory"
            color="#10b981"
            style="margin-top: 8px"
            :show-indicator="false"
          />
          <div style="margin-top: 6px; color: #94a3b8; font-size: 12px;">
            {{ resources.memoryUsed }} / {{ resources.memoryTotal }}
          </div>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="磁盘使用率">
            <template #prefix>
              <i class="ri-hard-drive-2-line stat-icon" style="color: #f59e0b;" />
            </template>
            <span :style="{ color: getUsageColor(resources.disk) }">{{ resources.disk }}%</span>
          </n-statistic>
          <n-progress
            type="line"
            :percentage="resources.disk"
            color="#f59e0b"
            style="margin-top: 8px"
            :show-indicator="false"
          />
          <div style="margin-top: 6px; color: #94a3b8; font-size: 12px;">
            {{ resources.diskUsed }} / {{ resources.diskTotal }}
          </div>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="SQLite DB 大小">
            <template #prefix>
              <i class="ri-file-list-3-line stat-icon" style="color: #ef4444;" />
            </template>
            <span>{{ resources.dbSize }}</span>
          </n-statistic>
          <div style="margin-top: 8px; color: #94a3b8; font-size: 12px;">
            /root/subskin/data/subskin.db
          </div>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- 系统负载快照 -->
    <n-grid :cols="isMobile ? 1 : 4" :x-gap="16" :y-gap="16" style="margin-top: 16px" responsive="screen">
      <n-gi>
        <n-card size="small" class="info-card">
          <div class="info-label">操作系统</div>
          <div class="info-value">{{ hostInfo.os }}</div>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="info-card">
          <div class="info-label">CPU 核心数</div>
          <div class="info-value">{{ hostInfo.cpuCores }}</div>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="info-card">
          <div class="info-label">系统运行时间</div>
          <div class="info-value">{{ hostInfo.uptime }}</div>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="info-card">
          <div class="info-label">最后刷新</div>
          <div class="info-value">{{ lastRefreshText }}</div>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- 服务状态 -->
    <n-card title="服务状态" style="margin-top: 24px" :bordered="false" class="table-card">
      <template #header-extra>
        <n-button size="small" @click="fetchAll" :loading="loading">
          <template #icon><i class="ri-refresh-line" /></template>
          刷新
        </n-button>
      </template>
      <n-data-table
        :columns="serviceColumns"
        :data="services"
        :bordered="false"
        :single-line="false"
        :row-key="(row: ServiceItem) => row.name"
        :loading="servicesLoading"
      />
    </n-card>

    <!-- 知识库向量化 -->
    <n-card title="知识库向量化 (Embedding)" style="margin-top: 24px" :bordered="false" class="table-card">
      <template #header-extra>
        <n-tag size="small" type="warning">手动触发</n-tag>
      </template>
      <n-space vertical :size="12">
        <p style="color: #94a3b8; font-size: 13px; margin: 0;">
          对 embedding 为空的文献文档执行增量向量化。此任务已从自动调度改为手动触发，点击按钮开始执行。
        </p>
        <n-space align="center">
          <n-button
            type="primary"
            :loading="embedLoading"
            :disabled="embedLoading"
            @click="handleTriggerEmbed"
          >
            <template #icon><i class="ri-database-2-line" /></template>
            {{ embedLoading ? '向量化执行中...' : '触发文献向量化' }}
          </n-button>
          <n-tag v-if="embedResult" size="small" :type="embedResult.failed_count > 0 ? 'warning' : 'success'">
            成功 {{ embedResult.embedded_count }} / 失败 {{ embedResult.failed_count }} / 总计 {{ embedResult.total }}
          </n-tag>
        </n-space>
        <p v-if="embedError" style="color: #ef4444; font-size: 12px; margin: 0;">{{ embedError }}</p>
      </n-space>
    </n-card>

    <!-- 日志查看 -->
    <n-card title="日志查看" style="margin-top: 24px" :bordered="false" class="log-card">
      <template #header-extra>
        <n-space align="center">
          <n-select
            v-model:value="logService"
            :options="logServiceOptions"
            size="small"
            style="width: 180px"
            @update:value="fetchLogs"
          />
          <n-button size="small" @click="fetchLogs" :loading="logsLoading">
            <template #icon><i class="ri-refresh-line" /></template>
            刷新
          </n-button>
        </n-space>
      </template>
      <n-space vertical>
        <n-space align="center" style="margin-bottom: 4px">
          <n-tag size="small" type="info">{{ logServiceLabel }}</n-tag>
          <n-tag size="small" type="default">{{ logLines }} 行</n-tag>
        </n-space>
        <div class="log-container">
          <n-code
            v-if="logText"
            :code="logText"
            language="plaintext"
            show-line-numbers
          />
          <n-empty v-else description="暂无日志" size="small" />
        </div>
      </n-space>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, h, computed } from 'vue'
import {
  NPageHeader,
  NGrid,
  NGi,
  NCard,
  NStatistic,
  NProgress,
  NDataTable,
  NTag,
  NButton,
  NSelect,
  NSpace,
  NCode,
  NEmpty,
  useMessage,
  useDialog,
} from 'naive-ui'
import request from '@/api/request'

const message = useMessage()
const dialog = useDialog()

// ── Types ──
interface ResourceData {
  cpu: number
  memory: number
  memoryUsed: string
  memoryTotal: string
  disk: number
  diskUsed: string
  diskTotal: string
  dbSize: string
}

interface HostInfoData {
  os: string
  cpuCores: string
  uptime: string
}

interface ServiceItem {
  name: string
  status: string
  actionLoading?: boolean
}

const isMobile = ref(false)
function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

// ── State ──
const resources = ref<ResourceData>({
  cpu: 0,
  memory: 0,
  memoryUsed: '-',
  memoryTotal: '-',
  disk: 0,
  diskUsed: '-',
  diskTotal: '-',
  dbSize: '-',
})

const hostInfo = ref<HostInfoData>({
  os: '-',
  cpuCores: '-',
  uptime: '-',
})

const services = ref<ServiceItem[]>([])
const servicesLoading = ref(false)
const logsLoading = ref(false)
const loading = ref(false)
const logText = ref('')
const logService = ref('subskin-backend')
const logLines = ref(50)
const lastRefreshText = ref('')

// ── Embedding 手动触发 ──
const embedLoading = ref(false)
const embedResult = ref<{ embedded_count: number; failed_count: number; total: number } | null>(null)
const embedError = ref('')

const logServiceOptions = [
  { label: 'subskin-backend', value: 'subskin-backend' },
  { label: 'subskin-scheduler', value: 'subskin-scheduler' },
  { label: 'nginx', value: 'nginx' },
  { label: '应用日志 (subskin.log)', value: 'file' },
]

const logServiceLabel = computed(() => {
  if (logService.value === 'file') return '/root/subskin/logs/subskin.log'
  return `journalctl -u ${logService.value}`
})

let refreshTimer: ReturnType<typeof setInterval> | null = null

// ── Table columns ──
const serviceColumns = [
  {
    title: '服务名称',
    key: 'name',
    width: 220,
    ellipsis: { tooltip: true },
  },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render(row: ServiceItem) {
      const typeMap: Record<string, string> = {
        running: 'success',
        stopped: 'default',
        error: 'error',
        unknown: 'warning',
      }
      const labelMap: Record<string, string> = {
        running: '运行中',
        stopped: '已停止',
        error: '异常',
        unknown: '未知',
      }
      return h(NTag, { type: typeMap[row.status] as any, size: 'small' }, {
        default: () => labelMap[row.status] || row.status,
      })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    fixed: 'right' as const,
    render(row: ServiceItem) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          row.status === 'running'
            ? h(
                NButton,
                {
                  size: 'small',
                  type: 'warning',
                  loading: row.actionLoading,
                  onClick: () => handleServiceAction(row, 'restart'),
                },
                { default: () => '重启' },
              )
            : h(
                NButton,
                {
                  size: 'small',
                  type: 'primary',
                  loading: row.actionLoading,
                  onClick: () => handleServiceAction(row, 'start'),
                },
                { default: () => '启动' },
              ),
          row.status === 'running'
            ? h(
                NButton,
                {
                  size: 'small',
                  type: 'error',
                  loading: row.actionLoading,
                  onClick: () => handleServiceAction(row, 'stop'),
                },
                { default: () => '停止' },
              )
            : null,
        ].filter(Boolean),
      })
    },
  },
]

// ── Helpers ──
function getUsageColor(value: number) {
  if (value >= 90) return '#ef4444'
  if (value >= 70) return '#f59e0b'
  return '#e2e8f0'
}

function formatBytes(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days} 天 ${hours} 小时`
  if (hours > 0) return `${hours} 小时 ${mins} 分钟`
  return `${mins} 分钟`
}

// ── Actions ──
function handleServiceAction(service: ServiceItem, action: string) {
  const labels: Record<string, string> = {
    start: '启动',
    stop: '停止',
    restart: '重启',
  }
  const label = labels[action] || action

  dialog.warning({
    title: `确认${label}`,
    content: `确定要${label}服务「${service.name}」吗？${
      action === 'stop' ? '此操作会使该服务不可用。' : action === 'restart' ? '重启期间服务会短暂中断。' : ''
    }`,
    positiveText: `确认${label}`,
    negativeText: '取消',
    onPositiveClick: () => executeServiceAction(service, action),
  })
}

async function executeServiceAction(service: ServiceItem, action: string) {
  service.actionLoading = true
  try {
    const { data } = await request.post(`/admin/system/services/${service.name}/action`, null, {
      params: { action },
    })
    if (data.status === 'ok') {
      message.success(`服务「${service.name}」${action === 'start' ? '启动' : action === 'stop' ? '停止' : '重启'}成功`)
      // Wait a moment for the service to settle, then refresh
      setTimeout(() => fetchAll(), 2000)
    } else {
      message.error(`操作失败：${data.stderr || '未知错误'}`)
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '操作失败，请检查后端服务权限')
  } finally {
    service.actionLoading = false
  }
}

// ── Embedding 触发 ──
async function handleTriggerEmbed() {
  dialog.warning({
    title: '确认触发向量化',
    content: '将对所有 embedding 为空的文献执行向量化，可能耗时较长（取决于文档数量）。确定继续？',
    positiveText: '确认执行',
    negativeText: '取消',
    onPositiveClick: async () => {
      embedLoading.value = true
      embedResult.value = null
      embedError.value = ''
      try {
        const { data } = await request.post('/admin/embed-batch')
        if (data.status === 'ok') {
          embedResult.value = data.result
          message.success(`向量化完成：成功 ${data.result.embedded_count}，失败 ${data.result.failed_count}`)
        } else {
          embedError.value = '向量化任务返回异常状态'
          message.error('向量化任务执行异常')
        }
      } catch (err: any) {
        embedError.value = err?.response?.data?.detail || '向量化请求失败，请稍后重试'
        message.error(embedError.value)
      } finally {
        embedLoading.value = false
      }
    },
  })
}

// ── API ──
async function fetchResources() {
  try {
    const { data } = await request.get('/admin/system/resources')
    resources.value = {
      cpu: data.cpu_percent ?? 0,
      memory: data.memory_percent ?? 0,
      memoryUsed: data.memory_used_mb != null ? formatBytes(data.memory_used_mb) : '-',
      memoryTotal: data.memory_total_mb != null ? formatBytes(data.memory_total_mb) : '-',
      disk: data.disk_percent ?? 0,
      diskUsed: data.disk_used_gb != null ? `${data.disk_used_gb} GB` : '-',
      diskTotal: data.disk_total_gb != null ? `${data.disk_total_gb} GB` : '-',
      dbSize: data.db_size_mb != null ? formatBytes(data.db_size_mb) : '-',
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取系统资源数据失败')
  }
}

async function fetchServices() {
  servicesLoading.value = true
  try {
    const { data } = await request.get('/admin/system/services')
    // Backend returns { services: [...] }
    const list = data.services || data
    services.value = (Array.isArray(list) ? list : []).map((s: any) => ({
      name: s.name,
      status: s.status || 'unknown',
      actionLoading: false,
    }))
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取服务状态失败')
    services.value = []
  } finally {
    servicesLoading.value = false
  }
}

async function fetchLogs() {
  logsLoading.value = true
  try {
    const { data } = await request.get('/admin/system/logs', {
      params: { lines: logLines.value, service: logService.value },
    })
    // Backend returns { service, lines: [...] }
    const lines = data.lines || data
    if (Array.isArray(lines)) {
      logText.value = lines.join('\n')
    } else if (typeof lines === 'string') {
      logText.value = lines
    } else {
      logText.value = '暂无日志'
    }
  } catch (err: any) {
    logText.value = `获取日志失败: ${err?.response?.data?.detail || err?.message || '未知错误'}`
  } finally {
    logsLoading.value = false
  }
}

async function fetchHostInfo() {
  try {
    const { data } = await request.get('/admin/system/resources')
    hostInfo.value = {
      os: 'Linux',
      cpuCores: data.cpu_cores != null ? `${data.cpu_cores} 核` : '-',
      uptime: data.uptime_seconds != null ? formatUptime(data.uptime_seconds) : '-',
    }
  } catch {
    // Host info is nice-to-have, silent fail
  }
}

function updateRefreshTime() {
  const now = new Date()
  lastRefreshText.value = now.toLocaleTimeString('zh-CN')
}

async function fetchAll() {
  loading.value = true
  await Promise.all([fetchResources(), fetchServices(), fetchLogs(), fetchHostInfo()])
  updateRefreshTime()
  loading.value = false
}

// ── Lifecycle ──
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchAll()
  refreshTimer = setInterval(() => {
    fetchAll()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.system-monitor-page {
  padding: 0;
}

.page-desc {
  color: #94a3b8;
  margin-top: 8px;
  font-size: 14px;
}

.stat-card {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.stat-card :deep(.n-card__content) {
  padding: 16px;
}

.stat-icon {
  font-size: 20px;
  margin-right: 8px;
  vertical-align: middle;
}

.info-card {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(148, 163, 184, 0.08);
  text-align: center;
}

.info-card :deep(.n-card__content) {
  padding: 12px 16px;
}

.info-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: #e2e8f0;
}

.table-card {
  background-color: #1e293b;
}

.log-card {
  background-color: #1e293b;
}

.log-container {
  max-height: 400px;
  overflow: auto;
  background: #0f172a;
  border-radius: 6px;
  padding: 12px;
}

:deep(.n-data-table .n-data-table-td) {
  background-color: #0f172a;
}

:deep(.n-data-table .n-data-table-th) {
  background-color: #1e293b;
}

:deep(.n-code) {
  background: transparent !important;
}
</style>
