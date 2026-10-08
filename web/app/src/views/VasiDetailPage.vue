<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useVasiAssess } from '@/composables/useVasiAssess'
import { useVasiShare } from '@/composables/useVasiShare'
import { useToast } from '@/composables/useToast'
import AssessmentObservationResult from '@/components/tracker/AssessmentObservationResult.vue'
import AnnotationReviewPanel from '@/components/tracker/AnnotationReviewPanel.vue'
import { toProtectedFileUrl } from '@/utils/file-url'
const route = useRoute()
const router = useRouter()
const assess = useVasiAssess()
const share = useVasiShare(assess)
const toast = useToast()
const loading = ref(true)
const failed = ref(false)
const editing = ref(false)
async function load() {
  loading.value = true; failed.value = false
  try { await assess.loadAssessment(Number(route.params.id)) } catch { failed.value = true } finally { loading.value = false }
}
watch(() => route.params.id, load, { immediate: true })
async function confirm(payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string; uncertaintyReviewed: boolean }) {
  try { await assess.handleTwoLayerConfirm(payload.skinMaskDataUrl, payload.lesionMaskDataUrl, payload.uncertaintyReviewed); editing.value = false } catch { toast.error('范围未保存，请重试') }
}
function continueRecord() { router.push({ path: '/assessment', query: { baseline: String(route.params.id) } }) }
</script>
<template>
  <div class="page overflow-y-auto text-gray-900 dark:text-gray-100 lg:max-w-5xl" :class="editing ? 'record-edit-shell' : 'space-y-5 py-5 pb-8 md:py-6 md:pb-10'">
    <header class="flex shrink-0 items-center gap-2"><router-link :to="{ path: '/assessment', query: { view: 'records' } }" class="-ml-2 flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800" aria-label="返回白斑记录"><i class="ri-arrow-left-line text-xl" aria-hidden="true"></i></router-link><h1 class="page-title">白斑记录</h1></header>
    <p v-if="loading" role="status" class="text-sm text-gray-500 dark:text-gray-400">正在加载记录…</p>
    <section v-else-if="failed" class="card p-5 text-sm text-gray-600 dark:text-gray-300"><p>记录暂时无法加载，或你没有访问权限。</p><button class="btn-primary mt-4 min-h-[44px]" @click="load">重试</button></section>
    <template v-else-if="assess.lastAssessment.value">
      <AnnotationReviewPanel v-if="editing" fit-screen :image="toProtectedFileUrl(assess.lastAssessment.value.imageUrl)" :skin="assess.aiSkinLayerUrl.value" :lesion="assess.aiLesionLayerUrl.value" :uncertain="assess.lastAssessment.value.measurement?.annotation?.uncertain_pixels ? assess.lastAssessment.value.measurement.annotation.uncertain_layer_data_url : null" :selector="assess.lastAssessment.value.measurement?.annotation?.protocol === 'skin-seg-v2' ? assess.selectRegion : undefined" :outline="assess.lastAssessment.value.measurement?.annotation?.protocol === 'skin-seg-v2' ? assess.outlineRegions : undefined" :busy="assess.isSubmittingContour.value" @confirm="confirm" @cancel="editing = false" />
      <AssessmentObservationResult v-else :result="assess.lastAssessment.value" :skin-layer="assess.aiSkinLayerUrl.value" :lesion-layer="assess.aiLesionLayerUrl.value" :visual-features="assess.visualFeatures.value" :saved="assess.autoFinalized.value" @save="editing = true" :busy="assess.isSubmittingContour.value" @adjust="editing = true" @done="router.push({path:'/assessment',query:{view:'records'}})" @share="share.shareResult" @retake="continueRecord" />
    </template>
  </div>
</template>

<style scoped>
.record-edit-shell { --work-top-padding: 0px; display: flex; flex: none; flex-direction: column; gap: 8px; padding-top: 8px; padding-bottom: 8px; height: calc(100svh - 56px - 55px - env(safe-area-inset-bottom, 0px) - var(--work-top-padding)); overflow: hidden; }
:global(html[data-ios] .record-edit-shell) { --work-top-padding: env(safe-area-inset-top, 0px); }
@media (min-width: 768px) { .record-edit-shell { height: calc(100svh - 56px - var(--work-top-padding)); } }
</style>
