<template>
  <main class="planning-page" :style="themeStyle">
    <header class="archive-heading">
      <div><p class="eyebrow">SUBSKIN · 项目记忆</p><h1>规划档案</h1><p class="description">从最初的想法，到每一次方案与修改。集中查看研究、设计和执行记录。</p></div>
      <button class="outline-button" :disabled="loading || reading" @click="refresh"><i class="ri-refresh-line" /> 刷新档案</button>
    </header>
    <section class="archive-stats" aria-label="档案概览">
      <div><span>已收录文档</span><strong>{{ archive?.stats.documents ?? '—' }} <small>份</small></strong></div>
      <div><span>规划主题</span><strong>{{ archive?.stats.topics ?? '—' }} <small>项</small></strong></div>
      <div><span>最近文件更新</span><strong class="latest-update">{{ latestUpdate }}</strong></div>
    </section>
    <form class="search-bar" @submit.prevent="setFilters({ q: search })">
      <button type="button" class="outline-button" :aria-expanded="showFilters" @click="showFilters = !showFilters"><i class="ri-filter-3-line" /> 筛选{{ activeFilters ? `（${activeFilters}）` : '' }}</button>
      <label for="archive-search" class="sr-only">搜索标题、正文或文件路径</label>
      <input id="archive-search" v-model="search" type="search" maxlength="200" placeholder="搜索标题、正文或文件路径…" />
      <button class="search-button" type="submit">搜索</button>
      <button v-if="selectedId" type="button" class="outline-button focus-toggle" @click="focused = !focused">{{ focused ? '显示列表' : '专注阅读' }}</button>
    </form>
    <div v-if="error" class="archive-error" role="alert"><span>{{ error }}</span><button @click="refresh">重试</button><router-link to="/login">重新登录</router-link></div>
    <details v-if="archive?.warnings.length" class="archive-warning"><summary>{{ archive.warnings.length }} 份文件未能载入，查看原因</summary><p v-for="item in archive.warnings" :key="item.path">{{ item.path }}：{{ item.message }}</p></details>
    <div class="archive-workspace" :class="{ 'has-document': selectedId, focused }">
      <div v-if="showFilters && !focused" class="filters-container">
        <button class="close-filters outline-button" @click="showFilters = false">关闭筛选</button>
        <ArchiveFilters :archive="archive" :filters="filters" @change="changeFilters" />
      </div>
      <div class="archive-content">
        <ArchiveList v-show="!focused" class="archive-list-pane" :items="archive?.items ?? []" :total="archive?.total ?? 0"
          :page="filters.page" :loading="loading" :selected-id="selectedId" :scroll="listScroll"
          @scroll="listScroll = $event" @select="select" @page="setFilters({ page: $event })" />
        <div class="archive-detail-pane">
          <div v-if="reading" class="empty-reader" role="status"><n-spin /><p>正在打开文档…</p></div>
          <div v-else-if="documentError" class="empty-reader" role="alert"><p>{{ documentError }}</p><button class="outline-button" @click="read">重试</button><button class="outline-button" @click="backToList">返回列表</button></div>
          <ArchiveReader v-else-if="document" :document="document" @back="backToList" @select="select" @open-path="openPath" />
          <div v-else class="empty-reader"><i class="ri-book-open-line" /><h2>每一份方案，都有迹可循</h2><p>选择左侧文档，查看正文与同主题的计划、进度和验收记录。</p><span>保留现有历史文档，不代表文件的全部修订版本。</span></div>
        </div>
      </div>
    </div>
  </main>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useThemeVars } from 'naive-ui'
import { usePlanningArchive } from '@/composables/usePlanningArchive'
import type { ArchiveFilters as Filters } from '@/types/planning'
import ArchiveFilters from '@/components/planning/ArchiveFilters.vue'
import ArchiveList from '@/components/planning/ArchiveList.vue'
import ArchiveReader from '@/components/planning/ArchiveReader.vue'
const { archive, document, loading, reading, error, documentError, selectedId, filters, listScroll,
  setFilters, select, openPath, refresh, read } = usePlanningArchive()
