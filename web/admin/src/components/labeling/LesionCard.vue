<script setup lang="ts">
/**
 * LesionCard — displays a single lesion's classification form and stats.
 *
 * Used inside LesionPanel. Shows body site, vitiligo type, stage,
 * area %, depigmentation level, and notes for one lesion.
 */

import { computed } from 'vue'
import type { LesionData } from '@/composables/useLesionManager'

const props = defineProps<{
  lesion: LesionData
  index: number
  active: boolean
}>()

const emit = defineEmits<{
  select: [index: number]
  remove: [index: number]
}>()

const bodySiteOptions = [
  { label: '面部', value: 'face' },
  { label: '颈部', value: 'neck' },
  { label: '躯干', value: 'trunk' },
  { label: '上肢', value: 'upper_limb' },
  { label: '下肢', value: 'lower_limb' },
  { label: '手部', value: 'hand' },
  { label: '足部', value: 'foot' },
  { label: '头皮', value: 'scalp' },
  { label: '全身', value: 'whole_body' },
]

const vitiligoTypeOptions = [
  { label: '非节段型', value: 'non_segmental' },
  { label: '节段型', value: 'segmental' },
  { label: '混合型', value: 'mixed' },
  { label: '未分类型', value: 'unclassified' },
  { label: '非白癜风', value: 'not_vitiligo' },
]

const stageOptions = [
  { label: '进展期', value: 'progressing' },
  { label: '稳定期', value: 'stable' },
  { label: '好转期', value: 'improving' },
  { label: '不确定', value: 'uncertain' },
]

const areaDisplay = computed(() => {
  if (props.lesion.areaPercentage == null) return '-'
  return `${props.lesion.areaPercentage.toFixed(1)}%`
})
</script>

<template>
  <div
    :style="{
      padding: '10px 12px',
      borderRadius: '8px',
      background: active ? 'rgba(99,102,241,0.12)' : 'rgba(15,23,42,0.6)',
      border: active ? '1px solid rgba(99,102,241,0.35)' : '1px solid rgba(148,163,184,0.1)',
      cursor: 'pointer',
      transition: 'all 0.15s',
    }"
    @click="emit('select', index)"
  >
    <!-- Header -->
    <div :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }">
      <div :style="{ display: 'flex', alignItems: 'center', gap: '6px' }">
        <span
          :style="{
            display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%',
            background: active ? '#818cf8' : '#475569',
            boxShadow: active ? '0 0 6px rgba(99,102,241,0.5)' : 'none',
          }"
        ></span>
        <span :style="{ fontSize: '12px', fontWeight: 600, color: active ? '#c7d2fe' : '#94a3b8' }">
          {{ lesion.label }}
        </span>
      </div>
      <div :style="{ display: 'flex', alignItems: 'center', gap: '4px' }">
        <span :style="{ fontSize: '11px', color: '#64748b', fontVariantNumeric: 'tabular-nums' }">
          {{ areaDisplay }}
        </span>
        <button
          v-if="active"
          :style="{
            padding: '2px 6px', borderRadius: '4px', fontSize: '10px',
            color: '#f87171', background: 'transparent', border: 'none', cursor: 'pointer',
          }"
          title="删除此白斑"
          @click.stop="emit('remove', index)"
        >
          <i class="ri-close-line"></i>
        </button>
      </div>
    </div>

    <!-- Quick info row -->
    <div :style="{ display: 'flex', gap: '4px', flexWrap: 'wrap', fontSize: '10px' }">
      <span v-if="lesion.bodySite" :style="{ padding: '1px 6px', borderRadius: '4px', background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }">
        {{ lesion.bodySite }}
      </span>
      <span v-if="lesion.vitiligoType" :style="{ padding: '1px 6px', borderRadius: '4px', background: 'rgba(245,158,11,0.15)', color: '#fbbf24' }">
        {{ lesion.vitiligoType }}
      </span>
      <span v-if="lesion.vitiligoStage" :style="{ padding: '1px 6px', borderRadius: '4px', background: 'rgba(16,185,129,0.15)', color: '#6ee7b7' }">
        {{ lesion.vitiligoStage }}
      </span>
      <span v-if="lesion.lesionMaskDataUrl" :style="{ padding: '1px 6px', borderRadius: '4px', background: 'rgba(236,72,153,0.15)', color: '#f9a8d4' }">
        <i class="ri-check-line"></i> 已填涂
      </span>
    </div>

    <!-- Expanded form (only when active) -->
    <div v-if="active" :style="{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }">
      <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }">
        <select v-model="lesion.bodySite" :style="selectStyle">
          <option :value="null">部位</option>
          <option v-for="opt in bodySiteOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select v-model="lesion.vitiligoType" :style="selectStyle">
          <option :value="null">分型</option>
          <option v-for="opt in vitiligoTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }">
        <select v-model="lesion.vitiligoStage" :style="selectStyle">
          <option :value="null">阶段</option>
          <option v-for="opt in stageOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <input v-model.number="lesion.areaPercentage" type="number" min="0" max="100" step="0.1" placeholder="面积 %" :style="inputStyle" />
      </div>
      <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }">
        <input v-model.number="lesion.depigmentationLevel" type="number" min="0" max="1" step="0.05" placeholder="脱色 0-1" :style="inputStyle" />
        <input v-model="lesion.notes" type="text" placeholder="备注" :style="inputStyle" />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
const selectStyle = {
  width: '100%', padding: '4px 6px',
  background: '#0f172a', color: '#e2e8f0',
  border: '1px solid rgba(148,163,184,0.2)',
  borderRadius: '4px', fontSize: '11px',
}

const inputStyle = {
  width: '100%', padding: '4px 6px',
  background: '#0f172a', color: '#e2e8f0',
  border: '1px solid rgba(148,163,184,0.2)',
  borderRadius: '4px', fontSize: '11px',
}
</script>
