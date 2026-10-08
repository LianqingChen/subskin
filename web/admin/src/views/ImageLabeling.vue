<template>
  <div class="image-label-page">
    <n-page-header title="图片打标管理" />
    <p class="page-desc">管理用户上传照片的 AI 标注与人工标注复核 — 打标数据沉淀为训练样本，持续优化白斑识别模型。为保护用户隐私，列表仅显示匿名编号，病情照片与用户身份不做关联展示</p>

    <n-grid :cols="isMobile ? 2 : 4" :x-gap="12" :y-gap="12" style="margin-top: 20px" responsive="screen">
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="总数" :value="stats.total" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="待标注" :value="stats.pending" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="已标注" :value="stats.labeled" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" class="stat-card">
          <n-statistic label="训练集就绪" :value="stats.training_ready" />
        </n-card>
      </n-gi>
    </n-grid>

    <n-card style="margin-top: 20px" :bordered="false" class="list-card">
      <template #header>
        <n-space align="center" justify="space-between" style="width: 100%" :wrap="false">
          <n-tabs v-model:value="activeTab" type="segment" size="small" @update:value="handleTabChange">
            <n-tab name="pending">待标注 ({{ stats.pending }})</n-tab>
            <n-tab name="labeled">已标注 ({{ stats.labeled }})</n-tab>
            <n-tab name="all">全部</n-tab>
          </n-tabs>
          <n-space :size="8" :wrap="false">
            <n-button size="small" @click="showUploadModal = true">
              <template #icon><i class="ri-upload-cloud-2-line" /></template>
              上传图片
            </n-button>
            <n-dropdown :options="exportOptions" @select="handleExport">
              <n-button size="small">
                <template #icon><i class="ri-download-2-line" /></template>
                导出
              </n-button>
            </n-dropdown>
            <n-button size="small" :loading="syncing" @click="handleSync">
              <template #icon><i class="ri-refresh-line" /></template>
              同步
            </n-button>
          </n-space>
        </n-space>
      </template>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <n-select
          v-model:value="filters.source"
          :options="sourceOptions"
          size="small"
          clearable
          placeholder="图片来源"
          style="width: 130px"
        />
        <n-select
          v-model:value="filters.body_site"
          :options="bodySiteOptions"
          size="small"
          clearable
          filterable
          placeholder="身体部位"
          style="width: 130px"
        />
        <n-date-picker
          v-model:value="filters.dateRange"
          type="daterange"
          size="small"
          clearable
          style="width: 260px"
        />
        <n-input-number
          v-model:value="filters.user_id"
          size="small"
          clearable
          :show-button="false"
          placeholder="用户 ID"
          style="width: 110px"
        />
        <n-input
          v-model:value="filters.username"
          size="small"
          clearable
          placeholder="用户昵称（返回匿名编号，仍可用于精确过滤）"
          style="width: 130px"
          @keyup.enter="applyFilters"
        />
        <n-button size="small" type="primary" @click="applyFilters">
          <template #icon><i class="ri-search-line" /></template>
          查询
        </n-button>
        <n-button size="small" quaternary @click="resetFilters">重置</n-button>
      </div>

      <!-- 批量选择栏 -->
      <div v-if="selectableItems.length > 0" class="bulk-bar">
        <n-checkbox
          :checked="allSelected"
          :indeterminate="someSelected"
          @update:checked="toggleSelectAll"
        >
          全选可选 ({{ selectableItems.length }})
        </n-checkbox>
        <template v-if="selectedIds.length > 0">
          <span class="bulk-count">已选 {{ selectedIds.length }} 张</span>
          <n-button size="small" type="primary" ghost :loading="bulkAdding" @click="bulkAddToTraining">
            <template #icon><i class="ri-database-2-line" /></template>
            批量添加至训练样本
          </n-button>
          <n-button size="small" quaternary @click="selectedIds = []">清空选择</n-button>
        </template>
      </div>

      <n-spin :show="loading">
        <div v-if="list.length === 0 && !loading" style="padding: 40px 0">
          <n-empty :description="activeTab === 'pending' ? '没有待标注的图片' : activeTab === 'labeled' ? '没有已标注的图片' : '暂无数据'" size="small" />
        </div>
        <div v-else class="label-rows">
          <div v-for="item in list" :key="item.id" class="label-row">
            <!-- 三图缩略区：原图 / 用户标注 / 管理员标注 -->
            <div class="label-row-thumbs" @click="openCompare(item)">
              <div class="thumb-cell">
                <img v-if="item.id" :src="proxyImageUrl(item.id)" loading="lazy" alt="原图" @error="onThumbError" />
                <div v-else class="thumb-placeholder"><i class="ri-image-line" /></div>
                <span class="thumb-label">原图</span>
                <div v-if="item.label_status === 'labeled'" class="thumb-badge">
                  <i class="ri-check-line"></i>
                </div>
              </div>
              <div class="thumb-cell">
                <img
                  v-if="item.has_user_annotation"
                  :src="userAnnotatedUrl(item.id)"
                  loading="lazy"
                  alt="用户标注"
                  @error="onThumbError"
                />
                <div v-else class="thumb-placeholder"><i class="ri-user-line" /></div>
                <span class="thumb-label">用户标注</span>
              </div>
              <div class="thumb-cell">
                <img
                  v-if="item.label_status === 'labeled'"
                  :src="adminAnnotatedUrl(item.id)"
                  loading="lazy"
                  alt="管理员标注"
                  @error="onThumbError"
                />
                <div v-else class="thumb-placeholder"><i class="ri-edit-2-line" /></div>
                <span class="thumb-label">管理员标注</span>
              </div>
            </div>

            <div class="label-row-body">
              <div class="label-row-header">
                <n-checkbox
                  v-if="item.label_status === 'labeled' && !item.in_training_set"
                  :checked="selectedIds.includes(item.id)"
                  @update:checked="(v: boolean) => toggleSelect(item.id, v)"
                />
                <span class="label-row-id">#{{ item.id }}</span>
                <n-tag :type="getStatusType(item.label_status)" size="tiny" :bordered="false">
                  {{ getStatusLabel(item.label_status) }}
                </n-tag>
                <span v-if="item.username" class="label-row-user">
                  <i class="ri-user-line"></i> {{ item.username }}
                </span>
                <span v-else-if="item.source === 'admin'" class="label-row-user muted">管理员上传</span>
                <span class="label-row-date">{{ formatShortDate(item.photo_date || item.created_at) }}</span>
              </div>

              <div class="label-row-sections">
                <div class="label-section ai-section">
                  <div class="section-title"><i class="ri-robot-2-line" /> AI 标注</div>
                  <div class="section-tags">
                    <n-tag size="tiny" :bordered="false">{{ item.body_site || '部位未知' }}</n-tag>
                    <n-tag v-if="item.ai_is_vitiligo != null" size="tiny" :bordered="false" :type="item.ai_is_vitiligo ? 'warning' : 'success'">
                      {{ item.ai_is_vitiligo ? '白癜风' : '正常' }}
                    </n-tag>
                    <n-tag v-if="item.ai_vitiligo_type" size="tiny" :bordered="false" type="info">{{ item.ai_vitiligo_type }}</n-tag>
                    <n-tag v-if="item.ai_area_percentage != null" size="tiny" :bordered="false">{{ item.ai_area_percentage }}%</n-tag>
                    <span v-if="item.ai_is_vitiligo == null" class="no-ai-tag">AI 未判断</span>
                  </div>
                </div>

                <div v-if="item.label_status === 'pending'" class="label-section human-section">
                  <div class="section-title"><i class="ri-edit-line" /> 人工标注</div>
                  <div class="section-form">
                    <n-button
                      type="primary"
                      size="tiny"
                      @click="openWorkspace(item)"
                    >
                      <template #icon><i class="ri-brush-line" /></template>
                      开始标注
                    </n-button>
                    <n-button size="tiny" @click="skipItem(item.id)">跳过</n-button>
                  </div>
                </div>

                <div v-else class="label-section human-section done">
                  <div class="section-title">
                    <i class="ri-check-line" /> 人工标注
                    <span v-if="item.labeled_at" class="section-time">{{ formatShortDate(item.labeled_at) }}</span>
                  </div>
                  <div class="section-tags">
                    <n-tag v-if="item.admin_is_vitiligo != null" size="tiny" :bordered="false" :type="item.admin_is_vitiligo ? 'warning' : 'success'">
                      {{ item.admin_is_vitiligo ? '白癜风' : '正常' }}
                    </n-tag>
                    <n-tag v-if="item.admin_vitiligo_type" size="tiny" :bordered="false" type="info">{{ item.admin_vitiligo_type }}</n-tag>
                    <n-tag v-if="item.admin_area_percentage != null" size="tiny" :bordered="false">{{ item.admin_area_percentage }}%</n-tag>
                    <span v-if="item.admin_is_vitiligo == null" class="no-ai-tag">未标注</span>
                    <n-tag v-if="item.in_training_set" size="tiny" :bordered="false" type="success" style="margin-left: auto;">
                      <i class="ri-database-2-line"></i> 已入训练集
                    </n-tag>
                  </div>
                  <div class="section-actions">
                    <n-button size="tiny" @click="openWorkspace(item)">
                      <template #icon><i class="ri-edit-2-line" /></template>
                      重新编辑
                    </n-button>
                    <n-button
                      v-if="!item.in_training_set"
                      size="tiny"
                      type="primary"
                      ghost
                      :loading="addingTrainingId === item.id"
                      @click="addToTraining(item)"
                    >
                      <template #icon><i class="ri-database-2-line" /></template>
                      添加至训练样本
                    </n-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </n-spin>

      <n-space justify="end" style="margin-top: 16px">
        <n-pagination
          v-model:page="currentPage"
          :page-size="pageSize"
          :item-count="total"
          @update:page="fetchList"
        />
      </n-space>
    </n-card>

    <!-- 三图对比 Modal -->
    <n-modal
      v-model:show="compareVisible"
      preset="card"
      :bordered="false"
      style="width: 94vw; max-width: 1200px;"
      :title="compareItem ? `三图对比 #${compareItem.id}${compareItem.username ? ' · ' + compareItem.username : ''}` : '三图对比'"
    >
      <div v-if="compareItem" class="compare-body">
        <div class="compare-grid">
          <div class="compare-cell">
            <img :src="proxyImageUrl(compareItem.id)" alt="原图" @error="onThumbError" />
            <div class="compare-caption">原图</div>
          </div>
          <div class="compare-cell">
            <img v-if="compareItem.has_user_annotation" :src="userAnnotatedUrl(compareItem.id)" alt="用户标注" @error="onThumbError" />
            <div v-else class="compare-empty"><i class="ri-user-line" /><span>无用户标注</span></div>
            <div class="compare-caption">用户标注（SubSkin 填涂）</div>
          </div>
          <div class="compare-cell">
            <img v-if="compareItem.label_status === 'labeled'" :src="adminAnnotatedUrl(compareItem.id)" alt="管理员标注" @error="onThumbError" />
            <div v-else class="compare-empty"><i class="ri-edit-2-line" /><span>未标注</span></div>
            <div class="compare-caption">管理员标注</div>
          </div>
        </div>
        <div class="compare-summary">
          <n-tag size="small" :bordered="false" :type="getStatusType(compareItem.label_status)">
            {{ getStatusLabel(compareItem.label_status) }}
          </n-tag>
          <n-tag size="small" :bordered="false">{{ compareItem.body_site || '部位未知' }}</n-tag>
          <span v-if="compareItem.ai_area_percentage != null" class="summary-item">AI 面积: {{ compareItem.ai_area_percentage }}%</span>
          <span v-if="compareItem.admin_area_percentage != null" class="summary-item">管理员面积: {{ compareItem.admin_area_percentage }}%</span>
          <span class="summary-item muted">{{ formatShortDate(compareItem.photo_date || compareItem.created_at) }}</span>
        </div>
      </div>
    </n-modal>

    <!-- 批量上传 Modal -->
    <n-modal
      v-model:show="showUploadModal"
      preset="card"
      title="批量上传图片"
      :bordered="false"
      :mask-closable="!uploading"
      style="width: 680px; max-width: 94vw;"
    >
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <p style="font-size: 13px; color: #94a3b8; margin: 0;">
          从本地上传白癜风患处照片，图片将加入待标注列表，可直接进行人工标注并作为 VASI 模型训练素材。
          支持 JPG / PNG / WebP 格式，单张最大 20MB。
        </p>

        <!-- Upload area -->
        <n-upload
          v-model:file-list="fileList"
          :multiple="true"
          :max="50"
          accept="image/jpeg,image/png,image/webp"
          list-type="image-card"
          :default-upload="false"
          :disabled="uploading"
          @change="onFileChange"
        >
          <n-button :disabled="uploading">
            <i class="ri-add-line" style="margin-right: 4px;"></i>选择图片
          </n-button>
        </n-upload>

        <!-- Progress -->
        <div v-if="uploading" style="display: flex; align-items: center; gap: 12px; padding: 12px; background: rgba(99,102,241,0.1); border-radius: 8px; border: 1px solid rgba(99,102,241,0.2);">
          <n-spin :size="18" />
          <span style="font-size: 13px; color: #a5b4fc;">正在上传 {{ uploadProgress }} / {{ validFiles.length }} 张...</span>
        </div>

        <!-- Result -->
        <div v-if="uploadResult" style="display: flex; flex-direction: column; gap: 8px; padding: 12px; border-radius: 8px;"
          :style="uploadResult.errors.length > 0
            ? { background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.3)' }
            : { background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)' }">
          <div style="display: flex; align-items: center; gap: 12px; font-size: 13px; color: #e2e8f0;">
            <span style="color: #10b981;">✅ 新建 {{ uploadResult.created }} 张</span>
            <span v-if="uploadResult.skipped > 0" style="color: #fbbf24;">⏭ 跳过 {{ uploadResult.skipped }} 张</span>
            <span v-if="uploadResult.errors.length > 0" style="color: #f87171;">❌ {{ uploadResult.errors.length }} 个错误</span>
          </div>
          <div v-if="uploadResult.errors.length > 0" style="max-height: 120px; overflow-y: auto;">
            <div v-for="(e, i) in uploadResult.errors" :key="i" style="font-size: 11px; color: #fbbf24; line-height: 1.6;">{{ e }}</div>
          </div>
        </div>
      </div>

      <template #footer>
        <n-space justify="end">
          <n-button @click="closeUploadModal" :disabled="uploading">关闭</n-button>
          <n-button
            type="primary"
            :loading="uploading"
            :disabled="validFiles.length === 0"
            @click="handleUpload"
          >
            <template #icon><i class="ri-upload-cloud-2-line" /></template>
            上传 ({{ validFiles.length }})
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import {
  NPageHeader, NGrid, NGi, NCard, NStatistic, NTag, NButton,
  NModal, NSpace, NTabs, NTab, NEmpty, NSpin, NUpload,
  NPagination, NDropdown, NSelect, NDatePicker, NInput, NInputNumber, NCheckbox,
  useMessage,
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import { useRouter } from 'vue-router'
import request from '@/api/request'

const router = useRouter()

const message = useMessage()

const isMobile = ref(false)
function checkMobile() { isMobile.value = window.innerWidth <= 768 }

interface LabelItem {
  id: number
  assessment_id?: number
  image_url: string
  image_hash?: string
  body_site?: string
  ai_body_site?: string
  ai_is_vitiligo?: boolean
  ai_vitiligo_type?: string
  ai_vitiligo_stage?: string
  ai_area_percentage?: number
  admin_body_site?: string
  admin_is_vitiligo?: boolean
  admin_vitiligo_type?: string
  admin_vitiligo_stage?: string
  admin_area_percentage?: number
  label_status: string
  is_user_deleted: boolean
  training_eligible: boolean
  created_at?: string
  labeled_at?: string
  // 列表新增字段（后端 list_image_labels）
  original_user_id?: number | null
  username?: string | null
  source?: 'user' | 'admin'
  photo_date?: string | null
  has_user_annotation?: boolean
  has_admin_annotation?: boolean
  has_admin_composite?: boolean
  in_training_set?: boolean
}

interface StatsData {
  total: number
  pending: number
  labeled: number
  skipped: number
  rejected: number
  training_ready: number
  user_deleted: number
}

const stats = ref<StatsData>({ total: 0, pending: 0, labeled: 0, skipped: 0, rejected: 0, training_ready: 0, user_deleted: 0 })
const list = ref<LabelItem[]>([])
const loading = ref(false)
const syncing = ref(false)
const activeTab = ref('pending')
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

// ── 筛选 ──
const filters = reactive({
  source: null as string | null,
  body_site: null as string | null,
  dateRange: null as [number, number] | null,
  user_id: null as number | null,
  username: '',
})

const sourceOptions = [
  { label: '用户上传', value: 'user' },
  { label: '管理员上传', value: 'admin' },
]

const bodySiteOptions = [
  '面部', '颈部', '头皮', '躯干前面', '躯干后面', '上肢近端', '上肢远端',
  '手部', '下肢近端', '下肢远端', '足部', '生殖器', '其他',
].map(s => ({ label: s, value: s }))

function applyFilters() {
  currentPage.value = 1
  fetchList()
}

function resetFilters() {
  filters.source = null
  filters.body_site = null
  filters.dateRange = null
  filters.user_id = null
  filters.username = ''
  applyFilters()
}

// ── 三图对比 ──
const compareVisible = ref(false)
const compareItem = ref<LabelItem | null>(null)

function openCompare(item: LabelItem) {
  compareItem.value = item
  compareVisible.value = true
}

// ── 添加至训练样本 ──
const addingTrainingId = ref<number | null>(null)

async function addToTraining(item: LabelItem) {
  addingTrainingId.value = item.id
  try {
    const { data } = await request.post<{ status: string; sample_id: number }>(
      `/vasi/admin/image-labels/${item.id}/training-sample`,
    )
    if (data.status === 'ok') {
      message.success('已添加至训练样本，可在训练数据页查看')
      item.in_training_set = true
      fetchStats()
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '添加失败')
  } finally {
    addingTrainingId.value = null
  }
}

// ── 批量选择与批量添加至训练样本 ──
const selectedIds = ref<number[]>([])
const bulkAdding = ref(false)

const selectableItems = computed(() =>
  list.value.filter(i => i.label_status === 'labeled' && !i.in_training_set),
)
const allSelected = computed(() =>
  selectableItems.value.length > 0
  && selectableItems.value.every(i => selectedIds.value.includes(i.id)),
)
const someSelected = computed(() =>
  selectedIds.value.length > 0 && !allSelected.value,
)

function toggleSelect(id: number, checked: boolean) {
  if (checked) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter(v => v !== id)
  }
}

