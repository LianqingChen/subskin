<template>
  <aside class="archive-filters" aria-label="档案筛选">
    <p class="filter-heading">文档分类</p>
    <button class="category" :class="{ active: !filters.category }" @click="emit('change', { category: '' })">
      <span>全部档案</span><span>{{ archive?.stats.documents ?? 0 }}</span>
    </button>
    <button v-for="item in archive?.categories ?? []" :key="item.value" class="category"
      :class="{ active: filters.category === item.value }" @click="emit('change', { category: item.value })">
      <span>{{ item.label }}</span><span>{{ item.count }}</span>
    </button>
    <label class="filter-heading" for="archive-source">文档来源</label>
    <select id="archive-source" :value="filters.source" @change="emit('change', { source: inputValue($event) })">
      <option value="">全部来源</option>
      <option v-for="item in archive?.sources ?? []" :key="item.value" :value="item.value">{{ item.label }}（{{ item.count }}）</option>
    </select>
    <label class="filter-heading" for="archive-month">文档月份</label>
    <select id="archive-month" :value="filters.month" @change="emit('change', { month: inputValue($event) })">
      <option value="">全部月份</option>
      <option v-for="item in archive?.months ?? []" :key="item.value" :value="item.value">{{ item.label }}（{{ item.count }}）</option>
    </select>
    <button class="reset" @click="emit('change', { q: '', category: '', source: '', month: '' })">清除全部筛选</button>
    <p class="source-note">保留原始文档与来源。文档中的计划、进度不代表正式上线状态。</p>
  </aside>
</template>
<script setup lang="ts">
import type { ArchiveFilters, ArchiveList } from '@/types/planning'
defineProps<{ archive: ArchiveList | null; filters: ArchiveFilters }>()
const emit = defineEmits<{ change: [patch: Partial<ArchiveFilters>] }>()
function inputValue(event: Event) { return (event.target as HTMLSelectElement).value }
</script>
<style scoped>
.archive-filters { padding: 16px; width: 208px; flex-shrink: 0; background: var(--archive-panel); border: 1px solid var(--archive-border); border-radius: 14px; }
.filter-heading { display: block; margin: 8px 0 10px; font-size: 12px; color: var(--archive-muted); font-weight: 600; }
.category { display: flex; justify-content: space-between; gap: 10px; width: 100%; padding: 10px; min-height: 44px; border: 0; border-radius: 8px; background: transparent; color: var(--archive-text); cursor: pointer; text-align: left; }
.category:hover, .category.active { background: var(--archive-accent-bg); color: var(--archive-accent); }
.category.active { font-weight: 600; }
select { width: 100%; min-height: 44px; border-radius: 8px; padding: 8px; background: var(--archive-background); color: var(--archive-text); border: 1px solid var(--archive-border); font-size: 12px; }
.reset { width: 100%; min-height: 44px; margin-top: 12px; border: 0; background: transparent; color: var(--archive-accent); cursor: pointer; }
.source-note { color: var(--archive-muted); line-height: 1.7; font-size: 12px; margin: 14px 0 0; }
@media (max-width: 767px) { .archive-filters { width: 100%; border: 0; } }
</style>
