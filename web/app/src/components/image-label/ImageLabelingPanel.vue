<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { imageLabelApi, getImageProxyUrl } from '@/api/image-label'
import type { ImageLabelListItem, ImageLabelDetail, LabelStats, AiPretrainResponse, ImageLabelAnnotation } from '@/api/image-label'
import MaskEditor from '@/components/tracker/MaskEditor.vue'

const activeView = ref<'list' | 'detail'>('list')
const loading = ref(false)
const stats = ref<LabelStats>({ total: 0, pending: 0, labeled: 0, skipped: 0, rejected: 0, training_ready: 0, user_deleted: 0 })
const items = ref<ImageLabelListItem[]>([])
const total = ref(0)
const offset = ref(0)
const limit = 20
const filterStatus = ref('')
const filterBodySite = ref('')
const filterVitiligo = ref<string>('')
const filterTraining = ref<string>('')

const selectedLabel = ref<ImageLabelDetail | null>(null)
const detailLoading = ref(false)
const showSyncModal = ref(false)
const syncLoading = ref(false)
const syncResult = ref<{ created: number; skipped: number; total: number } | null>(null)

// ── Fullscreen canvas state ──
const isCanvasFullscreen = ref(false)
const showFormPanel = ref(false)

const labelForm = ref({
  body_site: '',
  is_vitiligo: undefined as boolean | undefined,
  vitiligo_type: '',
  vitiligo_stage: '',
  area_percentage: undefined as number | undefined,
  vasi_score: undefined as number | undefined,
  depigmentation_level: undefined as number | undefined,
  notes: '',
  training_eligible: false,
})

const submitLoading = ref(false)
const selectedIds = ref<number[]>([])
const batchLoading = ref(false)

// ── Annotation tools state ──
type AnnotationTool = 'none' | 'mask'
const activeAnnotationTool = ref<AnnotationTool>('none')
const showMaskEditor = computed(() => activeAnnotationTool.value === 'mask')

// ── AI 预标注 & 像素填涂 ──
const aiPretrainLoading = ref(false)
const aiPretrainResult = ref<AiPretrainResponse | null>(null)
const aiPretrainError = ref('')
const maskData = ref<{ skinMaskDataUrl: string; lesionMaskDataUrl: string } | null>(null)
const savedAnnotations = ref<ImageLabelAnnotation[]>([])

const choices = ref({
  body_sites: [] as string[],
  vitiligo_types: [] as string[],
  stages: [] as string[],
  label_statuses: ['pending', 'labeled', 'skipped', 'rejected'],
  training_splits: ['train', 'val', 'test'],
})

const statusBadgeClass = computed(() => (s: string) => {
  const map: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
    labeled: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
    skipped: 'bg-gray-100 text-gray-800',
    rejected: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  }
  return map[s] || 'bg-gray-100 text-gray-800'
})

const statusLabel = computed(() => (s: string) => {
  const map: Record<string, string> = { pending: '待标注', labeled: '已标注', skipped: '已跳过', rejected: '已拒绝' }
  return map[s] || s
})

const vitiligoLabel = computed(() => (v: any) => {
  if (v === true) return '是'
  if (v === false) return '否'
  return '—'
})

const currentPage = computed(() => Math.floor(offset.value / limit) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit)))

async function fetchChoices() {
  try {
    choices.value = await imageLabelApi.getChoices()
  } catch (e) {
    console.error('Failed to fetch choices', e)
  }
}

async function fetchStats() {
  try {
    stats.value = await imageLabelApi.stats()
  } catch (e) {
    console.error('Failed to fetch stats', e)
  }
}

async function fetchList(resetOffset = false) {
  if (resetOffset) offset.value = 0
  loading.value = true
  try {
    const res = await imageLabelApi.list({
      limit,
      offset: offset.value,
      label_status: filterStatus.value || undefined,
      body_site: filterBodySite.value || undefined,
      is_vitiligo: filterVitiligo.value === 'true' ? true : filterVitiligo.value === 'false' ? false : undefined,
      training_eligible: filterTraining.value === 'true' ? true : filterTraining.value === 'false' ? false : undefined,
    })
    items.value = res.items
    total.value = res.total
  } catch (e) {
    console.error('Failed to fetch image labels', e)
  } finally {
    loading.value = false
  }
}

