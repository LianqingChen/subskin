<script setup lang="ts">
/**
 * LesionPanel — manages a list of LesionCard instances.
 *
 * Provides add/remove/switch functionality for multi-lesion labeling.
 * Sits in the right sidebar of LabelingWorkspace.
 */

import { useLesionManager } from '@/composables/useLesionManager'
import LesionCard from './LesionCard.vue'

const props = defineProps<{
  manager: ReturnType<typeof useLesionManager>
}>()

const emit = defineEmits<{
  'lesion-changed': [index: number]
}>()

function handleSelect(index: number) {
  props.manager.switchToLesion(index)
  emit('lesion-changed', index)
}

function handleRemove(index: number) {
  props.manager.removeLesion(index)
  // If we removed the active lesion, emit the new active index
  emit('lesion-changed', props.manager.activeIndex.value)
}

function handleAdd() {
  const lesion = props.manager.addLesion()
  emit('lesion-changed', props.manager.lesions.value.length - 1)
}
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', gap: '8px' }">
    <!-- Header -->
    <div :style="{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }">
      <span :style="{ fontSize: '12px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }">
        白斑区域 ({{ manager.lesionCount.value }})
      </span>
      <button
        :style="{
          padding: '4px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: 500,
          background: 'rgba(99,102,241,0.2)', color: '#a5b4fc',
          border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '4px',
        }"
        @click="handleAdd"
      >
        <i class="ri-add-line"></i> 添加
      </button>
    </div>

    <!-- Lesion list -->
    <div v-if="manager.lesions.value.length === 0" :style="{ padding: '16px', textAlign: 'center', color: '#475569', fontSize: '12px' }">
      暂无白斑区域，点击"添加"创建
    </div>
    <div v-else :style="{ display: 'flex', flexDirection: 'column', gap: '6px' }">
      <LesionCard
        v-for="(lesion, i) in manager.lesions.value"
        :key="lesion.regionIndex"
        :lesion="lesion"
        :index="i"
        :active="i === manager.activeIndex.value"
        @select="handleSelect"
        @remove="handleRemove"
      />
    </div>
  </div>
</template>