function toggleSelectAll(checked: boolean) {
  selectedIds.value = checked ? selectableItems.value.map(i => i.id) : []
}

async function bulkAddToTraining() {
  if (selectedIds.value.length === 0) return
  bulkAdding.value = true
  try {
    const { data } = await request.post<{
      added: number
      added_ids: number[]
      skipped: { label_id: number; reason: string }[]
    }>('/vasi/admin/image-labels/training-sample/batch', { label_ids: selectedIds.value })
    if (data.skipped.length === 0) {
      message.success(`已将 ${data.added} 条标注添加至训练样本`)
    } else {
      message.warning(`已添加 ${data.added} 条，跳过 ${data.skipped.length} 条（${data.skipped[0].reason}）`)
    }
    const addedSet = new Set(data.added_ids)
    list.value.forEach(i => { if (addedSet.has(i.id)) i.in_training_set = true })
    selectedIds.value = []
    fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '批量添加失败')
  } finally {
    bulkAdding.value = false
  }
}

// ── 批量上传状态 ──
const showUploadModal = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadResult = ref<{ created: number; skipped: number; errors: string[] } | null>(null)
const fileList = ref<UploadFileInfo[]>([])

const validFiles = computed(() =>
  fileList.value.filter(f => f.file && f.status !== 'removed')
)

