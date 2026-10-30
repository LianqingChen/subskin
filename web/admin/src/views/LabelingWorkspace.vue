<template>
  <main class="workspace">
    <header class="topbar">
      <n-button quaternary size="small" @click="exit"><template #icon><i class="ri-arrow-left-line" /></template>返回列表</n-button>
      <div v-if="task" class="title">
        <strong>#{{ task.id }}</strong>
        <n-tag size="small" :bordered="false">{{ ORIGIN_LABEL[task.origin] }}</n-tag>
        <span>{{ task.body_site_label ?? '部位未填' }}</span>
        <n-tag size="small" :type="statusType" :bordered="false">{{ STATUS_LABEL[task.status] }}</n-tag>
        <n-tag v-if="task.benchmark" size="small" type="warning" :bordered="false">基准集 · 盲标</n-tag>
        <n-tag v-if="task.user_revision_newer" size="small" type="info" :bordered="false">用户有新修订</n-tag>
        <n-tag v-if="labeler.restoredDraft.value" size="small" :bordered="false">已恢复本地草稿</n-tag>
      </div>
      <div class="nav">
        <n-button size="small" quaternary :disabled="!prevId" title="上一张 (Alt+←)" @click="go(prevId)"><i class="ri-arrow-left-s-line" /></n-button>
        <span class="position">{{ position }}</span>
        <n-button size="small" quaternary :disabled="!nextId" title="下一张 (Alt+→)" @click="go(nextId)"><i class="ri-arrow-right-s-line" /></n-button>
      </div>
      <div v-if="task" class="actions">
        <template v-if="closed">
          <n-button size="small" :disabled="busy" @click="reopen">恢复为待标注</n-button>
        </template>
        <template v-else>
          <n-button size="small" quaternary :disabled="busy" @click="skip">跳过</n-button>
          <n-button size="small" quaternary type="error" :disabled="busy" @click="showReject = true">不可用</n-button>
          <n-button size="small" :type="task.benchmark ? 'warning' : 'default'" :disabled="busy" @click="toggleBenchmark">
            {{ task.benchmark ? '移出基准集' : '设为基准集' }}</n-button>
          <n-button size="small" :disabled="busy" @click="save(false)">提交</n-button>
          <n-button size="small" type="primary" :loading="busy" title="Ctrl+Enter" @click="save(true)">提交并下一张</n-button>
        </template>
      </div>
    </header>

    <div v-if="labeler.loading.value && !task" class="state"><n-spin /><p>正在加载任务…</p></div>
    <div v-else-if="!task" class="state" role="alert"><p>{{ labeler.error.value || '任务不存在' }}</p><n-button @click="exit">返回列表</n-button></div>
    <div v-else class="body">
      <ToolPanel v-model:opacity="opacity" v-model:show-overlay="showOverlay" v-model:reference="reference"
        :editor="editor" :prefill="labeler.prefill.value" :blind="detail?.blind ?? false" :busy="busy" :has-layer="hasLayer"
        :reference-options="referenceOptions" @use-layer="labeler.useLayer" @redraft="labeler.redraft" @snap="labeler.snap" />
      <section class="stage">
        <ClassMapCanvas ref="canvas" :editor="editor" :image-url="image.url.value" :opacity="opacity" :show-overlay="showOverlay"
          :reference="peekMap" :peek-label="peekMap ? peekLabel : ''" />
        <div class="zoom">
          <button type="button" title="缩小 (-)" @click="canvas?.zoomAt(0.8)"><i class="ri-zoom-out-line" /></button>
          <button type="button" title="适应窗口 (`)" @click="canvas?.fit()"><i class="ri-fullscreen-exit-line" /></button>
          <button type="button" title="1:1" @click="canvas?.actualSize()">1:1</button>
          <button type="button" title="放大 (+)" @click="canvas?.zoomAt(1.25)"><i class="ri-zoom-in-line" /></button>
          <span class="sep" />
          <button type="button" :disabled="!editor.canUndo.value" title="撤销 (Ctrl+Z)" @click="editor.undo()"><i class="ri-arrow-go-back-line" /></button>
          <button type="button" :disabled="!editor.canRedo.value" title="重做 (Ctrl+Shift+Z)" @click="editor.redo()"><i class="ri-arrow-go-forward-line" /></button>
        </div>
        <p v-if="image.failed.value" class="image-error" role="alert">照片加载失败，请刷新重试</p>
        <p v-if="labeler.error.value" class="op-error" role="alert">{{ labeler.error.value }}</p>
      </section>
      <aside class="side">
        <n-tabs v-model:value="tab" type="line" size="small" animated>
          <n-tab-pane name="attrs" tab="图像属性">
            <AttributeForm v-if="choices" v-model:attributes="labeler.attributes.value" :choices="choices" />
          </n-tab-pane>
          <n-tab-pane name="review" :tab="reviewTab">
            <ReviewPanel :submissions="detail?.submissions ?? []" :gold="task.gold" :benchmark="task.benchmark" :me="me"
              :busy="busy" @approve="approve" @return="sendBack" @peek="pinSubmission" />
          </n-tab-pane>
          <n-tab-pane name="history" tab="版本">
            <SubmissionHistory :submissions="detail?.submissions ?? []" @peek="pinSubmission" />
          </n-tab-pane>
        </n-tabs>
        <p v-if="detail?.provenance?.source_note" class="provenance"><i class="ri-information-line" /> 来源：{{ detail.provenance.source_note }}</p>
        <p class="shortcuts">快捷键：1–5/0 类别 · B F W R 工具 · [ ] 画笔 · 空格拖动 · 按住 C 对照 · H 隐藏标注 · Ctrl+Z 撤销 · Ctrl+Enter 提交并下一张</p>
      </aside>
    </div>
    <RejectDialog v-model:show="showReject" :reasons="choices?.reject_reasons ?? []" @confirm="reject" />
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import ClassMapCanvas from '@/components/labeling/ClassMapCanvas.vue'
import ToolPanel from '@/components/labeling/ToolPanel.vue'
import AttributeForm from '@/components/labeling/AttributeForm.vue'
import ReviewPanel from '@/components/labeling/ReviewPanel.vue'
import SubmissionHistory from '@/components/labeling/SubmissionHistory.vue'
import RejectDialog from '@/components/labeling/RejectDialog.vue'
import { useClassMapEditor } from '@/composables/useClassMapEditor'
import { useLabelTask } from '@/composables/useLabelTask'
import { useLabelQueue } from '@/composables/useLabelQueue'
import { useAuthImage } from '@/composables/useAuthImage'
import { useLabelingChoices } from '@/composables/useLabelingChoices'
import { useWorkspaceShortcuts } from '@/composables/useWorkspaceShortcuts'
import { useAuthStore } from '@/stores/auth'
import { ORIGIN_LABEL, STATUS_LABEL } from '@/types/labeling'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const auth = useAuthStore()
const editor = useClassMapEditor()
const labeler = useLabelTask(editor)
const { choices } = useLabelingChoices()
const taskId = computed(() => Number(route.params.id) || 0)
const { prevId, nextId, position, returnTo } = useLabelQueue(() => taskId.value)
const image = useAuthImage(computed(() => (labeler.detail.value ? taskId.value : null)))
const canvas = ref<InstanceType<typeof ClassMapCanvas> | null>(null)

