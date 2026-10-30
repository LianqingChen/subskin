<template>
  <div class="task-list" role="list">
    <div v-if="!items.length" class="empty" role="status">
      <i class="ri-inbox-line" aria-hidden="true" /><p>{{ loading ? '正在加载…' : '当前筛选下没有任务' }}</p>
    </div>
    <div v-for="item in items" :key="item.id" class="row" role="listitem" tabindex="0"
      @click="emit('open', item.id)" @keydown.enter="emit('open', item.id)">
      <AuthThumb :id="item.id" :alt="`任务 #${item.id} 缩略图`" />
      <div class="cell main">
        <div class="line">
          <strong class="num">#{{ item.id }}</strong>
          <n-tag size="small" :bordered="false">{{ ORIGIN_LABEL[item.origin] }}</n-tag>
          <n-tag size="small" :type="STATUS_TYPE[item.status]" :bordered="false">{{ STATUS_LABEL[item.status] }}</n-tag>
          <span class="site">{{ item.body_site_label || '未填' }}</span>
        </div>
        <div class="line flags">
          <n-tag v-if="item.benchmark" size="small" type="info" :bordered="false">基准集</n-tag>
          <n-tag v-if="item.user_revision_newer" size="small" type="warning" :bordered="false">用户有新修订</n-tag>
          <n-tag v-if="item.escalate" size="small" type="error" :bordered="false">需医生</n-tag>
          <n-tag v-for="reason in item.rejection?.reasons ?? []" :key="reason" size="small" :bordered="false">{{ REASON_LABEL[reason] ?? reason }}</n-tag>
        </div>
        <p class="muted latest">{{ latestText(item) }}</p>
      </div>
      <div class="cell ratio num">
        <span class="muted label">白斑占比</span>
        <span>{{ ratioText(item) }}</span>
      </div>
      <div class="cell priority">
        <span class="muted label">优先级</span>
        <template v-if="item.priority !== null">
          <div class="bar" role="img" :aria-label="`优先级 ${Math.round(item.priority * 100)}`"><i :style="{ width: `${clamp(item.priority * 100)}%` }" /></div>
          <span class="num">{{ Math.round(item.priority * 100) }}</span>
        </template>
        <span v-else class="muted">—</span>
      </div>
      <n-button class="act" size="medium" :type="item.status === 'in_review' ? 'warning' : 'primary'" secondary
        @click.stop="emit('open', item.id)">{{ item.status === 'in_review' ? '复核' : '标注' }}</n-button>
    </div>
  </div>
</template>
<script setup lang="ts">
import AuthThumb from '@/components/labeling/AuthThumb.vue'
import { ORIGIN_LABEL, PREFILL_LABEL, REASON_LABEL, STATUS_LABEL, type TaskStatus, type TaskSummary } from '@/types/labeling'

defineProps<{ items: TaskSummary[]; loading: boolean }>()
const emit = defineEmits<{ open: [id: number] }>()

const STATUS_TYPE: Record<TaskStatus, 'default' | 'warning' | 'info' | 'success' | 'error'> = {
  pending: 'default', returned: 'warning', in_review: 'info', gold: 'success', rejected: 'error', skipped: 'default',
}
const clamp = (value: number) => Math.max(0, Math.min(100, value))
// lesion_ratio / user_ratio are already percentages (0–100); priority is 0–1.
const percent = (value: number | null) => (value === null ? '—' : `${value.toFixed(1)}%`)

function ratioText(item: TaskSummary) {
  return `管理员 ${percent(item.lesion_ratio)} / 用户 ${percent(item.user_ratio)}`
}
function relative(iso: string | null): string {
  if (!iso) return ''
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`
  if (minutes < 43200) return `${Math.floor(minutes / 1440)} 天前`
  return new Date(iso).toLocaleDateString('zh-CN')
}
function latestText(item: TaskSummary): string {
  const latest = item.latest
  if (!latest) return '暂无提交'
  return [latest.author ?? '未知', PREFILL_LABEL[latest.prefill_source], relative(latest.created_at)].filter(Boolean).join(' · ')
}
</script>
<style scoped>
.task-list { display: flex; flex-direction: column; gap: 8px; }
.row { display: grid; grid-template-columns: 56px minmax(0, 1fr) 190px 130px auto; align-items: center; gap: 14px; padding: 10px 14px; border: 1px solid var(--lb-border); border-radius: 12px; background: var(--lb-panel); cursor: pointer; }
.row:hover, .row:focus-visible { border-color: var(--lb-accent); outline: none; }
.cell { min-width: 0; }
.main { display: flex; flex-direction: column; gap: 6px; }
.line { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.flags:empty { display: none; }
.site { font-size: 13px; }
.muted { color: var(--lb-muted); font-size: 12px; margin: 0; }
.num { font-variant-numeric: tabular-nums; }
.ratio, .priority { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.label { display: none; }
.bar { height: 6px; border-radius: 3px; background: rgba(128, 128, 128, .2); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--lb-accent); }
.act { min-width: 64px; min-height: 44px; }
.empty { text-align: center; padding: 48px 0; color: var(--lb-muted); }
.empty i { font-size: 36px; }
@media (max-width: 1100px) { .row { grid-template-columns: 56px minmax(0, 1fr) auto; } .ratio, .priority { grid-column: 2; flex-direction: row; align-items: center; gap: 8px; } .label { display: inline; } .bar { width: 80px; } .act { grid-column: 3; grid-row: 1 / span 3; } }
@media (max-width: 767px) { .row { padding: 10px; gap: 10px; } .act { grid-row: 1; align-self: start; } }
</style>