function onFileChange(_: { file: UploadFileInfo; fileList: UploadFileInfo[] }) {
  uploadResult.value = null  // clear previous result on change
}

async function handleUpload() {
  if (validFiles.value.length === 0) return
  uploading.value = true
  uploadProgress.value = 0
  uploadResult.value = null

  try {
    const formData = new FormData()
    for (const f of validFiles.value) {
      if (f.file) formData.append('files', f.file)
    }

    const { data } = await request.post<{ created: number; skipped: number; errors: string[]; items: any[] }>(
      '/vasi/admin/image-labels/upload',
      formData,
      {
        onUploadProgress: (e) => {
          if (e.total) {
            uploadProgress.value = Math.min(validFiles.value.length, Math.ceil((e.loaded / e.total) * validFiles.value.length))
          }
        },
      },
    )

    uploadResult.value = data
    if (data.created > 0) {
      message.success(`成功上传 ${data.created} 张图片`)
      currentPage.value = 1
      await fetchStats()
      await fetchList()
    } else if (data.errors.length > 0) {
      message.warning(`上传完成: 新建 ${data.created}，跳过 ${data.skipped}，错误 ${data.errors.length}`)
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '上传失败，请重试')
  } finally {
    uploading.value = false
    fileList.value = []  // clear file list after upload (success or fail)
  }
}

