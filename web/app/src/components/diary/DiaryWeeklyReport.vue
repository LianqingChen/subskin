<script setup lang="ts">
/**
 * DiaryWeeklyReport — AI病情日记周报卡片
 * 展示：本周记录条数、心情分布、睡眠/压力概况、VASI评估、AI洞察与LLM总结
 * 设计上为可截图分享的独立浅色卡片
 */
import { computed } from 'vue'
import type { WeeklyReport } from '@/api/diary'
import { parseDate } from '@/utils/date'

const props = defineProps<{
  report: WeeklyReport
  moodConfig: Record<string, { emoji: string; label: string; color: string }>
}>()

const emit = defineEmits<{
  share: []
}>()

const WEEK_LABELS = ['一', '二', '三', '四', '五', '六', '日']

const sleepConfig: Record<string, { emoji: string; label: string }> = {
  good: { emoji: '😴', label: '睡得好' },
  fair: { emoji: '🌙', label: '一般' },
  poor: { emoji: '☕', label: '没睡好' },
}

function fmtDay(dateStr: string): string {
  const d = parseDate(dateStr)
  if (!d) return dateStr
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

const weekRangeText = computed(
  () => `${fmtDay(props.report.week_start)} - ${fmtDay(props.report.week_end)}`,
)

const moodEntries = computed(() =>
  Object.entries(props.report.mood_distribution)
    .filter(([key]) => props.moodConfig[key])
    .sort((a, b) => b[1] - a[1]),
)

const sleepEntries = computed(() =>
  Object.entries(props.report.sleep_distribution).filter(([key]) => sleepConfig[key]),
)

function dayMoodEmoji(moods: string[]): string {
  if (!moods.length) return ''
  const first = moods[0]
  return props.moodConfig[first]?.emoji || '🙂'
}

function isToday(dateStr: string): boolean {
  const now = new Date()
  const localToday = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  return dateStr === localToday
}
</script>

<template>
  <div class="weekly-report">
    <!-- Card header (gradient) -->
    <div class="weekly-report__header">
      <div class="weekly-report__header-decor weekly-report__header-decor--1"></div>
      <div class="weekly-report__header-decor weekly-report__header-decor--2"></div>
      <div class="weekly-report__header-main">
        <div>
          <p class="weekly-report__title">
            <i class="ri-sparkling-2-fill"></i>
            AI周报
          </p>
          <p class="weekly-report__range">{{ weekRangeText }}</p>
        </div>
        <button class="weekly-report__share-icon" title="分享周报" @click="emit('share')">
          <i class="ri-share-forward-line"></i>
        </button>
      </div>

      <!-- Stats row -->
      <div class="weekly-report__stats">
        <div class="weekly-report__stat">
          <span class="weekly-report__stat-value">{{ report.recorded_days }}</span>
          <span class="weekly-report__stat-label">记录天数</span>
        </div>
        <div class="weekly-report__stat-divider"></div>
        <div class="weekly-report__stat">
          <span class="weekly-report__stat-value">{{ report.entry_count }}</span>
          <span class="weekly-report__stat-label">日记条数</span>
        </div>
        <div class="weekly-report__stat-divider"></div>
        <div class="weekly-report__stat">
          <span class="weekly-report__stat-value">{{ report.current_streak }}</span>
          <span class="weekly-report__stat-label">连续天数</span>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="report.entry_count === 0" class="weekly-report__empty">
      <i class="ri-seedling-line weekly-report__empty-icon"></i>
      <p class="weekly-report__empty-title">本周还没有记录</p>
      <p class="weekly-report__empty-desc">每天30秒，记录心情与身体状态，周末来看你的专属周报</p>
    </div>

    <template v-else>
      <div class="weekly-report__body">
        <!-- Mood trend (7 days) -->
        <section class="weekly-report__section weekly-report__section--full">
          <h3 class="weekly-report__section-title">心情轨迹</h3>
          <div class="weekly-report__mood-row">
            <div
              v-for="(day, i) in report.daily_moods"
              :key="day.date"
              class="weekly-report__mood-day"
              :class="{ 'weekly-report__mood-day--today': isToday(day.date) }"
            >
              <span class="weekly-report__mood-emoji">
                {{ dayMoodEmoji(day.moods) || '·' }}
              </span>
              <span class="weekly-report__mood-label">{{ WEEK_LABELS[i] }}</span>
            </div>
          </div>

          <!-- Mood distribution -->
          <div v-if="moodEntries.length" class="weekly-report__chips">
            <span
              v-for="[key, count] in moodEntries"
              :key="key"
              class="weekly-report__chip"
              :style="{ borderColor: moodConfig[key].color + '40', color: moodConfig[key].color }"
            >
              {{ moodConfig[key].emoji }} {{ moodConfig[key].label }} × {{ count }}
            </span>
          </div>
        </section>

        <!-- Sleep & stress -->
        <section
          v-if="sleepEntries.length || report.avg_stress_level !== null"
          class="weekly-report__section"
        >
          <h3 class="weekly-report__section-title">睡眠与压力</h3>
          <div class="weekly-report__chips">
            <span
              v-for="[key, count] in sleepEntries"
              :key="key"
              class="weekly-report__chip weekly-report__chip--sleep"
            >
              {{ sleepConfig[key].emoji }} {{ sleepConfig[key].label }} × {{ count }}
            </span>
            <span v-if="report.avg_stress_level !== null" class="weekly-report__chip weekly-report__chip--stress">
              📊 平均压力 {{ report.avg_stress_level }}/5
            </span>
          </div>
        </section>

        <!-- VASI -->
        <section v-if="report.vasi_count > 0" class="weekly-report__section">
          <h3 class="weekly-report__section-title">患处评估</h3>
          <div class="weekly-report__vasi">
            <i class="ri-ruler-line"></i>
            <span>本周完成 {{ report.vasi_count }} 次 VASI 评估，坚持量化追踪</span>
          </div>
        </section>

        <!-- AI summary -->
        <section v-if="report.ai_summary" class="weekly-report__section weekly-report__section--full">
          <h3 class="weekly-report__section-title">
            <i class="ri-sparkling-2-line weekly-report__section-spark"></i>
            AI本周总结
          </h3>
          <p class="weekly-report__summary">{{ report.ai_summary }}</p>
        </section>

        <!-- Insights -->
        <section v-if="report.insights.length" class="weekly-report__section weekly-report__section--full">
          <h3 class="weekly-report__section-title">AI洞察</h3>
          <ul class="weekly-report__insights">
            <li v-for="(tip, i) in report.insights" :key="i" class="weekly-report__insight">
              <i class="ri-checkbox-circle-fill weekly-report__insight-icon"></i>
              <span>{{ tip }}</span>
            </li>
          </ul>
        </section>
      </div>

      <!-- Footer -->
      <div class="weekly-report__footer">
        <p class="weekly-report__disclaimer">内容仅供参考，治疗请遵医嘱</p>
        <button class="weekly-report__share-btn" @click="emit('share')">
          <i class="ri-image-edit-line"></i>
          生成分享海报
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.weekly-report {
  background: #ffffff;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px color-mix(in srgb, var(--color-primary-500) 8%, transparent);
}

/* Header */
.weekly-report__header {
  position: relative;
  background: linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-700) 100%);
  padding: 18px 18px 14px;
  color: #fff;
  overflow: hidden;
}

