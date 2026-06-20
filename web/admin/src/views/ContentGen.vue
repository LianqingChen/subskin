<template>
  <div class="content-gen-page">
    <n-page-header title="内容生成" />
    <p class="page-desc">管理 AI 生成内容的草稿、编辑与发布</p>

    <!-- AI 需求对话 -->
    <n-card style="margin-top: 20px" :bordered="false" class="ai-dialog-card">
      <div class="ai-dialog-header">
        <i class="ri-robot-line" style="font-size: 20px; color: #6366f1;" />
        <span class="ai-dialog-title">AI 内容助手</span>
        <n-tag size="small" type="info">输入需求，智能生成</n-tag>
      </div>
      <n-space vertical :size="12">
        <n-input
          v-model:value="aiPrompt"
          type="textarea"
          placeholder="用自然语言描述你想要的内容，例如：'生成一篇关于JAK抑制剂治疗白癜风最新进展的科普文章' 或 '写一篇帮助病友缓解焦虑的心理支持文章'"
          :rows="2"
          :autosize="{ minRows: 2, maxRows: 4 }"
          @keydown.enter.ctrl="handleAiGenerate"
        />
        <n-space align="center" justify="space-between">
          <n-space :size="8">
            <n-button type="primary" :loading="aiGenerating" @click="handleAiGenerate">
              <template #icon><i class="ri-magic-line" /></template>
              生成内容
            </n-button>
            <n-checkbox v-model:checked="aiAutoCreate" size="small">自动创建草稿</n-checkbox>
          </n-space>
          <span class="ai-hint">Ctrl+Enter 发送</span>
        </n-space>

        <!-- 生成状态 -->
        <n-alert v-if="aiStatus" :type="aiStatus === 'error' ? 'error' : 'info'" :show-icon="false" style="margin-top: 4px">
          <template v-if="aiStatus === 'thinking'">
            <n-space align="center" :size="8">
              <n-spin size="small" />
              <span>正在分析需求并搜索知识库...</span>
            </n-space>
          </template>
          <template v-else-if="aiStatus === 'generating'">
            <n-space align="center" :size="8">
              <n-spin size="small" />
              <span>正在生成内容...</span>
            </n-space>
          </template>
          <template v-else-if="aiStatus === 'error'">
            {{ aiError }}
          </template>
        </n-alert>

        <!-- 生成结果预览 -->
        <div v-if="aiResult" class="ai-result-preview">
          <n-divider />
          <div class="ai-result-header">
            <n-tag type="success" size="small">AI 生成结果</n-tag>
            <n-space :size="8">
              <n-button size="small" type="primary" :loading="aiAdopting" @click="adoptAiResult">
                <template #icon><i class="ri-check-line" /></template>
                采纳并创建草稿
              </n-button>
              <n-button size="small" @click="clearAiResult">
                <template #icon><i class="ri-close-line" /></template>
                清除
              </n-button>
            </n-space>
          </div>
          <n-card size="small" class="ai-result-content">
            <h4 class="ai-result-title">{{ aiResult.title }}</h4>
            <p class="ai-result-summary">{{ aiResult.summary }}</p>
            <div class="ai-result-body">{{ aiResult.content }}</div>
          </n-card>

          <!-- 搜索来源 -->
          <n-card v-if="aiResult.search_sources?.length" size="small" title="搜索来源" class="ai-sources-card" style="margin-top: 12px">
            <n-space vertical :size="6">
              <div v-for="(src, idx) in aiResult.search_sources" :key="idx" class="ai-source-item">
                <n-tag :type="src.source_type === 'encyclopedia' ? 'info' : src.source_type === 'raw_data' ? 'warning' : 'default'" size="tiny">
                  {{ src.source_type === 'encyclopedia' ? '百科' : src.source_type === 'raw_data' ? '原始数据' : '知识库' }}
                </n-tag>
                <span class="ai-source-title">{{ src.title }}</span>
                <a v-if="src.url" :href="src.url" target="_blank" class="ai-source-link">
                  <i class="ri-external-link-line" />
                </a>
              </div>
            </n-space>
          </n-card>
        </div>
      </n-space>
    </n-card>

    <!-- 统计与操作区 -->
    <n-card style="margin-top: 24px" :bordered="false" class="action-card">
      <n-space align="center" justify="space-between" wrap>
        <n-space align="center" wrap>
          <n-input-number
            v-model:value="generateCount"
            :min="1"
            :max="50"
            style="width: 120px"
            placeholder="生成数量"
          />
          <n-button type="primary" :loading="generating" @click="handleGenerate">
            <template #icon>
              <i class="ri-magic-line" />
            </template>
            生成内容
          </n-button>
          <n-divider vertical />
          <n-select
            v-model:value="filterCategory"
            :options="categoryFilterOptions"
            placeholder="分类筛选"
            style="width: 140px"
            clearable
            @update:value="handleFilterChange"
          />
          <n-select
            v-model:value="filterStatus"
            :options="statusFilterOptions"
            placeholder="状态筛选"
            style="width: 140px"
            clearable
            @update:value="handleFilterChange"
          />
          <n-button @click="handleRefresh">
            <template #icon>
              <i class="ri-refresh-line" />
            </template>
            刷新
          </n-button>
        </n-space>
        <n-tag v-if="lastGeneratedText" type="info" size="small">
          上次生成：{{ lastGeneratedText }}
        </n-tag>
      </n-space>
    </n-card>

    <!-- 草稿列表 -->
    <n-card style="margin-top: 16px" :bordered="false" class="table-card">
      <!-- Category quick tabs -->
      <n-space style="margin-bottom: 12px" :size="8" wrap>
        <n-tag
          :type="filterCategory === null ? 'primary' : 'default'"
          :bordered="false"
          size="medium"
          style="cursor: pointer"
          @click="filterCategory = null; handleFilterChange()"
        >
          全部
        </n-tag>
        <n-tag
          v-for="(label, value) in categoryMap"
          :key="value"
          :type="filterCategory === Number(value) ? 'primary' : 'default'"
          :bordered="false"
          size="medium"
          style="cursor: pointer"
          @click="filterCategory = Number(value); handleFilterChange()"
        >
          {{ label }}
        </n-tag>
      </n-space>

      <!-- Batch actions -->
      <div v-if="checkedRowKeys.length > 0" class="batch-actions">
        <n-space align="center" :size="12">
          <n-checkbox :checked="isAllChecked" :indeterminate="isIndeterminate" @update:checked="toggleSelectAll" />
          <span class="batch-count">已选 {{ checkedRowKeys.length }} 项</span>
          <n-button size="small" @click="toggleSelectAll">全选</n-button>
          <n-divider vertical />
          <n-button size="small" type="success" :loading="batchPublishing" @click="handleBatchPublish">
            <template #icon><i class="ri-send-plane-line" /></template>
            批量发布
          </n-button>
          <n-button size="small" type="error" :loading="batchDeleting" @click="handleBatchDelete">
            <template #icon><i class="ri-delete-bin-line" /></template>
            批量删除
          </n-button>
        </n-space>
      </div>

      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="drafts"
          :bordered="false"
          :single-line="false"
          :row-key="(row: DraftItem) => row.id"
          :checked-row-keys="checkedRowKeys"
          @update:checked-row-keys="handleCheckedChange"
          size="small"
          max-height="560px"
          scroll-x="800"
        />
      </n-spin>
      <n-empty v-if="!loading && drafts.length === 0" description="暂无草稿记录" size="small" style="margin-top: 16px;" />
      <n-space justify="end" style="margin-top: 16px">
        <n-pagination
          v-model:page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :item-count="pagination.itemCount"
          :page-sizes="[10, 20, 50]"
          show-size-picker
          show-quick-jumper
          @update:page="fetchDrafts"
          @update:page-size="handlePageSizeChange"
        />
      </n-space>
    </n-card>

    <!-- 编辑弹窗 -->
    <n-modal
      v-model:show="editModal.visible"
      preset="card"
      title="编辑草稿"
      style="width: 800px; max-width: 94vw;"
      :bordered="false"
      class="edit-modal"
    >
      <div class="edit-modal-body" style="max-height: 70vh; overflow-y: auto; padding-right: 4px;">
        <n-spin :show="editModal.loading">
          <n-form label-placement="top" :model="editForm">
            <n-form-item label="标题" required>
              <n-input v-model:value="editForm.title" placeholder="请输入标题" size="large" />
            </n-form-item>

            <n-form-item label="正文内容" required>
              <n-input
                v-model:value="editForm.content"
                type="textarea"
                placeholder="请输入正文内容"
                :rows="14"
                :autosize="{ minRows: 10, maxRows: 22 }"
              />
              <template #feedback>
                <span class="char-count">共 {{ editForm.content.length }} 字</span>
              </template>
            </n-form-item>

            <!-- AI 来源参考 -->
            <n-form-item v-if="editSourceRefs.length > 0" label="AI 来源参考">
              <n-space vertical :size="8">
                <div v-for="(ref, idx) in editSourceRefs" :key="idx" class="source-ref-item">
                  <i class="ri-link" style="color: #6366f1; margin-right: 6px;" />
                  <span class="ref-title">{{ ref.title || '未命名来源' }}</span>
                  <a v-if="ref.url" :href="ref.url" target="_blank" class="ref-url" :title="ref.url">
                    <i class="ri-external-link-line" />
                  </a>
                </div>
              </n-space>
            </n-form-item>

            <n-grid :cols="3" :x-gap="12">
              <n-gi>
                <n-form-item label="分类">
                  <n-select
                    v-model:value="editForm.category_id"
                    :options="categoryOptions"
                    placeholder="选择分类"
                  />
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="状态">
                  <n-select
                    v-model:value="editForm.status"
                    :options="statusEditOptions"
                    placeholder="选择状态"
                  />
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="城市">
                  <n-select
                    v-model:value="editForm.city"
                    :options="cityOptions"
                    placeholder="选择城市"
                    filterable
                    clearable
                  />
                </n-form-item>
              </n-gi>
            </n-grid>

            <n-grid :cols="2" :x-gap="12">
              <n-gi>
                <n-form-item label="心情">
                  <n-select
                    v-model:value="editForm.mood"
                    :options="moodOptions"
                    placeholder="选择心情"
                    clearable
                  />
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="标签">
                  <n-select
                    v-model:value="editForm.tag_names"
                    :options="tagSelectOptions"
                    placeholder="选择或输入标签"
                    multiple
                    filterable
                    tag
                    clearable
                  />
                </n-form-item>
              </n-gi>
            </n-grid>

            <!-- 图片管理 -->
            <n-form-item label="配图">
              <div v-if="editForm.images.filter(u => u).length > 0" class="image-preview-grid">
                <div v-for="(url, idx) in editForm.images.filter(u => u)" :key="idx" class="image-preview-item">
                  <n-image :src="url" style="height: 120px; width: 100%; object-fit: cover; border-radius: 6px;" />
                  <n-button
                    size="tiny"
                    type="error"
                    quaternary
                    class="image-remove-btn"
                    @click="removeImage(idx)"
                  >
                    <template #icon><i class="ri-close-line" /></template>
                  </n-button>
                </div>
              </div>
              <div class="image-input-row">
                <n-input
                  v-model:value="imageUrlInput"
                  placeholder="输入图片 URL 后按回车添加"
                  @keydown.enter.prevent="addImageUrl"
                />
                <n-button size="small" type="primary" @click="addImageUrl" :disabled="!imageUrlInput.trim()">
                  <template #icon><i class="ri-add-line" /></template>
                  添加
                </n-button>
              </div>
            </n-form-item>
          </n-form>
        </n-spin>
      </div>
      <template #footer>
        <n-space justify="end">
          <n-button @click="editModal.visible = false">取消</n-button>
          <n-button type="primary" :loading="editModal.saving" @click="handleSaveDraft">
            保存
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 发布预览弹窗 -->
    <n-modal
      v-model:show="publishModal.visible"
      preset="card"
      title="发布预览"
      style="width: 640px; max-width: 90vw;"
      :bordered="false"
      class="publish-modal"
    >
      <n-spin :show="publishModal.loading">
        <n-space vertical :size="16">
          <n-descriptions :column="1" size="small" :bordered="false">
            <n-descriptions-item label="标题">
              {{ publishModal.draft?.title || '-' }}
            </n-descriptions-item>
            <n-descriptions-item label="分类">
              {{ publishModal.draft?.category_name || categoryMap[publishModal.draft?.category_id || 0] || '-' }}
            </n-descriptions-item>
            <n-descriptions-item label="城市">
              {{ publishModal.draft?.city || '-' }}
            </n-descriptions-item>
            <n-descriptions-item label="心情">
              {{ publishModal.draft?.mood || '-' }}
            </n-descriptions-item>
            <n-descriptions-item label="标签">
              <n-space v-if="publishModal.draft?.tag_names?.length" :size="6" wrap>
                <n-tag v-for="tag in publishModal.draft.tag_names" :key="tag" size="small">
                  {{ tag }}
                </n-tag>
              </n-space>
              <span v-else>-</span>
            </n-descriptions-item>
          </n-descriptions>
          <n-card size="small" title="内容预览" class="inner-card">
            <div class="preview-content">{{ publishModal.draft?.content || publishModal.draft?.content_preview || '-' }}</div>
          </n-card>
          <n-alert type="info" :show-icon="false">
            发布后该草稿将同步到社区「发现」页面，且状态变为已发布，不可再编辑。
          </n-alert>
        </n-space>
      </n-spin>
      <template #footer>
        <n-space justify="end">
          <n-button @click="publishModal.visible = false">取消</n-button>
          <n-button type="success" :loading="publishModal.publishing" @click="confirmPublish">
            确认发布
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import {
  NPageHeader,
  NCard,
  NSpace,
  NButton,
  NInput,
  NInputNumber,
  NSelect,
  NDataTable,
  NTag,
  NModal,
  NForm,
  NFormItem,
  NGrid,
  NGi,
  NDivider,
  NImage,
  NDescriptions,
  NDescriptionsItem,
  NAlert,
  NSpin,
  NPagination,
  NEmpty,
  NCheckbox,
  useMessage,
  useDialog,
} from 'naive-ui'
import request from '@/api/request'

