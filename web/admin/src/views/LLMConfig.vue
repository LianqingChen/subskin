<template>
  <div class="llm-config-page">
    <n-page-header title="LLM 模块配置管理">
      <template #extra>
        <n-button size="small" :loading="refreshingEnv" @click="refreshFromEnv">
          <template #icon><i class="ri-refresh-line" /></template>
          刷新实际配置
        </n-button>
      </template>
    </n-page-header>
    <p class="page-desc">管理各业务模块的大模型供应商、模型和 API Key</p>

    <!-- Preset Tab Bar -->
    <div class="preset-tab-bar">
      <div
        v-for="preset in presetTabs"
        :key="preset.key"
        class="preset-tab"
        :class="{ active: activePreset === preset.key }"
        @click="switchPreset(preset.key)"
      >
        <i :class="preset.icon" class="preset-tab-icon" />
        <div class="preset-tab-text">
          <span class="preset-tab-name">{{ preset.name }}</span>
          <span class="preset-tab-desc">{{ preset.description }}</span>
        </div>
        <n-tag v-if="activePreset === preset.key" type="info" size="tiny" :bordered="false">当前</n-tag>
      </div>
    </div>

    <!-- Initial mode bar -->
    <div v-if="isInitialMode" class="apply-bar">
      <n-alert type="info" :show-icon="false">
        <template #header>
          <n-space align="center" justify="space-between">
            <span>
              初始配置 — 系统原始备份，不会随实际配置变化而改变
              <template v-if="backupTime">（备份时间：{{ backupTime }}）</template>
            </span>
            <n-space>
              <n-button size="small" @click="createBackup" :loading="creatingBackup">
                <template #icon><i class="ri-camera-line" /></template>
                重新备份
              </n-button>
              <n-button size="small" type="warning" @click="restoreBackup" :loading="restoringBackup">
                <template #icon><i class="ri-arrow-go-back-line" /></template>
                一键恢复到此配置
              </n-button>
            </n-space>
          </n-space>
        </template>
      </n-alert>
    </div>

    <!-- Preset preview bar -->
    <div v-if="isPresetMode" class="apply-bar">
      <n-alert type="warning" :show-icon="false">
        <template #header>
          <n-space align="center" justify="space-between">
            <span>正在预览「{{ activePresetName }}」— 以下为预览配置，尚未应用到生产环境</span>
            <n-space>
              <n-button size="small" @click="testAllPresetModules" :loading="testingAllModules">
                <template #icon><i class="ri-link" /></template>
                全部测试
              </n-button>
              <n-button size="small" type="primary" @click="applyCurrentPreset" :loading="applyingPreset">
                <template #icon><i class="ri-check-double-line" /></template>
                应用此预设
              </n-button>
            </n-space>
          </n-space>
        </template>
      </n-alert>
    </div>

    <!-- Preset info banner -->
    <div v-if="activePreset !== 'actual'" class="preset-info-banner">
      <n-text depth="3">
        共 {{ presetModuleCount }} 个模块，其中 {{ presetChangeCount }} 个配置将发生变化。
        点击左侧模块查看每个模块的配置对比。
      </n-text>
    </div>

    <n-grid :cols="isMobile ? 1 : 12" :x-gap="16" :y-gap="16" style="margin-top: 16px" responsive="screen">
      <!-- Left: Module list -->
      <n-gi :span="isMobile ? 1 : 5">
        <n-card :bordered="false" class="module-list-card">
          <template #header>
            <n-space align="center" justify="space-between" style="width: 100%">
              <span>模块列表</span>
              <n-tag size="small" type="info">{{ displayModules.length }} 个模块</n-tag>
            </n-space>
          </template>
          <n-space vertical :size="10">
            <div
              v-for="mod in displayModules"
              :key="mod.module_key"
              class="module-item"
              :class="{ active: selectedModuleKey === mod.module_key, changed: isPresetMode && mod._changed }"
              @click="selectModule(mod.module_key)"
            >
              <div class="module-header">
                <span class="module-name">{{ mod.module_name }}</span>
                <n-space :size="4" align="center">
                  <n-tag v-if="isPresetMode && mod._changed" type="warning" size="tiny" :bordered="false">变更</n-tag>
                  <n-tag :type="mod.is_active ? 'success' : 'default'" size="tiny" :bordered="false">
                    {{ mod.is_active ? '启用' : '禁用' }}
                  </n-tag>
                </n-space>
              </div>
              <div class="module-desc" v-if="mod.module_description">{{ mod.module_description }}</div>
              <div class="module-meta">
                <n-tag size="tiny" :bordered="false">
                  <template #icon><i :class="getProviderIcon(mod._provider || mod.provider)" /></template>
                  {{ getProviderLabel(mod._provider || mod.provider) }}
                </n-tag>
                <span class="model-text" v-if="mod._chat_model || mod.chat_model">{{ mod._chat_model || mod.chat_model }}</span>
                <n-tag v-if="showEmbedding(mod)" size="tiny" type="info" :bordered="false" class="embed-tag">
                  <template #icon><i class="ri-database-2-line" /></template>
                  {{ mod._embedding_model || mod.embedding_model }}
                </n-tag>
              </div>
              <!-- Diff indicator -->
              <div v-if="isPresetMode && mod._changed" class="module-diff">
                <n-text depth="3" style="font-size: 11px;">
                  {{ getDiffSummary(mod) }}
                </n-text>
              </div>
              <!-- Per-module preset quick apply -->
              <div v-if="activePreset === 'actual'" class="module-preset-row" @click.stop>
                <n-dropdown
                  :options="perModulePresetOptions"
                  :render-label="renderPresetLabel"
                  @select="(key: string) => applyPresetToModule(mod.module_key, key)"
                  placement="bottom-end"
                >
                  <n-button size="tiny" quaternary class="preset-apply-btn">
                    <template #icon><i class="ri-magic-line" /></template>
                    快捷预设
                  </n-button>
                </n-dropdown>
              </div>
            </div>
          </n-space>
        </n-card>
      </n-gi>

      <!-- Right: Config detail panel -->
      <n-gi :span="isMobile ? 1 : 7">
        <n-card :bordered="false" class="config-panel-card">
          <template #header>
            <div class="config-header">
              <span>
                {{ selectedModule?.module_name || '请选择模块' }}
                <span v-if="selectedModule" class="module-key-label">({{ selectedModule.module_key }})</span>
              </span>
              <n-space :size="8" align="center" v-if="selectedModule">
                <n-switch v-model:value="form.is_active" size="small">
                  <template #checked>启用</template>
                  <template #unchecked>禁用</template>
                </n-switch>
              </n-space>
            </div>
          </template>

          <n-spin :show="loading">
            <template v-if="selectedModule">
              <!-- Preset quick apply bar -->
              <div class="preset-quick-bar">
                <span class="preset-quick-label">快捷预设</span>
                <n-space :size="6">
                  <n-button
                    v-for="p in perModulePresetOptions"
                    :key="p.key"
                    size="small"
                    :type="activeQuickPreset === p.key ? 'primary' : 'default'"
                    ghost
                    @click="quickApplyPreset(p.key)"
                    :loading="quickApplying === p.key"
                  >
                    <template #icon><i :class="p.icon" /></template>
                    {{ p.label }}
                  </n-button>
                </n-space>
              </div>

              <!-- Edit form (always available when module is selected) -->
              <n-form label-placement="top" :model="form" size="medium" style="margin-top: 12px">
                <n-form-item label="供应商" path="provider">
                  <n-select v-model:value="form.provider" :options="providerOptions" placeholder="选择大模型供应商" @update:value="onProviderChange" />
                </n-form-item>
                <n-form-item label="Chat 模型">
                  <n-select v-model:value="form.chat_model" :options="chatModelOptions" placeholder="选择 Chat 模型" clearable filterable />
                </n-form-item>
                <n-form-item label="Vision 模型">
                  <n-select v-model:value="form.vision_model" :options="visionModelOptions" placeholder="选择 Vision 模型" clearable filterable />
                </n-form-item>
                <n-form-item v-if="showEmbeddingForModule" label="Embedding 模型">
                  <n-select v-model:value="form.embedding_model" :options="embeddingModelOptions" placeholder="仅 RAG 需要" clearable filterable />
                </n-form-item>
                <n-form-item label="Base URL">
                  <n-input v-model:value="form.base_url" placeholder="API 端点地址" />
                </n-form-item>
                <n-form-item label="API Key">
                  <n-input v-model:value="form.api_key" type="password" placeholder="输入 API Key" show-password-on="click" />
                </n-form-item>
                <n-space style="margin-top: 8px">
                  <n-button type="primary" :loading="saving" @click="handleSave">
                    <template #icon><i class="ri-save-line" /></template>
                    保存配置
                  </n-button>
                  <n-button :loading="testing" @click="handleTest">
                    <template #icon><i class="ri-link" /></template>
                    测试连接
                  </n-button>
                </n-space>
              </n-form>
            </template>

            <n-empty v-else description="从左侧选择一个模块开始配置" size="small" style="padding: 40px 0;" />
          </n-spin>

          <n-alert
            v-if="testResult"
            :type="testResult.ok ? 'success' : 'error'"
            :title="testResult.ok ? '连接测试成功' : '连接测试失败'"
            closable style="margin-top: 16px" @close="testResult = null"
          >
            <template v-if="testResult.ok">
              <p>供应商: {{ getProviderLabel(testResult.provider || '') }}</p>
              <p>模型: {{ testResult.model }}</p>
              <p>响应: {{ testResult.response }}</p>
            </template>
            <template v-else><p>{{ testResult.error }}</p></template>
          </n-alert>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { useMessage } from 'naive-ui'