async function openDetail(id: number) {
  detailLoading.value = true
  activeView.value = 'detail'
  isCanvasFullscreen.value = true
  showFormPanel.value = false
  // Reset state
  aiPretrainResult.value = null
  aiPretrainError.value = ''
  activeAnnotationTool.value = 'none'
  maskData.value = null
  savedAnnotations.value = []
  try {
    selectedLabel.value = await imageLabelApi.getDetail(id)
    if (selectedLabel.value) {
      labelForm.value = {
        body_site: selectedLabel.value.admin_body_site || selectedLabel.value.ai_body_site || '',
        is_vitiligo: selectedLabel.value.admin_is_vitiligo ?? selectedLabel.value.ai_is_vitiligo,
        vitiligo_type: selectedLabel.value.admin_vitiligo_type || selectedLabel.value.ai_vitiligo_type || '',
        vitiligo_stage: selectedLabel.value.admin_vitiligo_stage || selectedLabel.value.ai_vitiligo_stage || '',
        area_percentage: selectedLabel.value.admin_area_percentage ?? selectedLabel.value.ai_area_percentage,
        vasi_score: selectedLabel.value.admin_vasi_score ?? selectedLabel.value.ai_vasi_score,
        depigmentation_level: selectedLabel.value.admin_depigmentation_level ?? selectedLabel.value.user_depigmentation_level,
        notes: selectedLabel.value.admin_notes || '',
        training_eligible: selectedLabel.value.training_eligible,
      }
    }
  } catch (e) {
    console.error('Failed to fetch detail', e)
  } finally {
    detailLoading.value = false
  }
}

async function submitLabel() {
  if (!selectedLabel.value) return
  submitLoading.value = true
  try {
    await imageLabelApi.submitLabel(selectedLabel.value.id, {
      body_site: labelForm.value.body_site || undefined,
      is_vitiligo: labelForm.value.is_vitiligo,
      vitiligo_type: labelForm.value.vitiligo_type || undefined,
      vitiligo_stage: labelForm.value.vitiligo_stage || undefined,
      area_percentage: labelForm.value.area_percentage,
      vasi_score: labelForm.value.vasi_score,
      depigmentation_level: labelForm.value.depigmentation_level,
      notes: labelForm.value.notes || undefined,
      training_eligible: labelForm.value.training_eligible,
      annotations: savedAnnotations.value.length > 0 ? savedAnnotations.value : undefined,
    })
    // Reset state
    aiPretrainResult.value = null
    aiPretrainError.value = ''
    maskData.value = null
    savedAnnotations.value = []
    activeAnnotationTool.value = 'none'
    await fetchStats()
    await fetchList()
    activeView.value = 'list'
    isCanvasFullscreen.value = false
    selectedLabel.value = null
  } catch (e) {
    console.error('Failed to submit label', e)
  } finally {
    submitLoading.value = false
  }
}

function closeFullscreen() {
  isCanvasFullscreen.value = false
  activeView.value = 'list'
  selectedLabel.value = null
  // Reset annotation state
  aiPretrainResult.value = null
  aiPretrainError.value = ''
  maskData.value = null
  savedAnnotations.value = []
  activeAnnotationTool.value = 'none'
}

async function handleSync() {
  syncLoading.value = true
  try {
    const res = await imageLabelApi.syncAssessments()
    syncResult.value = { created: res.created, skipped: res.skipped, total: res.total_assessments }
    await fetchStats()
    await fetchList(true)
  } catch (e) {
    console.error('Failed to sync', e)
  } finally {
    syncLoading.value = false
  }
}

