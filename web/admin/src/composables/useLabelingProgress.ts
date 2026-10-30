import { onBeforeUnmount, onMounted, ref } from 'vue'
import { errorText, fetchProgress } from '@/api/labeling'
import type { LabelingProgress } from '@/types/labeling'

export function useLabelingProgress() {
  const progress = ref<LabelingProgress | null>(null)
  const loading = ref(false)
  const error = ref('')
  let disposed = false

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const result = await fetchProgress()
      if (!disposed) progress.value = result
    } catch (cause) {
      if (!disposed) error.value = errorText(cause, '加载标注进度失败')
    } finally { loading.value = false }
  }
  onMounted(() => { void load() })
  onBeforeUnmount(() => { disposed = true })
  return { progress, loading, error, load }
}