import request from '@/api/request'

const message = useMessage()

const isMobile = ref(false)
function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

interface ModuleItem {
  id: number
  module_key: string
  module_name: string
  module_description?: string
  provider: string
  chat_model?: string
  vision_model?: string
  embedding_model?: string
  base_url?: string
  is_active: boolean
  created_at?: string
  updated_at?: string
  _provider?: string
  _chat_model?: string
  _vision_model?: string
  _embedding_model?: string
  _changed?: boolean
  _changed_fields?: string[]
}

interface ModuleDetail extends ModuleItem {
  api_key?: string
}

interface ProviderInfo {
  key: string
  name: string
  models: Record<string, string[]>
  base_url: string
}

interface TestResult {
  ok: boolean
  model?: string
  provider?: string
  response?: string
  error?: string
}

interface CompareItem {
  module_key: string
  module_name: string
  current_provider: string
  current_chat_model?: string
  current_vision_model?: string
  current_embedding_model?: string
  new_provider: string
  new_chat_model?: string
  new_vision_model?: string
  new_embedding_model?: string
  changed: boolean
  changed_fields: string[]
}

interface CompareResponse {
  preset_key: string
  preset_name: string
  preset_description: string
  items: CompareItem[]
  change_count: number
}

const modules = ref<ModuleItem[]>([])
const providers = ref<ProviderInfo[]>([])
const activePreset = ref<string>('actual')
const selectedModuleKey = ref<string>('')
const selectedModule = ref<ModuleItem | null>(null)
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const applyingPreset = ref(false)
const refreshingEnv = ref(false)
const creatingBackup = ref(false)
const restoringBackup = ref(false)
const backupTime = ref<string | null>(null)
const backupModules = ref<ModuleItem[]>([])
const quickApplying = ref<string | null>(null)
const activeQuickPreset = ref<string | null>(null)