// ── AI 一键预标注 ──
async function handleAiPretrain() {
  if (!selectedLabel.value) return
  aiPretrainLoading.value = true
  aiPretrainError.value = ''
  try {
    const result = await imageLabelApi.aiPretrain(selectedLabel.value.id)
    aiPretrainResult.value = result

    if (result.body_site) {
      labelForm.value.body_site = result.body_site
    }
    if (result.is_vitiligo !== undefined) {
      labelForm.value.is_vitiligo = result.is_vitiligo
    }
    if (result.vitiligo_type) {
      labelForm.value.vitiligo_type = result.vitiligo_type
    }
    if (result.vitiligo_stage) {
      labelForm.value.vitiligo_stage = result.vitiligo_stage
    }
    if (result.area_percentage !== undefined) {
      labelForm.value.area_percentage = result.area_percentage
    }
    if (result.vasi_score !== undefined) {
      labelForm.value.vasi_score = result.vasi_score
    }
    if (result.depigmentation_level !== undefined) {
      labelForm.value.depigmentation_level = result.depigmentation_level
    }

    // Auto-activate pixel painting so the user can see & refine AI pre-labeled layers
    if (result.lesion_layer_data_url || result.skin_layer_data_url) {
      activeAnnotationTool.value = 'mask'
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail || ''
    const status = e?.response?.status || 0
    if (status === 400) {
      aiPretrainError.value = detail || '图片无法加载，请检查图片是否已损坏或删除'
    } else if (status === 500) {
      aiPretrainError.value = detail || 'AI 推理服务异常，请稍后重试'
    } else if (status === 0 || !status) {
      aiPretrainError.value = '网络连接失败，请检查服务器是否正常运行'
    } else {
      aiPretrainError.value = detail || 'AI预标注失败，请稍后重试'
    }
  } finally {
    aiPretrainLoading.value = false
  }
}

// ── 像素填涂 (Mask Editor) ──
function toggleMaskEditor() {
  if (selectedLabel.value?.is_user_deleted) return
  activeAnnotationTool.value = activeAnnotationTool.value === 'mask' ? 'none' : 'mask'
}

function handleMaskConfirm(payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string }) {
  maskData.value = payload

  const existingMaskIdx = savedAnnotations.value.findIndex(a => a.mask_data)
  const maskAnnotation: ImageLabelAnnotation = {
    source: 'admin',
    region_index: 0,
    mask_data: payload.lesionMaskDataUrl,
    skin_mask_data: payload.skinMaskDataUrl,
    notes: '管理员像素填涂蒙版',
  }
  if (existingMaskIdx >= 0) {
    savedAnnotations.value[existingMaskIdx] = maskAnnotation
  } else {
    savedAnnotations.value.push(maskAnnotation)
  }
}

function handleMaskCancel() {
  activeAnnotationTool.value = 'none'
}

async function batchSkip() {
  if (!selectedIds.value.length) return
  batchLoading.value = true
  try {
    await imageLabelApi.batchUpdateStatus(selectedIds.value, 'skipped')
    selectedIds.value = []
    await fetchList()
    await fetchStats()
  } catch (e) {
    console.error('Failed to batch skip', e)
  } finally {
    batchLoading.value = false
  }
}

async function batchReject() {
  if (!selectedIds.value.length) return
  batchLoading.value = true
  try {
    await imageLabelApi.batchUpdateStatus(selectedIds.value, 'rejected')
    selectedIds.value = []
    await fetchList()
    await fetchStats()
  } catch (e) {
    console.error('Failed to batch reject', e)
  } finally {
    batchLoading.value = false
  }
}