const message = useMessage()
const dialog = useDialog()

// ── Types ──
interface DraftItem {
  id: number
  title: string
  content_preview?: string
  category_id: number
  category_name?: string
  post_type: string
  status: string
  city?: string
  mood?: string
  tag_names: string[]
  images: string[]
  source_type?: string
  ai_confidence?: number
  scheduled_at?: string
  published_at?: string
  created_at?: string
}

interface DraftDetail extends DraftItem {
  content: string
  content_json?: string
  source_refs: Array<{ title: string; url: string }>
  published_post_id?: number
  updated_at?: string
}

interface GenerateResponse {
  status: string
  message: string
  created_count: number
  draft_ids: number[]
}

interface PublishResponse {
  status: string
  post_id: number
}

// ── Constants ──
const categoryMap: Record<number, string> = {
  1: '治疗分享',
  2: '心理支持',
  3: '护肤经验',
  4: '日常饮食',
  5: '诊断咨询',
  6: '科普百科',
  7: '其他',
  8: '白白日记',
}

const categoryOptions = Object.entries(categoryMap).map(([value, label]) => ({
  label,
  value: Number(value),
}))

const statusFilterOptions = [
  { label: '全部', value: '' },
  { label: '草稿', value: 'draft' },
  { label: '待发布', value: 'ready_to_publish' },
  { label: '已发布', value: 'published' },
]