async function refreshFromEnv() {
  refreshingEnv.value = true
  try {
    const res = await request.post('/admin/llm/refresh')
    message.success(`已刷新：更新了 ${res.data.updated_count} 个模块的配置`)
    await fetchModules()
    if (selectedModuleKey.value) {
      await fetchModuleDetail(selectedModuleKey.value)
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '刷新失败')
  } finally {
    refreshingEnv.value = false
  }
}
const testingAllModules = ref(false)
const testResult = ref<TestResult | null>(null)
const presetCompareData = ref<CompareResponse | null>(null)

const presetTabs = [
  { key: 'initial', name: '初始配置', description: '原始备份，永不修改', icon: 'ri-save-line' },
  { key: 'actual', name: '实际配置', description: '当前线上生产环境', icon: 'ri-check-double-line' },
  { key: 'recommended', name: '推荐配置', description: '按模块需求匹配最佳模型', icon: 'ri-star-line' },
  { key: 'economy', name: '经济配置', description: '最省钱的方案', icon: 'ri-money-cny-circle-line' },
  { key: 'performance', name: '强劲配置', description: '性能最强方案', icon: 'ri-rocket-line' },
]

const providerIcons: Record<string, string> = {
  dashscope: 'ri-cloud-line', bailian_codingplan: 'ri-cloud-line',
  volcengine: 'ri-fire-line', volc_codingplan: 'ri-fire-line',
  deepseek: 'ri-brain-line', moonshot: 'ri-moon-line',
  minimax: 'ri-sparkling-line', zhipuai: 'ri-cpu-line',
  openai: 'ri-openai-line', anthropic: 'ri-robot-line',
}

