import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import type { HospitalNotebook, HospitalMark, HospitalReviewDraft, HospitalSuggestion } from '@/types/hospital'

export function useHospitalNotebook() {
  const auth = useAuthStore()
  const toast = useToast()
  const owner = computed(() => String(auth.user?.id ?? 'guest'))
  const key = computed(() => `subskin-hospitals-v1:${owner.value}`)
  const notebook = ref<HospitalNotebook>({ marks: {}, reviews: {} })
  let readable = true
  watch(key, () => {
    notebook.value = { marks: {}, reviews: {} }
    readable = true
    try {
      const raw = localStorage.getItem(key.value)
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (!isNotebook(parsed)) throw new Error('Invalid notebook')
      notebook.value = parsed
    } catch {
      readable = false
      toast.warning('本机记录暂时无法读取，原记录未删除。')
    }
  }, { immediate: true, flush: 'sync' })
  function persist(next: HospitalNotebook): boolean {
    if (!readable) {
      toast.error('原记录无法读取，为避免覆盖，请先保留浏览器中的原记录。')
      return false
    }
    try {
      localStorage.setItem(key.value, JSON.stringify(next))
      notebook.value = next
      return true
    } catch {
      toast.error('浏览器未能保存，请检查存储空间或隐私模式。')
      return false
    }
  }
  function mark(id: string, value: HospitalMark) {
    const marks = { ...notebook.value.marks }
    if (marks[id] === value) delete marks[id]
    else marks[id] = value
    persist({ ...notebook.value, marks })
  }
  function saveReview(review: HospitalReviewDraft) {
    return persist({ ...notebook.value, reviews: { ...notebook.value.reviews, [review.hospitalId]: review } })
  }
  function saveSuggestion(suggestion: HospitalSuggestion) {
    return persist({ ...notebook.value, suggestion })
  }
  return { notebook, owner, mark, saveReview, saveSuggestion }
}


function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
function isNotebook(value: unknown): value is HospitalNotebook {
  if (!isRecord(value) || !isRecord(value.marks) || !isRecord(value.reviews)) return false
  if (!Object.values(value.marks).every(mark => mark === 'want' || mark === 'visited')) return false
  const reviewsValid = Object.entries(value.reviews).every(([id, review]) => {
    if (!isRecord(review) || review.hospitalId !== id || !isRecord(review.ratings)) return false
    return ['month', 'duration', 'cost', 'outcome', 'text', 'savedAt'].every(key => typeof review[key] === 'string')
      && Array.isArray(review.tags) && review.tags.every(tag => typeof tag === 'string')
      && Object.values(review.ratings).every(score => typeof score === 'string' && /^[1-5]$/.test(score))
  })
  const suggestion = value.suggestion
  return reviewsValid && (suggestion === undefined || (isRecord(suggestion)
    && ['name', 'city', 'source', 'note'].every(key => typeof suggestion[key] === 'string')))
}
