import { ref } from 'vue'
import { errorText, fetchChoices } from '@/api/labeling'
import type { LabelingChoices } from '@/types/labeling'

const cached = ref<LabelingChoices | null>(null)
let pending: Promise<void> | null = null

/** 枚举（部位词表、质量原因、体征等）来自后端，全局缓存一次。 */
export function useLabelingChoices() {
  const error = ref('')
  if (!cached.value && !pending) {
    pending = fetchChoices()
      .then((value) => { cached.value = value })
      .catch((cause) => { error.value = errorText(cause, '标注选项加载失败'); console.error(cause) })
      .finally(() => { pending = null })
  }
  return { choices: cached, error }
}
