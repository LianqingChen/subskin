<template>
  <section class="document-list" aria-label="规划文档列表">
    <header class="list-heading"><span>{{ total }} 份文档</span><span>按文档日期 · 最新在前</span></header>
    <div v-if="loading" class="list-state" role="status"><n-spin size="small" /> 正在检索档案…</div>
    <div v-else-if="!items.length" class="list-state">没有匹配的文档，试试其他关键词或清除筛选。</div>
    <div v-else ref="scroller" class="list-scroll" @scroll="rememberScroll">
      <button v-for="item in items" :key="item.id" class="document-card" :class="{ selected: item.id === selectedId }"
        :aria-current="item.id === selectedId ? 'true' : undefined" @click="emit('select', item.id)">
        <span class="card-meta"><span class="category-badge">{{ archiveCategories[item.category] }}</span>
          <time v-if="item.date" :datetime="item.date">{{ item.date }}</time><span v-else>日期未知</span></span>
        <strong>{{ item.title }}</strong>
        <span v-if="item.summary" class="card-summary">{{ item.summary }}</span>
        <span class="card-topic" :title="item.topic_title">{{ item.topic_title }}</span>
        <span class="card-bottom"><span>{{ item.source }}</span><span v-if="(item.related_count ?? 0) > 1">同主题 {{ item.related_count }} 份</span></span>
      </button>
    </div>
    <footer v-if="total > 20" class="pagination">
      <button :disabled="page <= 1 || loading" @click="emit('page', page - 1)">上一页</button>
      <span>{{ page }} / {{ Math.ceil(total / 20) }}</span>
      <button :disabled="page >= Math.ceil(total / 20) || loading" @click="emit('page', page + 1)">下一页</button>
    </footer>
  </section>
</template>
<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { archiveCategories } from '@/types/planning'
import type { ArchiveDocument } from '@/types/planning'
const props = defineProps<{ items: ArchiveDocument[]; total: number; page: number; loading: boolean; selectedId: string; scroll: number }>()
const emit = defineEmits<{ select: [id: string]; page: [page: number]; scroll: [top: number] }>()
const scroller = ref<HTMLElement | null>(null)
function rememberScroll() { emit('scroll', scroller.value?.scrollTop ?? 0) }
watch(() => [props.items, props.loading], async () => {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = props.scroll
}, { immediate: true })
</script>
<style scoped>
.document-list { min-width: 0; display: flex; flex-direction: column; border: 1px solid var(--archive-border); border-radius: 14px; overflow: hidden; background: var(--archive-panel); }
.list-heading { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 4px; padding: 16px; font-size: 12px; color: var(--archive-muted); border-bottom: 1px solid var(--archive-border); }
.list-scroll { max-height: 70dvh; overflow: auto; padding: 8px; }
.document-card { display: flex; flex-direction: column; gap: 10px; border: 1px solid transparent; border-bottom-color: var(--archive-border); width: 100%; padding: 16px 12px; text-align: left; color: var(--archive-text); background: transparent; cursor: pointer; border-radius: 10px; }
.document-card:hover, .document-card.selected { background: var(--archive-accent-bg); }
.document-card.selected { border-color: var(--archive-accent); }
.document-card strong { font-size: 15px; line-height: 1.65; overflow-wrap: anywhere; }
.card-meta, .card-bottom { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 11px; color: var(--archive-muted); }
.category-badge { padding: 3px 8px; border-radius: 5px; background: var(--archive-accent-bg); color: var(--archive-accent); }
.card-summary { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; color: var(--archive-muted); font-size: 12px; line-height: 1.7; }
.card-topic { color: var(--archive-muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.list-state { padding: 40px 24px; text-align: center; color: var(--archive-muted); line-height: 1.8; }
.pagination { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-top: 1px solid var(--archive-border); font-size: 12px; }
.pagination button { min-height: 44px; border: 0; color: var(--archive-accent); background: transparent; cursor: pointer; }
.pagination button:disabled { opacity: .4; cursor: default; }
</style>
