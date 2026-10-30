<template>
  <main class="gallery-page" :style="themeStyle">
    <header class="heading">
      <div>
        <h1>公开图库</h1>
        <p class="desc">PMC 开放获取论文与维基共享资源中授权可商用的白癜风照片（CC BY / CC0 等），用于标注与预训练。点开看大图与出处。</p>
      </div>
      <n-button :loading="loading" @click="load"><template #icon><i class="ri-refresh-line" /></template>刷新</n-button>
    </header>
    <section class="filters" aria-label="图库筛选">
      <div class="tabs" role="tablist">
        <button v-for="s in SOURCES" :key="s.value" type="button" role="tab" class="tab" :class="{ active: source === s.value }"
          :aria-selected="source === s.value" @click="source = s.value">{{ s.label }}</button>
      </div>
      <n-select v-model:value="status" class="status" :options="STATUSES" aria-label="状态" />
      <span class="count num">{{ list ? `${list.total} 张` : '' }}</span>
    </section>
    <div v-if="error" class="error" role="alert">{{ error }} <button type="button" @click="load">重试</button></div>
    <div v-else-if="list && !list.items.length" class="empty"><i class="ri-gallery-line" /><p>没有符合条件的照片</p></div>
    <ul class="grid">
      <li v-for="item in list?.items ?? []" :key="item.id">
        <button type="button" class="tile" :class="{ rejected: item.status === 'rejected' }" @click="selected = item">
          <AuthThumb :id="item.id" :size="180" :alt="`公开图库 #${item.id}`" />
          <span class="meta">
            <span class="num">#{{ item.id }}</span>
            <span class="lic">{{ item.external?.license }}</span>
            <i v-if="item.status === 'gold'" class="ri-medal-line gold" aria-label="金标准" />
            <i v-else-if="item.latest" class="ri-brush-line done" aria-label="已有标注" />
            <i v-if="item.status === 'rejected'" class="ri-close-circle-line bad" aria-label="不可用" />
          </span>
        </button>
      </li>
    </ul>
    <div v-if="list && list.total > GALLERY_PAGE" class="pager">
      <n-pagination v-model:page="page" :page-size="GALLERY_PAGE" :item-count="list.total" :page-slot="5" />
    </div>
    <GalleryLightbox :item="selected" :has-prev="index > 0" :has-next="!!list && index >= 0 && index < list.items.length - 1"
      @close="selected = null" @step="step" @label="label" @reject="(item) => { rejecting = item }" />
    <RejectDialog :show="!!rejecting" :reasons="choices?.reject_reasons ?? []" @update:show="(v) => { if (!v) rejecting = null }" @confirm="confirmReject" />
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMessage, useThemeVars } from 'naive-ui'
import AuthThumb from '@/components/labeling/AuthThumb.vue'
import GalleryLightbox from '@/components/labeling/GalleryLightbox.vue'
import RejectDialog from '@/components/labeling/RejectDialog.vue'
import { GALLERY_PAGE, useExternalGallery } from '@/composables/useExternalGallery'
import { useLabelingChoices } from '@/composables/useLabelingChoices'
import type { TaskSummary } from '@/types/labeling'

const { source, status, page, list, loading, error, selected, index, load, step, reject, label } = useExternalGallery()
const { choices } = useLabelingChoices()
const message = useMessage()
const rejecting = ref<TaskSummary | null>(null)
const SOURCES = [
  { value: 'any' as const, label: '全部' },
  { value: 'pmc_oa' as const, label: 'PMC 开放获取' },
  { value: 'wikimedia_commons' as const, label: '维基共享资源' },
]
const STATUSES = [
  { value: 'all', label: '全部状态' }, { value: 'open', label: '待标注' }, { value: 'review', label: '待复核' },
  { value: 'gold', label: '金标准' }, { value: 'rejected', label: '不可用' },
]
const theme = useThemeVars()
const themeStyle = computed(() => ({
  '--g-panel': theme.value.cardColor, '--g-text': theme.value.textColor1, '--g-muted': theme.value.textColor3,
  '--g-border': theme.value.borderColor, '--g-accent': theme.value.primaryColorHover, '--g-accent-bg': theme.value.primaryColor + '18',
}))
async function confirmReject(reasons: string[]) {
  const item = rejecting.value
  rejecting.value = null
  if (!item) return
  const failure = await reject(item, reasons)
  if (failure) message.error(failure); else message.info('已标记为不可用')
}
</script>

<style scoped>
.gallery-page { max-width: 1440px; margin: 0 auto; color: var(--g-text); padding-bottom: 24px; }
.heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
h1 { font-size: 26px; font-weight: 650; margin: 0; }
.desc { color: var(--g-muted); font-size: 13px; margin: 6px 0 0; line-height: 1.7; max-width: 760px; }
.filters { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 14px; }
.tabs { display: flex; gap: 4px; }
.tab { min-height: 44px; padding: 8px 14px; border: 0; border-radius: 9px; background: transparent; color: var(--g-muted); cursor: pointer; font-size: 13px; }
.tab.active { background: var(--g-accent-bg); color: var(--g-accent); font-weight: 600; }
.status { width: 140px; }
.count { color: var(--g-muted); font-size: 13px; }
.num { font-variant-numeric: tabular-nums; }
.grid { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
.tile { width: 100%; padding: 5px; border: 1px solid var(--g-border); border-radius: 12px; background: var(--g-panel); color: var(--g-text); cursor: pointer; display: grid; gap: 6px; justify-items: center; }
.tile:hover, .tile:focus-visible { border-color: var(--g-accent); outline: none; }
.tile.rejected { opacity: .45; }
.tile :deep(.thumb) { width: 100% !important; height: 180px !important; }
.meta { display: flex; align-items: center; gap: 6px; width: 100%; font-size: 12px; padding: 0 4px 2px; }
.lic { color: var(--g-muted); flex: 1; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gold { color: #fbbf24; } .done { color: #2dd4bf; } .bad { color: #f87171; }
.error { padding: 14px; border: 1px solid var(--g-border); border-radius: 10px; margin-bottom: 12px; }
.error button { background: none; border: 0; color: var(--g-accent); cursor: pointer; min-height: 44px; }
.empty { text-align: center; color: var(--g-muted); padding: 48px 0; }
.empty i { font-size: 36px; }
.pager { display: flex; justify-content: center; margin-top: 16px; }
@media (max-width: 767px) { h1 { font-size: 22px; } .grid { grid-template-columns: repeat(2, 1fr); gap: 8px; } .tile :deep(.thumb) { height: 140px !important; } }
</style>
