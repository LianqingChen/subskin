<script setup lang="ts">
/**
 * DiaryPage — AI病情日记
 *
 * 对话式记录 + AI结构化提取 + 日历视图 + 快捷记录
 * 核心交互：用户输入自然语言 → AI自动提取心情/睡眠/用药/压力/患处变化
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  createDiaryEntry,
  createQuickEntry,
  getDiaryEntries,
  getDiaryEntry,
  deleteDiaryEntry,
  getDiaryCalendar,
  getDiaryStats,
  getWeeklyReport,
} from '@/api/diary'
import type { DiaryEntry, CalendarResponse, WeeklyReport, DiaryImageInput } from '@/api/diary'
import DiaryEntryCard from '@/components/diary/DiaryEntryCard.vue'
import DiaryImageUploader from '@/components/diary/DiaryImageUploader.vue'
import DiaryCalendarMini from '@/components/diary/DiaryCalendarMini.vue'
import DiaryQuickPanel from '@/components/diary/DiaryQuickPanel.vue'
import DiaryWeeklyReport from '@/components/diary/DiaryWeeklyReport.vue'
import DiaryWeeklyPoster from '@/components/diary/DiaryWeeklyPoster.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'

const toast = useToast()
const authStore = useAuthStore()

// ── State ──
const entries = ref<DiaryEntry[]>([])
const loading = ref(false)
const submitting = ref(false)
const inputText = ref('')
const page = ref(1)
const total = ref(0)
const hasMore = computed(() => entries.value.length < total.value)

// Stats
const stats = ref<{ total_entries: number; current_streak: number; recorded_today: boolean; week_count: number } | null>(null)

// Tabs & weekly report
const activeTab = ref<'records' | 'weekly'>('records')
const weeklyReport = ref<WeeklyReport | null>(null)
const weeklyLoading = ref(false)
const showWeeklyPoster = ref(false)

// Calendar
const calendarData = ref<CalendarResponse | null>(null)
const showCalendar = ref(false)
const calendarYear = ref(new Date().getFullYear())
const calendarMonth = ref(new Date().getMonth() + 1)

// Quick panel
const showQuickPanel = ref(false)

// 图文日记：待上传图片
const router = useRouter()
const pendingImages = ref<DiaryImageInput[]>([])
const imageUploader = ref<InstanceType<typeof DiaryImageUploader>>()

// ── Mood config ──
const moodConfig: Record<string, { emoji: string; label: string; color: string }> = {
  good: { emoji: '😊', label: '开心', color: '#4CAF50' },
  neutral: { emoji: '😐', label: '一般', color: '#9E9E9E' },
  bad: { emoji: '😢', label: '低落', color: '#F44336' },
  anxious: { emoji: '😰', label: '焦虑', color: '#FF9800' },
  hopeful: { emoji: '🌟', label: '充满希望', color: '#26A69A' },
}

const skinConfig: Record<string, { emoji: string; label: string }> = {
  stable: { emoji: '➡️', label: '稳定' },
  improving: { emoji: '✨', label: '好转' },
  spreading: { emoji: '⚠️', label: '扩散' },
  new_spots: { emoji: '🆕', label: '新发' },
}

// ── Methods ──
async function loadEntries(reset = false) {
  if (reset) {
    page.value = 1
    entries.value = []
  }
  loading.value = true
  try {
    const offset = (page.value - 1) * 20
    const { data } = await getDiaryEntries({ limit: 20, offset })
    if (reset) {
      entries.value = data.items
    } else {
      entries.value.push(...data.items)
    }
    total.value = data.total
  } catch (e) {
    toast.show('加载日记失败', 'error')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const { data } = await getDiaryStats()
    stats.value = data
  } catch {
    // non-critical
  }
}

async function loadCalendar() {
  try {
    const { data } = await getDiaryCalendar(calendarYear.value, calendarMonth.value)
    calendarData.value = data
  } catch {
    // non-critical
  }
}

async function loadWeeklyReport() {
  weeklyLoading.value = true
  try {
    const { data } = await getWeeklyReport()
    weeklyReport.value = data
  } catch {
    // non-critical
  } finally {
    weeklyLoading.value = false
  }
}

function switchTab(tab: 'records' | 'weekly') {
  activeTab.value = tab
  if (tab === 'weekly') {
    loadWeeklyReport()
  }
}

async function submitEntry() {
  const text = inputText.value.trim()
  const hasImages = pendingImages.value.length > 0
  if (!text && !hasImages) return
  if (!authStore.isLoggedIn) {
    toast.show('请先登录后再记录日记', 'warning')
    return
  }
  submitting.value = true
  try {
    const { data } = await createDiaryEntry({
      raw_text: text || '图文记录',
      input_type: 'text',
      images: hasImages ? pendingImages.value : undefined,
    })
    entries.value.unshift(data)
    total.value++
    inputText.value = ''
    pendingImages.value = []
    imageUploader.value?.clearAll()
    toast.show('日记已记录，AI正在分析中 ✨', 'success')
    loadStats()
    loadCalendar()
    if (weeklyReport.value) loadWeeklyReport()
    // 带图日记：轮询刷新分析状态（图片视觉分析 + AI文字提取）
    if (hasImages) pollEntryStatus(data.id)
  } catch (e: any) {
    toast.show(e.response?.data?.detail || '记录失败，请重试', 'error')
  } finally {
    submitting.value = false
  }
}

function goToReports() {
  router.push({ name: 'skin-reports' })
}

// 轮询新创建带图日记的分析状态（图片轻量分析 + AI文字提取都是异步，需刷新才显示）
let pollTimer: ReturnType<typeof setInterval> | null = null

function pollEntryStatus(entryId: number) {
  if (pollTimer) clearInterval(pollTimer)
  let attempts = 0
  const maxAttempts = 24 // 约 2 分钟
  pollTimer = setInterval(async () => {
    attempts++
    try {
      const { data } = await getDiaryEntry(entryId)
      const idx = entries.value.findIndex((e) => e.id === entryId)
      if (idx >= 0) entries.value[idx] = data
      // 图片分析 + 文字提取都完成则停止
      const imagesDone = (data.images || []).every(
        (im) => im.analysis_status === 'light_done' || im.analysis_status === 'failed',
      )
      if ((imagesDone && data.ai_summary) || attempts >= maxAttempts) {
        if (pollTimer) {
          clearInterval(pollTimer)
          pollTimer = null
        }
      }
    } catch {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }
  }, 5000)
}

async function handleQuickRecord(payload: Record<string, any>) {
  if (!authStore.isLoggedIn) {
    toast.show('请先登录后再记录', 'warning')
    return
  }
  try {
    const { data } = await createQuickEntry(payload)
    entries.value.unshift(data)
    total.value++
    showQuickPanel.value = false
    toast.show('快捷记录成功 ✓', 'success')
    loadStats()
    loadCalendar()
    if (weeklyReport.value) loadWeeklyReport()
  } catch (e: any) {
    toast.show(e.response?.data?.detail || '记录失败', 'error')
  }
}

async function handleDelete(id: number) {
  try {
    await deleteDiaryEntry(id)
    entries.value = entries.value.filter((e) => e.id !== id)
    total.value--
    toast.show('已删除', 'success')
    loadStats()
    if (weeklyReport.value) loadWeeklyReport()
  } catch {
    toast.show('删除失败', 'error')
  }
}

function loadMore() {
  page.value++
  loadEntries()
}

// ── Init ──
onMounted(() => {
  // 未登录时不调用需认证的API，避免401→reload死循环
  if (!authStore.isLoggedIn) return
  loadEntries(true)
  loadStats()
  loadCalendar()
})

// 用户在本页登录成功后自动加载数据
watch(() => authStore.isLoggedIn, (loggedIn) => {
  if (loggedIn) {
    loadEntries(true)
    loadStats()
    loadCalendar()
  }
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="diary-page">
    <!-- Not logged in prompt -->
    <div v-if="!authStore.isLoggedIn" class="diary-login-prompt">
      <i class="ri-book-3-line diary-login-prompt__icon"></i>
      <p class="diary-login-prompt__title">登录后开始记录AI病情日记</p>
      <p class="diary-login-prompt__desc">记录每日状态，AI帮你追踪心情、睡眠、用药和患处变化趋势</p>
      <button class="diary-login-prompt__btn" @click="authStore.showLoginModal = true">
        <i class="ri-login-box-line"></i>
        立即登录
      </button>
    </div>

    <template v-else>
    <!-- Header -->
    <header class="diary-header">
      <div class="diary-header__top">
        <h1 class="diary-header__title">
          <i class="ri-book-3-line diary-header__icon"></i>
          AI病情日记
        </h1>
        <button class="diary-header__calendar-btn" @click="showCalendar = !showCalendar">
          <i class="ri-calendar-2-line"></i>
        </button>
      </div>

      <!-- Stats bar -->
      <div v-if="stats" class="diary-stats">
        <div class="diary-stats__item">
          <span class="diary-stats__value">{{ stats.total_entries }}</span>
          <span class="diary-stats__label">总记录</span>
        </div>
        <div class="diary-stats__item">
          <span class="diary-stats__value">{{ stats.current_streak }}</span>
          <span class="diary-stats__label">连续天数</span>
        </div>
        <div class="diary-stats__item">
          <span class="diary-stats__value">{{ stats.week_count }}</span>
          <span class="diary-stats__label">本周</span>
        </div>
      </div>

      <!-- Streak hint：今天未记录但连续天数仍在保持 -->
      <p v-if="stats && !stats.recorded_today && stats.current_streak > 0" class="diary-streak-hint">
        <i class="ri-time-line"></i>
        今天还没记录，已连续 {{ stats.current_streak }} 天，别断档哦～
      </p>
    </header>

    <!-- Tabs -->
    <div class="diary-tabs">
      <button
        class="diary-tabs__item"
        :class="{ 'diary-tabs__item--active': activeTab === 'records' }"
        @click="switchTab('records')"
      >
        <i class="ri-quill-pen-line"></i>
        日记记录
      </button>
      <button
        class="diary-tabs__item"
        :class="{ 'diary-tabs__item--active': activeTab === 'weekly' }"
        @click="switchTab('weekly')"
      >
        <i class="ri-sparkling-2-line"></i>
        AI周报
      </button>
      <button
        class="diary-tabs__item"
        @click="goToReports"
      >
        <i class="ri-file-chart-2-line"></i>
        白斑报告
      </button>
    </div>

    <!-- Weekly report tab -->
    <template v-if="activeTab === 'weekly'">
      <LoadingSpinner v-if="weeklyLoading" message="周报生成中..." />
      <template v-else-if="weeklyReport">
        <DiaryWeeklyReport
          :report="weeklyReport"
          :mood-config="moodConfig"
          @share="showWeeklyPoster = true"
        />
        <DiaryWeeklyPoster
          :visible="showWeeklyPoster"
          :report="weeklyReport"
          :mood-config="moodConfig"
          @close="showWeeklyPoster = false"
        />
      </template>
    </template>

    <template v-else>
    <!-- Calendar (collapsible) -->
    <transition name="slide-down">
      <DiaryCalendarMini
        v-if="showCalendar && calendarData"
        :data="calendarData"
        @month-change="(y: number, m: number) => { calendarYear = y; calendarMonth = m; loadCalendar() }"
      />
    </transition>

    <!-- Quick record button -->
    <div class="diary-quick-trigger">
      <button class="diary-quick-trigger__btn" @click="showQuickPanel = !showQuickPanel">
        <i class="ri-flashlight-line"></i>
        <span>快捷记录</span>
        <i :class="showQuickPanel ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'"></i>
      </button>
    </div>

    <!-- Quick panel -->
    <transition name="slide-down">
      <DiaryQuickPanel v-if="showQuickPanel" @submit="handleQuickRecord" />
    </transition>

    <!-- Input area -->
    <div class="diary-input">
      <div class="diary-input__box">
        <textarea
          v-model="inputText"
          class="diary-input__textarea"
          placeholder="记录今天的状态... 比如：今天心情不错，早上吃了黑芝麻糊，涂了他克莫司，白斑好像没什么变化"
          rows="3"
          maxlength="2000"
          @keydown.ctrl.enter="submitEntry"
          @keydown.meta.enter="submitEntry"
        ></textarea>
        <DiaryImageUploader
          ref="imageUploader"
          v-model="pendingImages"
        />
        <div class="diary-input__footer">
          <span class="diary-input__hint">Ctrl+Enter 发送</span>
          <button
            class="diary-input__submit"
            :disabled="(!inputText.trim() && pendingImages.length === 0) || submitting"
            @click="submitEntry"
          >
            <i v-if="submitting" class="ri-loader-4-line animate-spin"></i>
            <i v-else class="ri-send-plane-2-fill"></i>
            <span>{{ submitting ? 'AI分析中...' : '记录' }}</span>
          </button>
        </div>
      </div>
      <p class="diary-input__ai-note">
        <i class="ri-sparkling-2-fill"></i>
        AI会自动提取心情、睡眠、用药、压力、患处变化等信息
      </p>
    </div>

    <!-- Entry list -->
    <div class="diary-list">
      <LoadingSpinner v-if="loading && entries.length === 0" />

      <EmptyState
        v-else-if="entries.length === 0"
        icon="ri-book-open-line"
        title="还没有日记"
        description="记录每天的状态，AI帮你追踪病情变化趋势"
      />

      <template v-else>
        <DiaryEntryCard
          v-for="entry in entries"
          :key="entry.id"
          :entry="entry"
          :mood-config="moodConfig"
          :skin-config="skinConfig"
          @delete="handleDelete"
        />

        <!-- Load more -->
        <button v-if="hasMore" class="diary-list__more" @click="loadMore" :disabled="loading">
          <i v-if="loading" class="ri-loader-4-line animate-spin"></i>
          <span v-else>加载更多</span>
        </button>
      </template>
    </div>
    </template>
    </template>

    <MedicalDisclaimer class="diary-disclaimer" />
  </div>
</template>

<style scoped>
.diary-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 16px 16px 100px;
  min-height: 100vh;
}

@media (min-width: 768px) {
  .diary-page {
    max-width: 896px;
    padding: 24px 24px 48px;
  }
}

.diary-disclaimer {
  margin-top: 24px;
}

/* Login prompt */
.diary-login-prompt {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 64px 24px;
}