const isPresetMode = computed(() => activePreset.value !== 'actual' && activePreset.value !== 'initial')
const isInitialMode = computed(() => activePreset.value === 'initial')
const activePresetName = computed(() => presetTabs.find(t => t.key === activePreset.value)?.name || '')
const presetModuleCount = computed(() => presetCompareData.value?.items.length || 0)
const presetChangeCount = computed(() => presetCompareData.value?.change_count || 0)

const displayModules = computed(() => {
  if (isInitialMode.value) return backupModules.value
  if (activePreset.value === 'actual') return modules.value
  if (!presetCompareData.value) return modules.value
  return modules.value.map(mod => {
    const cmp = presetCompareData.value!.items.find(i => i.module_key === mod.module_key)
    if (!cmp || !cmp.changed) return { ...mod, _changed: false }
    return {
      ...mod,
      _provider: cmp.new_provider,
      _chat_model: cmp.new_chat_model,
      _vision_model: cmp.new_vision_model,
      _embedding_model: cmp.new_embedding_model,
      _changed: true,
      _changed_fields: cmp.changed_fields,
    }
  })
})

const form = ref({
  module_name: '', module_description: '', provider: '',
  chat_model: '', vision_model: '', embedding_model: '',
  api_key: '', base_url: '', is_active: true,
})

const providerOptions = computed(() => providers.value.map(p => ({ label: p.name, value: p.key })))
const currentProvider = computed(() => providers.value.find(p => p.key === form.value.provider))
const chatModelOptions = computed(() => (currentProvider.value?.models?.chat || []).map(m => ({ label: m, value: m })))
const visionModelOptions = computed(() => (currentProvider.value?.models?.vision || []).map(m => ({ label: m, value: m })))
const embeddingModelOptions = computed(() => (currentProvider.value?.models?.embedding || []).map(m => ({ label: m, value: m })))

function getProviderLabel(key?: string) { return providers.value.find(p => p.key === key)?.name || key || '未配置' }
function getProviderIcon(key?: string) { return providerIcons[key || ''] || 'ri-server-line' }
function showEmbedding(mod: ModuleItem) { return mod.module_key === 'rag' }
const showEmbeddingForModule = computed(() => selectedModule.value?.module_key === 'rag')
function getDiffSummary(mod: ModuleItem) {
  const parts: string[] = []
  if (mod._provider !== mod.provider) parts.push(`供应商→${getProviderLabel(mod._provider)}`)
  if (mod._chat_model !== mod.chat_model) parts.push(`Chat→${mod._chat_model}`)
  return parts.join('，') || '配置变更'
}