const statusEditOptions = [
  { label: '草稿', value: 'draft' },
  { label: '待发布', value: 'ready_to_publish' },
]

const cityOptions = [
  { label: '北京', value: '北京' }, { label: '上海', value: '上海' },
  { label: '广州', value: '广州' }, { label: '深圳', value: '深圳' },
  { label: '杭州', value: '杭州' }, { label: '成都', value: '成都' },
  { label: '武汉', value: '武汉' }, { label: '南京', value: '南京' },
  { label: '重庆', value: '重庆' }, { label: '西安', value: '西安' },
  { label: '苏州', value: '苏州' }, { label: '郑州', value: '郑州' },
  { label: '长春', value: '长春' }, { label: '天津', value: '天津' },
  { label: '石家庄', value: '石家庄' },
]

const moodOptions = [
  { label: '💭求知', value: '💭求知' }, { label: '📖学习', value: '📖学习' },
  { label: '🌱成长', value: '🌱成长' }, { label: '💪坚持中', value: '💪坚持中' },
  { label: '❤️温暖', value: '❤️温暖' }, { label: '🌟希望', value: '🌟希望' },
  { label: '📰关注', value: '📰关注' }, { label: '🔬探索', value: '🔬探索' },
  { label: '✨兴奋', value: '✨兴奋' }, { label: '📚记录', value: '📚记录' },
  { label: '📸回忆', value: '📸回忆' }, { label: '🌙感想', value: '🌙感想' },
]