const detail = labeler.detail
const task = labeler.task
const busy = computed(() => labeler.busy.value)
const me = computed(() => auth.user?.id ?? null)
const tab = ref('attrs')
const opacity = ref(0.45)
const showOverlay = ref(true)
const reference = ref('ai')
const peeking = ref(false)
const pinned = ref(false)
const showReject = ref(false)
const submissionMaps = shallowRef(new Map<number, Uint8Array>())

const closed = computed(() => task.value?.status === 'rejected' || task.value?.status === 'skipped')
const statusType = computed(() => ({ pending: 'default', returned: 'warning', in_review: 'info', gold: 'success', rejected: 'error', skipped: 'default' } as const)[task.value?.status ?? 'pending'])
const hasLayer = computed(() => ({ ai: !!labeler.layers.value.ai, user: !!labeler.layers.value.user, latest: !!labeler.layers.value.latest }))
const reviewTab = computed(() => (detail.value?.submissions.some((s) => s.status === 'submitted') ? '复核 ●' : '复核'))
const referenceOptions = computed(() => [
  ...(hasLayer.value.ai ? [{ label: 'AI 初稿', value: 'ai' }] : []),
  ...(hasLayer.value.user ? [{ label: '用户日记确认版', value: 'user' }] : []),
  ...(detail.value?.submissions ?? []).map((s) => ({ label: `版本 #${s.id}（${s.author ?? '管理员'}）`, value: `sub:${s.id}` })),
])
const peekLabel = computed(() => referenceOptions.value.find((o) => o.value === reference.value)?.label ?? '')
const peekMap = computed<Uint8Array | null>(() => {
  if (!peeking.value && !pinned.value) return null
  if (reference.value.startsWith('sub:')) return submissionMaps.value.get(Number(reference.value.slice(4))) ?? null
  return labeler.layers.value[reference.value as 'ai' | 'user'] ?? null
})

