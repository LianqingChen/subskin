<script setup lang="ts">
/**
 * DateWheelPicker — 年/月/日三列滚动选择器（iOS 滚轮风格）
 *
 * 三列分别滚动选择年月日，默认定位在当天日期；未来日期不可选。
 * 滚动停止后自动吸附取整，也可点选任意项。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ modelValue: string | null; minYear?: number; compact?: boolean }>(), { modelValue: null, minYear: 2000, compact: false })

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const ITEM_H = 44
const PAD_H = computed(() => props.compact ? 0 : ITEM_H * 2)
const MIN_YEAR = props.minYear

const now = new Date()
const curYear = now.getFullYear()
const curMonth = now.getMonth() + 1
const curDay = now.getDate()

function parseValue(v: string | null): { year: number; month: number; day: number } {
  if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const [y, m, d] = v.split('-').map(Number)
    if (y >= MIN_YEAR && y <= curYear && m >= 1 && m <= 12 && d >= 1 && d <= 31) {
      return { year: y, month: m, day: d }
    }
  }
  return { year: curYear, month: curMonth, day: curDay }
}

const init = parseValue(props.modelValue)
const year = ref(init.year)
const month = ref(init.month)
const day = ref(init.day)

const yEl = ref<HTMLElement | null>(null)
const mEl = ref<HTMLElement | null>(null)
const dEl = ref<HTMLElement | null>(null)

const yearOptions = computed<number[]>(() => {
  const arr: number[] = []
  for (let y = MIN_YEAR; y <= curYear; y++) arr.push(y)
  return arr
})

const maxMonth = computed(() => (year.value === curYear ? curMonth : 12))

const monthOptions = computed<number[]>(() => {
  const arr: number[] = []
  for (let m = 1; m <= maxMonth.value; m++) arr.push(m)
  return arr
})

const maxDay = computed(() => {
  const inMonth = new Date(year.value, month.value, 0).getDate()
  if (year.value === curYear && month.value === curMonth) return Math.min(inMonth, curDay)
  return inMonth
})

const dayOptions = computed<number[]>(() => {
  const arr: number[] = []
  for (let d = 1; d <= maxDay.value; d++) arr.push(d)
  return arr
})

function iso() {
  const mm = String(month.value).padStart(2, '0')
  const dd = String(day.value).padStart(2, '0')
  return `${year.value}-${mm}-${dd}`
}

function clamp() {
  if (month.value > maxMonth.value) month.value = maxMonth.value
  if (day.value > maxDay.value) day.value = maxDay.value
}

watch([year, month], clamp)

// 程序性重置（如父组件清除日期）时抑制回写，避免覆盖「未标注」状态
let suppressEmit = false

watch([year, month, day], () => {
  if (suppressEmit) return
  emit('update:modelValue', iso())
})

// 外部值变化（换照片编辑 / 清除日期）→ 跳转到对应年月日（空值回当天）
watch(
  () => props.modelValue,
  (v) => {
    suppressEmit = true
    const p = parseValue(v)
    year.value = p.year
    month.value = p.month
    day.value = p.day
    nextTick(() => {
      scrollToValue('year')
      scrollToValue('month')
      scrollToValue('day')
      suppressEmit = false
    })
  },
)

function elOf(kind: 'year' | 'month' | 'day'): HTMLElement | null {
  if (kind === 'year') return yEl.value
  if (kind === 'month') return mEl.value
  return dEl.value
}

function optsOf(kind: 'year' | 'month' | 'day'): number[] {
  if (kind === 'year') return yearOptions.value
  if (kind === 'month') return monthOptions.value
  return dayOptions.value
}

function valOf(kind: 'year' | 'month' | 'day'): number {
  if (kind === 'year') return year.value
  if (kind === 'month') return month.value
  return day.value
}

function scrollToValue(kind: 'year' | 'month' | 'day') {
  const el = elOf(kind)
  if (!el) return
  const opts = optsOf(kind)
  const idx = Math.max(0, opts.indexOf(valOf(kind)))
  el.scrollTop = idx * ITEM_H
}

const timers: Partial<Record<'year' | 'month' | 'day', number>> = {}

function onScroll(kind: 'year' | 'month' | 'day', e: Event) {
  const el = e.currentTarget as HTMLElement
  const prev = timers[kind]
  if (prev) window.clearTimeout(prev)
  timers[kind] = window.setTimeout(() => {
    const opts = optsOf(kind)
    const idx = Math.max(0, Math.min(opts.length - 1, Math.round(el.scrollTop / ITEM_H)))
    const v = opts[idx]
    if (kind === 'year') year.value = v
    else if (kind === 'month') month.value = v
    else day.value = v
  }, 80)
}

function pick(kind: 'year' | 'month' | 'day', v: number) {
  const prev = valOf(kind)
  if (kind === 'year') year.value = v
  else if (kind === 'month') month.value = v
  else day.value = v
  nextTick(() => scrollToValue(kind))
  // 点选与当前值相同的项（如默认当天）也要显式提交一次
  if (v === prev) emit('update:modelValue', iso())
}

// 选项列表变化（跨月/跨年）时，把滚动位置对齐到当前值
watch(() => monthOptions.value.length, () => nextTick(() => scrollToValue('month')))
watch(() => dayOptions.value.length, () => nextTick(() => scrollToValue('day')))

onMounted(() => {
  nextTick(() => {
    scrollToValue('year')
    scrollToValue('month')
    scrollToValue('day')
  })
  // 不自动回填日期：滚轮默认停在当天，但只有用户滚动/点选后才生效
})
</script>

<template>
  <div class="dwp" :class="{ 'dwp--compact': compact }">
    <div class="dwp__cols">
      <div class="dwp__col">
        <div
          ref="yEl"
          class="dwp__viewport"
          @scroll="onScroll('year', $event)"
        >
          <div class="dwp__pad" :style="{ height: PAD_H + 'px' }"></div>
          <button
            type="button"
            v-for="y in yearOptions"
            :key="y"
            class="dwp__item"
            :class="{ 'dwp__item--active': y === year }"
            @click="pick('year', y)"
          >
            {{ y }}年
          </button>
          <div class="dwp__pad" :style="{ height: PAD_H + 'px' }"></div>
        </div>
      </div>

      <div class="dwp__col">
        <div
          ref="mEl"
          class="dwp__viewport"
          @scroll="onScroll('month', $event)"
        >
          <div class="dwp__pad" :style="{ height: PAD_H + 'px' }"></div>
          <button
            type="button"
            v-for="m in monthOptions"
            :key="m"
            class="dwp__item"
            :class="{ 'dwp__item--active': m === month }"
            @click="pick('month', m)"
          >
            {{ m }}月
          </button>
          <div class="dwp__pad" :style="{ height: PAD_H + 'px' }"></div>
        </div>
      </div>

      <div class="dwp__col">
        <div
          ref="dEl"
          class="dwp__viewport"
          @scroll="onScroll('day', $event)"
        >
          <div class="dwp__pad" :style="{ height: PAD_H + 'px' }"></div>
          <button
            type="button"
            v-for="d in dayOptions"
            :key="d"
            class="dwp__item"
            :class="{ 'dwp__item--active': d === day }"
            @click="pick('day', d)"
          >
            {{ d }}日
          </button>
          <div class="dwp__pad" :style="{ height: PAD_H + 'px' }"></div>
        </div>
      </div>
    </div>

    <!-- 中间高亮带 -->
    <div class="dwp__band" aria-hidden="true"></div>
  </div>
</template>

<style scoped>
.dwp {
  position: relative;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

.dwp__cols {
  display: flex;
  gap: 6px;
}

.dwp__col {
  flex: 1;
  min-width: 0;
}

.dwp__viewport {
  height: 220px;
  overflow-y: auto;
  scroll-snap-type: y mandatory;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.dwp__viewport::-webkit-scrollbar {
  display: none;
}

.dwp__item {
  width: 100%;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  color: #64748b;
  scroll-snap-align: center;
  cursor: pointer;
  transition: color 0.12s;
}

.dwp__item--active {
  color: var(--color-primary-600);
  font-weight: 700;
  font-size: 16px;
}

.dwp__band {
  position: absolute;
  left: 0;
  right: 0;
  top: 88px;
  height: 44px;
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  pointer-events: none;
}

html.dark .dwp__item {
  color: #94a3b8;
}

html.dark .dwp__item--active {
  color: var(--color-primary-400);
}

html.dark .dwp__band {
  border-color: #334155;
}
.dwp--compact .dwp__viewport { height: 44px; }
.dwp--compact .dwp__band { top: 0; border: 0; }
.dwp--compact .dwp__item { font-size: 14px; }
</style>