const tagSelectOptions = [
  { label: '白癜风科普', value: '白癜风科普' }, { label: '免疫治疗', value: '免疫治疗' },
  { label: '新药研究', value: '新药研究' }, { label: '临床试验', value: '临床试验' },
  { label: '皮肤健康', value: '皮肤健康' }, { label: '光疗', value: '光疗' },
  { label: '激光治疗', value: '激光治疗' }, { label: '药物治疗', value: '药物治疗' },
  { label: '心理支持', value: '心理支持' }, { label: '情绪管理', value: '情绪管理' },
  { label: '自信心', value: '自信心' }, { label: '社交支持', value: '社交支持' },
  { label: '家庭关怀', value: '家庭关怀' }, { label: '心理健康', value: '心理健康' },
  { label: '最新动态', value: '最新动态' }, { label: '行业资讯', value: '行业资讯' },
  { label: '医学前沿', value: '医学前沿' }, { label: '科研突破', value: '科研突破' },
  { label: '药企动态', value: '药企动态' }, { label: '基金会活动', value: '基金会活动' },
  { label: '白白日记', value: '白白日记' }, { label: '每日分享', value: '每日分享' },
  { label: '生活感悟', value: '生活感悟' }, { label: '经验交流', value: '经验交流' },
  { label: '日常护理', value: '日常护理' }, { label: 'JAK抑制剂', value: 'JAK抑制剂' },
  { label: '自身免疫', value: '自身免疫' }, { label: '色素脱失', value: '色素脱失' },
]

