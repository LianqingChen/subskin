<script setup lang="ts">
import { computed } from 'vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import HospitalReviewCard from './HospitalReviewCard.vue'
import HospitalDimensionBars from './HospitalDimensionBars.vue'
import HospitalTagCloud from './HospitalTagCloud.vue'
import { RouterLink } from 'vue-router'
import type { HospitalReview, HospitalStats, HospitalView, ReviewSort, ReviewTarget } from '@/types/hospital'

/** 第二步：医院、医生、治疗方案、治疗经历的评价与分享（标签云 + 排序 + 公开列表 + 写评价入口）。 */
const props = defineProps<{
  hospital: HospitalView | null
  reviews: HospitalReview[]
  total: number
  loadedCount: number
  summary: HospitalStats
  target: ReviewTarget | ''
  sort: ReviewSort
  activeTag: string
  loading: boolean
  loadingMore?: boolean
  error?: string
  isLoggedIn: boolean
  /** 已举报过的评价 id（前端幂等提示，后端仍以唯一约束为准） */
  reportedIds?: number[]
}>()
const emit = defineEmits<{
  'update:target': [value: ReviewTarget | '']
  'update:tag': [value: string]
  'update:sort': [value: ReviewSort]
  write: []
  browse: []
  login: []
  remove: [id: number]
  helpful: [review: HospitalReview]
  report: [review: HospitalReview]
  appeal: [review: HospitalReview]
  more: []
  retry: []
  clear: []
}>()

const TABS: { id: ReviewTarget | ''; label: string }[] = [
  { id: '', label: '全部经验' },
  { id: 'hospital', label: '就诊流程' },
  { id: 'doctor', label: '沟通经历' },
  { id: 'treatment', label: '治疗方案' },
  { id: 'experience', label: '治疗经历' },
]
const tabs = computed(() => TABS.map(tab => ({ ...tab, count: countOf(tab.id) })))
function countOf(id: ReviewTarget | '') {
  if (id === '') return props.summary.reviewCount
  return props.summary.targets[id] ?? 0
}
// v3：板块顶部不再显示平均分，改为「6 维体验提及分布」（计数型，不做合并评分）
const filteredCount = computed(() => props.activeTag
  ? props.reviews.filter(r => r.tags.includes(props.activeTag)).length
  : props.reviews.length)
</script>