.diary-login-prompt__icon {
  font-size: 56px;
  color: var(--color-primary-500);
  opacity: 0.6;
  margin-bottom: 16px;
}

.diary-login-prompt__title {
  font-size: 18px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 8px;
}

html.dark .diary-login-prompt__title {
  color: #e2e8f0;
}

.diary-login-prompt__desc {
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.6;
  margin-bottom: 24px;
  max-width: 280px;
}

.diary-login-prompt__btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 28px;
  border-radius: 24px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--color-primary-500) 30%, transparent);
}

.diary-login-prompt__btn:active {
  transform: scale(0.96);
}

.diary-header {
  margin-bottom: 16px;
}

.diary-header__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.diary-header__title {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
}

html.dark .diary-header__title {
  color: #f1f5f9;
}

.diary-header__icon {
  color: var(--color-primary-500);
  font-size: 24px;
}

.diary-header__calendar-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-primary-500) 8%, transparent);
  color: var(--color-primary-500);
  font-size: 20px;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.diary-header__calendar-btn:active {
  transform: scale(0.92);
}

.diary-stats {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.diary-stats__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 8px;
  background: color-mix(in srgb, var(--color-primary-500) 5%, transparent);
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--color-primary-500) 10%, transparent);
}

.diary-stats__value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary-600);
}

