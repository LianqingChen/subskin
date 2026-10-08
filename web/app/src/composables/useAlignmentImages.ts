import { computed, onBeforeUnmount, shallowRef, ref, watch } from 'vue'
import { loadStoryImage } from '@/utils/assessment-story/render'
import { toProtectedFileUrl } from '@/utils/file-url'
import type { ImageDimensions } from '@/types/comparison-alignment'
export function useAlignmentImages(props: { beforeUrl: string; afterUrl: string }) {
  const before = shallowRef<ImageDimensions | null>(null), after = shallowRef<ImageDimensions | null>(null)
  const error = ref(''), loading = ref(false)
  const beforeUrl = computed(() => toProtectedFileUrl(props.beforeUrl)), afterUrl = computed(() => toProtectedFileUrl(props.afterUrl))
  let generation = 0
  async function load() {
    const current = ++generation
    before.value = null; after.value = null; error.value = ''; loading.value = true
    try {
      const images = await Promise.all([loadStoryImage(beforeUrl.value), loadStoryImage(afterUrl.value)])
      if (current !== generation) return
      before.value = { width: images[0].naturalWidth, height: images[0].naturalHeight }
      after.value = { width: images[1].naturalWidth, height: images[1].naturalHeight }
    } catch { if (current === generation) error.value = '照片暂未加载，请重试' }
    finally { if (current === generation) loading.value = false }
  }
  watch(() => [props.beforeUrl, props.afterUrl], load, { immediate: true })
  onBeforeUnmount(() => { generation++ })
  return { before, after, beforeUrl, afterUrl, error, loading, load }
}