const statusTypeMap: Record<string, string> = {
  draft: 'default',
  ready_to_publish: 'warning',
  published: 'success',
}

const statusLabelMap: Record<string, string> = {
  draft: '草稿',
  ready_to_publish: '待发布',
  published: '已发布',
}

// ── State ──
const drafts = ref<DraftItem[]>([])
const loading = ref(false)
const generating = ref(false)
const generateCount = ref(10)
const filterStatus = ref<string | null>(null)
const filterCategory = ref<number | null>(null)
const lastGeneratedText = ref('')

const aiPrompt = ref('')
const aiGenerating = ref(false)
const aiAdopting = ref(false)
const aiAutoCreate = ref(true)
const aiStatus = ref<'thinking' | 'generating' | 'error' | null>(null)
const aiError = ref('')
const aiResult = ref<AiGenerateResult | null>(null)

const checkedRowKeys = ref<Array<string | number>>([])
const batchPublishing = ref(false)
const batchDeleting = ref(false)

const isAllChecked = computed(() => {
  return drafts.value.length > 0 && checkedRowKeys.value.length === drafts.value.length
})

const isIndeterminate = computed(() => {
  return checkedRowKeys.value.length > 0 && checkedRowKeys.value.length < drafts.value.length
})

function handleCheckedChange(keys: Array<string | number>) {
  checkedRowKeys.value = keys
}

function toggleSelectAll() {
  if (isAllChecked.value) {
    checkedRowKeys.value = []
  } else {
    checkedRowKeys.value = drafts.value.map(d => d.id)
  }
}

interface AiGenerateResult {
  title: string
  content: string
  summary: string
  tags: string[]
  source_refs: Array<{ title: string; url: string }>
  search_sources: Array<{ title: string; snippet: string; url?: string; source_type: string }>
  draft_id?: number
}