async function fetchModules() {
  try {
    const res = await request.get<ModuleItem[]>('/admin/llm/modules')
    modules.value = res.data || []
  } catch (err: any) { message.error(err?.response?.data?.detail || '获取模块列表失败') }
}

async function fetchProviders() {
  try {
    const res = await request.get<{ providers: ProviderInfo[] }>('/admin/llm/providers')
    providers.value = res.data?.providers || []
  } catch (err: any) { message.error(err?.response?.data?.detail || '获取供应商列表失败') }
}

async function fetchModuleDetail(moduleKey: string) {
  loading.value = true
  try {
    const res = await request.get<ModuleDetail>(`/admin/llm/modules/${moduleKey}`)
    selectedModule.value = res.data
    form.value = {
      module_name: res.data.module_name || '', module_description: res.data.module_description || '',
      provider: res.data.provider || '', chat_model: res.data.chat_model || '',
      vision_model: res.data.vision_model || '', embedding_model: res.data.embedding_model || '',
      api_key: res.data.api_key || '', base_url: res.data.base_url || '', is_active: res.data.is_active,
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取模块配置失败')
    selectedModule.value = null
  } finally { loading.value = false }
}

function selectModule(moduleKey: string) {
  selectedModuleKey.value = moduleKey
  testResult.value = null
  activeQuickPreset.value = null
  fetchModuleDetail(moduleKey)
}

async function switchPreset(key: string) {
  activePreset.value = key
  selectedModuleKey.value = ''
  selectedModule.value = null
  testResult.value = null
  presetCompareData.value = null
  activeQuickPreset.value = null

  if (key === 'initial') {
    await loadBackup()
  } else if (key !== 'actual') {
    try {
      const res = await request.get<CompareResponse>(`/admin/llm/presets/${key}/preview`)
      presetCompareData.value = res.data
    } catch (err: any) { message.error('获取预设配置失败') }
  }
}

async function loadBackup() {
  try {
    const res = await request.get('/admin/llm/backup')
    if (res.data.status === 'ok' && res.data.modules.length > 0) {
      backupModules.value = res.data.modules
      backupTime.value = res.data.backup_time ? new Date(res.data.backup_time).toLocaleString('zh-CN') : null
    } else {
      // Auto-create backup on first visit
      await createBackup()
    }
  } catch { message.error('加载备份失败') }
}

async function createBackup() {
  creatingBackup.value = true
  try {
    const res = await request.post('/admin/llm/backup')
    backupModules.value = res.data.modules || []
    backupTime.value = res.data.backup_time ? new Date(res.data.backup_time).toLocaleString('zh-CN') : ''
    message.success('初始配置已备份')
  } catch (err: any) { message.error(err?.response?.data?.detail || '备份失败') }
  finally { creatingBackup.value = false }
}

async function restoreBackup() {
  restoringBackup.value = true
  try {
    const res = await request.post('/admin/llm/backup/restore')
    message.success(`已恢复初始配置，更新了 ${res.data.updated_count} 个模块`)
    activePreset.value = 'actual'
    await fetchModules()
  } catch (err: any) { message.error(err?.response?.data?.detail || '恢复失败') }
  finally { restoringBackup.value = false }
}

async function handleSave() {
  if (!selectedModule.value) return
  saving.value = true
  try {
    const payload: Record<string, any> = {}
    for (const k of ['module_name', 'module_description', 'provider', 'chat_model', 'vision_model', 'embedding_model', 'api_key', 'base_url', 'is_active']) {
      const val = (form.value as any)[k]
      if (val !== undefined && val !== null) payload[k] = val
    }
    const res = await request.put<ModuleDetail>(`/admin/llm/modules/${selectedModule.value.module_key}`, payload)
    const idx = modules.value.findIndex(m => m.module_key === selectedModule.value!.module_key)
    if (idx >= 0) modules.value[idx] = { ...modules.value[idx], provider: res.data.provider, chat_model: res.data.chat_model, embedding_model: res.data.embedding_model, is_active: res.data.is_active }
    selectedModule.value = res.data
    message.success('配置保存成功')
  } catch (err: any) { message.error(err?.response?.data?.detail || '保存配置失败') } finally { saving.value = false }
}

async function handleTest() {
  if (!selectedModule.value) return
  testing.value = true; testResult.value = null
  try {
    const p: Record<string, any> = {}
    if (form.value.provider) p.provider = form.value.provider
    if (form.value.chat_model) p.chat_model = form.value.chat_model
    if (form.value.api_key) p.api_key = form.value.api_key
    if (form.value.base_url) p.base_url = form.value.base_url
    const res = await request.post<TestResult>(`/admin/llm/modules/${selectedModule.value.module_key}/test`, p)
    testResult.value = res.data
  } catch (err: any) { testResult.value = { ok: false, error: err?.response?.data?.detail || '测试失败' } } finally { testing.value = false }
}

async function testAllPresetModules() {
  testingAllModules.value = true
  const items = presetCompareData.value?.items || []
  let ok = 0; let fail = 0
  for (const item of items) {
    try {
      const res = await request.post(`/admin/llm/presets/${activePreset.value}/test-module`, { module_key: item.module_key })
      if (res.data.ok) ok++; else fail++
    } catch { fail++ }
  }
  message.info(`测试完成: ${ok} 通过, ${fail} 失败`)
  testingAllModules.value = false
}

async function applyCurrentPreset() {
  applyingPreset.value = true
  try {
    const resp = await request.post('/admin/llm/presets/apply', { preset: activePreset.value })
    message.success(`已应用预设，更新了 ${resp.data.updated_count} 个模块`)
    activePreset.value = 'actual'
    await fetchModules()
  } catch (err: any) { message.error(err?.response?.data?.detail || '应用失败') } finally { applyingPreset.value = false }
}

function onProviderChange(val: string) {
  const p = providers.value.find(i => i.key === val)
  if (p) {
    form.value.base_url = p.base_url
    if (p.models?.chat?.length && !p.models.chat.includes(form.value.chat_model)) form.value.chat_model = p.models.chat[0]
    if (p.models?.vision?.length && !p.models.vision.includes(form.value.vision_model)) form.value.vision_model = p.models.vision[0]
    if (p.models?.embedding?.length && !p.models.embedding.includes(form.value.embedding_model)) form.value.embedding_model = p.models.embedding[0]
  }
}

const perModulePresetOptions = [
  { key: 'recommended', label: '推荐配置', icon: 'ri-star-line' },
  { key: 'economy', label: '经济配置', icon: 'ri-money-cny-circle-line' },
  { key: 'performance', label: '强劲配置', icon: 'ri-rocket-line' },
]

function renderPresetLabel(option: any) {
  return h('div', { style: 'display: flex; align-items: center; gap: 6px;' }, [
    h('i', { class: option.icon, style: 'font-size: 14px; color: #818cf8;' }),
    h('span', null, option.label),
  ])
}

async function quickApplyPreset(presetKey: string) {
  if (!selectedModuleKey.value) return
  quickApplying.value = presetKey
  activeQuickPreset.value = presetKey
  try {
    await request.post(`/admin/llm/presets/${presetKey}/apply-module`, { module_key: selectedModuleKey.value })
    message.success(`已将「${perModulePresetOptions.find(p => p.key === presetKey)?.label}」应用到当前模块`)
    await fetchModuleDetail(selectedModuleKey.value)
    await fetchModules()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '应用预设失败')
  } finally {
    quickApplying.value = null
  }
}