async function ensureSubmission(id: number) {
  if (submissionMaps.value.has(id)) return
  const map = await labeler.submissionLayer(id)
  if (map) submissionMaps.value = new Map(submissionMaps.value).set(id, map)
}
watch(reference, (value) => { if (value.startsWith('sub:')) ensureSubmission(Number(value.slice(4))) })
async function pinSubmission(id: number) {
  const key = `sub:${id}`
  if (pinned.value && reference.value === key) { pinned.value = false; return }
  reference.value = key
  await ensureSubmission(id)
  pinned.value = true
}

async function load() {
  submissionMaps.value = new Map()
  pinned.value = false
  await labeler.load(taskId.value)
  const first = referenceOptions.value[0]
  reference.value = first?.value ?? 'ai'
  if (task.value?.status === 'in_review') tab.value = 'review'
}
watch(taskId, load)
watch(() => [editor.version.value, labeler.attributes.value], () => labeler.scheduleDraft(), { deep: true })

function confirmLeave(): Promise<boolean> {
  if (!editor.dirty.value) return Promise.resolve(true)
  return new Promise((resolve) => dialog.warning({
    title: '有未提交的修改', content: '修改已在本机暂存，下次打开会恢复。确定离开？', positiveText: '离开', negativeText: '留下',
    onPositiveClick: () => resolve(true), onNegativeClick: () => resolve(false), onClose: () => resolve(false),
  }))
}
async function go(id: number | null) { if (id) await router.push({ name: 'LabelingWorkspace', params: { id } }) }
function exit() { router.push(returnTo.value) }
onBeforeRouteLeave(() => confirmLeave())
const beforeUnload = (e: BeforeUnloadEvent) => { if (editor.dirty.value) e.preventDefault() }