<template>
  <section aria-labelledby="hospital-review-title" class="card p-4 dark:bg-gray-900 md:p-5">
    <header class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 id="hospital-review-title" class="text-lg font-semibold md:text-xl">病友经验</h2>
        <p class="mt-1 text-sm leading-6 text-gray-500 dark:text-gray-400">
          <template v-if="hospital">正在看 <strong class="text-gray-700 dark:text-gray-200">{{ hospital.name }}</strong> 的就诊经历。</template>
          <template v-else>浏览各家医院的亲身经历，了解就诊过程、花费与需要留意的事。</template>
        </p>
      </div>
      <div v-if="hospital" class="flex items-center gap-2">
        <button class="min-h-11 px-2 text-sm text-primary-700 underline dark:text-primary-300" @click="emit('clear')">查看全部医院</button><span class="rounded-lg bg-gray-100 px-2 py-1 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">{{ summary.reviewCount }} 条病友评价</span>
      </div>
    </header>

    <div class="mb-4 grid gap-3 sm:grid-cols-2">
      <label class="text-sm text-gray-600 dark:text-gray-300">经验类型
        <select :value="target" class="mt-2 min-h-11 w-full rounded-xl border border-gray-200 bg-white px-3 dark:border-gray-700 dark:bg-gray-800" @change="emit('update:target', ($event.target as HTMLSelectElement).value as ReviewTarget | '')">
          <option v-for="tab in tabs" :key="tab.id" :value="tab.id">{{ tab.label }}{{ hospital && tab.count ? `（${tab.count}）` : '' }}</option>
        </select>
      </label>
      <div class="self-end rounded-xl bg-primary-50 p-3 text-xs leading-5 text-primary-800 dark:bg-primary-900 dark:text-primary-200">读经验时关注：何时就诊、花了多少时间、费用如何构成，以及当事人遇到了什么。</div>
    </div>
    <div>

      <!-- 固定免责条：不做医院间比较、不代表医疗水平（自拟，不伪称引自官方） -->
      <p class="mb-3 rounded-xl bg-gray-50 px-4 py-3 text-[11px] leading-5 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
        以下评价来自病友个人经历，<strong>不代表医疗水平评价</strong>，也不算疗效，仅供参考；个人经历不能作为疗效证据或就医推荐。
        如认为某条评价侵犯你的权益，可通过 <RouterLink class="underline" to="/hospitals/appeal">评价申诉</RouterLink> 提交，我们将在 3 个工作日内处理。
      </p>

      <HospitalDimensionBars v-if="hospital" class="mb-4" :items="summary.dimensionDistribution ?? []" :review-count="summary.reviewCount" />
      <HospitalTagCloud v-if="hospital" class="mb-4" :stats="summary" :active="activeTag" @select="emit('update:tag', $event)" />

      <div class="mb-4 flex flex-wrap items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 dark:bg-gray-800">
        <p class="flex-1 text-sm leading-6 text-gray-600 dark:text-gray-300">
          <template v-if="isLoggedIn">你的评价会公开显示，可随时删除。写下至少 20 字的亲身经历，其他信息可选填。</template>
          <template v-else>登录后即可发布评价，未登录也可以浏览全部公开评价。</template>
        </p>
        <button v-if="isLoggedIn" class="min-h-11 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white" @click="emit('write')"><i class="ri-edit-line mr-1" />分享就诊经历</button>
        <button v-else class="min-h-11 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white" @click="emit('login')">登录后写评价</button>
      </div>

      <div class="mb-3 flex flex-wrap items-center gap-2">
        <span class="text-xs text-gray-500 dark:text-gray-400">排序</span>
        <button v-for="option in [{ id: 'recent' as ReviewSort, label: '最新' }, { id: 'helpful' as ReviewSort, label: '最有用' }]" :key="option.id" :aria-pressed="sort === option.id" class="min-h-11 rounded-lg border px-3 text-xs" :class="sort === option.id ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-300'" @click="emit('update:sort', option.id)">{{ option.label }}</button>
        <span v-if="activeTag" class="text-sm text-gray-500 dark:text-gray-400">已加载的评价中，{{ filteredCount }} 条提到「{{ activeTag }}」<button class="min-h-11 px-2 text-primary-700 dark:text-primary-300" @click="emit('update:tag', '')">清除</button></span>
        <span class="ml-auto text-[11px] text-gray-400">有用票数只用于排列经验</span>
      </div>

      <LoadingSpinner v-if="loading" message="正在加载病友评价…" />
      <div v-else-if="error" role="status" class="rounded-xl bg-gray-50 p-4 text-sm dark:bg-gray-800">{{ error }}<button class="min-h-11 px-3 text-primary-700 underline dark:text-primary-300" @click="emit('retry')">重试经验</button></div>
      <div v-else-if="reviews.length" class="space-y-3">
        <HospitalReviewCard
          v-for="review in reviews" :key="review.id" :review="review" :show-hospital="!hospital"
          :reported="reportedIds?.includes(review.id) ?? false"
          @remove="emit('remove', $event)" @helpful="emit('helpful', $event)"
          @report="emit('report', $event)" @appeal="emit('appeal', $event)"
        />

      </div>
      <EmptyState v-else icon="ri-chat-smile-2-line" :title="activeTag ? '已加载的评价中暂无这个标签' : '还没有这类评价'" :description="activeTag ? '可以清除标签，或继续加载更多评价。' : '分享挂号、沟通或复诊经历，为病友提供参考。'" />
      <button v-if="!loading && total > loadedCount" :disabled="loadingMore" class="mt-4 min-h-11 w-full rounded-xl border border-gray-200 text-sm disabled:opacity-50 dark:border-gray-700" @click="emit('more')">{{ loadingMore ? '正在加载…' : `加载更多（还有 ${total - loadedCount} 条）` }}</button>
    </div>
  </section>
</template>
