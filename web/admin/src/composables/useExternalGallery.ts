import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { errorText, fetchTasks, setTaskStatus } from '@/api/labeling'
import { saveLabelQueue } from '@/composables/useLabelQueue'
import type { TaskFilters, TaskList, TaskSummary } from '@/types/labeling'

export const GALLERY_PAGE = 48
type Source = 'any' | 'pmc_oa' | 'wikimedia_commons'
type StatusFilter = 'all' | 'open' | 'review' | 'gold' | 'rejected'

/** 公开授权照片图库：按来源/状态浏览，看大图，标不可用或进入标注。 */
export function useExternalGallery() {
  const router = useRouter()
  const source = ref<Source>('any')
  const status = ref<StatusFilter>('all')
  const page = ref(1)
  const list = ref<TaskList | null>(null)
  const loading = ref(false)
  const error = ref('')
  const selected = ref<TaskSummary | null>(null)
  let request = 0

  const filters = computed<TaskFilters>(() => ({ status: status.value, external: source.value, sort: 'newest' }))
  const index = computed(() => (selected.value && list.value ? list.value.items.findIndex((i) => i.id === selected.value?.id) : -1))

  async function load() {
    const id = ++request
    loading.value = true; error.value = ''
    try {
      const result = await fetchTasks(filters.value, GALLERY_PAGE, (page.value - 1) * GALLERY_PAGE)
      if (id === request) list.value = result
    } catch (cause) {
      if (id === request) { list.value = null; error.value = errorText(cause, '图库加载失败') }
    } finally { if (id === request) loading.value = false }
  }

  function step(delta: number) {
    const items = list.value?.items ?? []
    const next = items[index.value + delta]
    if (next) selected.value = next
  }
  async function reject(item: TaskSummary, reasons: string[]): Promise<string | null> {
    try {
      await setTaskStatus(item.id, 'rejected', reasons)
      await load()
      selected.value = list.value?.items.find((i) => i.id === item.id) ?? null
      return null
    } catch (cause) { return errorText(cause, '标记失败') }
  }
  async function label(item: TaskSummary) {
    saveLabelQueue(list.value?.ids ?? [item.id], filters.value, '/external-gallery')
    await router.push({ name: 'LabelingWorkspace', params: { id: item.id } })
  }

  watch([source, status], () => { page.value = 1 })
  watch([source, status, page], load, { immediate: true })
  return { source, status, page, list, loading, error, selected, index, load, step, reject, label }
}
