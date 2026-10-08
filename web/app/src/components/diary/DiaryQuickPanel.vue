<script setup lang="ts">
/**
 * DiaryQuickPanel — 快捷记录面板
 * 一键选择心情/患处/睡眠/压力，无需打字
 */
import { ref } from 'vue'

const emit = defineEmits<{
  submit: [payload: Record<string, any>]
}>()

const selectedMood = ref<string | null>(null)
const selectedSkin = ref<string | null>(null)
const selectedSleep = ref<string | null>(null)
const selectedStress = ref<number | null>(null)
const note = ref('')

const moods = [
  { value: 'good', emoji: '😊', label: '开心' },
  { value: 'neutral', emoji: '😐', label: '一般' },
  { value: 'bad', emoji: '😢', label: '低落' },
  { value: 'anxious', emoji: '😰', label: '焦虑' },
  { value: 'hopeful', emoji: '🌟', label: '希望' },
]

const skins = [
  { value: 'stable', emoji: '➡️', label: '稳定' },
  { value: 'improving', emoji: '✨', label: '好转' },
  { value: 'spreading', emoji: '⚠️', label: '扩散' },
  { value: 'new_spots', emoji: '🆕', label: '新发' },
]

const sleeps = [
  { value: 'good', emoji: '😴', label: '好' },
  { value: 'fair', emoji: '🥱', label: '一般' },
  { value: 'poor', emoji: '😵', label: '差' },
]

function submit() {
  const payload: Record<string, any> = {}
  if (selectedMood.value) payload.mood = selectedMood.value
  if (selectedSkin.value) payload.skin_condition = selectedSkin.value
  if (selectedSleep.value) payload.sleep_quality = selectedSleep.value
  if (selectedStress.value) payload.stress_level = selectedStress.value
  if (note.value.trim()) payload.note = note.value.trim()

  if (Object.keys(payload).length === 0) return
  emit('submit', payload)

  // Reset
  selectedMood.value = null
  selectedSkin.value = null
  selectedSleep.value = null
  selectedStress.value = null
  note.value = ''
}

const hasSelection = ref(false)
function checkSelection() {
  hasSelection.value = !!(selectedMood.value || selectedSkin.value || selectedSleep.value || selectedStress.value || note.value.trim())
}
</script>

<template>
  <div class="quick-panel">
    <!-- Mood -->
    <div class="quick-panel__section">
      <span class="quick-panel__label">心情</span>
      <div class="quick-panel__options">
        <button
          v-for="m in moods"
          :key="m.value"
          class="quick-panel__opt"
          :class="{ 'quick-panel__opt--active': selectedMood === m.value }"
          @click="selectedMood = selectedMood === m.value ? null : m.value; checkSelection()"
        >
          <span class="quick-panel__opt-emoji">{{ m.emoji }}</span>
          <span class="quick-panel__opt-label">{{ m.label }}</span>
        </button>
      </div>
    </div>

    <!-- Skin condition -->
    <div class="quick-panel__section">
      <span class="quick-panel__label">患处</span>
      <div class="quick-panel__options">
        <button
          v-for="s in skins"
          :key="s.value"
          class="quick-panel__opt"
          :class="{ 'quick-panel__opt--active': selectedSkin === s.value }"
          @click="selectedSkin = selectedSkin === s.value ? null : s.value; checkSelection()"
        >
          <span class="quick-panel__opt-emoji">{{ s.emoji }}</span>
          <span class="quick-panel__opt-label">{{ s.label }}</span>
        </button>
      </div>
    </div>

    <!-- Sleep -->
    <div class="quick-panel__section">
      <span class="quick-panel__label">睡眠</span>
      <div class="quick-panel__options">
        <button
          v-for="s in sleeps"
          :key="s.value"
          class="quick-panel__opt"
          :class="{ 'quick-panel__opt--active': selectedSleep === s.value }"
          @click="selectedSleep = selectedSleep === s.value ? null : s.value; checkSelection()"
        >
          <span class="quick-panel__opt-emoji">{{ s.emoji }}</span>
          <span class="quick-panel__opt-label">{{ s.label }}</span>
        </button>
      </div>
    </div>

    <!-- Stress -->
    <div class="quick-panel__section">
      <span class="quick-panel__label">压力</span>
      <div class="quick-panel__options">
        <button
          v-for="n in 5"
          :key="n"
          class="quick-panel__opt quick-panel__opt--num"
          :class="{ 'quick-panel__opt--active': selectedStress === n }"
          @click="selectedStress = selectedStress === n ? null : n; checkSelection()"
        >
          {{ n }}
        </button>
      </div>
    </div>

    <!-- Note -->
    <div class="quick-panel__section">
      <input
        v-model="note"
        class="quick-panel__note"
        placeholder="补充说明（可选）"
        maxlength="200"
        @input="checkSelection"
      />
    </div>

    <!-- Submit -->
    <button
      class="quick-panel__submit"
      :disabled="!hasSelection"
      @click="submit"
    >
      <i class="ri-check-line"></i>
      记录
    </button>
  </div>
</template>

<style scoped>
.quick-panel {
  background: white;
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid #f1f5f9;
}

html.dark .quick-panel {
  background: #1e293b;
  border-color: #334155;
}

.quick-panel__section {
  margin-bottom: 12px;
}

.quick-panel__label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
  display: block;
}

html.dark .quick-panel__label {
  color: #94a3b8;
}

.quick-panel__options {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-panel__opt {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.15s;
}

html.dark .quick-panel__opt {
  border-color: #334155;
  background: #0f172a;
}

.quick-panel__opt--active {
  border-color: var(--color-primary-500);
  background: color-mix(in srgb, var(--color-primary-500) 10%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary-500) 15%, transparent);
}

.quick-panel__opt:active {
  transform: scale(0.94);
}

.quick-panel__opt-emoji {
  font-size: 18px;
}

.quick-panel__opt-label {
  font-size: 10px;
  color: #64748b;
}

html.dark .quick-panel__opt-label {
  color: #94a3b8;
}

.quick-panel__opt--num {
  flex-direction: row;
  width: 36px;
  height: 36px;
  padding: 0;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
}

.quick-panel__opt--num.quick-panel__opt--active {
  color: var(--color-primary-600);
}

.quick-panel__note {
  width: 100%;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 13px;
  color: #334155;
  outline: none;
  transition: border-color 0.2s;
}

html.dark .quick-panel__note {
  background: #0f172a;
  border-color: #334155;
  color: #e2e8f0;
}

.quick-panel__note:focus {
  border-color: var(--color-primary-500);
}

.quick-panel__submit {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px;
  border-radius: 10px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-panel__submit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.quick-panel__submit:not(:disabled):active {
  transform: scale(0.97);
}
</style>