async function applyPresetToModule(moduleKey: string, presetKey: string) {
  try {
    await request.post(`/admin/llm/presets/${presetKey}/apply-module`, { module_key: moduleKey })
    message.success(`已将「${perModulePresetOptions.find(p => p.key === presetKey)?.label}」应用到模块 ${moduleKey}`)
    await fetchModules()
    if (selectedModuleKey.value === moduleKey) {
      await fetchModuleDetail(moduleKey)
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '应用预设失败')
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchModules(); fetchProviders()
})
</script>

<style scoped>
.llm-config-page { padding: 0; }
.page-desc { color: #94a3b8; margin-top: 8px; font-size: 14px; }

.preset-tab-bar { display: flex; gap: 10px; margin-top: 20px; }
.preset-tab { flex: 1; display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-radius: 10px; background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(148, 163, 184, 0.08); cursor: pointer; transition: all 0.2s; position: relative; min-width: 0; }
.preset-tab:hover { border-color: #6366f1; background: rgba(99, 102, 241, 0.06); }
.preset-tab.active { border-color: #6366f1; background: rgba(99, 102, 241, 0.12); box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.3); }
.preset-tab-icon { font-size: 18px; color: #818cf8; flex-shrink: 0; }
.preset-tab-text { flex: 1; min-width: 0; }
.preset-tab-name { font-size: 14px; font-weight: 600; color: #e2e8f0; display: block; }
.preset-tab-desc { font-size: 11px; color: #94a3b8; display: block; margin-top: 1px; }

.apply-bar { margin-top: 12px; }
.preset-info-banner { margin-top: 6px; }

.module-list-card { background-color: #1e293b; }
.module-item { padding: 14px; border-radius: 8px; background-color: #0f172a; border: 1px solid transparent; cursor: pointer; transition: all 0.2s; }
.module-item:hover { border-color: #6366f1; }
.module-item.active { border-color: #6366f1; background-color: rgba(99, 102, 241, 0.1); }
.module-item.changed { border-left: 3px solid #f59e0b; }
.module-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.module-name { font-weight: 600; font-size: 14px; color: #e2e8f0; }
.module-desc { font-size: 12px; color: #64748b; margin-bottom: 8px; line-height: 1.4; }
.module-meta { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #94a3b8; }
.model-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px; font-size: 12px; color: #64748b; }
.embed-tag { margin-left: auto; flex-shrink: 0; }
.module-diff { margin-top: 6px; }
.module-preset-row { margin-top: 8px; display: flex; justify-content: flex-end; }
.preset-apply-btn { font-size: 11px; color: #818cf8; }

.preset-quick-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.08);
}
.preset-quick-label {
  font-size: 12px;
  color: #94a3b8;
  flex-shrink: 0;
  white-space: nowrap;
}

.config-panel-card { background-color: #1e293b; }
.config-header { display: flex; justify-content: space-between; align-items: center; width: 100%; font-weight: 600; font-size: 16px; }
.module-key-label { font-size: 13px; color: #94a3b8; font-weight: normal; margin-left: 4px; }

.diff-banner { margin-bottom: 16px; }
.diff-descriptions { background: rgba(15, 23, 42, 0.5); border-radius: 6px; padding: 8px; }
.diff-old { color: #ef4444; text-decoration: line-through; }
.diff-new { color: #10b981; font-weight: 600; }
.diff-arrow { color: #94a3b8; margin: 0 8px; }

.preset-detail-view { padding: 8px 0; }

@media (max-width: 768px) {
  .preset-tab-bar {
    overflow-x: auto;
    flex-wrap: nowrap;
    gap: 6px;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .preset-tab-bar::-webkit-scrollbar { display: none; }
  .preset-tab {
    flex: 0 0 auto;
    min-width: 140px;
    padding: 8px 10px;
    gap: 6px;
  }
  .preset-tab-name { font-size: 12px; }
  .preset-tab-desc { display: none; }
  .preset-tab-icon { font-size: 16px; }
  .module-item { padding: 10px; }
  .module-list-card { max-height: 320px; overflow-y: auto; }
  .config-header { flex-wrap: wrap; gap: 8px; }
  .preset-quick-bar {
    flex-wrap: wrap;
    gap: 6px;
  }
  .preset-quick-bar .n-button { font-size: 12px; }
}
</style>