function closeUploadModal() {
  if (uploading.value) return
  showUploadModal.value = false
  uploadResult.value = null
  fileList.value = []
}

const exportOptions = [
  { key: 'json', label: '导出 JSON' },
  { key: 'csv', label: '导出 CSV' },
  { key: 'images', label: '下载图片URL列表' },
]

function adminToken(): string {
  return localStorage.getItem('admin_token') || ''
}

function proxyImageUrl(id: number): string {
  // 后端图片代理端点 — admin 鉴权后流式返回原图
  // 解决: <img> 标签无法设 Authorization header, 改用 query string 传 token
  return `/api/vasi/admin/image-labels/${id}/image?access_token=${encodeURIComponent(adminToken())}`
}

function userAnnotatedUrl(id: number): string {
  // 用户在 SubSkin 填涂的合成图（原图 + 用户蒙层）；无用户标注时 404 → 占位
  return `/api/vasi/admin/image-labels/${id}/user-annotated-image?access_token=${encodeURIComponent(adminToken())}`
}

function adminAnnotatedUrl(id: number): string {
  // 管理员标注合成图（原图 + 管理员蒙层）；未标注时 404 → 占位
  return `/api/vasi/admin/image-labels/${id}/annotated-image?access_token=${encodeURIComponent(adminToken())}`
}

