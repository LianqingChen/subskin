import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isAxiosError } from 'axios'
import { useMessage } from 'naive-ui'
import { errorText, fetchStats, fetchTasks, importLegacy, syncDiary, uploadPhotos } from '@/api/labeling'
import { saveLabelQueue } from '@/composables/useLabelQueue'
import { useAuthStore } from '@/stores/auth'
import type { TaskFilters, TaskList, TaskOrigin, TaskStats, UploadResult } from '@/types/labeling'

export const PAGE_SIZE = 20
const STATUSES: TaskFilters['status'][] = ['open', 'review', 'pending', 'returned', 'in_review', 'gold', 'rejected', 'skipped', 'all']
const ORIGINS: TaskOrigin[] = ['diary', 'admin_upload', 'legacy_import']

export function useLabelingTasks() {
  const route = useRoute()
  const router = useRouter()
  const auth = useAuthStore()
  const message = useMessage()
  const list = ref<TaskList | null>(null)
  const stats = ref<TaskStats | null>(null)
  const loading = ref(false)
  const busy = ref(false)
  const error = ref('')
  let requestId = 0
  let disposed = false

  const param = (key: string) => (typeof route.query[key] === 'string' ? (route.query[key] as string) : '')
  const filters = computed<TaskFilters>(() => {
    const status = param('status') as TaskFilters['status']
    const origin = param('origin') as TaskOrigin
    return {
      status: STATUSES.includes(status) ? status : 'open',
      origin: ORIGINS.includes(origin) ? origin : null,
      group: param('group') || null,
      benchmark: param('bm') === '1' ? true : null,
      escalate: param('esc') === '1',
      mine: param('mine') === '1',
      sort: param('sort') === 'newest' ? 'newest' : 'queue',
    }
  })
  const page = computed(() => Math.max(1, Number.parseInt(param('page')) || 1))

  function handleError(cause: unknown, fallback: string): string {
    if (isAxiosError(cause) && (cause.response?.status === 401 || cause.response?.status === 403)) {
      requestId++
      list.value = null
      stats.value = null
      auth.token = null
      auth.user = null
      return cause.response.status === 401 ? '登录已过期，请重新登录管理后台' : '需要管理员权限，请重新登录'
    }
    return errorText(cause, fallback)
  }

  async function load() {
    const id = ++requestId
    loading.value = true
    error.value = ''
    try {
      const [tasks, summary] = await Promise.all([
        fetchTasks(filters.value, PAGE_SIZE, (page.value - 1) * PAGE_SIZE), fetchStats(),
      ])
      if (id === requestId && !disposed) { list.value = tasks; stats.value = summary }
    } catch (cause) {
      if (id === requestId && !disposed) { list.value = null; error.value = handleError(cause, '暂时无法读取任务列表，请重试') }
    } finally { if (id === requestId) loading.value = false }
  }

  async function setFilters(patch: Partial<TaskFilters> & { page?: number }) {
    const next = { ...filters.value, ...patch }
    const nextPage = patch.page ?? 1
    await router.replace({ query: {
      status: next.status !== 'open' ? next.status : undefined,
      origin: next.origin || undefined, group: next.group || undefined,
      bm: next.benchmark ? '1' : undefined, esc: next.escalate ? '1' : undefined,
      mine: next.mine ? '1' : undefined, sort: next.sort === 'newest' ? 'newest' : undefined,
      page: nextPage > 1 ? String(nextPage) : undefined,
    } })
  }

  async function open(id: number, ids: number[] = list.value?.ids ?? []) {
    saveLabelQueue(ids, filters.value, route.fullPath)
    await router.push({ name: 'LabelingWorkspace', params: { id } })
  }
  async function start() {
    const ids = list.value?.ids ?? []
    if (ids.length) await open(ids[0], ids)
  }

  async function run<T>(action: () => Promise<T>, fallback: string): Promise<T | null> {
    busy.value = true
    try { return await action() } catch (cause) {
      message.error(handleError(cause, fallback))
      return null
    } finally { busy.value = false }
  }
  async function sync() {
    const result = await run(syncDiary, '同步失败')
    if (!result) return
    message.success(result.synced ? `已同步 ${result.synced} 张日记照片` : '没有新的日记照片')
    await load()
  }
  async function convertLegacy() {
    const result = await run(() => importLegacy(true), '转入失败')
    if (!result) return
    const failed = result.failed.length
    if (failed) message.warning(`已转入 ${result.imported.length} 条，${failed} 条失败`)
    else message.success(`已转入 ${result.imported.length} 条旧版记录`)
    await load()
  }
  async function upload(files: File[], note: string, subjectRef: string): Promise<UploadResult | null> {
    const result = await run(() => uploadPhotos(files, note, subjectRef, true), '上传失败')
    if (result) await load()
    return result
  }

  watch([filters, page], () => { void load() }, { immediate: true })
  onBeforeUnmount(() => { disposed = true; requestId++ })
  return { list, stats, loading, busy, error, filters, page, setFilters, load, open, start, sync, convertLegacy, upload }
}
