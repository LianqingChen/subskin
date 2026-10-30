<template>
  <aside class="tool-panel" aria-label="标注工具">
    <section>
      <h3>类别 <small>数字键</small></h3>
      <div class="class-grid">
        <button v-for="c in CLASSES" :key="c.value" type="button" class="class-btn"
          :class="{ active: editor.activeClass.value === c.value }" :title="c.hint" @click="pick(c.value)">
          <span class="swatch" :style="swatch(c.color)" />
          <span class="name">{{ c.label }}</span>
          <kbd>{{ c.key }}</kbd>
          <span class="pct">{{ percent(c.value) }}</span>
        </button>
      </div>
    </section>
    <section>
      <h3>工具</h3>
      <div class="tool-row">
        <button v-for="t in TOOLS" :key="t.id" type="button" class="tool-btn" :class="{ active: editor.tool.value === t.id }"
          :title="t.hint" @click="editor.tool.value = t.id"><i :class="t.icon" /><span>{{ t.label }}</span><kbd>{{ t.key }}</kbd></button>
      </div>
      <label v-if="editor.tool.value === 'brush'" class="slider">画笔 {{ editor.brushSize.value }}px <small>[ ]</small>
        <n-slider v-model:value="editor.brushSize.value" :min="2" :max="120" :step="1" :tooltip="false" />
      </label>
      <label v-if="editor.tool.value === 'wand'" class="slider">颜色容差 {{ editor.tolerance.value }}
        <n-slider v-model:value="editor.tolerance.value" :min="4" :max="60" :step="1" :tooltip="false" />
      </label>
      <p class="tip">{{ toolTip }}</p>
    </section>
    <section>
      <h3>预填与辅助</h3>
      <div class="action-grid">
        <button type="button" :disabled="blind || !hasLayer.ai" @click="emit('use-layer', 'ai')"><i class="ri-magic-line" />载入 AI 初稿</button>
        <button type="button" :disabled="blind || !hasLayer.user" @click="emit('use-layer', 'user')"><i class="ri-user-line" />载入用户日记版</button>
        <button type="button" :disabled="!hasLayer.latest" @click="emit('use-layer', 'latest')"><i class="ri-history-line" />载入上一版本</button>
        <button type="button" :disabled="blind || busy" @click="emit('redraft')"><i class="ri-refresh-line" />重新生成初稿</button>
        <button type="button" :disabled="busy || !editor.stats.value.counts[2]" @click="emit('snap')"><i class="ri-focus-3-line" />白斑贴合边缘</button>
        <button type="button" :disabled="!editor.stats.value.counts[255]" @click="editor.fillUnknown(0)"><i class="ri-paint-fill" />未标处设为背景</button>
        <button type="button" class="danger" @click="emit('use-layer', 'blank')"><i class="ri-eraser-line" />全部清空重画</button>
      </div>
      <p class="tip">当前底稿：<strong>{{ PREFILL_LABEL[prefill] }}</strong>{{ blind ? '（基准集须盲标，不提供 AI/用户版）' : '' }}</p>
    </section>
    <section>
      <h3>显示</h3>
      <label class="slider">叠加透明度 {{ Math.round(opacity * 100) }}%
        <n-slider :value="opacity" :min="0.1" :max="0.9" :step="0.05" :tooltip="false" @update:value="emit('update:opacity', $event)" />
      </label>
      <div class="toggle-row">
        <n-switch :value="showOverlay" size="small" @update:value="emit('update:showOverlay', $event)" /> 显示标注 <kbd>H</kbd>
      </div>
      <label class="ref-select">对照查看（按住 <kbd>C</kbd>）
        <n-select :value="reference" size="small" :options="referenceOptions" @update:value="emit('update:reference', $event)" />
      </label>
    </section>
    <section class="summary">
      <div><span>白斑占比</span><strong>{{ ratio }}</strong></div>
      <div><span>已标像素</span><strong>{{ Math.round(editor.stats.value.labeledFraction * 100) }}%</strong></div>
      <p class="tip">占比 = 白斑 ÷（正常皮肤 + 白斑），与日记「照片内浅色占比」同一口径。</p>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ClassMapEditor, EditorTool } from '@/composables/useClassMapEditor'
import { PREFILL_LABEL, type PrefillSource } from '@/types/labeling'
import { CLASSES, type ClassValue } from '@/utils/classMap'