.weekly-report__header-decor {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
}

.weekly-report__header-decor--1 {
  width: 140px;
  height: 140px;
  right: -40px;
  top: -50px;
}

.weekly-report__header-decor--2 {
  width: 80px;
  height: 80px;
  right: 60px;
  bottom: -40px;
}

.weekly-report__header-main {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.weekly-report__title {
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
}

.weekly-report__range {
  font-size: 12px;
  opacity: 0.85;
  margin-top: 4px;
}

.weekly-report__share-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.weekly-report__share-icon:active {
  transform: scale(0.92);
  background: rgba(255, 255, 255, 0.3);
}

.weekly-report__stats {
  position: relative;
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  padding: 10px 0;
}

.weekly-report__stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.weekly-report__stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
}

.weekly-report__stat-label {
  font-size: 11px;
  opacity: 0.85;
}

.weekly-report__stat-divider {
  width: 1px;
  height: 26px;
  background: rgba(255, 255, 255, 0.25);
}

/* Empty */
.weekly-report__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 36px 24px;
}

.weekly-report__empty-icon {
  font-size: 40px;
  color: var(--color-primary-500);
  opacity: 0.5;
  margin-bottom: 10px;
}

.weekly-report__empty-title {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

html.dark .weekly-report__empty-title {
  color: #e2e8f0;
}

.weekly-report__empty-desc {
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.6;
}

/* Body */
.weekly-report__body {
  padding: 16px 18px 4px;
}

/* md+ 桌面：各 section 栅格并排，避免拓宽后稀疏单列 */
@media (min-width: 768px) {
  .weekly-report__body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 24px;
  }

  .weekly-report__section--full {
    grid-column: 1 / -1;
  }
}