.diary-stats__label {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

/* Streak hint */
.diary-streak-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(255, 152, 0, 0.08);
  border: 1px solid rgba(255, 152, 0, 0.2);
  color: #d97706;
  font-size: 12px;
}

.diary-streak-hint i {
  font-size: 14px;
}

/* Tabs */
.diary-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  padding: 4px;
  background: color-mix(in srgb, var(--color-primary-500) 5%, transparent);
  border-radius: 14px;
}

.diary-tabs__item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 0;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

html.dark .diary-tabs__item {
  color: #94a3b8;
}

.diary-tabs__item--active {
  background: white;
  color: var(--color-primary-600);
  font-weight: 600;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--color-primary-500) 15%, transparent);
}

html.dark .diary-tabs__item--active {
  background: #1e293b;
}

/* Quick trigger */
.diary-quick-trigger {
  margin-bottom: 12px;
}

.diary-quick-trigger__btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--color-primary-500) 20%, transparent);
  background: white;
  color: var(--color-primary-600);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

html.dark .diary-quick-trigger__btn {
  background: #1e293b;
}

.diary-quick-trigger__btn:active {
  transform: scale(0.96);
  background: color-mix(in srgb, var(--color-primary-500) 8%, transparent);
}

/* Input area */
.diary-input {
  margin-bottom: 20px;
}