const props = defineProps<{
  editor: ClassMapEditor
  prefill: PrefillSource
  blind: boolean
  busy: boolean
  hasLayer: { ai: boolean; user: boolean; latest: boolean }
  opacity: number
  showOverlay: boolean
  reference: string
  referenceOptions: { label: string; value: string }[]
}>()
const emit = defineEmits<{
  (e: 'use-layer', key: 'ai' | 'user' | 'latest' | 'blank'): void
  (e: 'redraft'): void
  (e: 'snap'): void
  (e: 'update:opacity', v: number): void
  (e: 'update:showOverlay', v: boolean): void
  (e: 'update:reference', v: string): void
}>()

const TOOLS: { id: EditorTool; label: string; icon: string; key: string; hint: string }[] = [
  { id: 'brush', label: '画笔', icon: 'ri-brush-line', key: 'B', hint: '按住拖动涂抹当前类别' },
  { id: 'fill', label: '填充', icon: 'ri-paint-fill', key: 'F', hint: '把点中的同类连通区改为当前类别；相连的同类会一起改，只改一部分请用魔棒或画笔' },
  { id: 'wand', label: '魔棒', icon: 'ri-magic-line', key: 'W', hint: '按照片颜色相近区域选取并改为当前类别' },
  { id: 'remove', label: '点除', icon: 'ri-delete-back-2-line', key: 'R', hint: '点中一块白斑，整块改回正常皮肤' },
]
const toolTip = computed(() => TOOLS.find((t) => t.id === props.editor.tool.value)?.hint ?? '')
const ratio = computed(() => { const r = props.editor.stats.value.lesionRatio; return r === null ? '—' : `${r.toFixed(1)}%` })

function pick(value: ClassValue) { props.editor.activeClass.value = value; if (props.editor.tool.value === 'remove') props.editor.tool.value = 'brush' }
function swatch(color: [number, number, number] | null) {
  return color ? { background: `rgb(${color.join(',')})` } : { background: 'repeating-linear-gradient(45deg,#475569 0 3px,transparent 3px 6px)' }
}
function percent(value: number) {
  const total = props.editor.map.value.length
  const n = props.editor.stats.value.counts[value] ?? 0
  return total ? `${((n / total) * 100).toFixed(n && n / total < 0.001 ? 2 : 0)}%` : ''
}
</script>

<style scoped>
.tool-panel { width: 260px; flex-shrink: 0; overflow-y: auto; padding: 12px; border-right: 1px solid #1f2937; background: #0b1220; color: #e2e8f0; font-size: 12px; }
section { margin-bottom: 16px; }
h3 { font-size: 12px; font-weight: 600; color: #94a3b8; margin: 0 0 8px; display: flex; justify-content: space-between; }
h3 small { font-weight: 400; }
kbd { font-size: 10px; padding: 0 4px; border: 1px solid #334155; border-radius: 4px; color: #94a3b8; font-family: inherit; }
.class-grid { display: grid; gap: 4px; }
.class-btn { display: grid; grid-template-columns: 14px 1fr auto 40px; align-items: center; gap: 8px; min-height: 36px; padding: 6px 8px; border: 1px solid #1f2937; border-radius: 8px; background: transparent; color: inherit; cursor: pointer; text-align: left; }
.class-btn.active { border-color: #14b8a6; background: rgba(20, 184, 166, .12); }
.swatch { width: 14px; height: 14px; border-radius: 4px; }
.pct { text-align: right; color: #94a3b8; font-variant-numeric: tabular-nums; }
.tool-row { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.tool-btn { display: flex; align-items: center; gap: 6px; min-height: 36px; padding: 6px 8px; border: 1px solid #1f2937; border-radius: 8px; background: transparent; color: inherit; cursor: pointer; }
.tool-btn span { flex: 1; text-align: left; }
.tool-btn.active { border-color: #14b8a6; background: rgba(20, 184, 166, .12); }
.slider { display: block; margin-top: 10px; color: #cbd5e1; }
.tip { color: #64748b; margin: 8px 0 0; line-height: 1.6; }
.action-grid { display: grid; gap: 4px; }
.action-grid button { display: flex; align-items: center; gap: 8px; min-height: 34px; padding: 6px 8px; border: 1px solid #1f2937; border-radius: 8px; background: transparent; color: #cbd5e1; cursor: pointer; text-align: left; }
.action-grid button:disabled { opacity: .4; cursor: default; }
.action-grid .danger { color: #fca5a5; }
.toggle-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.ref-select { display: grid; gap: 6px; margin-top: 10px; color: #cbd5e1; }
.summary { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.summary div { padding: 8px; border: 1px solid #1f2937; border-radius: 8px; display: grid; gap: 4px; }
.summary span { color: #94a3b8; }
.summary strong { font-size: 16px; font-variant-numeric: tabular-nums; }
.summary .tip { grid-column: 1 / -1; }
</style>
