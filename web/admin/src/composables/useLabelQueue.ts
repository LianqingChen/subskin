import { computed, ref } from 'vue'
import type { TaskFilters } from '@/types/labeling'

const KEY = 'labeling-queue'

interface StoredQueue { ids: number[]; filters: TaskFilters; returnTo?: string }

function read(): StoredQueue | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as StoredQueue) : null
  } catch (cause) {
    console.error('Invalid labeling queue in session storage:', cause)
    return null
  }
}

/** 列表页按当前筛选写入任务顺序，工作台据此「上一张 / 下一张」。 */
export function saveLabelQueue(ids: number[], filters: TaskFilters, returnTo?: string) {
  sessionStorage.setItem(KEY, JSON.stringify({ ids, filters, returnTo }))
}

export function useLabelQueue(currentId: () => number) {
  const stored = ref<StoredQueue | null>(read())
  const ids = computed(() => stored.value?.ids ?? [])
  const index = computed(() => ids.value.indexOf(currentId()))
  const prevId = computed(() => (index.value > 0 ? ids.value[index.value - 1] : null))
  const nextId = computed(() => (index.value >= 0 && index.value < ids.value.length - 1 ? ids.value[index.value + 1] : null))
  const position = computed(() => (index.value >= 0 ? `${index.value + 1} / ${ids.value.length}` : ''))
  const returnTo = computed(() => stored.value?.returnTo ?? '/image-labeling')
  return { ids, prevId, nextId, position, returnTo, filters: computed(() => stored.value?.filters ?? null) }
}