function onThumbError(event: Event) {
  // 兜底: 后端代理失败时 (极端情况) 用 data URI 占位符
  const img = event.target as HTMLImageElement
  if (img.dataset.fallback === '1') return // 已 fallback 一次, 不再循环
  img.dataset.fallback = '1'
  img.src =
    'data:image/svg+xml;utf8,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120" viewBox="0 0 160 120">' +
        '<rect width="160" height="120" fill="#fafafa"/>' +
        '<text x="80" y="65" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#bbb">图加载失败</text>' +
        '</svg>',
    )
}

function getStatusType(status: string) {
  switch (status) {
    case 'labeled': return 'success'
    case 'pending': return 'warning'
    case 'skipped': return 'default'
    case 'rejected': return 'error'
    default: return 'default'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'pending': return '待标注'
    case 'labeled': return '已标注'
    case 'skipped': return '已跳过'
    case 'rejected': return '已拒绝'
    default: return status || '未知'
  }
}

function formatShortDate(dateStr?: string) {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return dateStr }
}

function formatDateParam(ts: number): string {
  const d = new Date(ts)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function openWorkspace(item: LabelItem) {
  // 统一入口：全屏工作区。在用户手势内先请求全屏（保留激活状态），再路由跳转
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
    }
  } catch {
    // 全屏被浏览器拒绝 — 工作区内有手动全屏按钮兜底
  }
  router.push({ name: 'LabelingWorkspace', params: { id: item.id } })
}

