import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { trackClick } from '@/composables/useTracking'
import { useHospitalReviews } from '@/composables/useHospitalReviews'
import type {
  HospitalReview, HospitalReviewDraft, HospitalReviewPayload, HospitalView,
  ReviewReportReason, ReviewSort, ReviewTarget,
} from '@/types/hospital'

type Reviews = ReturnType<typeof useHospitalReviews>

export const REPORT_REASONS: { id: ReviewReportReason; label: string }[] = [
  { id: 'fake', label: '信息不实 / 非亲身经历' },
  { id: 'abuse', label: '人身攻击 / 侮辱性言辞' },
  { id: 'privacy', label: '泄露隐私' },
  { id: 'ad', label: '广告引流 / 留联系方式' },
  { id: 'promotion', label: '疗效夸大或推荐' },
  { id: 'other', label: '其他' },
]

/**
 * 就医经验评价交互流：发布 / 举报 / 有用 / 删除 / 申诉的弹窗状态与提交逻辑。
 * 主页跨院经验流（hospitalId() => null）与医院详情页（单院）共用。
 */
export function useHospitalReviewFlow(
  reviews: Reviews,
  options: {
    hospitalId: () => number | null
    reloadRegistry: () => Promise<void>
  },
) {
  const auth = useAuthStore()
  const toast = useToast()
  const router = useRouter()

  const target = ref<ReviewTarget | ''>('')
  const modal = ref<'composer' | 'report' | ''>('')
  const composerHospital = ref<HospitalView | null>(null)
  const composerTarget = ref<ReviewTarget>('hospital')
  const composerDraft = ref<HospitalReviewDraft | undefined>(undefined)
  const reportTarget = ref<HospitalReview | null>(null)
  const reportReason = ref<ReviewReportReason>('fake')
  const pendingRemoval = ref<number | null>(null)

  function openComposer(hospital: HospitalView, targetValue: ReviewTarget = 'hospital', draft?: HospitalReviewDraft) {
    if (!hospital.id) { toast.warning('当前展示的是离线目录，联网后即可发布评价。'); return false }
    if (!auth.isLoggedIn) { auth.showLoginModal = true; return false }
    composerHospital.value = hospital
    composerTarget.value = targetValue
    composerDraft.value = draft
    modal.value = 'composer'
    return true
  }

  async function submitReview(payload: HospitalReviewPayload) {
    const hospital = composerHospital.value
    if (!hospital?.id) return
    const result = await reviews.publish(hospital.id, payload)
    if (!result) return
    trackClick('hospital_review_publish', '发布评价', {
      target: payload.target,
      has_images: (payload.images?.length ?? 0) > 0,
      detail_score: result.review.detailScore,
    })
    modal.value = ''
    composerDraft.value = undefined
    await options.reloadRegistry()
    await reviews.load(options.hospitalId(), target.value)
    await reviews.loadMine()
  }

  async function onTargetChange(next: ReviewTarget | '') {
    target.value = next
    reviews.activeTag.value = ''
    await reviews.load(options.hospitalId(), next)
  }

  async function onSortChange(next: ReviewSort) {
    await reviews.setSort(next)
  }

  function onTagSelect(tag: string) {
    reviews.activeTag.value = tag
    if (tag) trackClick('hospital_tag_filter', tag)
  }

  async function onHelpful(review: HospitalReview) {
    const result = await reviews.markHelpful(review)
    if (result) trackClick('hospital_review_helpful', review.isHelpful ? '点有用' : '取消有用', { review_id: review.id })
  }

  function openReport(review: HospitalReview) {
    if (!auth.isLoggedIn) { auth.showLoginModal = true; return }
    reportTarget.value = review
    reportReason.value = 'fake'
    modal.value = 'report'
    trackClick('hospital_review_report_open', '打开举报', { review_id: review.id })
  }

  async function submitReport() {
    const targetReview = reportTarget.value
    if (!targetReview) return
    const result = await reviews.report(targetReview.id, reportReason.value)
    if (result) {
      trackClick('hospital_review_report', '提交举报', { review_id: targetReview.id, reason: reportReason.value })
      modal.value = ''
      reportTarget.value = null
    }
  }

  function closeReport() {
    modal.value = ''
    reportTarget.value = null
  }

  /** 申诉：带评价编号跳到公开申诉页（《民法典》第 1028 条救济通道） */
  function openAppeal(review?: HospitalReview) {
    trackClick('hospital_review_appeal_open', '打开申诉', { review_id: review?.id ?? 0 })
    router.push({ name: 'hospital-appeal', query: review ? { review: String(review.id) } : {} })
  }

  function confirmRemoval(id: number) {
    pendingRemoval.value = id
  }

  async function doRemove() {
    const id = pendingRemoval.value
    pendingRemoval.value = null
    if (id && await reviews.remove(id, options.hospitalId())) await options.reloadRegistry()
  }

  return {
    target, modal, composerHospital, composerTarget, composerDraft,
    reportTarget, reportReason, pendingRemoval,
    openComposer, submitReview, onTargetChange, onSortChange, onTagSelect, onHelpful,
    openReport, submitReport, closeReport, openAppeal, confirmRemoval, doRemove,
  }
}