async function handleAiGenerate() {
  const prompt = aiPrompt.value.trim()
  if (!prompt || prompt.length < 5) {
    message.warning('请至少输入5个字的需求描述')
    return
  }
  aiGenerating.value = true
  aiStatus.value = 'thinking'
  aiError.value = ''
  aiResult.value = null
  try {
    const { data } = await request.post<AiGenerateResult>('/admin/content/ai-generate', {
      prompt,
      auto_create: aiAutoCreate.value,
    })
    aiResult.value = data
    aiStatus.value = null
    if (data.draft_id) {
      message.success(`草稿已自动创建，ID: ${data.draft_id}`)
      await fetchDrafts()
    }
  } catch (err: any) {
    aiStatus.value = 'error'
    aiError.value = err?.response?.data?.detail || 'AI 生成失败，请检查 LLM 配置或稍后重试'
  } finally {
    aiGenerating.value = false
  }
}

async function adoptAiResult() {
  if (!aiResult.value) return
  aiAdopting.value = true
  try {
    await request.post<AiGenerateResult>('/admin/content/ai-generate', {
      prompt: aiPrompt.value,
      auto_create: true,
    })
    message.success('草稿已创建')
    aiResult.value = null
    aiPrompt.value = ''
    await fetchDrafts()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '创建草稿失败')
  } finally {
    aiAdopting.value = false
  }
}

function clearAiResult() {
  aiResult.value = null
  aiStatus.value = null
  aiError.value = ''
}

async function handleBatchPublish() {
  if (checkedRowKeys.value.length === 0) return
  batchPublishing.value = true
  try {
    const { data } = await request.post('/admin/content/drafts/batch-publish', {
      draft_ids: checkedRowKeys.value.map(Number),
    })
    message.success(`批量发布完成：成功 ${data.success.length} 篇${data.failed.length ? `，失败 ${data.failed.length} 篇` : ''}`)
    checkedRowKeys.value = []
    await fetchDrafts()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '批量发布失败')
  } finally {
    batchPublishing.value = false
  }
}

async function handleBatchDelete() {
  if (checkedRowKeys.value.length === 0) return
  batchDeleting.value = true
  try {
    const { data } = await request.delete('/admin/content/drafts/batch', {
      data: { draft_ids: checkedRowKeys.value.map(Number) },
    })
    message.success(`成功删除 ${data.deleted} 篇草稿（已发布的不会被删除）`)
    checkedRowKeys.value = []
    await fetchDrafts()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '批量删除失败')
  } finally {
    batchDeleting.value = false
  }
}

const categoryFilterOptions = Object.entries(categoryMap).map(([value, label]) => ({
  label,
  value: Number(value),
}))

const pagination = ref({
  page: 1,
  pageSize: 20,
  itemCount: 0,
})

const editModal = ref({
  visible: false,
  draftId: 0,
  loading: false,
  saving: false,
})

const editForm = ref({
  title: '',
  content: '',
  category_id: 1,
  status: 'draft' as string,
  city: '',
  mood: '',
  tag_names: [] as string[],
  images: [] as string[],
})

const publishModal = ref({
  visible: false,
  draftId: 0,
  draft: null as DraftDetail | null,
  loading: false,
  publishing: false,
})

const imageUrlInput = ref('')
const editSourceRefs = ref<Array<{ title: string; url: string }>>([])

function addImageUrl() {
  const url = imageUrlInput.value.trim()
  if (!url) return
  if (!editForm.value.images) editForm.value.images = []
  editForm.value.images.push(url)
  imageUrlInput.value = ''
}

function removeImage(idx: number) {
  editForm.value.images.splice(idx, 1)
}

// ── Helpers ──
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

function formatConfidence(v?: number) {
  if (v == null) return '-'
  return `${(v * 100).toFixed(0)}%`
}

