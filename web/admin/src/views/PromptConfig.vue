<template>
  <div class="prompt-config-page">
    <n-page-header title="提示词管理">
      <template #subtitle>
        编辑各业务模块的提示词模板，持续迭代白斑识别 / 体检解读 / 报告叙事的准确度。修改后立即生效，无需重启。
      </template>
    </n-page-header>

    <n-grid :cols="isMobile ? 1 : 12" :x-gap="16" :y-gap="16" style="margin-top: 16px" responsive="screen">
      <!-- Left: prompt list -->
      <n-gi :span="isMobile ? 1 : 5">
        <n-card :bordered="false" class="list-card">
          <template #header>
            <n-space align="center" justify="space-between" style="width: 100%">
              <span>提示词列表</span>
              <n-tag size="small" type="info">{{ prompts.length }} 条</n-tag>
            </n-space>
          </template>
          <n-space vertical :size="10">
            <div
              v-for="p in prompts"
              :key="p.module_key + '/' + p.prompt_key"
              class="prompt-item"
              :class="{ active: selectedKey === p.module_key + '/' + p.prompt_key }"
              @click="selectPrompt(p)"
            >
              <div class="prompt-header">
                <span class="prompt-name">{{ p.prompt_name }}</span>
                <n-tag size="tiny" :bordered="false" type="info">v{{ p.version }}</n-tag>
              </div>
              <div class="prompt-meta">
                <span class="module-key">{{ moduleLabel(p.module_key) }}</span>
                <span class="prompt-key">· {{ p.prompt_key }}</span>
              </div>
            </div>
          </n-space>
        </n-card>
      </n-gi>

      <!-- Right: editor -->
      <n-gi :span="isMobile ? 1 : 7">
        <n-card :bordered="false" class="editor-card">
          <template #header>
            <div class="editor-header">
              <span>{{ selected?.prompt_name || '请选择提示词' }}</span>
              <n-space :size="8" align="center" v-if="selected">
                <n-text depth="3" style="font-size: 12px">
                  更新于 {{ formatTime(selected.updated_at) }}
                </n-text>
              </n-space>
            </div>
          </template>

          <n-spin :show="loading">
            <template v-if="selected">
              <n-alert type="info" :show-icon="false" style="margin-bottom: 12px">
                提示词中的占位符（如 <code>{'{period}'}</code> <code>{'{payload}'}</code>）请勿删除，运行时由系统填入数据。
                修改后点击「保存」立即生效，无需重启后端。
              </n-alert>
              <n-input
                v-model:value="editorText"
                type="textarea"
                :autosize="{ minRows: 16, maxRows: 30 }"
                placeholder="输入提示词内容"
              />
              <n-space style="margin-top: 12px">
                <n-button type="primary" :loading="saving" @click="handleSave">
                  <template #icon><i class="ri-save-line" /></template>
                  保存
                </n-button>
                <n-button :loading="resetting" @click="handleReset">
                  <template #icon><i class="ri-arrow-go-back-line" /></template>
                  恢复默认
                </n-button>
              </n-space>
            </template>
            <n-empty v-else description="从左侧选择一个提示词开始编辑" size="small" style="padding: 40px 0;" />
          </n-spin>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import request from '@/api/request'

const message = useMessage()

const isMobile = ref(false)
function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

interface PromptItem {
  id: number
  module_key: string
  prompt_key: string
  prompt_name: string
  prompt_text: string
  has_default: boolean
  version: number
  is_active: boolean
  updated_by?: number
  created_at?: string
  updated_at?: string
}

const prompts = ref<PromptItem[]>([])
const selected = ref<PromptItem | null>(null)
const selectedKey = ref('')
const editorText = ref('')
const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)

const MODULE_LABELS: Record<string, string> = {
  vasi: 'VASI 白斑评估',
  medical_report: '医疗报告解读',
  skin_report: '白斑报告生成',
}

function moduleLabel(key: string) {
  return MODULE_LABELS[key] || key
}

function formatTime(iso?: string) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function selectPrompt(p: PromptItem) {
  selected.value = p
  selectedKey.value = p.module_key + '/' + p.prompt_key
  editorText.value = p.prompt_text
}

async function fetchPrompts() {
  loading.value = true
  try {
    const res = await request.get<PromptItem[]>('/admin/prompts')
    prompts.value = res.data || []
    // 默认选中第一条（VASI 白斑识别）
    if (prompts.value.length && !selected.value) {
      selectPrompt(prompts.value[0])
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取提示词列表失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!selected.value) return
  if (!editorText.value.trim()) {
    message.warning('提示词内容不能为空')
    return
  }
  saving.value = true
  try {
    const res = await request.put<PromptItem>(
      `/admin/prompts/${selected.value.module_key}/${selected.value.prompt_key}`,
      { prompt_text: editorText.value }
    )
    selected.value = res.data
    const idx = prompts.value.findIndex(
      p => p.module_key === res.data.module_key && p.prompt_key === res.data.prompt_key
    )
    if (idx >= 0) prompts.value[idx] = res.data
    message.success(`已保存，版本 v${res.data.version}`)
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  if (!selected.value) return
  resetting.value = true
  try {
    const res = await request.post<PromptItem>(
      `/admin/prompts/${selected.value.module_key}/${selected.value.prompt_key}/reset`
    )
    selected.value = res.data
    editorText.value = res.data.prompt_text
    const idx = prompts.value.findIndex(
      p => p.module_key === res.data.module_key && p.prompt_key === res.data.prompt_key
    )
    if (idx >= 0) prompts.value[idx] = res.data
    message.success('已恢复默认模板')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '恢复失败')
  } finally {
    resetting.value = false
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchPrompts()
})
</script>

<style scoped>
.prompt-config-page { padding: 0; }
.list-card { background-color: #1e293b; }
.editor-card { background-color: #1e293b; }
.prompt-item {
  padding: 14px;
  border-radius: 8px;
  background-color: #0f172a;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}
.prompt-item:hover { border-color: #6366f1; }
.prompt-item.active { border-color: #6366f1; background-color: rgba(99, 102, 241, 0.1); }
.prompt-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.prompt-name { font-weight: 600; font-size: 14px; color: #e2e8f0; }
.prompt-meta { font-size: 12px; color: #64748b; }
.module-key { color: #818cf8; }
.prompt-key { color: #64748b; }
.editor-header { display: flex; justify-content: space-between; align-items: center; width: 100%; font-weight: 600; font-size: 16px; }
.editor-header :deep(code) { background: rgba(99, 102, 241, 0.12); padding: 1px 4px; border-radius: 4px; color: #a5b4fc; }
</style>
