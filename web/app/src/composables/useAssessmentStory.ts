import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { isAxiosError } from 'axios'
import type { AssessmentResult } from '@/types/assessment'
import { generateAssessmentStory, generateAssessmentArtwork, type GeneratedStory } from '@/api/assessment-story'
import { useAuthStore } from '@/stores/auth'
import { toProtectedFileUrl } from '@/utils/file-url'
import { loadStoryShape, loadStoryImage, renderStoryPoster, silhouette } from '@/utils/assessment-story/render'
import type { StoryShape } from '@/utils/assessment-story/mask'
import type { StoryPeelArtwork } from '@/types/story-peel'
import { makeStory, type StoryTheme } from '@/utils/assessment-story/content'
import { journalSummary } from '@/utils/assessment-story/summary'
function settleSelection(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Aborted', 'AbortError')); return }
    const timer = setTimeout(() => { signal.removeEventListener('abort', cancel); resolve() }, 250)
    const cancel = () => { clearTimeout(timer); signal.removeEventListener('abort', cancel); reject(new DOMException('Aborted', 'AbortError')) }
    signal.addEventListener('abort', cancel, { once: true })
  })
}
type StoryPreview = Omit<GeneratedStory, 'source'> & { source: 'ai' | 'template' }
export function useAssessmentStory(props: { result: AssessmentResult; lesion?: string | null; saved?: boolean }) {
  const auth = useAuthStore(), story = ref<StoryPreview | null>(null)
  const url = ref(''), blob = ref<Blob | null>(null), loading = ref(false), enhancing = ref(false)
  const error = ref(''), notice = ref(''), needsConsent = ref(false)
  const selectedTheme = ref<StoryTheme>('sky')
  const peelArtwork = shallowRef<StoryPeelArtwork | null>(null)
  const drawing = ref(false), artGenerated = ref(false), artNotice = ref('')
  let retryArt = false
  let generation = 0, controller: AbortController | null = null
  const title = computed(() => story.value?.title || '')
  function clear() { peelArtwork.value = null; artGenerated.value = false; if (url.value) URL.revokeObjectURL(url.value); url.value = ''; blob.value = null; story.value = null }
  function show(output: Blob, content: StoryPreview, shape: StoryShape, artwork?: HTMLImageElement) {
    const previous = url.value
    try {
      const sticker = silhouette(shape, content.theme, artwork).toDataURL('image/png')
      peelArtwork.value = { url: sticker, width: shape.width, height: shape.height, bounds: { ...shape.bounds } }
    } catch { peelArtwork.value = null } // Optional interaction must never block the finished poster.
    story.value = content; blob.value = output; url.value = URL.createObjectURL(output)
    if (previous) URL.revokeObjectURL(previous)
  }
  async function load() {
    const current = ++generation, owner = auth.user?.id, summary = journalSummary(props.result), retry = retryArt, theme = selectedTheme.value
    retryArt = false
    const unchanged = () => current === generation && owner === auth.user?.id
    controller?.abort(); controller = new AbortController(); error.value = ''; notice.value = ''; needsConsent.value = false; enhancing.value = false; drawing.value = false; artNotice.value = ''
    if (story.value?.revision !== summary.revision || story.value?.theme !== theme) clear()
    loading.value = !blob.value
    if (!props.saved || !summary.reviewed || !props.lesion || !summary.revision) { clear(); loading.value = false; error.value = '保存确认范围后，即可生成轮廓故事'; return }
    try {
      const shape = await loadStoryShape(toProtectedFileUrl(props.lesion))
      if (!unchanged()) return
      if (!shape) { clear(); error.value = '本次没有可用于创作的轮廓，记录已保留'; return }
      // Art depends only on the reviewed mask. Optional AI text must never hide it.
      if (!blob.value) {
        const local = makeStory(shape, theme, props.result.bodySite, null, 0)
        const fallback: StoryPreview = { theme, title: local.title.replace(/\n/g, ''), source: 'template', revision: summary.revision }
        const output = await renderStoryPoster({ shape, theme, format: 'portrait', story: fallback })
        if (!unchanged()) return
        show(output, fallback, shape)
      }
      loading.value = false; enhancing.value = true
      try {
        await settleSelection(controller.signal)
        if (!unchanged()) return
        const result = await generateAssessmentStory(props.result.id, summary.revision, controller.signal, theme)
        if (result.theme !== theme) throw new Error('创意风格不一致')
        if (!unchanged()) return
        const output = await renderStoryPoster({ shape, theme: result.theme, format: 'portrait', story: result })
        if (!unchanged()) return
        show(output, result, shape); enhancing.value = false; drawing.value = true
        try {
          const dataUrl = await generateAssessmentArtwork(props.result.id, summary.revision, controller.signal, retry, theme)
          if (!unchanged()) return
          const artwork = await loadStoryImage(dataUrl)
          if (!unchanged()) return
          const final = await renderStoryPoster({ shape, theme: result.theme, format: 'portrait', story: result, artwork })
          if (unchanged()) { show(final, result, shape, artwork); artGenerated.value = true }
        } catch {
          if (unchanged()) artNotice.value = '艺术画面暂未生成，已保留轮廓创意与文案'
        } finally { if (unchanged()) drawing.value = false }
      } catch (e) {
        if (!unchanged()) return
        needsConsent.value = isAxiosError(e) && e.response?.status === 403
        notice.value = needsConsent.value ? 'AI文案尚未授权，轮廓创意仍可保存与分享' : 'AI文案暂未生成，已保留轮廓创意'
      }
    } catch {
      if (unchanged()) error.value = '轮廓图片暂未生成，请重试'
    } finally { if (unchanged()) { loading.value = false; enhancing.value = false; drawing.value = false } }
  }
  watch(() => [props.result.id, props.lesion, props.saved, journalSummary(props.result).revision, props.result.measurement?.annotation?.review_state, auth.user?.id, selectedTheme.value], () => { clear(); void load() }, { immediate: true, flush: 'sync' })
  function retryArtwork() { retryArt = true; void load() }
  onBeforeUnmount(() => { generation++; controller?.abort(); clear() })
  return { peelArtwork, selectedTheme, story, title, url, blob, loading, enhancing, drawing, artGenerated, artNotice, error, notice, needsConsent, load, retryArtwork }
}
