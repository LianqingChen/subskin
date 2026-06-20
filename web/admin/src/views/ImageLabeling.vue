<template>
  <div class="image-label-page">
    <n-page-header title="图片打标管理" />
    <p class="page-desc">管理用户上传照片的 AI 标注与人工标注复核 — AI 像素填涂预标注 + 人工修订</p>

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

      <n-spin :show="loading">
        <div v-if="list.length === 0 && !loading" style="padding: 40px 0">
          <n-empty :description="activeTab === 'pending' ? '没有待标注的图片' : activeTab === 'labeled' ? '没有已标注的图片' : '暂无数据'" size="small" />
        </div>
        <div v-else class="label-rows">
          <div v-for="item in list" :key="item.id" class="label-row">
            <div class="label-row-thumb" @click="openEditor(item)">
              <img v-if="item.id" :src="proxyImageUrl(item.id)" loading="lazy" alt="" @error="onThumbError($event)" />
              <div v-else class="thumb-placeholder"><i class="ri-image-line" /></div>
              <div v-if="item.label_status === 'labeled'" class="thumb-badge">
                <i class="ri-check-line"></i>
              </div>
            </div>

            <div class="label-row-body">
              <div class="label-row-header">
                <span class="label-row-id">#{{ item.id }}</span>
                <n-tag :type="getStatusType(item.label_status)" size="tiny" :bordered="false">
                  {{ getStatusLabel(item.label_status) }}
                </n-tag>
                <span v-if="item.admin_is_vitiligo != null" class="label-row-conf">
                  <i class="ri-shield-check-line"></i> 已审核
                </span>
                <span class="label-row-date">{{ formatShortDate(item.created_at) }}</span>
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
                      @click="openEditor(item)"
                    >
                      <template #icon><i class="ri-brush-line" /></template>
                      开始标注
                    </n-button>
                    <n-button
                      size="tiny"
                      @click="openWorkspace(item)"
                    >
                      <template #icon><i class="ri-external-link-line" /></template>
                      工作区
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
                    <n-tag v-if="item.training_eligible" size="tiny" :bordered="false" type="success" style="margin-left: auto;">
                      <i class="ri-database-2-line"></i> 训练就绪
                    </n-tag>
                  </div>
                  <div class="section-actions">
                    <n-button size="tiny" @click="openEditor(item)">
                      <template #icon><i class="ri-edit-2-line" /></template>
                      重新编辑
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

    <!-- 全屏标注编辑器 Modal -->
    <n-modal
      v-model:show="editorVisible"
      preset="card"
      :bordered="false"
      :mask-closable="false"
      style="width: 95vw; max-width: 1400px; height: 92vh;"
      :title="`图片打标 #${editingItem?.id ?? ''} — 用户填涂预填充 + 管理员修订`"
    >
      <template #header-extra>
        <n-tag v-if="editingItem" :type="getStatusType(editingItem.label_status)" size="small" :bordered="false">
          {{ getStatusLabel(editingItem.label_status) }}
        </n-tag>
      </template>
      <div v-if="editingItem" style="height: calc(92vh - 120px); overflow: hidden; display: flex; flex-direction: column;">
        <LabelingEditor
          ref="editorRef"
          :image-url="annotatedImageUrl || proxyImageUrl(editingItem.id)"
          :image-hash="editingItem.image_hash"
          :existing-ai-details="editingItem ? {
            body_site: editingItem.ai_body_site,
            is_vitiligo: editingItem.ai_is_vitiligo,
            vitiligo_type: editingItem.ai_vitiligo_type,
            vitiligo_stage: editingItem.ai_vitiligo_stage,
            area_percentage: editingItem.ai_area_percentage,
            vasi_score: (editingItem as any).ai_vasi_score,
            depigmentation_level: (editingItem as any).ai_depigmentation_level,
          } : null"
          :initial-admin-annotations="initialAnnotations"
          :initial-form="initialForm"
          :annotated-image-url="annotatedImageUrl"
          :ai-pretrain-available="true"
          @ai-pretrain="handleAiPretrain"
          @submit="handleEditorSubmit"
          @save-draft="handleSaveDraft"
          @cancel="editorVisible = false"
        />
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
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import {
  NPageHeader, NGrid, NGi, NCard, NStatistic, NTag, NButton,
  NModal, NSpace, NTabs, NTab, NEmpty, NSpin, NUpload,
  NPagination, NDropdown,
  useMessage,
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import LabelingEditor, { type AdminAnnotationItem, type LabelingEditorSubmit } from '@/components/labeling/LabelingEditor.vue'

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
  ai_vasi_score?: number
  ai_depigmentation_level?: number
  admin_body_site?: string
  admin_is_vitiligo?: boolean
  admin_vitiligo_type?: string
  admin_vitiligo_stage?: string
  admin_area_percentage?: number
  admin_vasi_score?: number
  admin_depigmentation_level?: number
  admin_notes?: string
  label_status: string
  is_user_deleted: boolean
  training_eligible: boolean
  created_at?: string
  labeled_at?: string
  ai_details?: string | null
  ai_confidence?: number
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
const submittingId = ref<number | null>(null)
const activeTab = ref('pending')
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

// ── 编辑器状态 ──
const editorVisible = ref(false)
const editorRef = ref<InstanceType<typeof LabelingEditor> | null>(null)
const editingItem = ref<LabelItem | null>(null)
const initialAnnotations = ref<AdminAnnotationItem[]>([])
const initialForm = ref<Partial<LabelingEditorSubmit> | undefined>(undefined)
const annotatedImageUrl = ref<string | null>(null)

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

function proxyImageUrl(id: number): string {
  // 后端图片代理端点 — admin 鉴权后流式返回原图
  // 解决: <img> 标签无法设 Authorization header, 改用 query string 传 token
  const token = localStorage.getItem('admin_token') || ''
  return `/api/vasi/admin/image-labels/${id}/image?access_token=${encodeURIComponent(token)}`
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

async function openEditor(item: LabelItem) {
  editingItem.value = item
  initialAnnotations.value = []
  initialForm.value = undefined
  annotatedImageUrl.value = null

  // ── 先加载所有数据，再显示编辑器（消除异步时序问题）──

  // 1. 加载已有管理员标注（如果有）
  try {
    const { data } = await request.get<{ annotations: AdminAnnotationItem[] }>(
      `/vasi/admin/image-labels/${item.id}/annotations`
    )
    initialAnnotations.value = data.annotations || []
    const firstMask = initialAnnotations.value.find(a => a.mask_data)
    const firstSkin = initialAnnotations.value.find(a => a.skin_mask_data)
    message.info(`加载标注: ${initialAnnotations.value.length}条, mask=${firstMask?.mask_data?.length || 0}字节, skinMask=${firstSkin?.skin_mask_data?.length || 0}字节`)
    console.log('[openEditor] Loaded admin annotations:', initialAnnotations.value.length,
      'hasMask:', initialAnnotations.value.some(a => a.mask_data),
      'hasSkinMask:', initialAnnotations.value.some(a => a.skin_mask_data))
  } catch (err: any) {
    if (err?.response?.status !== 404) {
      console.warn('加载已有标注失败', err)
    }
  }

  // 1.5. 加载详情（合成图 URL + admin_* 标注字段 — 用作表单回退值）
  try {
    const { data: detail } = await request.get<{
      annotated_image_url?: string | null
      admin_body_site?: string | null
      admin_is_vitiligo?: boolean | null
      admin_vitiligo_type?: string | null
      admin_vitiligo_stage?: string | null
      admin_area_percentage?: number | null
      admin_vasi_score?: number | null
      admin_depigmentation_level?: number | null
      admin_notes?: string | null
    }>(`/vasi/admin/image-labels/${item.id}`)
    if (detail.annotated_image_url) {
      const token = localStorage.getItem('admin_token') || ''
      annotatedImageUrl.value = `/api/vasi/admin/image-labels/${item.id}/annotated-image?access_token=${encodeURIComponent(token)}`
    }
    // ⚠️ FIX: Pass admin_* fields as fallback — they may contain annotation
    // metadata that was saved to ImageLabel but not to ImageLabelAnnotation
    // records (e.g., when buildAnnotations returned [] due to no canvas data).
    initialForm.value = {
      body_site: detail.admin_body_site ?? null,
      is_vitiligo: detail.admin_is_vitiligo ?? null,
      vitiligo_type: detail.admin_vitiligo_type ?? null,
      vitiligo_stage: detail.admin_vitiligo_stage ?? null,
      area_percentage: detail.admin_area_percentage ?? null,
      vasi_score: detail.admin_vasi_score ?? null,
      depigmentation_level: detail.admin_depigmentation_level ?? null,
      notes: detail.admin_notes ?? null,
    }
  } catch (err: any) {
    console.warn('加载标注详情失败', err)
  }

  // 2. 加载用户测评页面的填涂数据 — 预填充画布
  //    管理员可以在用户的基础上修改，无需从零开始
  if (initialAnnotations.value.length === 0) {
    try {
      const { data: userData } = await request.get<{
        has_user_data: boolean
        has_ai_data: boolean
        user_annotations: any[]
        ai_annotations: any[]
        assessment_summary: any
      }>(`/vasi/admin/image-labels/${item.id}/user-annotations`)

      if (userData.has_user_data || userData.has_ai_data) {
        const prefillAnnotations: AdminAnnotationItem[] = []

        if (userData.has_user_data && userData.user_annotations.length > 0) {
          for (const ua of userData.user_annotations) {
            prefillAnnotations.push({
              source: 'admin',
              region_index: ua.region_index || 0,
              body_site: ua.body_site || null,
              is_vitiligo: ua.is_vitiligo ?? null,
              vitiligo_type: ua.vitiligo_type || null,
              vitiligo_stage: ua.vitiligo_stage || null,
              area_percentage: ua.area_percentage ?? null,
              depigmentation_level: ua.depigmentation_level ?? null,
              region_contour: null,
              region_bbox: null,
              mask_data: ua.mask_data || null,
              skin_mask_data: ua.skin_mask_data || null,
              confidence: ua.confidence ?? null,
              notes: '预填充自用户填涂结果 — 管理员审核修改',
            })
          }
        }

        if (!userData.has_user_data && userData.has_ai_data && userData.ai_annotations.length > 0) {
          for (const aa of userData.ai_annotations) {
            prefillAnnotations.push({
              source: 'admin',
              region_index: aa.region_index || 0,
              body_site: aa.body_site || null,
              is_vitiligo: aa.is_vitiligo ?? null,
              vitiligo_type: aa.vitiligo_type || null,
              vitiligo_stage: aa.vitiligo_stage || null,
              area_percentage: aa.area_percentage ?? null,
              depigmentation_level: aa.depigmentation_level ?? null,
              region_contour: null,
              region_bbox: null,
              mask_data: aa.mask_data || null,
              skin_mask_data: aa.skin_mask_data || null,
              confidence: aa.confidence ?? null,
              notes: '预填充自AI填涂结果 — 管理员审核修改',
            })
          }
        }

        if (userData.assessment_summary) {
          const s = userData.assessment_summary
          if (prefillAnnotations.length > 0) {
            prefillAnnotations[0].notes = [
              prefillAnnotations[0].notes || '',
              `评估摘要: body_site=${s.body_site}, area=${s.final_area_percentage ?? s.area_percentage ?? 'N/A'}`,
            ].filter(Boolean).join(' | ')
          }
        }

        if (prefillAnnotations.length > 0) {
          initialAnnotations.value = prefillAnnotations
          console.log(`预填充 ${prefillAnnotations.length} 条用户/AI填涂数据，管理员可直接在此基础上修改`)
        }
      }
    } catch (err: any) {
      if (err?.response?.status !== 404) {
        console.warn('加载用户预填充数据失败', err)
      }
    }
  }

  // ── 数据全部就绪后再显示编辑器 ──
  // 这样 LabelingEditor 挂载时 initialAdminAnnotations 已有数据，
  // loadFromProps → loadMaskLayers 在组件初始化阶段即可恢复图层
  editorVisible.value = true
  await nextTick()
}

async function handleAiPretrain() {
  if (!editingItem.value) return
  try {
    message.info('AI 推理中…')
    const { data } = await request.post<{
      contours: any[]
      lesion_layer_data_url?: string | null
      skin_layer_data_url?: string | null
      body_site?: string
      is_vitiligo?: boolean
      vitiligo_type?: string
      vitiligo_stage?: string
      area_percentage?: number
      vasi_score?: number
      depigmentation_level?: number
      confidence?: number
      duration_ms?: number
    }>(`/vasi/admin/image-labels/${editingItem.value.id}/ai-pretrain`)

    if (data.lesion_layer_data_url || data.skin_layer_data_url) {
      editorRef.value?.applyAiMask(data.skin_layer_data_url || null, data.lesion_layer_data_url || null)
      message.success(`AI 预标注完成: 皮肤+白斑像素蒙版已生成, 耗时 ${Math.round((data.duration_ms || 0) / 1000)}s`)
    } else {
      message.warning('AI 推理未返回蒙版数据, 请手动像素填涂')
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || ''
    const status = err?.response?.status || 0
    if (status === 400) {
      message.error(detail || '图片无法加载，请检查图片是否已损坏或删除')
    } else if (status === 404) {
      message.error(detail || '标注记录不存在')
    } else if (status === 500) {
      message.error(detail || 'AI 推理服务异常，请稍后重试')
    } else if (status === 0 || !status) {
      message.error('网络连接失败，请检查服务器是否正常运行')
    } else {
      message.error(detail || 'AI 预标注失败')
    }
  }
}

async function handleSaveDraft(payload: LabelingEditorSubmit) {
  if (!editingItem.value) return
  const labelId = editingItem.value.id
  try {
    // Save draft — same payload as submit but with draft_mode=true
    const compressedAnnotations = payload.annotations.map(ann => {
      if (ann.mask_data && ann.mask_data.startsWith('data:image/png;base64,')) {
        const sizeMB = (ann.mask_data.length * 3) / 4 / 1024 / 1024
        if (sizeMB > 2) {
          message.warning(`Mask 大小 ${sizeMB.toFixed(1)}MB, 考虑压缩或减少填涂范围`)
        }
      }
      return ann
    })

    // DEBUG: show what we're about to send
    message.info(`暂存中: annotations=${compressedAnnotations.length}条, mask=${compressedAnnotations[0]?.mask_data?.length || 0}字节, skinMask=${compressedAnnotations[0]?.skin_mask_data?.length || 0}字节, annotatedImg=${payload.annotated_image?.length || 0}字节`)

    const submitPayload = {
      body_site: payload.body_site,
      is_vitiligo: payload.is_vitiligo,
      vitiligo_type: payload.vitiligo_type,
      vitiligo_stage: payload.vitiligo_stage,
      area_percentage: payload.area_percentage,
      vasi_score: payload.vasi_score,
      depigmentation_level: payload.depigmentation_level,
      notes: payload.notes,
      training_eligible: payload.training_eligible,
      annotations: compressedAnnotations,
      annotated_image: payload.annotated_image || null,  // 保存合成预览图
      draft_mode: true,  // KEY: save as draft, not finalize
    }

    await request.post(`/vasi/admin/image-labels/${labelId}/label`, submitPayload)
    message.success('已暂存！您可以稍后继续编辑')
  } catch (err: any) {
    const status = err?.response?.status || 0
    if (status === 401) {
      message.error('登录已过期，请重新登录管理后台')
    } else {
      message.error(err?.response?.data?.detail || '暂存失败')
    }
  }
}

async function handleEditorSubmit(payload: LabelingEditorSubmit) {
  if (!editingItem.value) return
  submittingId.value = editingItem.value.id
  try {
    // 把 mask_data 中的大图也压缩一下
    const compressedAnnotations = payload.annotations.map(ann => {
      if (ann.mask_data && ann.mask_data.startsWith('data:image/png;base64,')) {
        // 简单检查大小, 超过 2MB 的 mask 警告
        const sizeMB = (ann.mask_data.length * 3) / 4 / 1024 / 1024
        if (sizeMB > 2) {
          message.warning(`Mask 大小 ${sizeMB.toFixed(1)}MB, 考虑压缩或减少填涂范围`)
        }
      }
      return ann
    })

    // 如果有标注合成图（原始照片 + 画笔涂层叠加），作为额外 annotation 保存
    if (payload.annotated_image) {
      compressedAnnotations.push({
        source: 'admin',
        region_index: compressedAnnotations.length,
        body_site: payload.body_site,
        is_vitiligo: payload.is_vitiligo,
        vitiligo_type: payload.vitiligo_type,
        vitiligo_stage: payload.vitiligo_stage,
        area_percentage: payload.area_percentage,
        depigmentation_level: payload.depigmentation_level,
        region_contour: null,
        region_bbox: null,
        mask_data: payload.annotated_image,
        confidence: null,
        notes: '标注合成图（原始照片+画笔涂层）',
      })
    }

    const submitPayload = {
      body_site: payload.body_site,
      is_vitiligo: payload.is_vitiligo,
      vitiligo_type: payload.vitiligo_type,
      vitiligo_stage: payload.vitiligo_stage,
      area_percentage: payload.area_percentage,
      vasi_score: payload.vasi_score,
      depigmentation_level: payload.depigmentation_level,
      notes: payload.notes,
      training_eligible: payload.training_eligible,
      annotations: compressedAnnotations,
    }
    // 只去掉空字符串 annotations (空字符串在 Pydantic 会被拒绝)
    // null 值显式传递给后端, 配合 exclude_unset 实现字段清除
    await request.post(`/vasi/admin/image-labels/${editingItem.value.id}/label`, submitPayload)
    message.success(`标注成功! 共 ${compressedAnnotations.length} 处白斑`)
    editorVisible.value = false
    fetchList()
    fetchStats()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '提交失败')
  } finally {
    submittingId.value = null
  }
}

function openWorkspace(item: LabelItem) {
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
  try {
    const params: any = { limit: pageSize, offset: (currentPage.value - 1) * pageSize }
    if (activeTab.value === 'pending') params.label_status = 'pending'
    else if (activeTab.value === 'labeled') params.label_status = 'labeled'
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
    else if (activeTab.value === 'labeled') params.set('label_status', 'labeled')
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

.label-row-thumb {
  position: relative;
  width: 80px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 6px;
  overflow: hidden;
  background: #1e293b;
  cursor: pointer;
}
.label-row-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  font-size: 24px;
}
.thumb-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  background: #10b981;
  color: #fff;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
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
.label-row-conf {
  font-size: 11px;
  color: #10b981;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
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

@media (max-width: 768px) {
  .label-row { flex-direction: column; gap: 8px; padding: 10px; }
  .label-row-thumb { width: 100%; height: 120px; }
  .label-row-thumb img { object-fit: contain; }
  .human-section .section-form { gap: 4px; }
}
</style>
