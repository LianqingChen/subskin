<template>
  <main class="labeling-page" :style="themeStyle">
    <header class="heading">
      <div><h1>图片打标</h1><p class="desc">「日记」照片与后台上传图片的五类标注、复核与金标准</p></div>
      <div class="buttons">
        <n-button type="primary" size="large" :disabled="!list?.ids.length" @click="start"><template #icon><i class="ri-play-circle-line" /></template>开始标注</n-button>
        <n-button size="large" :loading="busy" @click="sync"><template #icon><i class="ri-refresh-line" /></template>同步日记照片</n-button>
        <n-button size="large" @click="showUpload = true"><template #icon><i class="ri-upload-2-line" /></template>上传图片</n-button>
        <n-button v-if="stats && stats.legacy > 0" size="large" :disabled="busy" @click="confirmLegacy">转入旧版记录（{{ stats.legacy }}）</n-button>
      </div>
    </header>
    <section class="stats" aria-label="任务概览">
      <button v-for="item in STAT_ITEMS" :key="item.label" class="stat" :class="{ active: filters.status === item.status }" @click="setFilters({ status: item.status })">
        <span>{{ item.label }}</span><strong class="num">{{ stats ? stats.counts[item.key] : '—' }}</strong>
      </button>
    </section>
    <p v-if="stats && stats.hidden_unconsented > 0" class="note">另有 {{ stats.hidden_unconsented }} 张日记照片因用户未授权“帮助改进白斑识别”而不可见</p>
    <div v-if="error" class="error" role="alert"><span>{{ error }}</span><button @click="load">重试</button><router-link to="/login">重新登录</router-link></div>
    <TaskFilters :filters="filters" @change="setFilters" />
    <TaskTable :items="list?.items ?? []" :loading="loading" @open="(id) => open(id)" />
    <div v-if="list && list.total > PAGE_SIZE" class="pager">
      <n-pagination :page="page" :page-size="PAGE_SIZE" :item-count="list.total" :page-slot="5" @update:page="(p: number) => setFilters({ page: p })" />
    </div>
    <UploadDialog v-model:show="showUpload" :busy="busy" :submit-fn="upload" />
  </main>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDialog, useThemeVars } from 'naive-ui'
import { PAGE_SIZE, useLabelingTasks } from '@/composables/useLabelingTasks'
import TaskFilters from '@/components/labeling/TaskFilters.vue'
import TaskTable from '@/components/labeling/TaskTable.vue'
import UploadDialog from '@/components/labeling/UploadDialog.vue'
import type { TaskFilters as Filters, TaskStatus } from '@/types/labeling'

const { list, stats, loading, busy, error, filters, page, setFilters, load, open, start, sync, convertLegacy, upload } = useLabelingTasks()
const dialog = useDialog()
const showUpload = ref(false)
const theme = useThemeVars()
const themeStyle = computed(() => ({
  '--lb-panel': theme.value.cardColor, '--lb-text': theme.value.textColor1, '--lb-muted': theme.value.textColor3,
  '--lb-border': theme.value.borderColor, '--lb-accent': theme.value.primaryColorHover, '--lb-accent-bg': theme.value.primaryColor + '18',
}))
const STAT_ITEMS: { label: string; key: TaskStatus; status: Filters['status'] }[] = [
  { label: '待标注', key: 'pending', status: 'pending' }, { label: '已退回', key: 'returned', status: 'returned' },
  { label: '待复核', key: 'in_review', status: 'review' }, { label: '金标准', key: 'gold', status: 'gold' },
  { label: '不可用', key: 'rejected', status: 'rejected' }, { label: '已跳过', key: 'skipped', status: 'skipped' },
]
function confirmLegacy() {
  dialog.warning({
    title: '转入旧版记录',
    content: '将旧流水线（分型/分期/二值掩膜）的打标记录转换为五类标注任务，转换后需要重新标注与复核。其中当年由后台上传的图片没有来源授权记录：点「转入」即表示你确认这些图片有权用于模型训练，系统会记录确认人。用户日记照片仍按用户授权显示。',
    positiveText: '确认并转入', negativeText: '取消',
    onPositiveClick: () => convertLegacy(),
  })
}
</script>
<style scoped>
.labeling-page { max-width: 1440px; margin: 0 auto; color: var(--lb-text); padding-bottom: 24px; }
.heading { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 14px; margin-bottom: 18px; }
h1 { font-size: 26px; font-weight: 650; margin: 0; }
.desc { color: var(--lb-muted); font-size: 13px; margin: 6px 0 0; }
.buttons { display: flex; flex-wrap: wrap; gap: 8px; }
.stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 10px; }
.stat { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; min-height: 44px; padding: 12px 16px; border: 1px solid var(--lb-border); border-radius: 12px; background: var(--lb-panel); color: var(--lb-text); cursor: pointer; text-align: left; }
.stat span { color: var(--lb-muted); font-size: 12px; }
.stat strong { font-size: 22px; font-weight: 600; }
.stat.active { border-color: var(--lb-accent); background: var(--lb-accent-bg); }
.num { font-variant-numeric: tabular-nums; }
.note { color: var(--lb-muted); font-size: 12px; margin: 0 0 12px; }
.error { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; padding: 14px; margin-bottom: 14px; border: 1px solid var(--lb-border); border-radius: 10px; background: var(--lb-accent-bg); }
.error button, .error a { min-height: 44px; display: inline-flex; align-items: center; color: var(--lb-accent); background: none; border: 0; cursor: pointer; }
.pager { display: flex; justify-content: center; margin-top: 16px; }
@media (max-width: 1100px) { .stats { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 767px) { h1 { font-size: 22px; } .stat { padding: 10px 12px; } .buttons > * { flex: 1 1 auto; } }
</style>
