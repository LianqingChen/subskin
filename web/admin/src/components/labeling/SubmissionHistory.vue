<template>
  <ol v-if="submissions.length" class="history">
    <li v-for="s in submissions" :key="s.id">
      <div class="line">
        <strong>#{{ s.id }}</strong>
        <n-tag size="tiny" :type="TYPE[s.status]" :bordered="false">{{ STATUS[s.status] }}</n-tag>
        <span class="muted">{{ s.author ?? '管理员' }} · {{ PREFILL_LABEL[s.prefill_source] }}</span>
        <button type="button" class="link" @click="emit('peek', s.id)">对照</button>
      </div>
      <div class="muted">
        <time v-if="s.created_at" :datetime="s.created_at">{{ fmt(s.created_at) }}</time>
        · 白斑 {{ s.stats.lesion_ratio != null ? s.stats.lesion_ratio.toFixed(1) + '%' : '—' }}
        <template v-if="s.review_mode"> · {{ s.review_mode === 'dual' ? '双人复核' : '单人复核' }}</template>
      </div>
      <p v-if="s.review_note" class="note">{{ s.reviewer ?? '复核人' }}：{{ s.review_note }}</p>
    </li>
  </ol>
  <p v-else class="muted">还没有提交过版本。每次提交都会保留，不会覆盖。</p>
</template>

<script setup lang="ts">
import { PREFILL_LABEL, type SubmissionStatus, type SubmissionSummary } from '@/types/labeling'

defineProps<{ submissions: SubmissionSummary[] }>()
const emit = defineEmits<{ (e: 'peek', id: number): void }>()
const STATUS: Record<SubmissionStatus, string> = { submitted: '待复核', approved: '已通过', returned: '已退回', superseded: '已取代' }
const TYPE: Record<SubmissionStatus, 'info' | 'success' | 'warning' | 'default'> = {
  submitted: 'info', approved: 'success', returned: 'warning', superseded: 'default',
}
function fmt(iso: string) { return new Date(iso.endsWith('Z') ? iso : iso + 'Z').toLocaleString('zh-CN', { hour12: false }) }
</script>

<style scoped>
.history { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; font-size: 12px; color: #cbd5e1; }
li { border-left: 2px solid #1f2937; padding-left: 10px; display: grid; gap: 4px; }
.line { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.muted { color: #94a3b8; }
.note { margin: 0; color: #fbbf24; }
.link { margin-left: auto; background: none; border: 0; color: #2dd4bf; cursor: pointer; font-size: 12px; min-height: 28px; }
</style>