const theme = useThemeVars()
const themeStyle = computed(() => ({
  '--archive-panel': theme.value.cardColor, '--archive-background': theme.value.bodyColor,
  '--archive-text': theme.value.textColor1, '--archive-muted': theme.value.textColor3,
  '--archive-border': theme.value.borderColor, '--archive-accent': theme.value.primaryColorHover,
  '--archive-accent-bg': theme.value.primaryColor + '18',
}))
const search = ref(filters.value.q)
const showFilters = ref(window.innerWidth >= 768)
const focused = ref(false)
const activeFilters = computed(() => [filters.value.category, filters.value.source, filters.value.month].filter(Boolean).length)
const latestUpdate = computed(() => archive.value?.stats.updated_at ? new Date(archive.value.stats.updated_at).toLocaleDateString('zh-CN') : '—')
watch(() => filters.value.q, (value) => { search.value = value })
watch(selectedId, (id) => { if (!id) focused.value = false })
async function backToList() { focused.value = false; await select('') }
async function changeFilters(patch: Partial<Filters>) {
  await setFilters(patch)
  if (window.innerWidth < 768) { showFilters.value = false; await backToList() }
}
</script>
<style scoped>
.planning-page { max-width: 1440px; margin: 0 auto; color: var(--archive-text); padding-bottom: 24px; }
.archive-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 24px; }
.eyebrow { font-size: 11px; letter-spacing: .15em; color: var(--archive-accent); margin: 0 0 8px; }
h1 { font-size: 28px; font-weight: 650; line-height: 1.4; margin: 0; }
.description { color: var(--archive-muted); margin: 8px 0 0; font-size: 13px; line-height: 1.7; }
.outline-button { display: inline-flex; justify-content: center; align-items: center; gap: 6px; min-height: 44px; padding: 8px 14px; border: 1px solid var(--archive-border); border-radius: 9px; background: transparent; color: var(--archive-text); cursor: pointer; flex-shrink: 0; font-size: 12px; }
button:disabled { opacity: .5; cursor: default; }
.archive-stats { display: grid; grid-template-columns: 1fr 1fr 1.3fr; gap: 12px; margin-bottom: 20px; }
.archive-stats > div { display: flex; flex-direction: column; gap: 8px; background: var(--archive-panel); border: 1px solid var(--archive-border); border-radius: 12px; padding: 16px 20px; }
.archive-stats span { color: var(--archive-muted); font-size: 12px; }
.archive-stats strong { font-size: 26px; font-weight: 600; }.archive-stats small { font-size: 12px; color: var(--archive-muted); font-weight: 400; }
.archive-stats .latest-update { font-size: 20px; line-height: 39px; }
.search-bar { display: flex; gap: 10px; margin-bottom: 16px; }
.search-bar input { flex: 1; min-width: 0; min-height: 44px; border: 1px solid var(--archive-border); border-radius: 9px; padding: 10px 14px; background: var(--archive-panel); color: var(--archive-text); font-size: 13px; }
.search-button { min-height: 44px; padding: 8px 18px; border: 0; border-radius: 9px; background: var(--archive-accent); color: var(--archive-background); cursor: pointer; }
.archive-workspace { display: flex; align-items: flex-start; gap: 16px; }
.archive-content { flex: 1; min-width: 0; display: grid; grid-template-columns: minmax(260px, .8fr) minmax(0, 1.4fr); gap: 16px; }
.archive-detail-pane { min-width: 0; }.focused .archive-content { grid-template-columns: minmax(0, 1fr); }
.empty-reader { min-height: 400px; border: 1px dashed var(--archive-border); border-radius: 14px; padding: 56px 28px; text-align: center; color: var(--archive-muted); }
.empty-reader > i { font-size: 42px; color: var(--archive-accent); }.empty-reader h2 { font-size: 18px; color: var(--archive-text); margin: 16px 0; }.empty-reader p { font-size: 13px; line-height: 1.9; }.empty-reader span { display: block; margin-top: 24px; font-size: 11px; }
.empty-reader button { margin: 8px; }
.archive-error, .archive-warning { padding: 16px; margin-bottom: 16px; border: 1px solid var(--archive-border); border-radius: 10px; background: var(--archive-accent-bg); overflow-wrap: anywhere; }
.archive-error { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }.archive-error button, .archive-error a { color: var(--archive-accent); min-height: 44px; display: inline-flex; align-items: center; cursor: pointer; }
.archive-warning { font-size: 12px; }.close-filters { display: none; }
@media (max-width: 1250px) { .archive-content { grid-template-columns: minmax(0, 1fr); } .archive-detail-pane { display: none; } .has-document .archive-detail-pane { display: block; } .has-document .archive-list-pane { display: none !important; } .focus-toggle { display: none; } }
@media (max-width: 767px) {
  .archive-heading { align-items: flex-start; gap: 8px; } h1 { font-size: 23px; }.archive-heading > button { padding: 8px 10px; }
  .archive-stats { gap: 6px; }.archive-stats > div { padding: 12px 10px; }.archive-stats strong { font-size: 22px; }.archive-stats .latest-update { font-size: 14px; line-height: 33px; }.archive-stats span { font-size: 11px; }
  .filters-container { position: fixed; z-index: 2100; inset: 0 15% 0 0; background: var(--archive-panel); overflow-y: auto; padding: 16px 8px; box-shadow: 0 0 0 100vmax #0008; }.close-filters { display: flex; margin: 0 16px 8px auto; }
  .search-bar { gap: 6px; }.search-bar > .outline-button { padding: 8px 10px; }.search-button { padding: 8px 12px; }.search-bar input { padding: 8px; }
}
</style>