function handleTabChange() {
  currentPage.value = 1
  fetchList()
}

async function fetchStats() {
  try {
    const { data } = await request.get<StatsData>('/vasi/admin/image-labels/stats')
    stats.value = data
  } catch { /* silent */ }
}

async function fetchList() {
  loading.value = true
  selectedIds.value = []
  try {
    const params: any = { limit: pageSize, offset: (currentPage.value - 1) * pageSize }
    if (activeTab.value === 'pending') params.label_status = 'pending'
    else if (activeTab.value === 'labeled') params.label_status = 'labeled'
    if (filters.source) params.source = filters.source
    if (filters.body_site) params.body_site = filters.body_site
    if (filters.dateRange) {
      params.date_from = formatDateParam(filters.dateRange[0])
      params.date_to = formatDateParam(filters.dateRange[1])
    }
    if (filters.user_id != null) params.user_id = filters.user_id
    if (filters.username.trim()) params.username = filters.username.trim()
    const { data } = await request.get<{ total: number; items: LabelItem[] }>('/vasi/admin/image-labels', { params })
    list.value = data.items || []
    total.value = data.total || 0
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取列表失败')
    list.value = []
  } finally {
    loading.value = false
  }
}

async function skipItem(id: number) {
  try {
    await request.post('/vasi/admin/image-labels/batch-status', { ids: [id], label_status: 'skipped' })
    message.success('已跳过')
    fetchList()
    fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '操作失败')
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const { data } = await request.post('/vasi/admin/image-labels/sync-assessments')
    message.success(`同步完成: 新增 ${data.created}，跳过 ${data.skipped}`)
    fetchList()
    fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '同步失败')
  } finally {
    syncing.value = false
  }
}

