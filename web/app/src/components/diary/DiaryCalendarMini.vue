<script setup lang="ts">
/**
 * DiaryCalendarMini — 迷你日历视图
 * 显示当月哪些天有日记记录，点击月份切换
 */
import { computed } from 'vue'
import type { CalendarResponse } from '@/api/diary'

const props = defineProps<{
  data: CalendarResponse
}>()

const emit = defineEmits<{
  'month-change': [year: number, month: number]
}>()

const weekdays = ['日', '一', '二', '三', '四', '五', '六']

const calendarGrid = computed(() => {
  const { year, month, days } = props.data
  const firstDay = new Date(year, month - 1, 1).getDay()
  const daysInMonth = new Date(year, month, 0).getDate()
  const dayMap = new Map(days.map((d) => [d.date, d]))

  const grid: Array<{ day: number; date: string; hasEntry: boolean; count: number } | null> = []

  // Fill leading blanks
  for (let i = 0; i < firstDay; i++) {
    grid.push(null)
  }

  // Fill days
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const info = dayMap.get(dateStr)
    grid.push({
      day: d,
      date: dateStr,
      hasEntry: !!info,
      count: info?.count || 0,
    })
  }

  return grid
})

const isToday = (dateStr: string) => {
  const today = new Date()
  const t = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  return dateStr === t
}

function prevMonth() {
  let y = props.data.year
  let m = props.data.month - 1
  if (m < 1) { m = 12; y-- }
  emit('month-change', y, m)
}

function nextMonth() {
  let y = props.data.year
  let m = props.data.month + 1
  if (m > 12) { m = 1; y++ }
  emit('month-change', y, m)
}
</script>

<template>
  <div class="cal-mini">
    <div class="cal-mini__header">
      <button class="cal-mini__nav" @click="prevMonth">
        <i class="ri-arrow-left-s-line"></i>
      </button>
      <span class="cal-mini__title">{{ data.year }}年{{ data.month }}月</span>
      <button class="cal-mini__nav" @click="nextMonth">
        <i class="ri-arrow-right-s-line"></i>
      </button>
    </div>

    <div class="cal-mini__weekdays">
      <span v-for="w in weekdays" :key="w" class="cal-mini__weekday">{{ w }}</span>
    </div>

    <div class="cal-mini__grid">
      <div v-for="(cell, idx) in calendarGrid" :key="idx" class="cal-mini__cell">
        <template v-if="cell">
          <div
            class="cal-mini__day"
            :class="{
              'cal-mini__day--today': isToday(cell.date),
              'cal-mini__day--has-entry': cell.hasEntry,
            }"
          >
            {{ cell.day }}
            <span v-if="cell.hasEntry" class="cal-mini__dot"></span>
          </div>
        </template>
      </div>
    </div>

    <div class="cal-mini__footer">
      本月 {{ data.days.reduce((sum, d) => sum + d.count, 0) }} 条记录
    </div>
  </div>
</template>

<style scoped>
.cal-mini {
  background: white;
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid #f1f5f9;
}

html.dark .cal-mini {
  background: #1e293b;
  border-color: #334155;
}

.cal-mini__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.cal-mini__title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

html.dark .cal-mini__title {
  color: #e2e8f0;
}

.cal-mini__nav {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: #f1f5f9;
  color: #64748b;
  cursor: pointer;
  font-size: 16px;
}

html.dark .cal-mini__nav {
  background: #334155;
  color: #94a3b8;
}

.cal-mini__weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: 4px;
}

.cal-mini__weekday {
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  padding: 4px 0;
}

.cal-mini__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.cal-mini__cell {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cal-mini__day {
  position: relative;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;
}

html.dark .cal-mini__day {
  color: #94a3b8;
}

.cal-mini__day--today {
  font-weight: 700;
  color: var(--color-primary-600);
  border: 1px solid color-mix(in srgb, var(--color-primary-500) 30%, transparent);
}

.cal-mini__day--has-entry {
  background: color-mix(in srgb, var(--color-primary-500) 10%, transparent);
  font-weight: 600;
}

.cal-mini__dot {
  position: absolute;
  bottom: 3px;
  left: 50%;
  transform: translateX(-50%);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-primary-500);
}

.cal-mini__footer {
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 8px;
}
</style>