// ── Columns ──
const columns = computed(() => [
  {
    type: 'selection' as const,
    width: 40,
  },
  {
    title: 'ID',
    key: 'id',
    width: 70,
    ellipsis: { tooltip: true },
  },
  {
    title: '标题',
    key: 'title',
    ellipsis: { tooltip: true },
    render(row: DraftItem) {
      return row.title || '-'
    },
  },
  {
    title: '分类',
    key: 'category_name',
    width: 110,
    render(row: DraftItem) {
      return row.category_name || categoryMap[row.category_id] || '-'
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row: DraftItem) {
      return h(NTag, { type: statusTypeMap[row.status] as any, size: 'small' }, {
        default: () => statusLabelMap[row.status] || row.status,
      })
    },
  },
  {
    title: '城市',
    key: 'city',
    width: 100,
    render(row: DraftItem) {
      return row.city || '-'
    },
  },
  {
    title: '心情',
    key: 'mood',
    width: 100,
    render(row: DraftItem) {
      return row.mood || '-'
    },
  },
  {
    title: '标签',
    key: 'tag_names',
    width: 160,
    ellipsis: { tooltip: true },
    render(row: DraftItem) {
      if (!row.tag_names?.length) return '-'
      return row.tag_names.join(', ')
    },
  },
  {
    title: 'AI置信度',
    key: 'ai_confidence',
    width: 90,
    render(row: DraftItem) {
      return formatConfidence(row.ai_confidence)
    },
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 170,
    render(row: DraftItem) {
      return formatDate(row.created_at)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    fixed: 'right' as const,
    render(row: DraftItem) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => openEditModal(row) }, { default: () => '编辑' }),
          row.status !== 'published'
            ? h(NButton, { size: 'small', type: 'success', onClick: () => openPublishModal(row) }, { default: () => '发布' })
            : null,
          h(
            NButton,
            { size: 'small', type: 'error', ghost: true, onClick: () => handleDelete(row) },
            { default: () => '删除' },
          ),
        ].filter(Boolean),
      })
    },
  },
])

// ── API ──
async function fetchDrafts() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      sort: 'id_asc',
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    if (filterCategory.value) {
      params.category_id = filterCategory.value
    }
    const res = await request.get<DraftItem[]>('/admin/content/drafts', { params })
    const data = Array.isArray(res.data) ? res.data : []
    drafts.value = data
    // 后端未返回 total，用启发式分页
    if (data.length === pagination.value.pageSize) {
      pagination.value.itemCount = pagination.value.page * pagination.value.pageSize + 1
    } else {
      pagination.value.itemCount = (pagination.value.page - 1) * pagination.value.pageSize + data.length
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取草稿列表失败')
    drafts.value = []
    pagination.value.itemCount = 0
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  pagination.value.page = 1
  checkedRowKeys.value = []
  fetchDrafts()
}

function handlePageSizeChange(size: number) {
  pagination.value.pageSize = size
  pagination.value.page = 1
  checkedRowKeys.value = []
  fetchDrafts()
}

function handleRefresh() {
  fetchDrafts()
}

async function handleGenerate() {
  generating.value = true
  try {
    const res = await request.post<GenerateResponse>('/admin/content/generate', null, {
      params: { count: generateCount.value },
    })
    const data = res.data
    message.success(data.message || `成功生成 ${data.created_count} 篇内容`)
    lastGeneratedText.value = formatDate(new Date().toISOString())
    pagination.value.page = 1
    await fetchDrafts()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '生成内容失败')
  } finally {
    generating.value = false
  }
}

// ── Edit ──
async function openEditModal(row: DraftItem) {
  editModal.value.draftId = row.id
  editModal.value.visible = true
  editModal.value.loading = true
  try {
    const res = await request.get<DraftDetail>(`/admin/content/drafts/${row.id}`)
    const d = res.data
    editForm.value = {
      title: d.title || '',
      content: d.content || '',
      category_id: d.category_id ?? 1,
      status: d.status || 'draft',
      city: d.city || '',
      mood: d.mood || '',
      tag_names: d.tag_names || [],
      images: d.images || [],
    }
    editSourceRefs.value = d.source_refs || []
    imageUrlInput.value = ''
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取草稿详情失败')
    editModal.value.visible = false
  } finally {
    editModal.value.loading = false
  }
}

async function handleSaveDraft() {
  if (!editForm.value.title.trim()) {
    message.warning('请输入标题')
    return
  }
  editModal.value.saving = true
  try {
    const payload: Record<string, any> = {
      title: editForm.value.title,
      content: editForm.value.content,
      category_id: editForm.value.category_id,
      status: editForm.value.status,
      city: editForm.value.city || undefined,
      mood: editForm.value.mood || undefined,
      tag_names: editForm.value.tag_names,
      images: editForm.value.images.filter(u => u.trim()),
    }
    await request.put(`/admin/content/drafts/${editModal.value.draftId}`, payload)
    message.success('保存成功')
    editModal.value.visible = false
    await fetchDrafts()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '保存失败')
  } finally {
    editModal.value.saving = false
  }
}

