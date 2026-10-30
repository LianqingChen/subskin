<template>
  <section class="filters" aria-label="任务筛选">
    <div class="tabs" role="tablist">
      <button v-for="tab in TABS" :key="tab.value" role="tab" class="tab" :class="{ active: filters.status === tab.value }"
        :aria-selected="filters.status === tab.value" @click="emit('change', { status: tab.value })">{{ tab.label }}</button>
    </div>
    <div class="controls">
      <n-select class="sel" size="medium" :value="filters.origin ?? ''" :options="originOptions" aria-label="来源" @update:value="(v: string) => emit('change', { origin: (v || null) as TaskOrigin | null })" />
      <n-select class="sel" size="medium" :value="filters.group ?? ''" :options="groupOptions" aria-label="部位分组" @update:value="(v: string) => emit('change', { group: v || null })" />
      <n-select class="sel" size="medium" :value="filters.sort ?? 'queue'" :options="SORTS" aria-label="排序" @update:value="(v: 'queue' | 'newest') => emit('change', { sort: v })" />
      <n-checkbox :checked="Boolean(filters.benchmark)" @update:checked="(v: boolean) => emit('change', { benchmark: v || null })">仅基准集</n-checkbox>
      <n-checkbox :checked="Boolean(filters.escalate)" @update:checked="(v: boolean) => emit('change', { escalate: v })">需医生</n-checkbox>
      <n-checkbox :checked="Boolean(filters.mine)" @update:checked="(v: boolean) => emit('change', { mine: v })">我提交的</n-checkbox>
    </div>
  </section>
</template>
<script setup lang="ts">
import { GROUP_LABEL, ORIGIN_LABEL, type TaskFilters, type TaskOrigin } from '@/types/labeling'

defineProps<{ filters: TaskFilters }>()
const emit = defineEmits<{ change: [patch: Partial<TaskFilters>] }>()

const TABS: { value: TaskFilters['status']; label: string }[] = [
  { value: 'open', label: '待处理' }, { value: 'review', label: '待复核' }, { value: 'gold', label: '金标准' },
  { value: 'rejected', label: '不可用' }, { value: 'skipped', label: '已跳过' }, { value: 'all', label: '全部' },
]
const SORTS = [{ label: '队列顺序', value: 'queue' }, { label: '最新', value: 'newest' }]
const originOptions = [{ label: '全部来源', value: '' },
  ...(Object.keys(ORIGIN_LABEL) as TaskOrigin[]).map((value) => ({ label: ORIGIN_LABEL[value], value }))]
const groupOptions = [{ label: '全部部位', value: '' },
  ...Object.entries(GROUP_LABEL).map(([value, label]) => ({ label, value }))]
</script>
<style scoped>
.filters { display: flex; flex-direction: column; gap: 12px; margin-bottom: 14px; }
.tabs { display: flex; gap: 4px; overflow-x: auto; }
.tab { min-height: 44px; padding: 8px 14px; border: 0; border-radius: 9px; background: transparent; color: var(--lb-muted); cursor: pointer; font-size: 13px; white-space: nowrap; }
.tab.active { background: var(--lb-accent-bg); color: var(--lb-accent); font-weight: 600; }
.controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; }
.sel { width: 130px; }
@media (max-width: 767px) { .sel { flex: 1 1 100px; } }
</style>
