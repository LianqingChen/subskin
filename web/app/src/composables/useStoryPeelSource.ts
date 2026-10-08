import { onBeforeUnmount, ref, watch } from 'vue'
import { loadPhotoMasks, renderPhotoMasks } from '@/utils/photo-mask-canvas'
import { toProtectedFileUrl } from '@/utils/file-url'

export function useStoryPeelSource(props: { image?: string | null; skin?: string | null; lesion?: string | null }) {
  const url = ref(''), aspect = ref(1), loading = ref(false), error = ref('')
  let generation = 0
  function clear() {
    if (url.value) URL.revokeObjectURL(url.value)
    url.value = ''
  }
  async function load() {
    const current = ++generation
    clear(); error.value = ''; loading.value = true
    try {
      if (!props.image || !props.lesion) throw new Error('missing source')
      const state = await loadPhotoMasks({ image: toProtectedFileUrl(props.image), skin: toProtectedFileUrl(props.skin), lesion: toProtectedFileUrl(props.lesion) })
      if (current !== generation) return
      const canvas = document.createElement('canvas')
      renderPhotoMasks(canvas, state)
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('source render failed')), 'image/png'))
      if (current !== generation) return
      aspect.value = canvas.width / canvas.height
      url.value = URL.createObjectURL(blob)
    } catch {
      if (current === generation) error.value = '来源照片暂未加载，创意图片仍可保存'
    } finally {
      if (current === generation) loading.value = false
    }
  }
  watch(() => [props.image, props.skin, props.lesion], load, { immediate: true })
  onBeforeUnmount(() => { generation++; clear() })
  return { url, aspect, loading, error, load }
}
