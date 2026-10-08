<script setup lang="ts">
/**
 * ComparisonHistoryPanel — 对比报告历史面板
 *
 * 桌面端：复用测评页左侧边栏（w-52）
 * 移动端：底部抽屉（通过父组件控制显示）
 * 列表为「对比报告」（report_type=comparison），时间倒序，每页默认 5 条。
 * 未选部位 = 全量历史；选中部位 = 该部位的报告（由父组件传入筛选）。
 */
import { computed } from 'vue'
import { reportTime } from '@/utils/report-time'
import { PART_LABELS } from '@/constants/bodySites'
import type { SkinReportListItem } from '@/api/skin_report'

const props = defineProps<{
  items: SkinReportListItem[]
  loading: boolean
  total: number
  page: number
  pageSize: number
  totalPages: number
  bodySiteFilter: string | null
}>()

const emit = defineEmits<{
  viewReport: [id: number]
  goToPage: [page: number]
  setPageSize: [size: number]
}>()

const siteLabel = computed(() =>
  props.bodySiteFilter ? (PART_LABELS[props.bodySiteFilter] || props.bodySiteFilter) : null,
)

function trendStyle(trend?: string) {
  if (trend === '好转')
    return { cls: 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300', icon: 'ri-arrow-down-line' }
  if (trend === '加重')
    return { cls: 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300', icon: 'ri-arrow-up-line' }
  if (trend === '稳定')
    return { cls: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300', icon: 'ri-subtract-line' }
  return { cls: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300', icon: 'ri-question-line' }
}

</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div v-if="siteLabel" class="flex items-center justify-end px-4 py-3 border-b border-gray-100 dark:border-gray-700">
      <span
        v-if="siteLabel"
        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-50 dark:bg-primary-900 text-primary-700 dark:text-primary-300 text-[10px] font-semibold"
      >
        <i class="ri-focus-3-line"></i>{{ siteLabel }}
      </span>
    </div>

    <!-- List -->
    <div class="flex-1 overflow-y-auto">
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-8 text-gray-400">
        <svg class="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        加载中...
      </div>

      <!-- Empty -->
      <div v-else-if="!items.length" class="flex flex-col items-center justify-center py-8 px-4 text-gray-400 dark:text-gray-500">
        <i class="ri-file-chart-2-line text-3xl mb-2"></i>
        <p class="text-xs">暂无对比报告</p>
        <p class="text-[10px] text-gray-400 dark:text-gray-500 mt-1 text-center">在「白斑对比」中选择两张照片或两次记录</p>
      </div>

      <!-- Items -->
      <div v-else class="grid gap-2 p-2 lg:grid-cols-2">
        <button
          v-for="item in items"
          :key="item.id"
          class="w-full min-h-[56px] flex items-start gap-3 py-3 px-3 rounded-xl bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left"
          @click="emit('viewReport', item.id)"
        >
          <i class="ri-file-chart-2-line text-lg text-primary-500 shrink-0 mt-0.5" aria-hidden="true"></i>

          <!-- Meta -->
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
              {{ item.headline || item.title }}
            </p>
            <div class="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400 mt-1 flex-wrap">
              <span
                v-if="item.trend"
                class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full font-medium"
                :class="trendStyle(item.trend).cls"
              >
                <i :class="trendStyle(item.trend).icon"></i>{{ item.trend }}
              </span>
              <span v-if="item.status === 'generating'" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full font-medium bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-300">
                <i class="ri-loader-4-line"></i>生成中
              </span>
              <span>{{ item.body_site_label }}</span>
              <time :datetime="item.generated_at || item.created_at">{{ reportTime(item) }}</time>
            </div>
          </div>
        </button>
      </div>
    </div>

    <!-- Pagination -->
    <div
      v-if="total > pageSize"
      class="flex items-center justify-between px-4 py-2 border-t border-gray-100 dark:border-gray-700 text-xs text-gray-500"
    >
      <select
        :value="pageSize"
        @change="emit('setPageSize', Number(($event.target as HTMLSelectElement).value))"
        class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-1.5 py-0.5 text-xs"
      >
        <option :value="5">5条</option>
        <option :value="10">10条</option>
        <option :value="20">20条</option>
        <option :value="50">50条</option>
      </select>
      <span>{{ total }}条</span>
      <div class="flex items-center gap-1">
        <button
          class="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-30 min-h-[36px]"
          :disabled="page <= 1"
          @click="emit('goToPage', page - 1)"
        >‹</button>
        <span>{{ page }}/{{ totalPages }}</span>
        <button
          class="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-30 min-h-[36px]"
          :disabled="page >= totalPages"
          @click="emit('goToPage', page + 1)"
        >›</button>
      </div>
    </div>
  </div>
</template>
