<script setup lang="ts">
/**
 * ShortcutPanel — collapsible keyboard shortcut reference for the labeling workspace.
 */

import { ref, computed } from 'vue'
import { ALL_TOOLS } from '@/components/labeling/tools/BaseTool'

const expanded = ref(false)

const shortcuts = computed(() => [
  { key: 'B', desc: '皮肤画笔', icon: 'ri-brush-line' },
  { key: 'L', desc: '白斑画笔', icon: 'ri-brush-2-line' },
  { key: 'G', desc: '智能填充', icon: 'ri-contrast-drop-2-line' },
  { key: 'S', desc: '套索选择', icon: 'ri-shapes-line' },
  { key: 'P', desc: '多边形选择', icon: 'ri-pentagon-line' },
  { key: 'E', desc: '橡皮擦', icon: 'ri-eraser-line' },
  { key: '1-6', desc: '快速切换工具', icon: 'ri-keyboard-box-line' },
  { key: 'Ctrl+Z', desc: '撤销', icon: 'ri-arrow-go-back-line' },
  { key: 'Ctrl+Y', desc: '重做', icon: 'ri-arrow-go-forward-line' },
  { key: '空格+拖拽', desc: '平移画布', icon: 'ri-drag-move-line' },
  { key: '滚轮', desc: '缩放', icon: 'ri-zoom-in-line' },
  { key: 'R', desc: '适应窗口', icon: 'ri-fullscreen-line' },
  { key: 'F', desc: '画布全屏', icon: 'ri-fullscreen-fill' },
  { key: 'Esc', desc: '取消/关闭', icon: 'ri-close-line' },
  { key: '[ / ]', desc: '调整填充容差', icon: 'ri-contrast-drop-line' },
  { key: 'Backspace', desc: '删除多边形顶点', icon: 'ri-delete-back-line' },
  { key: 'Enter', desc: '闭合多边形', icon: 'ri-check-line' },
])
</script>

<template>
  <div
    :style="{
      background: 'rgba(15,23,42,0.7)',
      border: '1px solid rgba(148,163,184,0.12)',
      borderRadius: '8px',
      overflow: 'hidden',
      transition: 'all 0.2s',
      flexShrink: 0,
    }"
  >
    <!-- Toggle header -->
    <button
      :style="{
        width: '100%', padding: '8px 12px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'transparent', border: 'none', color: '#94a3b8',
        fontSize: '11px', fontWeight: 600, cursor: 'pointer',
        textTransform: 'uppercase', letterSpacing: '0.5px',
      }"
      @click="expanded = !expanded"
    >
      <span :style="{ display: 'flex', alignItems: 'center', gap: '6px' }">
        <i class="ri-keyboard-box-line"></i> 快捷键
      </span>
      <i :class="expanded ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'"></i>
    </button>

    <!-- Shortcut list -->
    <div
      v-if="expanded"
      :style="{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px',
        padding: '4px 12px 10px', maxHeight: '220px', overflowY: 'auto',
      }"
    >
      <div
        v-for="s in shortcuts" :key="s.key"
        :style="{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '3px 6px', borderRadius: '4px',
          fontSize: '11px', color: '#cbd5e1',
        }"
      >
        <kbd
          :style="{
            display: 'inline-block', padding: '1px 5px',
            background: 'rgba(99,102,241,0.2)', border: '1px solid rgba(99,102,241,0.3)',
            borderRadius: '3px', fontSize: '10px', fontFamily: 'monospace',
            color: '#a5b4fc', minWidth: '20px', textAlign: 'center',
          }"
        >{{ s.key }}</kbd>
        <span :style="{ fontSize: '10px', color: '#64748b' }">{{ s.desc }}</span>
      </div>
    </div>
  </div>
</template>
