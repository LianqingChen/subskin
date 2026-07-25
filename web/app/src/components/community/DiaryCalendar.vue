<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { communityApi } from '@/api/community'
import type { DiaryCalendarEntry } from '@/api/community'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  selectEntry: [entry: DiaryCalendarEntry]
}>()

const loading = ref(false)
const currentDate = ref(new Date())
const entries = ref<Record<string, DiaryCalendarEntry[]>>({})
const selectedDate = ref<string | null>(null)

const year = computed(() => currentDate.value.getFullYear())
const month = computed(() => currentDate.value.getMonth() + 1)

const weekDays = ['日', '一', '二', '三', '四', '五', '六']

const calendarDays = computed(() => {
  const firstDay = new Date(year.value, month.value - 1, 1)
  const lastDay = new Date(year.value, month.value, 0)
  const startWeekday = firstDay.getDay()
  const daysInMonth = lastDay.getDate()

  const days: { date: string; day: number; isCurrentMonth: boolean; hasEntry: boolean }[] = []

  // Previous month padding
  const prevMonthLastDay = new Date(year.value, month.value - 1, 0).getDate()
  for (let i = startWeekday - 1; i >= 0; i--) {
    const d = prevMonthLastDay - i
    const m = month.value === 1 ? 12 : month.value - 1
    const y = month.value === 1 ? year.value - 1 : year.value
    days.push({ date: `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`, day: d, isCurrentMonth: false, hasEntry: false })
  }

  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year.value}-${String(month.value).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    days.push({ date: dateStr, day: d, isCurrentMonth: true, hasEntry: !!entries.value[dateStr]?.length })
  }

  // Next month padding
  const remaining = 42 - days.length
  for (let d = 1; d <= remaining; d++) {
    const m = month.value === 12 ? 1 : month.value + 1
    const y = month.value === 12 ? year.value + 1 : year.value
    days.push({ date: `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`, day: d, isCurrentMonth: false, hasEntry: false })
  }

  return days
})

const selectedEntries = computed(() => {
  if (!selectedDate.value) return []
  return entries.value[selectedDate.value] || []
})

const todayStr = computed(() => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
})

async function loadCalendar() {
  loading.value = true
  try {
    const res = await communityApi.getDiaryCalendar(year.value, month.value)
    entries.value = res.entries
  } catch {
    entries.value = {}
  } finally {
    loading.value = false
  }
}

function prevMonth() {
  currentDate.value = new Date(year.value, month.value - 2, 1)
}

function nextMonth() {
  currentDate.value = new Date(year.value, month.value, 1)
}

function selectDay(dateStr: string) {
  selectedDate.value = dateStr === selectedDate.value ? null : dateStr
}

function getDiaryTypeIcon(type: string | null): string {
  switch (type) {
    case 'medication': return 'ri-capsule-line'
    case 'phototherapy': return 'ri-sun-line'
    case 'mood': return 'ri-emotion-happy-line'
    case 'diet': return 'ri-restaurant-line'
    default: return 'ri-file-text-line'
  }
}

function getDiaryTypeLabel(type: string | null): string {
  switch (type) {
    case 'medication': return '用药'
    case 'phototherapy': return '光疗'
    case 'mood': return '心情'
    case 'diet': return '饮食'
    default: return '日记'
  }
}

watch(() => currentDate.value, () => {
  loadCalendar()
})

onMounted(() => {
  if (props.visible) loadCalendar()
})

watch(() => props.visible, (v) => {
  if (v) loadCalendar()
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div class="absolute inset-0 bg-black/40" @click="emit('close')"></div>
      <div class="relative w-full max-w-md mx-auto bg-white rounded-t-2xl md:rounded-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <button @click="prevMonth" class="p-2 text-gray-500 hover:text-gray-900">
            <i class="ri-arrow-left-s-line text-xl"></i>
          </button>
          <h3 class="text-base font-semibold text-gray-900">{{ year }}年{{ month }}月</h3>
          <button @click="nextMonth" class="p-2 text-gray-500 hover:text-gray-900">
            <i class="ri-arrow-right-s-line text-xl"></i>
          </button>
        </div>

        <!-- Calendar Grid -->
        <div class="px-4 py-2">
          <div class="grid grid-cols-7 gap-1 mb-2">
            <div v-for="day in weekDays" :key="day" class="text-center text-xs text-gray-400 py-1">{{ day }}</div>
          </div>
          <div class="grid grid-cols-7 gap-1">
            <button
              v-for="(d, idx) in calendarDays"
              :key="idx"
              @click="d.isCurrentMonth && selectDay(d.date)"
              class="relative aspect-square flex items-center justify-center rounded-lg text-sm transition-colors"
              :class="[
                d.isCurrentMonth ? 'text-gray-900 hover:bg-primary-50' : 'text-gray-300',
                d.date === todayStr && 'ring-1 ring-primary-400',
                d.date === selectedDate && 'bg-primary-500 text-white hover:bg-primary-600',
                d.hasEntry && d.date !== selectedDate && 'bg-primary-50',
              ]"
            >
              {{ d.day }}
              <span v-if="d.hasEntry && d.isCurrentMonth" class="absolute bottom-1 w-1 h-1 rounded-full" :class="d.date === selectedDate ? 'bg-white' : 'bg-primary-500'"></span>
            </button>
          </div>
        </div>

        <!-- Selected Date Entries -->
        <div v-if="selectedDate" class="flex-1 overflow-y-auto px-4 pb-4 border-t border-gray-100">
          <div class="py-2 text-sm font-medium text-gray-700">{{ selectedDate }}</div>
          <div v-if="selectedEntries.length === 0" class="text-center py-4 text-gray-400 text-sm">
            这天还没有日记
          </div>
          <div v-else class="space-y-2">
            <button
              v-for="entry in selectedEntries"
              :key="entry.id"
              @click="emit('selectEntry', entry)"
              class="w-full flex items-center gap-3 p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors text-left"
            >
              <div class="w-8 h-8 rounded-lg bg-primary-100 flex items-center justify-center flex-shrink-0">
                <i :class="getDiaryTypeIcon(entry.diary_type)" class="text-primary-600"></i>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-900 truncate">{{ entry.title }}</div>
                <div class="text-xs text-gray-500">{{ getDiaryTypeLabel(entry.diary_type) }}{{ entry.mood ? ' · ' + entry.mood : '' }}</div>
              </div>
              <i class="ri-arrow-right-s-line text-gray-400"></i>
            </button>
          </div>
        </div>

        <!-- Legend -->
        <div class="px-4 py-3 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-500">
          <span class="flex items-center gap-1"><i class="ri-capsule-line"></i> 用药</span>
          <span class="flex items-center gap-1"><i class="ri-sun-line"></i> 光疗</span>
          <span class="flex items-center gap-1"><i class="ri-emotion-happy-line"></i> 心情</span>
          <span class="flex items-center gap-1"><i class="ri-restaurant-line"></i> 饮食</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>
