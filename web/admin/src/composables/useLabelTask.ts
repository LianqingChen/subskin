import { computed, ref, shallowRef } from 'vue'
import * as api from '@/api/labeling'
import type { LabelAttributes, PrefillSource, TaskDetail } from '@/types/labeling'
import { decodeClassMap, encodeClassMap, UNKNOWN } from '@/utils/classMap'
import type { ClassMapEditor } from './useClassMapEditor'

export type ReferenceKey = 'ai' | 'user' | 'latest'

export function emptyAttributes(): LabelAttributes {
  return { quality_issues: [], shot_type: 'unknown', imaging: 'rgb_phone', lighting: 'unknown', monk_skin_tone: null,
    body_site: null, signs: {}, escalate: false, notes: '' }
}

const draftKey = (id: number) => `labeling-draft-${id}`
interface LocalDraft { labels: string; attributes: LabelAttributes; prefill: PrefillSource; base: number | null; at: number }

/** 单个任务：加载参考层、选择预填、本地暂存、提交与复核。 */
export function useLabelTask(editor: ClassMapEditor) {
  const detail = ref<TaskDetail | null>(null)
  const layers = shallowRef<Partial<Record<ReferenceKey, Uint8Array>>>({})
  const attributes = ref<LabelAttributes>(emptyAttributes())
  const prefill = ref<PrefillSource>('none')
  const loading = ref(false)
  const busy = ref(false)
  const error = ref('')
  const restoredDraft = ref(false)
  let openedAt = Date.now()
  let saveTimer: ReturnType<typeof setTimeout> | null = null

  const task = computed(() => detail.value?.task ?? null)
  const latestBase = computed(() => detail.value?.submissions.find((s) => s.status !== 'superseded')?.id ?? null)

  async function decodeLayers(d: TaskDetail) {
    const { width, height } = d.image
    const out: Partial<Record<ReferenceKey, Uint8Array>> = {}
    for (const key of ['ai', 'user', 'latest'] as ReferenceKey[]) {
      const url = d.layers[key]
      if (url) out[key] = await decodeClassMap(url, width, height)
    }
    layers.value = out
  }

  function readDraft(id: number): LocalDraft | null {
    try {
      const raw = localStorage.getItem(draftKey(id))
      return raw ? (JSON.parse(raw) as LocalDraft) : null
    } catch (cause) {
      console.error('Discarding unreadable labeling draft:', cause)
      return null
    }
  }

  async function load(id: number) {
    loading.value = true; error.value = ''; restoredDraft.value = false
    try {
      const d = await api.fetchTask(id)
      await decodeLayers(d)
      detail.value = d
      const { width, height } = d.image
      const latest = d.submissions.find((s) => s.status !== 'superseded')
      attributes.value = { ...emptyAttributes(), ...(latest?.attributes ?? {}), body_site: latest?.attributes.body_site ?? d.task.body_site }
      const draft = readDraft(id)
      if (draft && draft.base === latestBase.value) {
        editor.reset(await decodeClassMap(draft.labels, width, height), width, height)
        attributes.value = { ...emptyAttributes(), ...draft.attributes }
        prefill.value = d.blind ? 'none' : draft.prefill
        restoredDraft.value = true
      } else {
        const base = d.blind ? null : layers.value.latest ?? layers.value.user ?? layers.value.ai ?? null
        prefill.value = d.blind || !base ? 'none' : layers.value.latest ? 'previous' : layers.value.user ? 'user' : 'ai'
        editor.reset(base ? base.slice() : new Uint8Array(width * height).fill(UNKNOWN), width, height)
      }
      openedAt = Date.now()
    } catch (cause) {
      detail.value = null
      error.value = api.errorText(cause, '任务加载失败')
    } finally {
      loading.value = false
    }
  }

  function useLayer(key: ReferenceKey | 'blank') {
    const d = detail.value
    if (!d) return
    if (key === 'blank') {
      editor.replace(new Uint8Array(d.image.width * d.image.height).fill(UNKNOWN))
      prefill.value = 'none'
      return
    }
    const layer = layers.value[key]
    if (!layer) return
    editor.replace(layer.slice())
    prefill.value = key === 'latest' ? 'previous' : key
  }

  function scheduleDraft() {
    const d = detail.value
    if (!d || !editor.dirty.value) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      const value: LocalDraft = { labels: encodeClassMap(editor.map.value, d.image.width, d.image.height),
        attributes: attributes.value, prefill: prefill.value, base: latestBase.value, at: Date.now() }
      try { localStorage.setItem(draftKey(d.task.id), JSON.stringify(value)) } catch (cause) { console.error('Draft not saved:', cause) }
    }, 1500)
  }
  function dropDraft(id: number) { if (saveTimer) clearTimeout(saveTimer); localStorage.removeItem(draftKey(id)) }

  async function run<T>(fn: () => Promise<T>, fallback: string): Promise<T | null> {
    busy.value = true; error.value = ''
    try { return await fn() } catch (cause) { error.value = api.errorText(cause, fallback); return null } finally { busy.value = false }
  }

  async function submit() {
    const d = detail.value
    if (!d) return null
    return run(async () => {
      const labels = encodeClassMap(editor.map.value, d.image.width, d.image.height)
      const result = await api.submitLabels(d.task.id, { labels, attributes: attributes.value, prefill_source: prefill.value,
        duration_ms: Date.now() - openedAt })
      dropDraft(d.task.id)
      editor.markSaved()
      return result
    }, '提交失败')
  }
  async function snap() {
    const d = detail.value
    if (!d) return
    await run(async () => {
      const url = await api.snapEdges(d.task.id, encodeClassMap(editor.map.value, d.image.width, d.image.height))
      editor.replace(await decodeClassMap(url, d.image.width, d.image.height))
    }, '边缘贴合失败')
  }
  async function redraft() {
    const d = detail.value
    if (!d) return
    await run(async () => {
      const { labels } = await api.redraft(d.task.id)
      const map = await decodeClassMap(labels, d.image.width, d.image.height)
      layers.value = { ...layers.value, ai: map }
      editor.replace(map.slice())
      prefill.value = 'ai'
    }, 'AI 初稿生成失败')
  }
  async function submissionLayer(submissionId: number) {
    const d = detail.value
    if (!d) return null
    return run(async () => decodeClassMap(await api.fetchSubmissionLabels(d.task.id, submissionId), d.image.width, d.image.height),
      '版本加载失败')
  }

  const approve = (id: number, note: string) => run(() => api.approveSubmission(id, note), '复核通过失败')
  const reject = (id: number, note: string) => run(() => api.returnSubmission(id, note), '退回失败')
  const setStatus = (status: 'skipped' | 'rejected' | 'pending', reasons: string[] = []) =>
    run(() => api.setTaskStatus((detail.value as TaskDetail).task.id, status, reasons), '状态更新失败')
  const setBenchmark = (flag: boolean) => run(() => api.setBenchmark((detail.value as TaskDetail).task.id, flag), '基准集设置失败')

  return { detail, task, layers, attributes, prefill, loading, busy, error, restoredDraft,
    load, useLayer, scheduleDraft, dropDraft, submit, snap, redraft, submissionLayer, approve, reject, setStatus, setBenchmark }
}
