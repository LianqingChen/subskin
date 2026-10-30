<template>
  <div class="block">
    <div class="title">训练记录</div>
    <div v-for="r in runs" :key="r.run_id" class="row">
      <code>{{ r.run_id }}</code>
      <n-tag :type="(STATE[r.state] ?? ['', 'default'])[1]" size="small" :bordered="false">{{ (STATE[r.state] ?? [r.state])[0] }}</n-tag>
      <span v-if="r.state === 'completed'" class="num">白斑 Dice {{ pct(r.gate.dice) }}（线上初稿 {{ pct(r.gate.baseline_dice) }}）· 皮肤 Dice {{ pct(r.gate.skin_dice) }}</span>
      <span v-if="r.error" class="err">{{ r.error }}</span>
      <n-button v-if="ACTIVE.includes(r.state)" size="small" @click="emit('cancel', r.run_id)">停止</n-button>
      <template v-if="r.state === 'completed'">
        <n-button v-if="r.gate.passed" size="small" type="warning" @click="emit('register', r)">登记上线</n-button>
        <span v-else class="muted">未达门槛：{{ r.gate.reasons.join('；') }}</span>
      </template>
    </div>
  </div>
</template>
<script setup lang="ts">
import type { Run } from '@/types/training'

defineProps<{ runs: Run[] }>()
const emit = defineEmits<{ cancel: [id: string]; register: [run: Run] }>()
const ACTIVE = ['queued', 'training', 'evaluating']
const STATE: Record<string, [string, 'default' | 'info' | 'success' | 'error' | 'warning']> = {
  queued: ['排队中', 'default'], training: ['训练中', 'info'], evaluating: ['评测中', 'info'], completed: ['已完成', 'success'], failed: ['失败', 'error'],
}
const pct = (v?: number | null) => (v == null ? '—' : v.toFixed(3))
</script>
<style scoped>
.block { margin-top: 16px; }
.title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid var(--tr-border); font-size: 12px; }
.row code { font-size: 11px; color: var(--tr-accent); }
.muted { color: var(--tr-muted); }
.err { color: #e88080; }
.num { font-variant-numeric: tabular-nums; }
</style>
