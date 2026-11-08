<script setup lang="ts">
/**
 * 知识审核（/knowledge-review）。同行·知识/前沿的内容只有走完
 * 草稿 → 编辑审核 → 医学审核 → 发布 才对用户可见；退回草稿会作废已有审核。
 * 内容修改走 web/shared/knowledge/seed.json（git 审阅）+「导入种子」，只刷新仍为草稿的条目。
 */
import { computed, onMounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {
  NButton, NCard, NEmpty, NInput, NModal, NRadioButton, NRadioGroup, NSpace, NSpin, NTag, useMessage,
} from 'naive-ui'
import request from '@/api/request'

type Kind = 'cards' | 'pipeline' | 'digests' | 'relations'
type Status = 'draft' | 'editor_reviewed' | 'medical_reviewed' | 'published' | 'retired'
interface Source { type?: string; ref?: string; title?: string; url?: string; label?: string; quote?: string; year?: number }
interface Item {
  id: number
  status: Status
  title?: string
  title_en?: string
  slug?: string
  summary?: string
  body_md?: string
  one_liner?: string
  why_it_matters?: string
  limitations?: string
  latest_event?: string
  phase?: string
  evidence_level?: string
  sources?: Source[]
  regions?: { region: string; status: string; date?: string | null }[]
  reviewer_notes?: string | null
  medical_reviewer_label?: string | null
  medical_reviewed_at?: string | null
  published_at?: string | null
  seed_version?: string | null
  url?: string | null
}

const KINDS: { key: Kind; label: string }[] = [
  { key: 'cards', label: '知识卡' },
  { key: 'pipeline', label: '研发管线' },
  { key: 'digests', label: '论文速递' },
  { key: 'relations', label: '图谱关系' },
]
const STATUS_LABEL: Record<Status, string> = {
  draft: '草稿', editor_reviewed: '编辑已审', medical_reviewed: '医学已审', published: '已发布', retired: '已下线',
}
const STATUS_TYPE: Record<Status, 'default' | 'info' | 'warning' | 'success' | 'error'> = {
  draft: 'default', editor_reviewed: 'info', medical_reviewed: 'warning', published: 'success', retired: 'error',
}
const NEXT: Record<Status, { to: Status; label: string } | null> = {
  draft: { to: 'editor_reviewed', label: '编辑审核通过' },
  editor_reviewed: { to: 'medical_reviewed', label: '医学审核通过' },
  medical_reviewed: { to: 'published', label: '发布' },
  published: { to: 'retired', label: '下线' },
  retired: null,
}

const md = new MarkdownIt({ html: false, linkify: true })
const message = useMessage()
const kind = ref<Kind>('cards')
const status = ref<Status | ''>('')
const items = ref<Item[]>([])
const counts = ref<Record<string, number>>({})
const loading = ref(false)
const expanded = ref<number | null>(null)
const dialog = ref<{ item: Item; to: Status } | null>(null)
const note = ref('')
const reviewer = ref('')
const busy = ref(false)

const needsNote = computed(() => dialog.value?.to === 'draft')
const needsReviewer = computed(() => dialog.value?.to === 'medical_reviewed')

function html(text?: string) {
  return DOMPurify.sanitize(md.render(text || ''))
}
function errorText(e: unknown, fallback: string) {
  const detail = (e as { response?: { data?: { detail?: { message?: string } | string } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : detail?.message || fallback
}

async function load() {
  loading.value = true
  try {
    const { data } = await request.get(`/admin/knowledge/${kind.value}`, { params: { status: status.value || undefined } })
    items.value = data.items
    counts.value = data.counts
  } catch (e) {
    message.error(errorText(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

async function importSeed() {
  busy.value = true
  try {
    const { data } = await request.post('/admin/knowledge/seed/import')
    message.success(`已导入种子 ${data.version ?? ''}`)
    await load()
  } catch (e) {
    message.error(errorText(e, '导入失败'))
  } finally {
    busy.value = false
  }
}

function ask(item: Item, to: Status) {
  dialog.value = { item, to }
  note.value = ''
  reviewer.value = item.medical_reviewer_label || ''
}

async function confirm() {
  if (!dialog.value) return
  if (needsNote.value && !note.value.trim()) return message.warning('请写明退回原因')
  if (needsReviewer.value && !reviewer.value.trim()) return message.warning('请填写医学审核人（姓名与资质）')
  busy.value = true
  try {
    await request.post(`/admin/knowledge/${kind.value}/${dialog.value.item.id}/transition`, {
      to: dialog.value.to, note: note.value, reviewer_label: reviewer.value,
    })
    message.success('已更新')
    dialog.value = null
    await load()
  } catch (e) {
    message.error(errorText(e, '操作失败'))
  } finally {
    busy.value = false
  }
}

watch([kind, status], load)
onMounted(load)
</script>

<template>
  <div class="knowledge-review">
    <NCard title="知识审核" size="small">
      <template #header-extra>
        <NButton size="small" :loading="busy" @click="importSeed">导入种子</NButton>
      </template>
      <p class="hint">
        只有「已发布」内容对用户可见。发布前必须完成医学审核并记录审核人；退回草稿会作废已有审核。
        主站管理员账号可在同行页预览草稿。内容修改请改 <code>web/shared/knowledge/seed.json</code> 后导入（只刷新草稿）。
      </p>
      <NSpace vertical :size="12">
        <NRadioGroup v-model:value="kind" size="small">
          <NRadioButton v-for="k in KINDS" :key="k.key" :value="k.key">{{ k.label }}</NRadioButton>
        </NRadioGroup>
        <NRadioGroup v-model:value="status" size="small">
          <NRadioButton value="">全部</NRadioButton>
          <NRadioButton v-for="(label, key) in STATUS_LABEL" :key="key" :value="key">
            {{ label }} {{ counts[key] ?? 0 }}
          </NRadioButton>
        </NRadioGroup>
      </NSpace>
    </NCard>

    <NSpin :show="loading">
      <NEmpty v-if="!loading && !items.length" class="empty" description="没有内容，可先导入种子" />
      <NCard v-for="item in items" :key="item.id" size="small" class="item">
        <div class="row">
          <NTag :type="STATUS_TYPE[item.status]" size="small">{{ STATUS_LABEL[item.status] }}</NTag>
          <NTag v-if="item.evidence_level" size="small">证据 {{ item.evidence_level }}</NTag>
          <strong class="title">{{ item.title }}</strong>
          <span v-if="item.phase" class="muted">{{ item.phase }}</span>
        </div>
        <p v-if="item.summary || item.one_liner || item.latest_event" class="muted">
          {{ item.summary || item.one_liner || item.latest_event }}
        </p>
        <p v-if="item.reviewer_notes" class="notes"><i class="ri-error-warning-line" /> 审核提示：{{ item.reviewer_notes }}</p>
        <p v-if="item.medical_reviewer_label" class="muted">医学审核：{{ item.medical_reviewer_label }} · {{ item.medical_reviewed_at?.slice(0, 10) }}</p>

        <div v-if="expanded === item.id" class="detail">
          <div v-if="item.body_md" class="markdown" v-html="html(item.body_md)" />
          <template v-if="item.why_it_matters">
            <p><b>为什么值得关注：</b>{{ item.why_it_matters }}</p>
            <p><b>局限：</b>{{ item.limitations }}</p>
          </template>
          <p v-for="r in item.regions || []" :key="r.region" class="muted">{{ r.region }}：{{ r.status }} {{ r.date || '' }}</p>
          <ol v-if="item.sources?.length" class="sources">
            <li v-for="(s, i) in item.sources" :key="i">
              <a v-if="s.url" :href="s.url" target="_blank" rel="noopener noreferrer">{{ s.title || s.label || s.ref }}</a>
              <span v-else>{{ s.title || s.label || s.ref }}</span>
              <span class="muted"> {{ s.type }} {{ s.ref }} {{ s.year || '' }}</span>
              <div v-if="s.quote" class="muted quote">“{{ s.quote }}”</div>
            </li>
          </ol>
          <a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer">原文</a>
        </div>

        <NSpace class="actions" :size="8">
          <NButton size="small" quaternary @click="expanded = expanded === item.id ? null : item.id">
            {{ expanded === item.id ? '收起' : '查看全文与来源' }}
          </NButton>
          <NButton v-if="NEXT[item.status]" size="small" type="primary" @click="ask(item, NEXT[item.status]!.to)">
            {{ NEXT[item.status]!.label }}
          </NButton>
          <NButton v-if="item.status !== 'draft'" size="small" @click="ask(item, 'draft')">退回草稿</NButton>
        </NSpace>
      </NCard>
    </NSpin>

    <NModal :show="!!dialog" preset="card" style="max-width: 32rem" :title="dialog ? `${STATUS_LABEL[dialog.item.status]} → ${STATUS_LABEL[dialog.to]}` : ''" @update:show="(v: boolean) => { if (!v) dialog = null }">
      <NSpace vertical>
        <p v-if="dialog?.to === 'published'" class="notes">发布后所有用户可见。请确认来源、证据等级和措辞（不得有功效断言、推荐用药或产品）。</p>
        <NInput v-if="needsReviewer" v-model:value="reviewer" placeholder="医学审核人，例如：张三 · 某医院皮肤科主治医师" />
        <NInput v-model:value="note" type="textarea" :placeholder="needsNote ? '退回原因（必填）' : '备注（可选）'" />
        <NSpace justify="end">
          <NButton @click="dialog = null">取消</NButton>
          <NButton type="primary" :loading="busy" @click="confirm">确认</NButton>
        </NSpace>
      </NSpace>
    </NModal>
  </div>
</template>

<style scoped>
.knowledge-review { display: flex; flex-direction: column; gap: 12px; }
.hint { margin: 0 0 12px; font-size: 13px; color: #6b7280; line-height: 1.6; }
.item { margin-top: 8px; }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.title { font-size: 15px; }
.muted { color: #6b7280; font-size: 13px; margin: 6px 0 0; }
.notes { color: #b45309; font-size: 13px; margin: 6px 0 0; }
.detail { margin-top: 10px; padding: 10px 12px; border-radius: 8px; background: rgba(148, 163, 184, 0.08); }
.markdown :deep(h2) { font-size: 15px; margin: 12px 0 6px; }
.markdown :deep(p), .markdown :deep(li) { font-size: 14px; line-height: 1.7; }
.sources { padding-left: 18px; font-size: 13px; }
.quote { font-style: italic; }
.actions { margin-top: 10px; }
.empty { padding: 32px 0; }
</style>