function handleExport(key: string) {
  const params = new URLSearchParams()
  if (activeTab.value === 'pending') params.set('label_status', 'pending')
  else if (activeTab.value === 'labeled') params.set('label_status', 'labeled')

  if (key === 'json' || key === 'csv') {
    params.set('format', key)
    const url = `/api/vasi/admin/image-labels/export?${params.toString()}`
    window.open(url, '_blank')
  } else if (key === 'images') {
    exportImageList()
  }
}

async function exportImageList() {
  try {
    const params: any = { limit: 5000, offset: 0 }
    if (activeTab.value === 'pending') params.label_status = 'pending'
    const { data } = await request.get<{ items: LabelItem[] }>('/vasi/admin/image-labels', { params })
    const urls = (data.items || []).map(i => i.image_url).filter(Boolean)
    const blob = new Blob([urls.join('\n')], { type: 'text/plain' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'image_urls.txt'
    link.click()
    URL.revokeObjectURL(link.href)
    message.success(`已导出 ${urls.length} 个图片链接`)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '导出失败')
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchStats()
  fetchList()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.image-label-page { padding: 0; }
.page-desc { color: #94a3b8; margin-top: 8px; font-size: 14px; }
.stat-card { background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.1); }
.stat-card :deep(.n-card__content) { padding: 16px; }
.list-card { background-color: #1e293b; }

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 0 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  margin-bottom: 14px;
}

.bulk-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 10px;
  margin-bottom: 12px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px dashed rgba(99, 102, 241, 0.25);
}

.bulk-count {
  font-size: 12px;
  color: #a5b4fc;
}

.label-rows { display: flex; flex-direction: column; gap: 10px; }

.label-row {
  display: flex;
  gap: 14px;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.08);
  transition: border-color 0.15s;
}
.label-row:hover { border-color: rgba(99, 102, 241, 0.3); }

/* ── 三图缩略区 ── */
.label-row-thumbs {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  cursor: pointer;
}
.thumb-cell {
  position: relative;
  width: 72px;
  height: 92px;
  border-radius: 6px;
  overflow: hidden;
  background: #1e293b;
  border: 1px solid rgba(148, 163, 184, 0.12);
}
.thumb-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
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
.thumb-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  background: #10b981;
  color: #fff;
  border-radius: 50%;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}

.label-row-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label-row-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.label-row-id {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
}
.label-row-user {
  font-size: 11px;
  color: #a5b4fc;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.label-row-user.muted { color: #64748b; }
.label-row-date {
  font-size: 11px;
  color: #475569;
  margin-left: auto;
}

.label-row-sections {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.section-title {
  font-size: 11px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}
.section-title i { font-size: 12px; }
.section-time {
  margin-left: auto;
  font-size: 10px;
  color: #475569;
}
.section-tags {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.section-actions {
  margin-top: 4px;
  display: flex;
  gap: 4px;
}
.no-ai-tag {
  font-size: 11px;
  color: #475569;
  font-style: italic;
}

.human-section .section-form {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.human-section.done .section-tags {
  padding-left: 0;
}

.ai-section { border-left: 2px solid #6366f1; padding-left: 8px; }
.human-section { border-left: 2px solid #10b981; padding-left: 8px; }
.human-section.done { border-left-color: #475569; }

/* ── 三图对比 Modal ── */
.compare-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.compare-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.compare-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.compare-cell img {
  width: 100%;
  max-height: 52vh;
  object-fit: contain;
  border-radius: 8px;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.12);
}
.compare-empty {
  height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 8px;
  background: #0f172a;
  border: 1px dashed rgba(148, 163, 184, 0.2);
  color: #475569;
  font-size: 26px;
}
.compare-empty span { font-size: 12px; }
.compare-caption {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}
.compare-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #cbd5e1;
}
.summary-item.muted { color: #64748b; }

@media (max-width: 768px) {
  .label-row { flex-direction: column; gap: 8px; padding: 10px; }
  .label-row-thumbs { width: 100%; }
  .thumb-cell { flex: 1; height: 100px; }
  .compare-grid { grid-template-columns: 1fr; }
  .compare-empty { height: 160px; }
  .human-section .section-form { gap: 4px; }
}
</style>