function confirmUnknown(): Promise<boolean> {
  const fraction = editor.stats.value.labeledFraction
  if (fraction >= 0.5) return Promise.resolve(true)
  return new Promise((resolve) => dialog.warning({
    title: '超过一半像素未标', content: `当前只标了 ${Math.round(fraction * 100)}% 的像素。未标处训练时会被忽略；确定是有意留空？`,
    positiveText: '确定提交', negativeText: '继续标注', onPositiveClick: () => resolve(true), onNegativeClick: () => resolve(false),
    onClose: () => resolve(false),
  }))
}
async function save(advance: boolean) {
  if (!(await confirmUnknown())) return
  const result = await labeler.submit()
  if (!result) return message.error(labeler.error.value)
  message.success('已提交，等待复核')
  if (advance && nextId.value) await go(nextId.value)
  else await load()
}
async function approve(id: number, note: string) {
  const r = await labeler.approve(id, note)
  if (!r) return message.error(labeler.error.value)
  message.success(r.review_mode === 'dual' ? '已通过（双人复核），设为金标准' : '已通过（单人复核），设为金标准')
  await load()
}
async function sendBack(id: number, note: string) {
  if ((await labeler.reject(id, note)) === null) return message.error(labeler.error.value)
  message.info('已退回')
  await load()
}
async function skip() {
  if ((await labeler.setStatus('skipped')) === null) return message.error(labeler.error.value)
  editor.markSaved()
  if (nextId.value) await go(nextId.value); else await load()
}
async function reject(reasons: string[]) {
  showReject.value = false
  if ((await labeler.setStatus('rejected', reasons)) === null) return message.error(labeler.error.value)
  labeler.dropDraft(taskId.value)
  editor.markSaved()
  message.info('已标记为不可用，金标准（如有）已撤销')
  if (nextId.value) await go(nextId.value); else await load()
}
async function reopen() { if ((await labeler.setStatus('pending')) !== null) await load() }
function toggleBenchmark() {
  const on = !task.value?.benchmark
  dialog.warning({
    title: on ? '设为基准集（锁定测试集）' : '移出基准集',
    content: on ? '基准集样本必须盲标（不预填）并由第二位管理员复核；之前用预填做的版本将不再计入。该用户的全部样本会进入测试集。' : '移出后按普通样本处理。',
    positiveText: '确定', negativeText: '取消',
    onPositiveClick: async () => { if ((await labeler.setBenchmark(on)) !== null) await load(); else message.error(labeler.error.value) },
  })
}

useWorkspaceShortcuts(editor, {
  submitNext: () => { if (!closed.value && !busy.value) save(true) },
  next: () => go(nextId.value), prev: () => go(prevId.value),
  toggleOverlay: () => { showOverlay.value = !showOverlay.value },
  peek: (on) => { peeking.value = on },
  zoom: (f) => canvas.value?.zoomAt(f), fit: () => canvas.value?.fit(),
})
onMounted(async () => {
  window.addEventListener('beforeunload', beforeUnload)
  if (!auth.user) await auth.fetchUser()
  await load()
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<style scoped>
.workspace { position: fixed; inset: 0; z-index: 1000; display: flex; flex-direction: column; background: #0b1220; color: #e2e8f0; height: 100vh; height: 100dvh; }
.topbar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid #1f2937; flex-wrap: wrap; }
.title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.nav { display: flex; align-items: center; gap: 4px; margin-left: auto; }
.position { font-size: 12px; color: #94a3b8; font-variant-numeric: tabular-nums; min-width: 56px; text-align: center; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; }
.state { flex: 1; display: grid; place-content: center; justify-items: center; gap: 12px; color: #94a3b8; }
.body { flex: 1; display: flex; min-height: 0; }
.stage { position: relative; flex: 1; display: flex; min-width: 0; }
.zoom { position: absolute; right: 12px; bottom: 12px; display: flex; gap: 2px; padding: 4px; border-radius: 10px; background: rgba(15, 23, 42, .9); border: 1px solid #1f2937; }
.zoom button { min-width: 36px; height: 36px; border: 0; border-radius: 8px; background: transparent; color: #e2e8f0; cursor: pointer; font-size: 12px; }
.zoom button:disabled { opacity: .35; cursor: default; }
.zoom .sep { width: 1px; background: #334155; margin: 4px 2px; }
.image-error, .op-error { position: absolute; left: 12px; bottom: 12px; margin: 0; padding: 6px 10px; border-radius: 8px; background: rgba(127, 29, 29, .9); color: #fee2e2; font-size: 12px; max-width: 60%; }
.op-error { bottom: 52px; }
.side { width: 340px; flex-shrink: 0; overflow-y: auto; padding: 8px 12px 16px; border-left: 1px solid #1f2937; }
.provenance, .shortcuts { font-size: 11px; color: #64748b; line-height: 1.6; margin: 12px 0 0; }
@media (max-width: 1100px) {
  .body { flex-direction: column; overflow-y: auto; }
  .body > :deep(.tool-panel) { width: 100%; max-height: 32vh; border-right: 0; border-bottom: 1px solid #1f2937; }
  .body :deep(.class-grid), .body :deep(.action-grid) { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .stage { min-height: 55vh; }
  .side { width: 100%; border-left: 0; border-top: 1px solid #1f2937; }
}
</style>
