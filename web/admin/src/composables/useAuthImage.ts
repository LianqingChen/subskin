import { onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { fetchTaskImage } from '@/api/labeling'

/** 带鉴权头拉取任务图片并转成 object URL；组件卸载或 id 变化时回收。 */
export function useAuthImage(taskId: Ref<number | null>, size: 'full' | 'thumb' = 'full') {
  const url = ref<string | null>(null)
  const failed = ref(false)
  let version = 0

  function revoke() {
    if (url.value) URL.revokeObjectURL(url.value)
    url.value = null
  }

  async function load(id: number | null) {
    const current = ++version
    revoke()
    failed.value = false
    if (!id) return
    try {
      const blob = await fetchTaskImage(id, size)
      if (current !== version) return
      url.value = URL.createObjectURL(blob)
    } catch (cause) {
      if (current === version) failed.value = true
      console.error('Failed to load labeling image:', cause)
    }
  }

  watch(taskId, load, { immediate: true })
  onBeforeUnmount(() => { version++; revoke() })
  return { url, failed }
}