function toggleSelect(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function toggleAll() {
  if (selectedIds.value.length === items.value.length) {
    selectedIds.value = []
  } else {
    selectedIds.value = items.value.map(i => i.id)
  }
}

function prevPage() {
  if (offset.value >= limit) {
    offset.value -= limit
    fetchList()
  }
}

function nextPage() {
  if (offset.value + limit < total.value) {
    offset.value += limit
    fetchList()
  }
}

watch([filterStatus, filterBodySite, filterVitiligo, filterTraining], () => {
  fetchList(true)
})

onMounted(() => {
  fetchChoices()
  fetchStats()
  fetchList(true)
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <div class="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold text-gray-900 dark:text-white">
            <i class="ri-image-line mr-2"></i>图片打标管理
          </h1>
          <p class="text-sm text-gray-500  mt-1">
            管理员审核标注用户上传的白斑图片，为 VASI 模型训练提供高质量数据
          </p>
        </div>
        <button
          @click="showSyncModal = true"
          class="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <i class="ri-refresh-line mr-1"></i>同步评估数据
        </button>
      </div>

      <!-- Stats Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <div class="bg-white rounded-lg p-3 text-center">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ stats.total }}</div>
          <div class="text-xs text-gray-500 ">全部</div>
        </div>
        <div class="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3 text-center">
          <div class="text-2xl font-bold text-yellow-700 dark:text-yellow-300">{{ stats.pending }}</div>
          <div class="text-xs text-yellow-600 dark:text-yellow-400">待标注</div>
        </div>
        <div class="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-center">
          <div class="text-2xl font-bold text-green-700 dark:text-green-300">{{ stats.labeled }}</div>
          <div class="text-xs text-green-600 dark:text-green-400">已标注</div>
        </div>
        <div class="bg-gray-100 rounded-lg p-3 text-center">
          <div class="text-2xl font-bold text-gray-700">{{ stats.skipped }}</div>
          <div class="text-xs text-gray-500 ">已跳过</div>
        </div>
        <div class="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 text-center">
          <div class="text-2xl font-bold text-red-700 dark:text-red-300">{{ stats.rejected }}</div>
          <div class="text-xs text-red-600 dark:text-red-400">已拒绝</div>
        </div>
        <div class="bg-teal-50 dark:bg-teal-900/20 rounded-lg p-3 text-center">
          <div class="text-2xl font-bold text-teal-700 dark:text-teal-300">{{ stats.training_ready }}</div>
          <div class="text-xs text-teal-600 dark:text-teal-400">训练就绪</div>
        </div>
        <div class="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3 text-center">
          <div class="text-2xl font-bold text-orange-700 dark:text-orange-300">{{ stats.user_deleted }}</div>
          <div class="text-xs text-orange-600 dark:text-orange-400">用户已删</div>
        </div>
      </div>

      <!-- Filters -->
      <div class="bg-white rounded-xl p-4 shadow-sm">
        <div class="flex flex-wrap gap-3 items-center">
          <select v-model="filterStatus" class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:text-white">
            <option value="">全部状态</option>
            <option v-for="s in choices.label_statuses" :key="s" :value="s">{{ statusLabel(s) }}</option>
          </select>
          <select v-model="filterBodySite" class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:text-white">
            <option value="">全部部位</option>
            <option v-for="bs in choices.body_sites" :key="bs" :value="bs">{{ bs }}</option>
          </select>
          <select v-model="filterVitiligo" class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:text-white">
            <option value="">是否白癜风</option>
            <option value="true">是 (白癜风)</option>
            <option value="false">否 (非白癜风)</option>
          </select>
          <select v-model="filterTraining" class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:text-white">
            <option value="">训练标记</option>
            <option value="true">适合训练</option>
            <option value="false">不适合</option>
          </select>
          <span class="text-sm text-gray-500  ml-auto">共 {{ total }} 条</span>
        </div>
      </div>

      <!-- List View -->
      <template v-if="activeView === 'list'">
        <div v-if="selectedIds.length" class="flex items-center gap-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
          <span class="text-sm text-blue-700 dark:text-blue-300">已选 {{ selectedIds.length }} 项</span>
          <button @click="batchSkip" :disabled="batchLoading" class="px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50">
            批量跳过
          </button>
          <button @click="batchReject" :disabled="batchLoading" class="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50">
            批量拒绝
          </button>
          <button @click="selectedIds = []" class="text-sm text-blue-600 dark:text-blue-400 hover:underline">取消选择</button>
        </div>

        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-3 text-left">
                    <input type="checkbox" :checked="selectedIds.length === items.length && items.length > 0" @change="toggleAll" class="rounded" />
                  </th>
                  <th class="px-3 py-3 text-left text-gray-600">图片</th>
                  <th class="px-3 py-3 text-left text-gray-600">部位</th>
                  <th class="px-3 py-3 text-left text-gray-600">AI判定</th>
                  <th class="px-3 py-3 text-left text-gray-600">AI面积</th>
                  <th class="px-3 py-3 text-left text-gray-600">管理员标注</th>
                  <th class="px-3 py-3 text-left text-gray-600">状态</th>
                  <th class="px-3 py-3 text-left text-gray-600">适合训练</th>
                  <th class="px-3 py-3 text-center text-gray-600">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
                <tr v-if="loading">
                  <td colspan="9" class="px-3 py-8 text-center text-gray-400">
                    <i class="ri-loader-4-line ri-lg animate-spin mr-1"></i>加载中...
                  </td>
                </tr>
                <tr v-else-if="!items.length">
                  <td colspan="9" class="px-3 py-8 text-center text-gray-400">暂无打标数据，请点击"同步评估数据"导入</td>
                </tr>
                <tr v-for="item in items" :key="item.id" class="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
                  :class="{ 'bg-orange-50 dark:bg-orange-900/10': item.is_user_deleted }">
                  <td class="px-3 py-2">
                    <input type="checkbox" :value="item.id" :checked="selectedIds.includes(item.id)" @change="toggleSelect(item.id)" class="rounded" />
                  </td>
                  <td class="px-3 py-2">
                    <div class="flex items-center gap-2">
                      <img v-if="!item.is_user_deleted" :src="getImageProxyUrl(item.id)" class="w-12 h-12 object-cover rounded-lg border border-gray-200 dark:border-gray-600" alt="" />
                      <div v-else class="w-12 h-12 bg-gray-200  rounded-lg flex items-center justify-center text-gray-400">
                        <i class="ri-lock-line"></i>
                      </div>
                      <span v-if="item.is_user_deleted" class="text-xs text-orange-500">
                        <i class="ri-shield-keyhole-line"></i> 已脱敏
                      </span>
                    </div>
                  </td>
                  <td class="px-3 py-2 text-gray-900 dark:text-white">{{ item.body_site || '—' }}</td>
                  <td class="px-3 py-2">
                    <span v-if="item.ai_is_vitiligo === true" class="text-teal-600 dark:text-teal-400">白癜风</span>
                    <span v-else-if="item.ai_is_vitiligo === false" class="text-gray-500">非白癜风</span>
                    <span v-else class="text-gray-400">—</span>
                    <div v-if="item.ai_vitiligo_type" class="text-xs text-gray-500 ">{{ item.ai_vitiligo_type }}</div>
                  </td>
                  <td class="px-3 py-2 text-gray-900 dark:text-white">{{ item.ai_area_percentage != null ? item.ai_area_percentage.toFixed(1) + '%' : '—' }}</td>
                  <td class="px-3 py-2">
                    <span v-if="item.admin_is_vitiligo === true" class="text-teal-600 dark:text-teal-400">白癜风</span>
                    <span v-else-if="item.admin_is_vitiligo === false" class="text-gray-500">非白癜风</span>
                    <span v-else class="text-gray-400">未标注</span>
                    <div v-if="item.admin_vitiligo_type" class="text-xs text-gray-500 ">{{ item.admin_vitiligo_type }}</div>
                  </td>
                  <td class="px-3 py-2">
                    <span class="px-2 py-0.5 rounded-full text-xs font-medium" :class="statusBadgeClass(item.label_status)">
                      {{ statusLabel(item.label_status) }}
                    </span>
                  </td>
                  <td class="px-3 py-2">
                    <i v-if="item.training_eligible" class="ri-check-line text-green-500"></i>
                    <i v-else class="ri-close-line text-gray-400"></i>
                  </td>
                  <td class="px-3 py-2 text-center">
                    <button @click="openDetail(item.id)" class="px-3 py-1 text-sm text-teal-600 dark:text-teal-400 hover:underline">
                      标注
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <span class="text-sm text-gray-500 ">
              第 {{ currentPage }} / {{ totalPages }} 页
            </span>
            <div class="flex gap-2">
              <button @click="prevPage" :disabled="offset === 0" class="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed">
                上一页
              </button>
              <button @click="nextPage" :disabled="offset + limit >= total" class="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed">
                下一页
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- Fullscreen Detail View -->
      <template v-if="activeView === 'detail' && selectedLabel">
        <Teleport to="body">
          <div class="fixed inset-0 z-50 bg-gray-900 flex flex-col">
            <!-- Top bar -->
            <div class="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700 shrink-0">
              <div class="flex items-center gap-3">
                <span class="text-sm font-semibold text-white">标注详情 #{{ selectedLabel.id }}</span>
                <span class="px-2 py-0.5 rounded-full text-xs font-medium" :class="statusBadgeClass(selectedLabel.label_status)">
                  {{ statusLabel(selectedLabel.label_status) }}
                </span>
                <span v-if="selectedLabel.is_user_deleted" class="px-2 py-0.5 rounded-full text-xs font-medium bg-orange-500/20 text-orange-300">
                  <i class="ri-shield-keyhole-line mr-0.5"></i>用户已删除(保留脱敏)
                </span>
              </div>

              <div class="flex items-center gap-2">
                <!-- Annotation tool toggles -->
                <button
                  @click="toggleMaskEditor"
                  :disabled="!selectedLabel || selectedLabel.is_user_deleted"
                  class="px-2.5 py-1 text-xs rounded-md transition-colors flex items-center gap-1"
                  :class="showMaskEditor
                    ? 'bg-gray-600 text-teal-300 shadow-sm'
                    : 'text-gray-400 hover:text-gray-200'"
                >
                  <i class="ri-brush-line"></i>像素填涂
                </button>

                <button
                  @click="handleAiPretrain"
                  :disabled="aiPretrainLoading || !selectedLabel || selectedLabel.is_user_deleted"
                  class="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1"
                >
                  <i v-if="aiPretrainLoading" class="ri-loader-4-line animate-spin"></i>
                  <i v-else class="ri-robot-line"></i>AI预标注
                </button>

                <button
                  @click="showFormPanel = !showFormPanel"
                  class="px-3 py-1.5 text-xs rounded-lg transition-colors flex items-center gap-1"
                  :class="showFormPanel ? 'bg-teal-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'"
                >
                  <i class="ri-file-list-line"></i>标注表单
                </button>

                <button
                  @click="closeFullscreen"
                  class="ml-2 w-8 h-8 flex items-center justify-center rounded-full bg-gray-700 hover:bg-red-600 text-gray-300 hover:text-white transition-colors"
                  title="关闭并返回列表"
                >
                  <i class="ri-close-line text-lg"></i>
                </button>
              </div>
            </div>

            <!-- Main content area -->
            <div class="flex-1 flex overflow-hidden relative">
              <!-- Canvas area -->
              <div class="flex-1 relative" :class="{ 'mr-96': showFormPanel }">
                <!-- Loading state -->
                <div v-if="detailLoading" class="absolute inset-0 flex items-center justify-center z-10 bg-gray-900">
                  <div class="text-center text-gray-400">
                    <i class="ri-loader-4-line ri-lg animate-spin block mb-2"></i>
                    <p class="text-sm">加载中...</p>
                  </div>
                </div>

                <!-- AI pretrain error -->
                <div v-if="aiPretrainError" class="absolute top-3 left-3 right-3 z-20 p-2 bg-red-500/20 border border-red-500/30 text-red-300 text-xs rounded-lg flex items-start gap-1">
                  <i class="ri-error-warning-line flex-shrink-0 mt-0.5"></i>
                  <span>{{ aiPretrainError }}</span>
                </div>

                <!-- Mask Editor Mode -->
                <div v-if="showMaskEditor && !selectedLabel.is_user_deleted" class="w-full h-full">
                  <MaskEditor
                    :image-url="getImageProxyUrl(selectedLabel.id)"
                    :editable="true"
                    :full-height="true"
                    :initial-skin-layer-url="aiPretrainResult?.skin_layer_data_url || null"
                    :initial-lesion-layer-url="aiPretrainResult?.lesion_layer_data_url || null"
                    @confirm="handleMaskConfirm"
                    @cancel="handleMaskCancel"
                  />
                </div>

                <!-- Normal Image Preview (no annotation tool active) -->
                <div v-else class="w-full h-full flex items-center justify-center p-8">
                  <div v-if="!selectedLabel.is_user_deleted" class="max-w-full max-h-full flex items-center justify-center">
                    <img
                      :src="getImageProxyUrl(selectedLabel.id)"
                      class="max-w-full max-h-full object-contain rounded-lg"
                      alt="评估图片"
                      style="max-height: calc(100vh - 64px);"
                    />
                  </div>
                  <div v-else class="text-center p-8 text-gray-400">
                    <i class="ri-lock-line text-4xl mb-2 block"></i>
                    <p class="text-sm">该图片已被用户删除，仅保留用于训练</p>
                    <p class="text-xs mt-1">任何情况下不会向用户展示</p>
                  </div>
                </div>

                <!-- AI Pretrain Result Summary -->
                <div v-if="aiPretrainResult && activeAnnotationTool === 'none' && !selectedLabel.is_user_deleted" class="absolute bottom-4 left-4 z-20 p-3 bg-gray-800/90 backdrop-blur rounded-lg text-xs space-y-1.5 max-w-xs">
                  <div class="font-medium text-blue-300 flex items-center gap-1">
                    <i class="ri-robot-line"></i>AI预标注结果
                  </div>
                  <div class="text-gray-300 grid grid-cols-2 gap-x-3 gap-y-0.5">
                    <span>耗时 {{ ((aiPretrainResult.duration_ms || 0) / 1000).toFixed(1) }}s</span>
                    <span v-if="aiPretrainResult.lesion_layer_data_url">已生成像素蒙版</span>
                    <span v-if="aiPretrainResult.body_site">部位: {{ aiPretrainResult.body_site }}</span>
                    <span v-if="aiPretrainResult.confidence != null">置信度: {{ (aiPretrainResult.confidence * 100).toFixed(0) }}%</span>
                    <span v-if="aiPretrainResult.area_percentage != null">面积: {{ aiPretrainResult.area_percentage.toFixed(1) }}%</span>
                    <span v-if="aiPretrainResult.lesion_layer_data_url" class="text-teal-400 col-span-2">
                      <i class="ri-check-double-line mr-0.5"></i>包含蒙版数据，可点击"像素填涂"微调
                    </span>
                  </div>
                </div>

                <!-- Mask data saved indicator -->
                <div v-if="maskData && activeAnnotationTool === 'none'" class="absolute bottom-4 left-4 z-20 text-xs text-green-400 bg-gray-800/90 backdrop-blur rounded-lg px-3 py-1.5 flex items-center gap-1">
                  <i class="ri-check-line"></i>蒙版已编辑，提交标注时一并保存
                </div>

              </div>

              <!-- Side Form Panel -->
              <transition name="slide-panel">
                <div v-if="showFormPanel" class="w-96 bg-gray-800 border-l border-gray-700 overflow-y-auto shrink-0">
                  <div class="p-4 space-y-4">
                    <div class="flex items-center justify-between">
                      <h3 class="text-sm font-medium text-gray-200">标注表单</h3>
                      <button @click="showFormPanel = false" class="text-gray-400 hover:text-gray-200">
                        <i class="ri-close-line"></i>
                      </button>
                    </div>

                    <!-- AI Results -->
                    <div>
                      <h3 class="text-xs font-medium text-gray-400 mb-2 flex items-center gap-1">
                        <i class="ri-robot-line"></i> AI 识别结果
                      </h3>
                      <div class="bg-gray-700/50 rounded-lg p-3 grid grid-cols-2 gap-2 text-xs">
                        <div><span class="text-gray-400">部位:</span> <span class="text-gray-200">{{ selectedLabel.ai_body_site || '—' }}</span></div>
                        <div><span class="text-gray-400">是否白癜风:</span> <span class="text-gray-200">{{ vitiligoLabel(selectedLabel.ai_is_vitiligo) }}</span></div>
                        <div><span class="text-gray-400">分型:</span> <span class="text-gray-200">{{ selectedLabel.ai_vitiligo_type || '—' }}</span></div>
                        <div><span class="text-gray-400">阶段:</span> <span class="text-gray-200">{{ selectedLabel.ai_vitiligo_stage || '—' }}</span></div>
                        <div><span class="text-gray-400">面积占比:</span> <span class="text-gray-200">{{ selectedLabel.ai_area_percentage != null ? selectedLabel.ai_area_percentage.toFixed(1) + '%' : '—' }}</span></div>
                        <div><span class="text-gray-400">VASI评分:</span> <span class="text-gray-200">{{ selectedLabel.ai_vasi_score != null ? selectedLabel.ai_vasi_score.toFixed(2) : '—' }}</span></div>
                        <div><span class="text-gray-400">置信度:</span> <span class="text-gray-200">{{ selectedLabel.ai_confidence != null ? (selectedLabel.ai_confidence * 100).toFixed(0) + '%' : '—' }}</span></div>
                      </div>
                    </div>

                    <!-- User Results -->
                    <div v-if="selectedLabel.user_area_percentage != null || selectedLabel.user_vasi_score != null">
                      <h3 class="text-xs font-medium text-gray-400 mb-2 flex items-center gap-1">
                        <i class="ri-user-line"></i> 用户校准结果
                      </h3>
                      <div class="bg-gray-700/50 rounded-lg p-3 grid grid-cols-2 gap-2 text-xs">
                        <div><span class="text-gray-400">部位:</span> <span class="text-gray-200">{{ selectedLabel.user_body_site || '—' }}</span></div>
                        <div><span class="text-gray-400">面积占比:</span> <span class="text-gray-200">{{ selectedLabel.user_area_percentage != null ? selectedLabel.user_area_percentage.toFixed(1) + '%' : '—' }}</span></div>
                        <div><span class="text-gray-400">VASI评分:</span> <span class="text-gray-200">{{ selectedLabel.user_vasi_score != null ? selectedLabel.user_vasi_score.toFixed(2) : '—' }}</span></div>
                        <div><span class="text-gray-400">脱色程度:</span> <span class="text-gray-200">{{ selectedLabel.user_depigmentation_level != null ? (selectedLabel.user_depigmentation_level * 100).toFixed(0) + '%' : '—' }}</span></div>
                        <div v-if="selectedLabel.user_notes" class="col-span-2"><span class="text-gray-400">备注:</span> <span class="text-gray-200">{{ selectedLabel.user_notes }}</span></div>
                      </div>
                    </div>

                    <!-- Admin Labeling Form -->
                    <div>
                      <h3 class="text-xs font-medium text-gray-400 mb-2 flex items-center gap-1">
                        <i class="ri-shield-check-line"></i> 管理员标注（最终结果）
                      </h3>
                      <div class="space-y-3">
                        <div class="grid grid-cols-2 gap-3">
                          <div>
                            <label class="block text-xs text-gray-400 mb-1">身体部位</label>
                            <select v-model="labelForm.body_site" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200">
                              <option value="">请选择</option>
                              <option v-for="bs in choices.body_sites" :key="bs" :value="bs">{{ bs }}</option>
                            </select>
                          </div>
                          <div>
                            <label class="block text-xs text-gray-400 mb-1">是否白癜风</label>
                            <select v-model="labelForm.is_vitiligo" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200">
                              <option :value="undefined">未判定</option>
                              <option :value="true">是 (白癜风)</option>
                              <option :value="false">否 (非白癜风)</option>
                            </select>
                          </div>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                          <div>
                            <label class="block text-xs text-gray-400 mb-1">白癜风分型</label>
                            <select v-model="labelForm.vitiligo_type" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200">
                              <option value="">请选择</option>
                              <option v-for="vt in choices.vitiligo_types" :key="vt" :value="vt">{{ vt }}</option>
                            </select>
                          </div>
                          <div>
                            <label class="block text-xs text-gray-400 mb-1">病情阶段</label>
                            <select v-model="labelForm.vitiligo_stage" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200">
                              <option value="">请选择</option>
                              <option v-for="st in choices.stages" :key="st" :value="st">{{ st }}</option>
                            </select>
                          </div>
                        </div>
                        <div class="grid grid-cols-3 gap-3">
                          <div>
                            <label class="block text-xs text-gray-400 mb-1">面积占比 (%)</label>
                            <input v-model.number="labelForm.area_percentage" type="number" min="0" max="100" step="0.1" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200" />
                          </div>
                          <div>
                            <label class="block text-xs text-gray-400 mb-1">VASI评分</label>
                            <input v-model.number="labelForm.vasi_score" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200" />
                          </div>
                          <div>
                            <label class="block text-xs text-gray-400 mb-1">脱色程度 (0-1)</label>
                            <input v-model.number="labelForm.depigmentation_level" type="number" min="0" max="1" step="0.1" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200" />
                          </div>
                        </div>
                        <div>
                          <label class="block text-xs text-gray-400 mb-1">管理员备注</label>
                          <textarea v-model="labelForm.notes" rows="2" class="w-full px-3 py-2 border border-gray-600 rounded-lg text-sm bg-gray-700 text-gray-200" placeholder="标注说明、补充信息等"></textarea>
                        </div>
                        <div class="flex items-center gap-2">
                          <input v-model="labelForm.training_eligible" type="checkbox" id="training-eligible-fs" class="rounded" />
                          <label for="training-eligible-fs" class="text-sm text-gray-300">适合作为训练数据</label>
                        </div>
                      </div>
                    </div>

                    <div class="flex gap-3 pt-2">
                      <button @click="submitLabel" :disabled="submitLoading" class="flex-1 px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50">
                        <i v-if="submitLoading" class="ri-loader-4-line animate-spin mr-1"></i>
                        <i v-else class="ri-check-line mr-1"></i>提交标注
                      </button>
                    </div>
                  </div>
                </div>
              </transition>
            </div>
          </div>
        </Teleport>
      </template>

      <!-- Sync Modal -->
      <div v-if="showSyncModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showSyncModal = false">
        <div class="bg-white rounded-xl p-6 max-w-md w-full shadow-xl">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">从 VASI 评估数据同步</h3>
          <p class="text-sm text-gray-600  mb-4">
            将所有已有的 VASI 评估图片导入打标系统。已同步过的记录不会重复创建。
          </p>
          <div v-if="syncResult" class="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 mb-4 text-sm">
            <p class="text-green-700 dark:text-green-300">同步完成！</p>
            <p class="text-green-600 dark:text-green-400">新建 {{ syncResult.created }} 条，跳过 {{ syncResult.skipped }} 条，共 {{ syncResult.total }} 条评估记录</p>
          </div>
          <div class="flex gap-3 justify-end">
            <button @click="showSyncModal = false; syncResult = null" class="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-300 text-gray-700">
              关闭
            </button>
            <button @click="handleSync" :disabled="syncLoading" class="px-4 py-2 text-sm bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors disabled:opacity-50">
              <i v-if="syncLoading" class="ri-loader-4-line animate-spin mr-1"></i>开始同步
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Slide panel transition */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: all 0.25s ease;
}
.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
