import { computed, ref } from 'vue'
import {
  deleteHospitalReview,
  fetchHospitalReviews,
  fetchMyHospitalReviews,
  publishHospitalReview,
  reportHospitalReview,
  submitHospitalReviewAppeal,
  toggleReviewHelpful,
  uploadReviewImage,
} from '@/api/hospital'
import { useToast } from '@/composables/useToast'
import {
  EMPTY_STATS, type HospitalReview, type HospitalReviewAppealPayload, type HospitalReviewPayload,
  type HospitalStats, type ReviewReportReason, type ReviewSort, type ReviewTarget,
} from '@/types/hospital'

const PAGE_SIZE = 20

/** Public experiences with request isolation across hospital/filter changes. */
export function useHospitalReviews() {
  const toast = useToast()
  const reviews = ref<HospitalReview[]>([])
  const mine = ref<HospitalReview[]>([])
  const summary = ref<HospitalStats>({ ...EMPTY_STATS })
  const total = ref(0)
  const loading = ref(false)
  const loadingMore = ref(false)
  const publishing = ref(false)
  const sort = ref<ReviewSort>('recent')
  const activeTag = ref('')
  const uploadedUrls = ref<string[]>([])
  /** 本次会话已举报过的评价 id（前端幂等提示，后端仍以唯一约束为准） */
  const reportedIds = ref<Set<number>>(new Set())
  const error = ref('')
  let requestId = 0
  let currentId: number | null = null
  let currentTarget: ReviewTarget | '' = ''

  /** 前端标签筛选（后端只按 target 过滤，标签在已加载数据内过滤） */
  const visibleReviews = computed(() => activeTag.value
    ? reviews.value.filter(review => review.tags.includes(activeTag.value))
    : reviews.value)

  /** 重新加载第一页（切换医院、评价类型或排序时调用） */
  async function load(hospitalId: number | null, target: ReviewTarget | '' = '') {
    const request = ++requestId
    error.value = ''
    loadingMore.value = false
    currentId = hospitalId
    currentTarget = target
    reviews.value = []
    total.value = 0
    summary.value = { ...EMPTY_STATS }
    loading.value = true
    try {
      const result = await fetchHospitalReviews(hospitalId, { target, limit: PAGE_SIZE, offset: 0, sort: sort.value })
      if (request !== requestId) return
      reviews.value = result.items
      total.value = result.total
      summary.value = result.summary
    } catch {
      if (request === requestId) error.value = '经验加载失败，请重试；你仍可使用医院目录。'
    } finally {
      if (request === requestId) loading.value = false
    }
  }

  /** 追加下一页（「加载更多」） */
  async function loadMore() {
    if (loading.value || loadingMore.value || reviews.value.length >= total.value) return
    const request = requestId
    loadingMore.value = true
    try {
      const result = await fetchHospitalReviews(currentId, {
        target: currentTarget, limit: PAGE_SIZE, offset: reviews.value.length, sort: sort.value,
      })
      if (request !== requestId) return
      const known = new Set(reviews.value.map(r => r.id))
      reviews.value = [...reviews.value, ...result.items.filter(r => !known.has(r.id))]
      total.value = result.total
    } catch {
      toast.error('加载更多失败，请稍后重试')
    } finally {
      if (request === requestId) loadingMore.value = false
    }
  }

  async function setSort(next: ReviewSort) {
    if (sort.value === next) return
    sort.value = next
    await load(currentId, currentTarget)
  }

  async function loadMine() {
    try {
      mine.value = await fetchMyHospitalReviews()
    } catch {
      mine.value = []
    }
  }

  async function publish(hospitalId: number, payload: HospitalReviewPayload) {
    publishing.value = true
    try {
      const result = await publishHospitalReview(hospitalId, payload)
      toast.success(result.message || '评价已发布')
      return result
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || '发布失败，请稍后重试')
      return null
    } finally {
      publishing.value = false
    }
  }

  async function remove(reviewId: number, hospitalId: number | null) {
    try {
      await deleteHospitalReview(reviewId)
      toast.success('评价已删除')
      reviews.value = reviews.value.filter(r => r.id !== reviewId)
      total.value = Math.max(0, total.value - 1)
      mine.value = mine.value.filter(r => r.id !== reviewId)
      await load(hospitalId, currentTarget)
      return true
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || '删除失败，请稍后重试')
      return false
    }
  }

  /** 凭证图上传（≤3 张，逐张上传后返回 URL） */
  async function upload(file: File) {
    try {
      const url = await uploadReviewImage(file)
      uploadedUrls.value = [...uploadedUrls.value, url]
      return url
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || '图片上传失败，请稍后重试')
      return null
    }
  }

  /** 举报一条评价（一人一次；成功后本地标记，避免重复点击） */
  async function report(reviewId: number, reasonCode: ReviewReportReason, detail?: string) {
    try {
      const result = await reportHospitalReview(reviewId, reasonCode, detail)
      reportedIds.value = new Set([...reportedIds.value, reviewId])
      toast.success('举报已提交，我们会尽快复核')
      return result
    } catch (e) {
      const detailText = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detailText || '举报提交失败，请稍后重试')
      return null
    }
  }

  /** 提交申诉（被评价方 / 认为评价被误判的作者） */
  async function appeal(payload: HospitalReviewAppealPayload) {
    try {
      const result = await submitHospitalReviewAppeal(payload)
      toast.success('申诉已提交，我们会在 3 个工作日内反馈')
      return result
    } catch (e) {
      const detailText = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detailText || '申诉提交失败，请稍后重试')
      return null
    }
  }

  /** 有用投票（本地先更新，失败回滚） */
  async function markHelpful(review: HospitalReview) {
    const previous = { count: review.helpfulCount, mine: review.isHelpful }
    review.isHelpful = !review.isHelpful
    review.helpfulCount = Math.max(0, review.helpfulCount + (review.isHelpful ? 1 : -1))
    try {
      const result = await toggleReviewHelpful(review.id)
      review.helpfulCount = result.helpfulCount
      review.isHelpful = result.isHelpful
      return result
    } catch (e) {
      review.helpfulCount = previous.count
      review.isHelpful = previous.mine
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || '操作失败，请稍后重试')
      return null
    }
  }

  return {
    reviews, mine, summary, total, loading, loadingMore, publishing, sort, activeTag, visibleReviews, error,
    load, loadMore, setSort, loadMine, publish, remove, upload, markHelpful, report, appeal,
    uploadedUrls, reportedIds,
  }
}
