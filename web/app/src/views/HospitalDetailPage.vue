<script setup lang="ts">
/**
 * 医院详情页：单院资料 + 该院病友经验 + 写评价（全站唯一评价撰写入口）。
 * 目录卡片、首屏 CTA、标记「去过」的引导最终都汇聚到这里。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { useRoute, useRouter } from 'vue-router'
import { useHospitalNotebook } from '@/composables/useHospitalNotebook'
import { useHospitalRegistry } from '@/composables/useHospitalRegistry'
import { useHospitalReviews } from '@/composables/useHospitalReviews'
import { REPORT_REASONS, useHospitalReviewFlow } from '@/composables/useHospitalReviewFlow'
import { trackClick } from '@/composables/useTracking'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import HospitalReviewBoard from '@/components/hospitals/HospitalReviewBoard.vue'
import HospitalReviewComposer from '@/components/hospitals/HospitalReviewComposer.vue'
import HospitalDialog from '@/components/hospitals/HospitalDialog.vue'
import HospitalSuggestionForm from '@/components/hospitals/HospitalSuggestionForm.vue'
import HospitalReportDialog from '@/components/hospitals/HospitalReportDialog.vue'
import type { HospitalMark, HospitalSuggestion } from '@/types/hospital'

const CHECKLIST = ['应该挂普通皮肤科、专病门诊，还是专家门诊？', '拟定方案的目标、评估时间和可能的不适是什么？', '检查、治疗、复诊分别收费多少，哪些可医保结算？', '需要多久复诊一次，能否在当地接续治疗？']

const { notebook, mark, saveSuggestion } = useHospitalNotebook()
const { hospitals, loading: registryLoading, load: loadRegistry } = useHospitalRegistry()
const hospitalReviews = useHospitalReviews()
const { reviews, visibleReviews, summary, total: reviewTotalCount, loading: reviewsLoading,
  loadingMore, publishing, sort, activeTag, load: loadReviews, loadMore, loadMine,
  upload: uploadReviewImage, reportedIds, error: reviewsError } = hospitalReviews

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const hospital = computed(() => {
  const key = String(route.params.key ?? '')
  return hospitals.value.find(h => h.key === key || h.slug === key) ?? null
})

const { target, modal: flowModal, composerTarget, composerDraft, reportTarget, reportReason,
  pendingRemoval, openComposer, submitReview, onTargetChange, onSortChange, onTagSelect, onHelpful,
  openReport, submitReport, closeReport, openAppeal, confirmRemoval, doRemove,
} = useHospitalReviewFlow(hospitalReviews, { hospitalId: () => hospital.value?.id ?? null, reloadRegistry: loadRegistry })

const pageModal = ref<'suggestion' | ''>('')
const visitedPrompt = ref(false)

const currentMark = computed(() => hospital.value ? notebook.value.marks[hospital.value.key] : undefined)
const draft = computed(() => hospital.value ? notebook.value.reviews[hospital.value.key] : undefined)
// v3：不展示任何平均分/星级（避免被当作医院得分与排名依据）
const mentionedTags = computed(() => (hospital.value?.stats.topTags ?? []).slice(0, 4).map(item => item.tag))

function onMark(value: HospitalMark) {
  const targetHospital = hospital.value
  if (!targetHospital) return
  mark(targetHospital.key, value)
  visitedPrompt.value = notebook.value.marks[targetHospital.key] === 'visited'
  if (visitedPrompt.value) trackClick('hospital_scene_entry', '标记去过后引导', { from: 'visited', hospital: targetHospital.key })
}
function writeReview(targetValue: 'hospital' | 'experience' = 'hospital') {
  const targetHospital = hospital.value
  if (!targetHospital) return
  visitedPrompt.value = false
  openComposer(targetHospital, targetValue)
}
function useDraft() {
  const targetHospital = hospital.value
  if (!targetHospital || !draft.value) return
  openComposer(targetHospital, 'experience', draft.value)
}
function saveInfo(info: HospitalSuggestion) {
  if (saveSuggestion(info)) { toast.success('补充纠错已保存到本机，尚未公开。'); pageModal.value = '' }
}
function backToDirectory() {
  router.push({ name: 'hospitals' })
}

async function loadForHospital() {
  const targetHospital = hospital.value
  if (!targetHospital) return
  document.title = `${targetHospital.name} - 就医经验 - SubSkin`
  if (!targetHospital.id) return
  await loadReviews(targetHospital.id, target.value)
  if (auth.isLoggedIn) await loadMine()
}

onMounted(async () => {
  await loadRegistry()
  await loadForHospital()
  if (route.query.write && hospital.value) {
    trackClick('hospital_scene_entry', '场景入口进入写评价', { from: String(route.query.from ?? 'link') })
    openComposer(hospital.value, 'experience')
  }
})
// 同组件内切换医院（如从推荐链接跳到另一家）
watch(() => route.params.key, async (next, prev) => {
  if (!next || next === prev) return
  activeTag.value = ''
  await loadForHospital()
})

let schema: HTMLScriptElement | undefined
watch(hospital, targetHospital => {
  schema?.remove()
  schema = undefined
  if (!targetHospital) return
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({
    '@context': 'https://schema.org', '@type': 'Hospital', name: targetHospital.name,
    address: {
      '@type': 'PostalAddress', addressRegion: targetHospital.province,
      addressLocality: targetHospital.city, streetAddress: targetHospital.address || targetHospital.district,
    },
    url: `${location.origin}/hospitals/${targetHospital.key}`,
    ...(targetHospital.source ? { sameAs: targetHospital.source } : {}),
  })
  document.head.appendChild(schema)
}, { immediate: true })
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div class="page pb-8 pt-4 text-gray-900 dark:text-gray-100 md:pt-6">
    <nav aria-label="返回目录" class="mb-4">
      <RouterLink :to="{ name: 'hospitals' }" class="inline-flex min-h-11 items-center gap-1 text-sm text-gray-500 hover:text-primary-700 dark:text-gray-400 dark:hover:text-primary-300"><i class="ri-arrow-left-line" />返回医院目录</RouterLink>
    </nav>

    <LoadingSpinner v-if="registryLoading && !hospital" message="正在加载医院资料…" />
    <EmptyState
      v-else-if="!hospital" icon="ri-hospital-line" title="没有找到这家医院"
      description="链接可能已失效，回目录重新查找，或补充一家医院。"
      action-label="返回医院目录" @action="backToDirectory"
    />

    <template v-else>
      <header class="card p-4 dark:bg-gray-900 md:p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="w-full min-w-0 sm:w-auto sm:flex-1">
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
              <span>{{ hospital.province }} · {{ hospital.city }}<template v-if="hospital.district"> · {{ hospital.district }}</template></span>
              <span v-if="hospital.kind">{{ hospital.kind }}</span>
              <span
                class="rounded-md px-1.5 py-0.5"
                :class="hospital.origin === 'community' ? 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' : 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300'"
              >{{ hospital.origin === 'community' ? '病友补充 · 官方信息待核实' : '平台收录 · 附官方来源' }}</span>
            </div>
            <h1 class="page-title mt-1.5">{{ hospital.name }}</h1>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ hospital.department || '科室待确认' }}</p>
          </div>
          <div class="flex shrink-0 items-center gap-1">
            <button :aria-pressed="currentMark === 'want'" class="min-h-11 rounded-lg px-3 text-sm text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800" :class="{ 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300': currentMark === 'want' }" @click="onMark('want')"><i :class="currentMark === 'want' ? 'ri-bookmark-fill' : 'ri-bookmark-line'" /> 想去</button>
            <button :aria-pressed="currentMark === 'visited'" class="min-h-11 rounded-lg px-3 text-sm text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800" :class="{ 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300': currentMark === 'visited' }" @click="onMark('visited')"><i class="ri-map-pin-user-line" /> 去过</button>
          </div>
        </div>
        <div v-if="visitedPrompt" class="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-primary-50 p-3 dark:bg-primary-900">
          <p class="min-w-0 flex-1 text-sm">已标记去过。留下这次就诊中值得提醒病友的事吧。</p>
          <button class="min-h-11 px-3 text-sm text-primary-700 dark:text-primary-300" @click="writeReview('experience')">写这次经历</button>
          <button class="min-h-11 px-2 text-sm text-gray-500" @click="visitedPrompt = false">以后再说</button>
        </div>
      </header>

      <!-- 桌面端两栏：左侧病友经验（主内容），右侧医院资料；手机端资料在前 -->
      <div class="mt-4 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(300px,380px)] lg:items-start lg:gap-6">
      <section aria-labelledby="hospital-info-title" class="card p-4 dark:bg-gray-900 md:p-5 lg:order-2">
        <h2 id="hospital-info-title" class="mb-3 text-lg font-semibold">医院资料</h2>
        <p v-if="hospital.address" class="rounded-xl bg-gray-50 p-3 text-xs leading-6 text-gray-600 dark:bg-gray-800 dark:text-gray-300"><i class="ri-map-pin-line mr-1" />{{ hospital.address }}</p>
        <p v-if="hospital.summary" class="mt-3 text-sm leading-7 text-gray-600 dark:text-gray-300">{{ hospital.summary }}</p>

        <div class="mt-3 flex flex-wrap gap-3 text-xs">
          <span class="rounded-lg bg-gray-100 px-3 py-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300">病友评价 {{ hospital.stats.reviewCount }} 条</span>
          <span v-if="mentionedTags.length" class="rounded-lg bg-gray-100 px-3 py-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300">常被提到：{{ mentionedTags.join('、') }}</span>
          <span class="rounded-lg bg-gray-100 px-3 py-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300">医生评价 {{ hospital.stats.doctorCount }}</span>
          <span class="rounded-lg bg-gray-100 px-3 py-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300">治疗方案 {{ hospital.stats.treatmentCount }}</span>
        </div>

        <div v-if="hospital.features.length" class="mt-3 flex flex-wrap gap-1.5">
          <span v-for="tag in hospital.features" :key="tag" class="rounded-md bg-gray-100 px-2 py-1 text-[11px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">{{ tag }}</span>
        </div>

        <div class="mt-4 rounded-xl bg-gray-50 p-4 dark:bg-gray-800">
          <h3 class="text-sm font-medium">官方资料</h3>
          <p class="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400">出诊、院区、设备、医保和费用可能变化，请出发前核实。查看官方科室介绍可了解医生团队与诊疗方向。</p>
          <a v-if="hospital.source" :href="hospital.source" target="_blank" rel="noopener noreferrer" class="mt-2 inline-flex min-h-11 items-center text-sm font-medium text-primary-700 dark:text-primary-300">查看医院官方来源 <i class="ri-external-link-line ml-1" /></a>
          <p class="text-[11px] text-gray-400">
            <template v-if="hospital.checkedAt">资料核对：{{ hospital.checkedAt }} · </template>收录不代表推荐或排名
          </p>
        </div>

        <details class="mt-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
          <summary class="min-h-11 cursor-pointer text-sm font-medium leading-[44px]">就诊前，带着这 4 个问题</summary>
          <ul class="mt-2 space-y-3">
            <li v-for="(item, i) in CHECKLIST" :key="item" class="flex gap-2 text-xs leading-6 text-gray-600 dark:text-gray-300"><span class="text-primary-600">0{{ i + 1 }}</span>{{ item }}</li>
          </ul>
          <p class="mt-3 text-xs text-gray-500">本文不构成医疗建议。</p>
        </details>

        <div v-if="draft" class="mt-4 rounded-xl bg-primary-50 p-4 dark:bg-primary-900">
          <h3 class="text-sm font-medium">你有一条保存在本机的经历草稿 · 未公开</h3>
          <p class="mt-2 text-xs text-gray-500">{{ draft.month }} · {{ draft.duration || '时长未填写' }} · {{ draft.outcome || '效果未填写' }}</p>
          <p class="mt-3 whitespace-pre-wrap break-words text-sm leading-7">{{ draft.text }}</p>
          <button class="mt-3 min-h-11 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white" @click="useDraft">用这份草稿公开分享</button>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-3">
          <button class="min-h-11 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white" @click="writeReview('hospital')"><i class="ri-edit-line mr-1" />写评价 / 分享经历</button>
          <button class="min-h-11 px-2 text-xs text-gray-500 underline" @click="pageModal = 'suggestion'">信息有变化？填写纠错草稿</button>
        </div>
      </section>

      <div class="mt-4 min-w-0 lg:order-1 lg:mt-0">
        <p v-if="!hospital.id" role="status" class="rounded-xl bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">当前展示的是离线目录，联网后可查看该院病友经验并发布评价。</p>
        <HospitalReviewBoard
          v-else
          :hospital="hospital" :reviews="visibleReviews" :loaded-count="reviews.length"
          :summary="summary" :total="reviewTotalCount" :target="target" :sort="sort" :active-tag="activeTag"
          :loading="reviewsLoading" :error="reviewsError" :is-logged-in="auth.isLoggedIn" :loading-more="loadingMore"
          :reported-ids="[...reportedIds]"
          @update:target="onTargetChange" @update:tag="onTagSelect" @update:sort="onSortChange"
          @browse="backToDirectory" @write="writeReview('experience')" @login="auth.showLoginModal = true"
          @remove="confirmRemoval" @helpful="onHelpful" @report="openReport" @appeal="openAppeal"
          @more="loadMore" @clear="backToDirectory" @retry="loadReviews(hospital.id, target)"
        />
      </div>
      </div>

      <footer class="mt-6 border-t border-gray-200 pt-4 text-xs leading-6 text-gray-500 dark:border-gray-800 dark:text-gray-400">
        <p>医院信息以官方发布为准，病友补充资料需核实。个人经历不代表医疗水平或治疗效果。</p>
        <div class="flex flex-wrap gap-4">
          <RouterLink class="inline-flex min-h-11 items-center underline" to="/hospitals/rules">社区公约</RouterLink>
          <RouterLink class="inline-flex min-h-11 items-center underline" to="/hospitals/appeal">评价申诉</RouterLink>
          <RouterLink class="inline-flex min-h-11 items-center underline" to="/privacy">隐私保护</RouterLink>
        </div>
        <MedicalDisclaimer variant="inline" message="本文不构成医疗建议。诊疗安排以医院官方信息及面诊为准，个人经历不代表他人的治疗效果。" />
      </footer>

      <HospitalDialog v-if="flowModal === 'composer'" :key="hospital.key" :title="`评价 ${hospital.name}`" @close="flowModal = ''">
        <HospitalReviewComposer
          :hospital="hospital" :initial-target="composerTarget" :draft="composerDraft"
          :publishing="publishing" :upload-image="uploadReviewImage"
          @save="submitReview" @cancel="flowModal = ''"
        />
      </HospitalDialog>
      <HospitalDialog v-if="pageModal === 'suggestion'" title="信息纠错（本机草稿）" @close="pageModal = ''">
        <HospitalSuggestionForm :hospital-name="hospital.name" :draft="notebook.suggestion" @save="saveInfo" />
      </HospitalDialog>
      <HospitalReportDialog
        v-if="flowModal === 'report' && reportTarget" :review="reportTarget" :reasons="REPORT_REASONS"
        :reason="reportReason" @update:reason="reportReason = $event" @submit="submitReport" @close="closeReport"
      />
      <ConfirmDialog
        :visible="pendingRemoval !== null" title="删除这条评价？" message="删除后其他病友将看不到这条内容，操作不可撤销。"
        confirm-text="删除" @confirm="doRemove" @cancel="pendingRemoval = null"
      />
    </template>
  </div>
</template>
