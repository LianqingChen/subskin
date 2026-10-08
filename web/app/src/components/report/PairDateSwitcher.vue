<script setup lang="ts">
/**
 * PairDateSwitcher — 前后对比日期切换器
 *
 * 两行日期 chips（前/后），仅列出本次报告所选照片的日期（不做日历筛选）。
 * 默认选中最早与最晚两张；点击任一 chip 即切换对比的照片对。
 * 若选择导致"前晚于后"，自动交换两个选择。
 * 质量差（过暗/模糊）的照片显示警示角标。
 */
import type { TimelineFrame } from '@/api/skin_report'

const props = defineProps<{
  frames: TimelineFrame[]
  beforeIndex: number
  afterIndex: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:beforeIndex': [value: number]
  'update:afterIndex': [value: number]
}>()

function fmtShort(d?: string) {
  return d ? d.slice(5, 10).replace('-', '/') : ''
}

function applyPair(a: number, b: number) {
  const [before, after] = a <= b ? [a, b] : [b, a]
  emit('update:beforeIndex', before)
  emit('update:afterIndex', after)
}
function pickBefore(i: number) {
  if (props.disabled || i === props.beforeIndex) return
  applyPair(i, i === props.afterIndex ? props.beforeIndex : props.afterIndex)
}
function pickAfter(i: number) {
  if (props.disabled || i === props.afterIndex) return
  applyPair(i === props.beforeIndex ? props.afterIndex : props.beforeIndex, i)
}

function isPoor(f?: TimelineFrame) {
  return f?.quality === 'poor'
}
</script>

<template>
  <div class="pds">
    <div class="pds__row">
      <span class="pds__tag pds__tag--before"><i class="ri-arrow-left-line"></i>前</span>
      <div class="pds__chips">
        <button
          v-for="(f, i) in frames"
          :key="'b' + i"
          type="button"
          class="pds__chip"
          :class="{ 'pds__chip--active-before': i === beforeIndex }"
          :disabled="disabled"
          @click="pickBefore(i)"
        >
          {{ fmtShort(f?.date) }}
          <i v-if="isPoor(f)" class="ri-error-warning-line pds__warn" title="该照片光线/清晰度较差，对比结果仅供参考"></i>
        </button>
      </div>
    </div>
    <div class="pds__row">
      <span class="pds__tag pds__tag--after"><i class="ri-arrow-right-line"></i>后</span>
      <div class="pds__chips">
        <button
          v-for="(f, i) in frames"
          :key="'a' + i"
          type="button"
          class="pds__chip"
          :class="{ 'pds__chip--active-after': i === afterIndex }"
          :disabled="disabled"
          @click="pickAfter(i)"
        >
          {{ fmtShort(f?.date) }}
          <i v-if="isPoor(f)" class="ri-error-warning-line pds__warn" title="该照片光线/清晰度较差，对比结果仅供参考"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pds {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.pds__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pds__tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  width: 44px;
  justify-content: center;
  padding: 5px 0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
}

.pds__tag i {
  font-size: 13px;
}

.pds__tag--before {
  background: #f1f5f9;
  color: #475569;
}

.pds__tag--after {
  background: #ccfbf1;
  color: #0f766e;
}

html.dark .pds__tag--before {
  background: #1e293b;
  color: #cbd5e1;
}

html.dark .pds__tag--after {
  background: rgba(13, 148, 136, 0.2);
  color: #5eead4;
}

.pds__chips {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
}

.pds__chips::-webkit-scrollbar {
  display: none;
}

.pds__chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 6px 12px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: white;
  color: #475569;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
  min-height: 44px;
}

html.dark .pds__chip {
  background: #1e293b;
  border-color: #334155;
  color: #cbd5e1;
}

.pds__chip:disabled {
  opacity: 0.6;
  cursor: wait;
}

.pds__chip--active-before {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
  font-weight: 600;
}

html.dark .pds__chip--active-before {
  background: rgba(13, 148, 136, 0.15);
  color: #5eead4;
}

.pds__chip--active-after {
  border-color: #0f766e;
  background: #0f766e;
  color: white;
  font-weight: 600;
}

.pds__warn {
  font-size: 12px;
  color: #d97706;
}
</style>
