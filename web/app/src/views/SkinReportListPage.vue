<script setup lang="ts">
/**
 * SkinReportListPage — 白斑变化报告列表
 * 顶部提供周报/月报快捷生成入口（基于可用性预览），列表按类型筛选。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSkinReports, getPeriodicPreview, createPeriodicReport } from '@/api/skin_report'
import type { SkinReportListItem, PeriodicPreviewItem } from '@/api/skin_report'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const toast = useToast()
const authStore = useAuthStore()
const reports = ref<SkinReportListItem[]>([])
const loading = ref(false)
const previews = ref<PeriodicPreviewItem[]>([])
const typeFilter = ref<'all' | 'comparison' | 'weekly' | 'monthly'>('all')
const generating = ref<Set<string>>(new Set())
let pollTimer: ReturnType<typeof setInterval> | null = null

// 访客也可能被小白管家引导到此页（报告属个人健康数据，需登录）；
// 未登录时显示登录引导，不发起会被 401 的请求
const isLoggedIn = computed(() => authStore.isLoggedIn)

const filteredReports = computed(() =>
  typeFilter.value === 'all'
    ? reports.value
    : reports.value.filter((r) => r.report_type === typeFilter.value),
)

const typeTabs = [
  { key: 'all', label: '全部' },
  { key: 'weekly', label: '周报' },
  { key: 'monthly', label: '月报' },
  { key: 'comparison', label: '对比报告' },
] as const

async function load() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const { data } = await getSkinReports({ limit: 50 })
    reports.value = data.items
  } catch {
    toast.show('加载报告失败', 'error')
  } finally {
    loading.value = false
  }
}

async function loadPreviews() {
  if (!isLoggedIn.value) return
  try {
    const { data } = await getPeriodicPreview()
    previews.value = data.items
  } catch {
    previews.value = []
  }
}

/** 生成周报/月报：后台异步，进入轮询直到状态不再是 generating */
async function generatePeriodic(item: PeriodicPreviewItem) {
  if (generating.value.has(item.label)) return
  generating.value.add(item.label)
  try {
    await createPeriodicReport({ period_type: item.period_type, anchor_date: item.period_start })
    toast.show('正在生成，约需 1-2 分钟', 'success')
    startPolling()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '生成失败，请稍后重试'
    toast.show(msg, 'error')
    generating.value.delete(item.label)
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await load()
    await loadPreviews()
    const hasGenerating = reports.value.some((r) => r.status === 'generating')
    if (!hasGenerating) {
      stopPolling()
      generating.value.clear()
    }
  }, 6000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function previewBusy(item: PeriodicPreviewItem) {
  return (
    generating.value.has(item.label) ||
    item.existing_status === 'generating' ||
    reports.value.some(
      (r) => r.id === item.existing_report_id && r.status === 'generating',
    )
  )
}

function previewDone(item: PeriodicPreviewItem) {
  return !!item.existing_report_id && item.existing_status === 'completed'
}

/** 快捷卡点击：已有报告→查看；可生成→生成 */
function handleQuick(item: PeriodicPreviewItem) {
  if (previewDone(item) && item.existing_report_id) {
    router.push({ name: 'skin-report-view', params: { id: item.existing_report_id } })
    return
  }
  generatePeriodic(item)
}

function trendStyle(trend?: string) {
  if (trend === '好转')
    return { cls: 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300', icon: 'ri-arrow-down-line' }
  if (trend === '加重')
    return { cls: 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300', icon: 'ri-arrow-up-line' }
  if (trend === '稳定')
    return { cls: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300', icon: 'ri-subtract-line' }
  return { cls: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300', icon: 'ri-question-line' }
}

function typeLabel(t: string) {
  if (t === 'weekly') return '周报'
  if (t === 'monthly') return '月报'
  return '对比报告'
}

function fmtDate(d: string | null) {
  return d ? d.slice(0, 10) : ''
}

onMounted(() => {
  load()
  loadPreviews()
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="srl-page">
    <header class="srl-header">
      <div class="srl-header__inner">
        <button class="srl-back" @click="router.push('/community')">
          <i class="ri-arrow-left-s-line"></i>
        </button>
        <h1 class="srl-header__title">白斑变化报告</h1>
        <button class="srl-new" @click="router.push({ name: 'skin-report-new' })">
          <i class="ri-add-line"></i>
        </button>
      </div>
    </header>

    <main class="srl-main">
      <LoadingSpinner v-if="loading" message="加载中..." />

      <EmptyState
        v-else-if="!isLoggedIn"
        icon="ri-lock-line"
        title="登录后查看你的白斑报告"
        description="白斑变化报告属于个人健康数据，需要登录后访问"
        action-label="登录 / 注册"
        @action="authStore.showLoginModal = true"
      />

      <template v-else>
        <!-- 周报/月报快捷生成 -->
        <div v-if="previews.length" class="srl-quick">
          <button
            v-for="p in previews"
            :key="p.label"
            class="srl-quick__card"
            :class="{ 'srl-quick__card--off': !p.can_generate && !previewDone(p) }"
            @click="p.can_generate || previewDone(p) ? handleQuick(p) : router.push({ name: 'skin-report-new' })"
          >
            <i
              class="srl-quick__icon"
              :class="p.period_type === 'weekly' ? 'ri-calendar-check-line' : 'ri-calendar-todo-line'"
            ></i>
            <div class="srl-quick__body">
              <div class="srl-quick__label">{{ p.label }}</div>
              <div class="srl-quick__meta">
                <template v-if="previewBusy(p)">
                  <i class="ri-loader-4-line ri-spin"></i> AI 分析中…
                </template>
                <template v-else-if="previewDone(p)">已生成 · 点击查看</template>
                <template v-else-if="p.can_generate">
                  {{ p.site_count }}个部位 {{ p.photo_count }}张照片可分析
                </template>
                <template v-else>本周期待新的白斑照片</template>
              </div>
            </div>
            <i
              v-if="!previewBusy(p) && (p.can_generate || previewDone(p))"
              class="ri-arrow-right-s-line srl-quick__arrow"
            ></i>
          </button>
        </div>

        <!-- 类型筛选 -->
        <div v-if="reports.length" class="srl-tabs">
          <button
            v-for="t in typeTabs"
            :key="t.key"
            class="srl-tab"
            :class="{ 'srl-tab--active': typeFilter === t.key }"
            @click="typeFilter = t.key"
          >
            {{ t.label }}
          </button>
        </div>

        <EmptyState
          v-if="reports.length === 0"
          icon="ri-file-chart-2-line"
          title="还没有报告"
          description="上传白斑照片生成周报/月报，或选择日记照片生成对比报告"
          action-label="生成第一份报告"
          @action="router.push({ name: 'skin-report-new' })"
        />

        <EmptyState
          v-else-if="filteredReports.length === 0"
          icon="ri-file-chart-2-line"
          title="该类型暂无报告"
          description="切换筛选或生成新报告"
        />

        <button
          v-for="r in filteredReports"
          :key="r.id"
          class="srl-card"
          @click="router.push({ name: 'skin-report-view', params: { id: r.id } })"
        >
          <div class="srl-card__top">
            <div class="srl-card__title-wrap">
              <i
                class="srl-card__type"
                :class="r.report_type === 'weekly' ? 'ri-calendar-check-line' : r.report_type === 'monthly' ? 'ri-calendar-todo-line' : 'ri-file-chart-2-line'"
              ></i>
              <span v-if="r.has_vasi" class="srl-card__vasi-tag"><i class="ri-microscope-line"></i> 深度评估</span>
              <span class="srl-card__title">{{ r.headline || r.title }}</span>
            </div>
            <span v-if="r.trend" class="srl-card__trend" :class="trendStyle(r.trend).cls">
              <i :class="trendStyle(r.trend).icon"></i> {{ r.trend }}
            </span>
          </div>
          <div class="srl-card__meta">
            <span><i class="ri-file-list-3-line"></i> {{ typeLabel(r.report_type) }}</span>
            <span v-if="r.sites_summary"><i class="ri-map-pin-line"></i> {{ r.sites_summary.total }}个部位</span>
            <span v-else><i class="ri-map-pin-line"></i> {{ r.body_site_label }}</span>
            <span><i class="ri-calendar-line"></i> {{ fmtDate(r.period_start) }} ~ {{ fmtDate(r.period_end) }}</span>
          </div>
          <div class="srl-card__footer">
            <span class="srl-card__date">{{ fmtDate(r.created_at) }}</span>
            <span class="srl-card__share" v-if="r.is_public">
              <i class="ri-global-line"></i> 已分享
            </span>
          </div>
        </button>
      </template>
    </main>
  </div>
</template>

<style scoped>
.srl-page {
  min-height: 0;
  min-height: 0;
  background: #f5f7fa;
}

html.dark .srl-page {
  background: #0f172a;
}

.srl-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(245, 247, 250, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #e2e8f0;
}

html.dark .srl-header {
  background: rgba(15, 23, 42, 0.85);
  border-color: #1e293b;
}

.srl-header__inner {
  max-width: 896px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  height: 48px;
}

.srl-back {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #475569;
  font-size: 22px;
  cursor: pointer;
}

html.dark .srl-back {
  color: #cbd5e1;
}

.srl-header__title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

html.dark .srl-header__title {
  color: #f1f5f9;
}

.srl-new {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 22px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.srl-main {
  max-width: 896px;
  margin: 0 auto;
  /* 移动端预留 BottomNav(54px) + 安全区，避免末尾内容被遮挡 */
  padding: 16px 16px calc(70px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── 周报/月报快捷生成卡 ── */
.srl-quick {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.srl-quick__card {
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  background: white;
  border: 1px solid var(--color-primary-100, #ccfbf1);
  border-radius: 14px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s;
}

html.dark .srl-quick__card {
  background: #1e293b;
  border-color: var(--color-primary-900, #134e4a);
}

.srl-quick__card:active {
  transform: scale(0.99);
}

.srl-quick__card--off {
  opacity: 0.55;
  border-color: #f1f5f9;
}

html.dark .srl-quick__card--off {
  border-color: #334155;
}

.srl-quick__icon {
  font-size: 24px;
  color: var(--color-primary-500);
  flex-shrink: 0;
}

.srl-quick__body {
  flex: 1;
  min-width: 0;
}

.srl-quick__label {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

html.dark .srl-quick__label {
  color: #f1f5f9;
}

.srl-quick__meta {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

html.dark .srl-quick__meta {
  color: #94a3b8;
}

.srl-quick__arrow {
  color: var(--color-primary-500);
  font-size: 18px;
  flex-shrink: 0;
}

/* ── 类型筛选 ── */
.srl-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 2px 0 4px;
  scrollbar-width: none;
}

.srl-tabs::-webkit-scrollbar {
  display: none;
}

.srl-tab {
  padding: 6px 14px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: white;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

html.dark .srl-tab {
  background: #1e293b;
  border-color: #334155;
  color: #94a3b8;
}

.srl-tab--active {
  background: var(--color-primary-50, #f0fdfa);
  border-color: var(--color-primary-500);
  color: var(--color-primary-700);
  font-weight: 600;
}

html.dark .srl-tab--active {
  background: rgba(13, 148, 136, 0.15);
  color: var(--color-primary-300, #5eead4);
}

.srl-card__type {
  color: var(--color-primary-500);
  font-size: 16px;
  flex-shrink: 0;
}

.srl-card__vasi-tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  color: var(--color-primary-600);
  background: var(--color-primary-50, #f0fdfa);
  border-radius: 8px;
  padding: 2px 6px;
  flex-shrink: 0;
}

html.dark .srl-card__vasi-tag {
  background: rgba(13, 148, 136, 0.15);
  color: var(--color-primary-300, #5eead4);
}

.srl-cta {
  margin-top: 16px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  border-radius: 22px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.srl-card {
  text-align: left;
  background: white;
  border-radius: 14px;
  padding: 14px 16px;
  border: 1px solid #f1f5f9;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
}

html.dark .srl-card {
  background: #1e293b;
  border-color: #334155;
}

.srl-card:active {
  transform: scale(0.99);
}

.srl-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.srl-card__title-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.srl-card__vasi {
  color: var(--color-primary-500);
  font-size: 16px;
  flex-shrink: 0;
}

.srl-card__title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
}

html.dark .srl-card__title {
  color: #f1f5f9;
}

.srl-card__trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.srl-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.srl-card__meta i {
  margin-right: 2px;
}

.srl-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #cbd5e1;
}

.srl-card__share {
  color: var(--color-primary-500);
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
</style>