.diary-input__box {
  background: white;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 12px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

html.dark .diary-input__box {
  background: #1e293b;
  border-color: #334155;
}

.diary-input__box:focus-within {
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary-500) 10%, transparent);
}

.diary-input__textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 15px;
  line-height: 1.6;
  color: #334155;
  background: transparent;
  font-family: inherit;
}

html.dark .diary-input__textarea {
  color: #e2e8f0;
}

.diary-input__textarea::placeholder {
  color: #94a3b8;
}

.diary-input__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

html.dark .diary-input__footer {
  border-top-color: #334155;
}

.diary-input__hint {
  font-size: 11px;
  color: #cbd5e1;
}

.diary-input__submit {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  border-radius: 20px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.diary-input__submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.diary-input__submit:not(:disabled):active {
  transform: scale(0.95);
}

.diary-input__ai-note {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 11px;
  color: #94a3b8;
}

.diary-input__ai-note i {
  color: var(--color-primary-500);
}

/* Entry list */
.diary-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.diary-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px;
  text-align: center;
  color: #94a3b8;
}

.diary-list__empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.diary-list__empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 4px;
}

.diary-list__empty-desc {
  font-size: 13px;
}

.diary-list__spinner {
  font-size: 24px;
  color: var(--color-primary-500);
  margin-bottom: 8px;
}

.diary-list__more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border-radius: 12px;
  border: 1px dashed #e2e8f0;
  background: transparent;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

html.dark .diary-list__more {
  border-color: #334155;
}

.diary-list__more:active {
  background: color-mix(in srgb, var(--color-primary-500) 5%, transparent);
}

/* Transitions */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
