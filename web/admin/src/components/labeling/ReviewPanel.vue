<template>
  <section class="review">
    <template v-if="pending">
      <header>
        <strong>待复核 · 版本 #{{ pending.id }}</strong>
        <span>{{ pending.author ?? '管理员' }} · {{ PREFILL_LABEL[pending.prefill_source] }} · {{ minutes(pending.duration_ms) }}</span>
      </header>
      <dl class="metrics">
        <div><dt>白斑占比</dt><dd>{{ pct(pending.stats.lesion_ratio) }}</dd></div>
        <div><dt>已标像素</dt><dd>{{ pending.stats.labeled_fraction != null ? Math.round(pending.stats.labeled_fraction * 100) + '%' : '—' }}</dd></div>
        <div><dt>与 AI 初稿（白斑 Dice）</dt><dd>{{ dice(pending.stats.vs_ai?.lesion_dice) }}</dd></div>
        <div><dt>与用户日记版（白斑 Dice）</dt><dd>{{ dice(pending.stats.vs_user?.lesion_dice) }}</dd></div>
      </dl>
      <p class="rule" :class="{ warn: blocked }">{{ ruleText }}</p>
      <n-input v-model:value="note" type="textarea" size="small" maxlength="500" :autosize="{ minRows: 2, maxRows: 4 }"
        placeholder="复核意见（退回时必填，写清哪里需要改）" />
      <div class="actions">
        <n-button size="small" :disabled="busy" @click="emit('peek', pending.id)"><template #icon><i class="ri-eye-line" /></template>对照此版本</n-button>
        <n-button size="small" type="warning" :disabled="busy || !note.trim()" @click="emit('return', pending.id, note)">退回</n-button>
        <n-button size="small" type="primary" :disabled="busy || blocked" @click="emit('approve', pending.id, note)">通过，设为金标准</n-button>
      </div>
    </template>
    <p v-else class="empty">当前没有待复核的提交。提交后可由你或其他管理员复核。</p>
    <div v-if="gold" class="gold"><i class="ri-medal-line" /> 金标准：版本 #{{ gold.submission_id ?? '—' }} · {{ gold.review_mode === 'dual' ? '双人复核' : '单人复核' }}</div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PREFILL_LABEL, type GoldInfo, type SubmissionSummary } from '@/types/labeling'

const props = defineProps<{ submissions: SubmissionSummary[]; gold: GoldInfo | null; benchmark: boolean; me: number | null; busy: boolean }>()
const emit = defineEmits<{
  (e: 'approve', id: number, note: string): void
  (e: 'return', id: number, note: string): void
  (e: 'peek', id: number): void
}>()
const note = ref('')
const pending = computed(() => props.submissions.find((s) => s.status === 'submitted') ?? null)
const own = computed(() => !!pending.value && pending.value.author_id === props.me)
const blocked = computed(() => props.benchmark && (own.value || !pending.value?.blind))
const ruleText = computed(() => {
  if (props.benchmark && !pending.value?.blind) return '基准集样本必须盲标，这个版本用了预填，不能通过。'
  if (props.benchmark && own.value) return '基准集样本须由提交人以外的管理员复核。'
  if (own.value) return '这是你自己的提交：可以通过，但会记为「单人复核」。'
  return '你不是提交人：通过将记为「双人复核」。'
})
watch(pending, () => { note.value = '' })
function pct(v?: number | null) { return v == null ? '—' : `${v.toFixed(1)}%` }
function dice(v?: number | null) { return v == null ? '—' : v.toFixed(2) }
function minutes(ms: number | null) { return ms ? `${(ms / 60000).toFixed(1)} 分钟` : '用时未知' }
</script>

<style scoped>
.review { display: grid; gap: 10px; font-size: 12px; color: #cbd5e1; }
header { display: grid; gap: 4px; }
header span { color: #94a3b8; }
.metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 0; }
.metrics div { border: 1px solid #1f2937; border-radius: 8px; padding: 6px 8px; }
dt { color: #94a3b8; }
dd { margin: 2px 0 0; font-size: 15px; font-variant-numeric: tabular-nums; }
.rule { margin: 0; color: #94a3b8; line-height: 1.6; }
.rule.warn { color: #fbbf24; }
.actions { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
.empty { color: #64748b; margin: 0; }
.gold { color: #fcd34d; }
</style>
