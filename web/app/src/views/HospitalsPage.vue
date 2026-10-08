<script setup lang="ts">
/**
 * 就医经验主页：目录即首页。
 * 动线：找医院 → 进详情页看资料/经验 → 在详情页写评价；跨院经验流默认折叠，先看目录。
 * 数据分层：view 只使用 composable（useHospital*），不直接调用 api/*。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import siteModules from '../../../shared/site-modules.json'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import { useRoute, useRouter } from 'vue-router'
import { useHospitalNotebook } from '@/composables/useHospitalNotebook'
import { useHospitalRegistry } from '@/composables/useHospitalRegistry'
import { useHospitalDirectory } from '@/composables/useHospitalDirectory'
import { useHospitalReviews } from '@/composables/useHospitalReviews'
import { REPORT_REASONS, useHospitalReviewFlow } from '@/composables/useHospitalReviewFlow'
import { trackClick } from '@/composables/useTracking'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import HospitalPicker from '@/components/hospitals/HospitalPicker.vue'
import HospitalQuickReviewCta from '@/components/hospitals/HospitalQuickReviewCta.vue'
import HospitalCreateForm from '@/components/hospitals/HospitalCreateForm.vue'
import HospitalReviewBoard from '@/components/hospitals/HospitalReviewBoard.vue'
import HospitalDialog from '@/components/hospitals/HospitalDialog.vue'
import HospitalCompare from '@/components/hospitals/HospitalCompare.vue'
import HospitalReportDialog from '@/components/hospitals/HospitalReportDialog.vue'
import type { HospitalCreatePayload, HospitalFilterState, HospitalMark, HospitalView } from '@/types/hospital'

const { notebook, mark } = useHospitalNotebook()
const { hospitals, offline, loading: registryLoading, error: registryError, load: loadRegistry,
  create: createHospital, reviewTotal, communityTotal } = useHospitalRegistry()
const { query, province, city, district, feature, onlyMarked, onlyReviewed, comparisonKeys,
  provinces, cities, districts, features, filtered, compared, coverage,
  total: directoryTotal, compare } = useHospitalDirectory(hospitals, notebook)
const hospitalReviews = useHospitalReviews()
const { reviews: feedReviews, visibleReviews, summary, total: feedTotal, loading: feedLoading, loadingMore,
  sort, activeTag, load: loadReviews, loadMore, reportedIds, error: feedError } = hospitalReviews
const { target, modal: flowModal, reportTarget, reportReason, pendingRemoval,
  onTargetChange, onSortChange, onTagSelect, onHelpful,
  openReport, submitReport, closeReport, openAppeal, confirmRemoval, doRemove,
} = useHospitalReviewFlow(hospitalReviews, { hospitalId: () => null, reloadRegistry: loadRegistry })
const auth = useAuthStore()
const toast = useToast()
const route = useRoute()
const router = useRouter()

const pageModal = ref<'create' | 'compare' | ''>('')
const quickPickerOpen = ref(false)
const feedRequested = ref(false)
const visitedPrompt = ref<HospitalView | null>(null)
const pickerSection = ref<HTMLElement>()
const hospitalLabel = siteModules.modules.find(module => module.path === '/hospitals')?.label ?? '就医经验'

const filters = computed<HospitalFilterState>({
  get: () => ({
    query: query.value, province: province.value, city: city.value, district: district.value,
    feature: feature.value, onlyMarked: onlyMarked.value, onlyReviewed: onlyReviewed.value,
  }),
  set: value => {
    query.value = value.query
    province.value = value.province
    city.value = value.city
    district.value = value.district
    feature.value = value.feature
    onlyMarked.value = value.onlyMarked
    onlyReviewed.value = value.onlyReviewed
  },
})

function openDetail(hospital: HospitalView) {
  trackClick('hospital_detail_open', '目录卡片进详情', { hospital: hospital.key })
  router.push({ name: 'hospital-detail', params: { key: hospital.key } })
}
function onMark(key: string, value: HospitalMark) {
  mark(key, value)
  if (value !== 'visited') { visitedPrompt.value = null; return }
  const hospital = hospitals.value.find(h => h.key === key) ?? null
  visitedPrompt.value = hospital
  if (hospital) trackClick('hospital_scene_entry', '标记去过后引导', { from: 'visited', hospital: hospital.key })
}
function startFromVisited() {
  const hospital = visitedPrompt.value
  if (!hospital) return
  router.push({ name: 'hospital-detail', params: { key: hospital.key }, query: { write: '1', from: 'visited' } })
}
function openQuickReview() {
  trackClick('hospital_quick_review_open', '首屏写评价入口', { scene: 'directory' })
  quickPickerOpen.value = true
}
function pickForWriting(hospital: HospitalView) {
  quickPickerOpen.value = false
  router.push({ name: 'hospital-detail', params: { key: hospital.key }, query: { write: '1' } })
}
async function expandFeed() {
  feedRequested.value = true
  await loadReviews(null, target.value)
  trackClick('hospital_feed_expand', '展开跨院经验流', {})
}
async function submitCreate(payload: HospitalCreatePayload) {
  try {
    const created = await createHospital(payload)
    pageModal.value = ''
    toast.success(`已创建「${created.name}」，现在可以写第一条评价了。`)
    router.push({ name: 'hospital-detail', params: { key: created.key } })
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    toast.error(detail || '创建失败，请稍后重试')
  }
}

watch(() => auth.isLoggedIn, loggedIn => {
  if (loggedIn && feedRequested.value) void hospitalReviews.loadMine()
})
watch(() => auth.user?.id, () => {
  if (!feedRequested.value) return
  hospitalReviews.reviews.value = []
  hospitalReviews.reportedIds.value = new Set()
  void loadReviews(null, target.value)
})

onMounted(async () => {
  await loadRegistry()
  // 旧链接兼容：?hospital=key → 详情页
  const presetKey = String(route.query.hospital ?? '')
  if (presetKey) {
    const found = hospitals.value.find(h => h.key === presetKey || h.slug === presetKey)
    if (found) {
      const { hospital: _legacy, ...rest } = route.query
      router.replace({ name: 'hospital-detail', params: { key: found.key }, query: rest })
      return
    }
  }
  if (route.query.write) {
    trackClick('hospital_scene_entry', '场景入口进入写评价', { from: String(route.query.from ?? 'link') })
    quickPickerOpen.value = true
  }
})

let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({
    '@context': 'https://schema.org', '@type': 'CollectionPage', name: hospitalLabel,
    description: '白癜风病友的医院目录与就诊经历分享，按省市查找医院，阅读病友亲身经历',
    url: `${location.origin}/hospitals`,
  })
  document.head.appendChild(schema)
})
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div class="page pb-8 pt-4 text-gray-900 dark:text-gray-100 md:pt-6">
    <router-link to="/community" class="mb-2 inline-flex min-h-11 items-center gap-1 text-sm text-gray-500 hover:text-primary-700 dark:text-gray-400 dark:hover:text-primary-300"><i class="ri-arrow-left-s-line" aria-hidden="true"></i>返回发现</router-link>
    <header class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div class="min-w-0">
        <p class="text-xs font-semibold tracking-widest text-primary-700 dark:text-primary-300">{{ hospitalLabel }} · 病友互助</p>
        <h1 class="page-title mt-1">找医院，看病友经验</h1>
      </div>
      <button class="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white transition-colors hover:bg-primary-700" @click="openQuickReview"><i class="ri-edit-2-line" aria-hidden="true" />分享就诊经历</button>
    </header>
    <p class="mb-4 text-xs leading-5 text-gray-500 dark:text-gray-400">
      已收录 <strong class="text-gray-900 dark:text-gray-100">{{ hospitals.length }}</strong> 家医院 · {{ coverage }} 个省级地区 · {{ reviewTotal }} 条病友经验<template v-if="communityTotal"> · {{ communityTotal }} 家病友补充</template><template v-if="offline"> · 离线目录</template>。收录不代表推荐。
    </p>
    <p v-if="registryError" role="status" class="mb-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">{{ registryError }}（发布经验需要联网）</p>

    <div ref="pickerSection" class="space-y-4">
      <HospitalPicker
        v-model="filters" :hospitals="filtered" :all-hospitals="hospitals" :total="directoryTotal" :provinces="provinces"
        :cities="cities" :districts="districts" :features="features" :marks="notebook.marks"
        :comparison-keys="comparisonKeys" :loading="registryLoading"
        @open="openDetail" @mark="onMark" @compare="compare" @create="pageModal = 'create'" @write="pickForWriting"
      />
      <div v-if="visitedPrompt" class="card flex flex-wrap items-center gap-3 p-4 dark:bg-gray-900">
        <p class="min-w-0 flex-1 text-sm">已标记去过「{{ visitedPrompt.name }}」。留下这次就诊中值得提醒病友的事吧。</p>
        <button class="min-h-11 px-3 text-primary-700 dark:text-primary-300" @click="startFromVisited">写这次经历</button>
        <button class="min-h-11 px-2 text-sm text-gray-500" @click="visitedPrompt = null">以后再说</button>
      </div>
    </div>

    <section v-if="reviewTotal > 0" aria-labelledby="feed-title" class="mt-6">
      <div class="mb-3 flex items-center justify-between gap-3">
        <h2 id="feed-title" class="text-base font-semibold">病友们的最新经验<span class="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">共 {{ reviewTotal }} 条</span></h2>
        <button v-if="!feedRequested" class="min-h-11 rounded-xl border border-primary-200 px-4 text-sm font-medium text-primary-700 dark:border-primary-800 dark:text-primary-300" @click="expandFeed">展开看看<i class="ri-arrow-down-s-line ml-1" /></button>
        <button v-else class="min-h-11 px-3 text-sm text-gray-500 dark:text-gray-400" @click="feedRequested = false">收起</button>
      </div>
      <HospitalReviewBoard
        v-if="feedRequested"
        :hospital="null" :reviews="visibleReviews" :loaded-count="feedReviews.length"
        :summary="summary" :total="feedTotal" :target="target" :sort="sort" :active-tag="activeTag"
        :loading="feedLoading" :error="feedError" :is-logged-in="auth.isLoggedIn" :loading-more="loadingMore"
        :reported-ids="[...reportedIds]"
        @update:target="onTargetChange" @update:tag="onTagSelect" @update:sort="onSortChange"
        @browse="pickerSection?.scrollIntoView({ behavior: 'smooth', block: 'start' })"
        @write="openQuickReview" @login="auth.showLoginModal = true"
        @remove="confirmRemoval" @helpful="onHelpful" @report="openReport" @appeal="openAppeal"
        @more="loadMore" @clear="() => {}" @retry="loadReviews(null, target)"
      />
    </section>

    <div v-if="comparisonKeys.length" class="sticky bottom-24 z-20 mt-5 flex flex-wrap items-center gap-3 rounded-xl border border-primary-200 bg-white p-3 shadow-lg md:bottom-4 dark:border-primary-800 dark:bg-gray-900">
      <p class="flex-1 text-xs">已选 {{ comparisonKeys.length }} / 3 家医院资料</p>
      <button class="min-h-11 px-2 text-xs text-gray-500" @click="comparisonKeys = []">清空对比</button>
      <button :disabled="comparisonKeys.length < 2" class="min-h-11 rounded-lg bg-primary-600 px-4 text-xs text-white disabled:opacity-40" @click="pageModal = 'compare'">{{ comparisonKeys.length < 2 ? '再选一家' : '对比资料' }}</button>
    </div>

    <footer class="mt-6 border-t border-gray-200 pt-4 text-xs leading-6 text-gray-500 dark:border-gray-800 dark:text-gray-400">
      <p>医院信息以官方发布为准，病友补充资料需核实。个人经历不代表医疗水平或治疗效果。</p>
      <div class="flex flex-wrap gap-4">
        <RouterLink class="inline-flex min-h-11 items-center underline" to="/hospitals/rules">社区公约</RouterLink>
        <RouterLink class="inline-flex min-h-11 items-center underline" to="/hospitals/appeal">评价申诉</RouterLink>
        <RouterLink class="inline-flex min-h-11 items-center underline" to="/hospitals/treatments">治疗知识</RouterLink>
        <RouterLink class="inline-flex min-h-11 items-center underline" to="/privacy">隐私保护</RouterLink>
      </div>
      <MedicalDisclaimer variant="inline" message="本文不构成医疗建议。诊疗安排以医院官方信息及面诊为准，个人经历不代表他人的治疗效果。" />
    </footer>

    <HospitalDialog v-if="quickPickerOpen" title="先选择你就诊的医院" @close="quickPickerOpen = false">
      <HospitalQuickReviewCta
        :selected="null" :hospitals="hospitals" :marks="notebook.marks" :is-logged-in="auth.isLoggedIn"
        :open="true" @update:open="quickPickerOpen = $event" @pick="pickForWriting"
        @login="auth.showLoginModal = true"
        @browse="quickPickerOpen = false; pickerSection?.scrollIntoView({ behavior: 'smooth', block: 'start' })"
      />
    </HospitalDialog>
    <HospitalDialog v-if="pageModal === 'create'" title="补充一家医院" @close="pageModal = ''">
      <HospitalCreateForm :province="province" :city="city" :district="district" :name="query" @save="submitCreate" />
    </HospitalDialog>
    <HospitalDialog v-if="pageModal === 'compare'" title="医院对比" wide @close="pageModal = ''">
      <HospitalCompare :hospitals="compared" @remove="compare" />
    </HospitalDialog>
    <HospitalReportDialog
      v-if="flowModal === 'report' && reportTarget" :review="reportTarget" :reasons="REPORT_REASONS"
      :reason="reportReason" @update:reason="reportReason = $event" @submit="submitReport" @close="closeReport"
    />
    <ConfirmDialog
      :visible="pendingRemoval !== null" title="删除这条评价？" message="删除后其他病友将看不到这条内容，操作不可撤销。"
      confirm-text="删除" @confirm="doRemove" @cancel="pendingRemoval = null"
    />
  </div>
</template>
