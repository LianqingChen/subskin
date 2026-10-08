import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isAxiosError } from 'axios'
import { fetchArchive, fetchArchiveDocument, resolveArchiveDocument } from '@/api/planning'
import type { ArchiveDetail, ArchiveFilters, ArchiveList } from '@/types/planning'
import { useAuthStore } from '@/stores/auth'

export function usePlanningArchive() {
  const route = useRoute()
  const router = useRouter()
  const auth = useAuthStore()
  const archive = ref<ArchiveList | null>(null)
  const document = ref<ArchiveDetail | null>(null)
  const loading = ref(false)
  const reading = ref(false)
  const error = ref('')
  const documentError = ref('')
  const listScroll = ref(0)
  let listRequest = 0
  let detailRequest = 0
  let linkRequest = 0
  let disposed = false
  const stringParam = (key: string) => typeof route.query[key] === 'string' ? route.query[key] as string : ''
  const selectedId = computed(() => stringParam('doc'))
  const filters = computed<ArchiveFilters>(() => ({
    q: stringParam('q'), category: stringParam('category'), source: stringParam('source'),
    month: stringParam('month'), page: Math.max(1, Number.parseInt(stringParam('page')) || 1),
  }))

  function clearPrivateState() {
    listRequest++; detailRequest++; linkRequest++
    archive.value = null; document.value = null
    loading.value = false; reading.value = false
  }
  function messageFor(cause: unknown): string {
    if (isAxiosError(cause)) {
      const status = cause.response?.status
      if (status === 401 || status === 403) {
        clearPrivateState()
        auth.token = null; auth.user = null
        const message = status === 401 ? '登录已过期，请重新登录管理后台' : '需要管理员权限，请重新登录'
        error.value = message
        documentError.value = message
        return message
      }
      if (status === 404) return '文档不存在或已移除，请刷新档案列表'
      if (status === 413) return '文档超过大小限制，暂时无法打开'
    }
    return '暂时无法读取，请重试'
  }
  async function load(refresh = false) {
    const version = ++listRequest
    loading.value = true; error.value = ''
    try {
      const result = await fetchArchive(filters.value, refresh)
      if (version === listRequest && !disposed) archive.value = result
    } catch (cause) {
      if (version === listRequest && !disposed) { archive.value = null; error.value = messageFor(cause) }
    } finally { if (version === listRequest) loading.value = false }
  }
  async function read() {
    const version = ++detailRequest
    linkRequest++
    document.value = null; documentError.value = ''
    reading.value = Boolean(selectedId.value)
    if (!selectedId.value) return
    try {
      const result = await fetchArchiveDocument(selectedId.value)
      if (version === detailRequest && !disposed) document.value = result
    } catch (cause) {
      if (version === detailRequest && !disposed) documentError.value = messageFor(cause)
    } finally { if (version === detailRequest) reading.value = false }
  }
  async function setFilters(patch: Partial<ArchiveFilters>) {
    listScroll.value = 0
    const next = { ...filters.value, ...patch, page: patch.page ?? 1 }
    await router.replace({ query: { ...route.query, q: next.q || undefined,
      category: next.category || undefined, source: next.source || undefined,
      month: next.month || undefined, page: next.page > 1 ? String(next.page) : undefined } })
  }
  async function select(id: string) {
    await router.push({ query: { ...route.query, doc: id || undefined } })
  }
  async function openPath(path: string) {
    const version = ++linkRequest
    try {
      const id = await resolveArchiveDocument(path)
      if (version === linkRequest && !disposed) await select(id)
    } catch (cause) {
      if (version === linkRequest && !disposed) documentError.value = messageFor(cause)
    }
  }
  async function refresh() {
    await load(true)
    if (selectedId.value && !error.value) await read()
  }
  watch(filters, () => { void load() }, { immediate: true })
  watch(selectedId, () => { void read() }, { immediate: true })
  watch(() => auth.isLoggedIn, (loggedIn) => { if (!loggedIn) clearPrivateState() })
  onBeforeUnmount(() => { disposed = true; clearPrivateState() })
  return { archive, document, loading, reading, error, documentError, selectedId, filters,
    listScroll, setFilters, select, openPath, refresh, read }
}
