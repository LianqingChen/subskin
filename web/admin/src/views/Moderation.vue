<template>
  <div class="moderation-page">
    <n-page-header title="风控审核" />
    <p class="page-desc">管理内容风控审核队列与复核历史</p>

    <!-- 统计卡片 -->
    <n-grid :cols="isMobile ? 1 : 3" :x-gap="16" :y-gap="16" style="margin-top: 24px" responsive="screen">
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="待审核数量" :value="stats.pending">
            <template #prefix>
              <i class="ri-file-warning-line stat-icon" style="color: #f59e0b;" />
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="今日已处理" :value="stats.today_reviewed">
            <template #prefix>
              <i class="ri-check-double-line stat-icon" style="color: #10b981;" />
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="高风险数量" :value="stats.high_risk">
            <template #prefix>
              <i class="ri-error-warning-line stat-icon" style="color: #ef4444;" />
            </template>
          </n-statistic>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- 标签页 -->
    <n-card style="margin-top: 24px" :bordered="false" class="tab-card">
      <n-tabs :type="isMobile ? 'segment' : 'line'" v-model:value="activeTab" @update:value="onTabChange">
        <n-tab-pane name="pending" tab="待审核队列">
          <n-data-table
            :columns="pendingColumns"
            :data="pendingList"
            :bordered="false"
            :single-line="false"
            size="small"
            :loading="pendingLoading"
            :row-key="(row: ModerationItem) => row.id"
            max-height="520px"
            scroll-x="800"
          />
          <n-empty v-if="!pendingLoading && pendingList.length === 0" description="暂无待审核内容" size="small" style="margin-top: 24px;" />
          <n-space justify="end" style="margin-top: 16px">
            <n-pagination
              v-model:page="pendingPagination.page"
              v-model:page-size="pendingPagination.pageSize"
              :item-count="pendingPagination.itemCount"
              :page-sizes="[10, 20, 50]"
              show-size-picker
              show-quick-jumper
              @update:page="fetchPending"
              @update:page-size="handlePendingPageSizeChange"
            />
          </n-space>
        </n-tab-pane>

        <n-tab-pane name="history" tab="复核历史">
          <n-data-table
            :columns="historyColumns"
            :data="historyList"
            :bordered="false"
            :single-line="false"
            size="small"
            :loading="historyLoading"
            :row-key="(row: ModerationItem) => row.id"
            max-height="520px"
            scroll-x="800"
          />
          <n-empty v-if="!historyLoading && historyList.length === 0" description="暂无审核历史" size="small" style="margin-top: 24px;" />
          <n-space justify="end" style="margin-top: 16px">
            <n-pagination
              v-model:page="historyPagination.page"
              v-model:page-size="historyPagination.pageSize"
              :item-count="historyPagination.itemCount"
              :page-sizes="[10, 20, 50]"
              show-size-picker
              show-quick-jumper
              @update:page="fetchHistory"
              @update:page-size="handleHistoryPageSizeChange"
            />
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <!-- 复核弹窗 -->
    <n-modal
      v-model:show="reviewModal.visible"
      preset="card"
      title="内容复核"
      style="width: 720px; max-width: 90vw;"
      :bordered="false"
      class="review-modal"
    >
      <n-spin :show="reviewModal.loading">
        <n-space vertical :size="16">
          <!-- 内容快照 -->
          <n-card size="small" title="内容快照" class="inner-card">
            <n-descriptions :column="1" size="small" :bordered="false">
              <n-descriptions-item label="帖子标题">
                {{ reviewModal.item?.post_title || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="作者">
                {{ reviewModal.item?.author_username || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="内容类型">
                {{ reviewModal.item?.content_type || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="内容">
                <div class="content-snapshot">{{ reviewModal.item?.content_snapshot || '-' }}</div>
              </n-descriptions-item>
            </n-descriptions>
          </n-card>

          <!-- AI 分析结果 -->
          <n-card size="small" title="AI 分析结果" class="inner-card">
            <n-descriptions :column="2" size="small" :bordered="false">
              <n-descriptions-item label="风险等级">
                <n-tag v-if="reviewModal.item" :type="getRiskType(reviewModal.item.risk_level)" size="small">
                  {{ getRiskLabel(reviewModal.item.risk_level) }}
                </n-tag>
              </n-descriptions-item>
              <n-descriptions-item label="AI 置信度">
                <n-tag v-if="reviewModal.item" type="info" size="small">
                  {{ formatConfidence(reviewModal.item.ai_confidence) }}
                </n-tag>
              </n-descriptions-item>
              <n-descriptions-item label="风险分类" :span="2">
                <n-space v-if="reviewModal.item?.risk_categories?.length" :size="6">
                  <n-tag v-for="cat in reviewModal.item.risk_categories" :key="cat" type="warning" size="small">
                    {{ cat }}
                  </n-tag>
                </n-space>
                <span v-else>-</span>
              </n-descriptions-item>
              <n-descriptions-item label="自动建议" :span="2">
                {{ reviewModal.item?.auto_action || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="AI 理由" :span="2">
                <div class="ai-reason">{{ reviewModal.item?.ai_reason || '-' }}</div>
              </n-descriptions-item>
            </n-descriptions>
          </n-card>

          <!-- 复核操作 -->
          <n-card v-if="reviewModal.item?.status === 'pending'" size="small" title="复核操作" class="inner-card">
            <n-form label-placement="top" :model="reviewForm">
              <n-form-item label="复核结论">
                <n-radio-group v-model:value="reviewForm.action">
                  <n-space>
                    <n-radio value="approve">通过</n-radio>
                    <n-radio value="reject">拒绝</n-radio>
                    <n-radio value="penalize">处罚</n-radio>
                  </n-space>
                </n-radio-group>
              </n-form-item>
              <n-form-item label="复核备注">
                <n-input
                  v-model:value="reviewForm.note"
                  type="textarea"
                  placeholder="请输入复核备注（可选）"
                  :rows="3"
                />
              </n-form-item>
            </n-form>
          </n-card>

          <!-- 已复核信息 -->
          <n-card v-if="reviewModal.item && reviewModal.item.status !== 'pending'" size="small" title="复核记录" class="inner-card">
            <n-descriptions :column="2" size="small" :bordered="false">
              <n-descriptions-item label="复核人">
                {{ reviewModal.item.reviewed_by || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="复核时间">
                {{ formatDate(reviewModal.item.reviewed_at) }}
              </n-descriptions-item>
              <n-descriptions-item label="复核结果">
                <n-tag :type="getStatusType(reviewModal.item.status)" size="small">
                  {{ getStatusLabel(reviewModal.item.status) }}
                </n-tag>
              </n-descriptions-item>
              <n-descriptions-item v-if="reviewModal.item.review_note" label="复核备注" :span="2">
                {{ reviewModal.item.review_note }}
              </n-descriptions-item>
            </n-descriptions>
          </n-card>
        </n-space>
      </n-spin>

      <template #footer>
        <n-space justify="end">
          <n-button @click="reviewModal.visible = false">关闭</n-button>
          <template v-if="reviewModal.item?.status === 'pending'">
            <n-button type="success" :loading="reviewModal.submitting" @click="submitReview('approve')">
              通过
            </n-button>
            <n-button type="error" :loading="reviewModal.submitting" @click="submitReview('reject')">
              拒绝
            </n-button>
            <n-button type="warning" :loading="reviewModal.submitting" @click="submitReview('penalize')">
              处罚
            </n-button>
          </template>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import {
  NPageHeader,
  NGrid,
  NGi,
  NCard,
  NStatistic,
  NTabs,
  NTabPane,
  NDataTable,
  NTag,
  NButton,
  NModal,
  NSpace,
  NForm,
  NFormItem,
  NRadioGroup,
  NRadio,
  NInput,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NSpin,
  NPagination,
  useMessage,
} from 'naive-ui'
import request from '@/api/request'

const message = useMessage()

const isMobile = ref(false)
function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

// ── Types ──
interface ModerationItem {
  id: number
  post_id: number
  user_id: number
  content_type: string
  content_snapshot: string
  risk_level: string
  risk_categories: string[]
  auto_action: string
  ai_reason: string
  ai_confidence: number
  status: string
  reviewed_by?: string
  reviewed_at?: string
  review_note?: string
  created_at: string
  author_username?: string
  post_title?: string
}

interface StatsData {
  pending: number
  today_reviewed: number
  high_risk: number
}

// ── State ──
const activeTab = ref('pending')
const stats = ref<StatsData>({ pending: 0, today_reviewed: 0, high_risk: 0 })

const pendingList = ref<ModerationItem[]>([])
const pendingLoading = ref(false)
const pendingPagination = ref({ page: 1, pageSize: 10, itemCount: 0 })

const historyList = ref<ModerationItem[]>([])
const historyLoading = ref(false)
const historyPagination = ref({ page: 1, pageSize: 10, itemCount: 0 })

const reviewModal = ref({
  visible: false,
  item: null as ModerationItem | null,
  loading: false,
  submitting: false,
})

const reviewForm = ref({
  action: 'approve' as 'approve' | 'reject' | 'penalize',
  note: '',
})

// ── Helpers ──
function getRiskType(level: string) {
  switch (level) {
    case 'high': return 'error'
    case 'medium': return 'warning'
    case 'low': return 'success'
    default: return 'default'
  }
}

function getRiskLabel(level: string) {
  switch (level) {
    case 'high': return '高风险'
    case 'medium': return '中风险'
    case 'low': return '低风险'
    default: return level || '未知'
  }
}

function getStatusType(status: string) {
  switch (status) {
    case 'approved': return 'success'
    case 'rejected': return 'error'
    case 'penalized': return 'warning'
    case 'pending': return 'default'
    default: return 'default'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'approved': return '已通过'
    case 'rejected': return '已拒绝'
    case 'penalized': return '已处罚'
    case 'pending': return '待审核'
    default: return status || '未知'
  }
}

function formatConfidence(v?: number) {
  if (v == null) return '-'
  return `${(v * 100).toFixed(1)}%`
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

// ── Columns ──
const pendingColumns = computed<any[]>(() => {
  const cols: any[] = []
  if (!isMobile.value) {
    cols.push({ title: 'ID', key: 'id', width: 70, ellipsis: { tooltip: true } })
  }
  cols.push(
    {
      title: '作者',
      key: 'author_username',
      width: isMobile.value ? 80 : 120,
      ellipsis: { tooltip: true },
      render(row: ModerationItem) {
        return row.author_username || `用户#${row.user_id}`
      },
    },
    {
      title: '内容类型',
      key: 'content_type',
      width: isMobile.value ? 80 : 110,
      ellipsis: { tooltip: true },
    },
    {
      title: '风险等级',
      key: 'risk_level',
      width: 80,
      render(row: ModerationItem) {
        return h(NTag, { type: getRiskType(row.risk_level) as any, size: 'small' }, {
          default: () => getRiskLabel(row.risk_level),
        })
      },
    },
  )
  if (!isMobile.value) {
    cols.push({
      title: 'AI理由',
      key: 'ai_reason',
      ellipsis: { tooltip: true },
      render(row: ModerationItem) {
        return row.ai_reason || '-'
      },
    })
    cols.push({
      title: '创建时间',
      key: 'created_at',
      width: 170,
      render(row: ModerationItem) {
        return formatDate(row.created_at)
      },
    })
  }
  cols.push({
    title: '操作',
    key: 'actions',
    width: isMobile.value ? 160 : 240,
    fixed: 'right' as const,
    render(row: ModerationItem) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', type: 'success', onClick: () => quickReview(row, 'approve') }, { default: () => '通过' }),
          h(NButton, { size: 'small', type: 'error', onClick: () => quickReview(row, 'reject') }, { default: () => '拒绝' }),
          h(NButton, { size: 'small', onClick: () => openReviewModal(row) }, { default: () => '详情' }),
        ],
      })
    },
  })
  return cols
})

const historyColumns = computed<any[]>(() => {
  const cols: any[] = []
  if (!isMobile.value) {
    cols.push({ title: 'ID', key: 'id', width: 70, ellipsis: { tooltip: true } })
  }
  cols.push(
    {
      title: '作者',
      key: 'author_username',
      width: isMobile.value ? 80 : 120,
      ellipsis: { tooltip: true },
      render(row: ModerationItem) {
        return row.author_username || `用户#${row.user_id}`
      },
    },
    {
      title: '风险等级',
      key: 'risk_level',
      width: 80,
      render(row: ModerationItem) {
        return h(NTag, { type: getRiskType(row.risk_level) as any, size: 'small' }, {
          default: () => getRiskLabel(row.risk_level),
        })
      },
    },
    {
      title: '复核结果',
      key: 'status',
      width: 80,
      render(row: ModerationItem) {
        return h(NTag, { type: getStatusType(row.status) as any, size: 'small' }, {
          default: () => getStatusLabel(row.status),
        })
      },
    },
  )
  if (!isMobile.value) {
    cols.push(
      {
        title: '内容类型',
        key: 'content_type',
        width: 110,
        ellipsis: { tooltip: true },
      },
      {
        title: 'AI理由',
        key: 'ai_reason',
        ellipsis: { tooltip: true },
        render(row: ModerationItem) {
          return row.ai_reason || '-'
        },
      },
      {
        title: '复核人',
        key: 'reviewed_by',
        width: 110,
        ellipsis: { tooltip: true },
        render(row: ModerationItem) {
          return row.reviewed_by || '-'
        },
      },
      {
        title: '复核时间',
        key: 'reviewed_at',
        width: 170,
        render(row: ModerationItem) {
          return formatDate(row.reviewed_at)
        },
      },
    )
  }
  cols.push({
    title: '操作',
    key: 'actions',
    width: 80,
    fixed: 'right' as const,
    render(row: ModerationItem) {
      return h(NButton, { size: 'small', onClick: () => openReviewModal(row) }, { default: () => '详情' })
    },
  })
  return cols
})

// ── API ──
async function fetchStats() {
  try {
    const { data } = await request.get<StatsData>('/moderation/stats')
    stats.value = data
  } catch (err: any) {
    // 静默失败，使用本地计算兜底
    stats.value.pending = pendingPagination.value.itemCount || pendingList.value.length || 0
    stats.value.high_risk = pendingList.value.filter(i => i.risk_level === 'high').length
  }
}

async function fetchPending() {
  pendingLoading.value = true
  try {
    const { data } = await request.get<{ items: ModerationItem[]; total: number }>('/moderation/pending', {
      params: { page: pendingPagination.value.page, page_size: pendingPagination.value.pageSize },
    })
    pendingList.value = data.items || []
    pendingPagination.value.itemCount = data.total || 0
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取待审核列表失败')
    pendingList.value = []
    pendingPagination.value.itemCount = 0
  } finally {
    pendingLoading.value = false
  }
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    const { data } = await request.get<{ items: ModerationItem[]; total: number }>('/moderation/history', {
      params: { page: historyPagination.value.page, page_size: historyPagination.value.pageSize },
    })
    historyList.value = data.items || []
    historyPagination.value.itemCount = data.total || 0
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取审核历史失败')
    historyList.value = []
    historyPagination.value.itemCount = 0
  } finally {
    historyLoading.value = false
  }
}

function onTabChange(tab: string) {
  if (tab === 'pending') {
    fetchPending()
  } else if (tab === 'history') {
    fetchHistory()
  }
}

function handlePendingPageSizeChange(size: number) {
  pendingPagination.value.pageSize = size
  pendingPagination.value.page = 1
  fetchPending()
}

function handleHistoryPageSizeChange(size: number) {
  historyPagination.value.pageSize = size
  historyPagination.value.page = 1
  fetchHistory()
}

function openReviewModal(item: ModerationItem) {
  reviewModal.value.item = item
  reviewForm.value.action = 'approve'
  reviewForm.value.note = ''
  reviewModal.value.visible = true
}

async function quickReview(item: ModerationItem, action: 'approve' | 'reject' | 'penalize') {
  try {
    await request.post(`/moderation/${item.id}/review`, { action, note: '' })
    message.success(action === 'approve' ? '已通过' : action === 'reject' ? '已拒绝' : '已处罚')
    fetchPending()
    fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '操作失败')
  }
}

async function submitReview(action: 'approve' | 'reject' | 'penalize') {
  if (!reviewModal.value.item) return
  reviewForm.value.action = action
  reviewModal.value.submitting = true
  try {
    await request.post(`/moderation/${reviewModal.value.item.id}/review`, {
      action: reviewForm.value.action,
      note: reviewForm.value.note,
    })
    message.success(action === 'approve' ? '已通过' : action === 'reject' ? '已拒绝' : '已处罚')
    reviewModal.value.visible = false
    fetchPending()
    fetchHistory()
    fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '复核提交失败')
  } finally {
    reviewModal.value.submitting = false
  }
}

// ── Lifecycle ──
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchPending()
  fetchHistory()
  fetchStats()
})
</script>

<style scoped>
.moderation-page {
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

.tab-card {
  background-color: #1e293b;
}

.inner-card {
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.content-snapshot {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}

.ai-reason {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: #cbd5e1;
}

:deep(.n-data-table .n-data-table-td) {
  background-color: #0f172a;
}

:deep(.n-data-table .n-data-table-th) {
  background-color: #1e293b;
}

:deep(.n-descriptions .n-descriptions-table-content) {
  background-color: transparent;
}

:deep(.n-descriptions .n-descriptions-table-header) {
  background-color: transparent;
}
</style>