.weekly-report__section {
  margin-bottom: 16px;
}

.weekly-report__section-title {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 4px;
}

html.dark .weekly-report__section-title {
  color: #94a3b8;
}

.weekly-report__section-spark {
  color: var(--color-primary-500);
}

/* Mood row */
.weekly-report__mood-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.weekly-report__mood-day {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 36px;
}

.weekly-report__mood-emoji {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  background: #f1f5f9;
  color: #cbd5e1;
}

.weekly-report__mood-day--today .weekly-report__mood-emoji {
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary-500) 50%, transparent);
}

.weekly-report__mood-label {
  font-size: 10px;
  color: #94a3b8;
}

/* Chips */
.weekly-report__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.weekly-report__chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  color: #64748b;
  background: #f8fafc;
}

html.dark .weekly-report__chip {
  background: #0f172a;
  border-color: #334155;
  color: #94a3b8;
}

.weekly-report__chip--sleep {
  border-color: rgba(129, 140, 248, 0.25);
  color: #6366f1;
}

.weekly-report__chip--stress {
  border-color: rgba(239, 68, 68, 0.25);
  color: #dc2626;
}

/* VASI */
.weekly-report__vasi {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #059669;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 12px;
  padding: 10px 12px;
}

.weekly-report__vasi i {
  font-size: 16px;
}

/* AI summary */
.weekly-report__summary {
  font-size: 13.5px;
  line-height: 1.8;
  color: #334155;
  background: linear-gradient(135deg, color-mix(in srgb, var(--color-primary-500) 6%, transparent), color-mix(in srgb, var(--color-primary-700) 4%, transparent));
  border: 1px solid color-mix(in srgb, var(--color-primary-500) 15%, transparent);
  border-radius: 12px;
  padding: 12px 14px;
}

html.dark .weekly-report__summary {
  color: #e2e8f0;
}

/* Insights */
.weekly-report__insights {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.weekly-report__insight {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

html.dark .weekly-report__insight {
  color: #cbd5e1;
}

.weekly-report__insight-icon {
  color: var(--color-primary-500);
  font-size: 15px;
  margin-top: 2px;
  flex-shrink: 0;
}

/* Footer */
.weekly-report__footer {
  padding: 12px 18px 16px;
  border-top: 1px dashed #e2e8f0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

html.dark .weekly-report__footer {
  border-top-color: #334155;
}

.weekly-report__disclaimer {
  font-size: 11px;
  color: #cbd5e1;
}

.weekly-report__share-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  border-radius: 22px;
  border: none;
  background: var(--color-primary-500);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--color-primary-500) 30%, transparent);
}

.weekly-report__share-btn:active {
  transform: scale(0.96);
}
</style>