// ── Publish ──
async function openPublishModal(row: DraftItem) {
  publishModal.value.draftId = row.id
  publishModal.value.visible = true
  publishModal.value.loading = true
  try {
    const res = await request.get<DraftDetail>(`/admin/content/drafts/${row.id}`)
    publishModal.value.draft = res.data
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取草稿详情失败')
    publishModal.value.visible = false
  } finally {
    publishModal.value.loading = false
  }
}

async function confirmPublish() {
  publishModal.value.publishing = true
  try {
    const res = await request.post<PublishResponse>(`/admin/content/drafts/${publishModal.value.draftId}/publish`)
    const data = res.data
    message.success(`发布成功，帖子 ID: ${data.post_id}`)
    publishModal.value.visible = false
    await fetchDrafts()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '发布失败')
  } finally {
    publishModal.value.publishing = false
  }
}

// ── Delete ──
function handleDelete(row: DraftItem) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除草稿「${row.title || row.id}」吗？此操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    positiveButtonProps: { type: 'error' },
    onPositiveClick: async () => {
      try {
        await request.delete(`/admin/content/drafts/${row.id}`)
        message.success('删除成功')
        await fetchDrafts()
      } catch (err: any) {
        message.error(err?.response?.data?.detail || '删除失败')
      }
    },
  })
}

onMounted(() => {
  fetchDrafts()
})
</script>

<style scoped>
.content-gen-page {
  padding: 0;
}

.page-desc {
  color: #94a3b8;
  margin-top: 8px;
  font-size: 14px;
}

.action-card {
  background-color: #1e293b;
}

.table-card {
  background-color: #1e293b;
}

.edit-modal :deep(.n-card) {
  background-color: #1e293b;
}

.publish-modal :deep(.n-card) {
  background-color: #1e293b;
}

.inner-card {
  background-color: #0f172a;
}

.preview-content {
  white-space: pre-wrap;
  line-height: 1.7;
  max-height: 240px;
  overflow-y: auto;
  color: #e2e8f0;
  font-size: 14px;
}

:deep(.n-data-table .n-data-table-td) {
  background-color: #0f172a;
}

:deep(.n-data-table .n-data-table-th) {
  background-color: #1e293b;
}

.char-count {
  font-size: 12px;
  color: #94a3b8;
}

.source-ref-item {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 6px;
  font-size: 13px;
}

.ref-title {
  color: #cbd5e1;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ref-url {
  color: #6366f1;
  margin-left: 8px;
  flex-shrink: 0;
}

.image-preview-grid {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.image-preview-item {
  position: relative;
  width: 160px;
}

.image-remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0.8;
}

.image-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.ai-dialog-card {
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
  border: 1px solid rgba(99, 102, 241, 0.15);
}

.ai-dialog-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.ai-dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
}

.ai-hint {
  font-size: 12px;
  color: #64748b;
}

.ai-result-preview {
  margin-top: 0;
}

.ai-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.ai-result-content {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(99, 102, 241, 0.1);
}

.ai-result-title {
  margin: 0 0 6px;
  font-size: 16px;
  color: #f8fafc;
}

.ai-result-summary {
  color: #94a3b8;
  font-size: 13px;
  margin-bottom: 10px;
}

.ai-result-body {
  white-space: pre-wrap;
  line-height: 1.8;
  color: #cbd5e1;
  font-size: 14px;
  max-height: 300px;
  overflow-y: auto;
}

.ai-sources-card {
  background: rgba(15, 23, 42, 0.4);
}

.ai-source-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.ai-source-title {
  color: #cbd5e1;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-source-link {
  color: #6366f1;
  flex-shrink: 0;
}

.batch-actions {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  margin-bottom: 8px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 8px;
}

.batch-count {
  color: #cbd5e1;
  font-size: 13px;
  font-weight: 500;
}
</style>
