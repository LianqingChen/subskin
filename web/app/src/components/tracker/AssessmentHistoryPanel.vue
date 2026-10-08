<script setup lang="ts">
/**
 * AssessmentHistoryPanel — 评估历史侧边栏
 *
 * 桌面端：固定在左侧（w-52）
 * 移动端：底部抽屉/面板（通过父组件控制显示）
 *
 * 多选模式提供两级对比入口：
 * - 生成对比报告（2-4 条，异步 AI 深度分析）
 * - 快速对比（恰好 2 条，即时滑块对比）
 */
import { computed } from 'vue'
import { PART_LABELS } from '@/constants/bodySites'
import { toProtectedFileUrl } from '@/utils/file-url'

const props = defineProps<{
  items: Array<{
    id: number
    date: string
    bodySite: string
    vasiScore: number
    areaPercentage: number
    stage: string
    imageUrl?: string
  }>
  loading: boolean
  total: number
  page: number
  pageSize: number
  totalPages: number
  selectMode: boolean
  selectedIds: Set<number>
  swipedId: number | null
  deletingIds: Set<number>
  /** 生成对比报告可纳入的最大条数 */
  maxCompare?: number
}>()

const emit = defineEmits<{
  viewDetail: [id: number]
  compareSelected: []
  newAssessment: []
  toggleSelectMode: []
  toggleSelect: [id: number]
  deleteSingle: [id: number]
  deleteSelected: []
  goToPage: [page: number]
  setPageSize: [size: number]
  touchStart: [e: TouchEvent]
  touchEnd: [e: TouchEvent, id: number]
}>()

const maxCompare = computed(() => props.maxCompare ?? 4)

const selectedItems = computed(() => props.items.filter((i) => props.selectedIds.has(i.id)))

/** 跨部位多选：无法直接生成对比报告（需同一部位） */
const mixedSelected = computed(
  () =>
    selectedItems.value.length >= 2 &&
    new Set(selectedItems.value.map((i) => i.bodySite).filter(Boolean)).size > 1,
)

const canCompare = computed(
  () =>
    selectedItems.value.length >= 2 &&
    selectedItems.value.length <= maxCompare.value,
)

function isSwiped(id: number) { return props.swipedId === id }

function thumbUrl(url?: string) {
  return url ? (toProtectedFileUrl(url) || url) : ''
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
      <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">
        <i class="ri-history-line mr-1.5"></i>评估历史
      </h3>
      <div class="flex items-center gap-1.5">
        <button
          v-if="items.length && !selectMode"
          class="text-sm text-primary-500 hover:text-primary-700 dark:hover:text-primary-300 min-h-[40px] px-2 py-1"
          @click="emit('toggleSelectMode')"
        >
          多选
        </button>
        <button
          v-if="selectMode"
          class="text-sm text-gray-400 hover:text-gray-600 min-h-[40px] px-2 py-1"
          @click="emit('toggleSelectMode')"
        >
          取消
        </button>
        <button
          class="text-sm text-primary-500 hover:text-primary-700 dark:hover:text-primary-300 min-h-[40px] px-2 py-1"
          @click="emit('newAssessment')"
        >
          <i class="ri-add-line"></i>
        </button>
      </div>
    </div>

    <!-- 多选操作区：两级对比入口 + 批量删除 -->
    <div
      v-if="selectMode"
      class="shrink-0 px-3 py-2.5 border-b border-gray-100 dark:border-gray-700 bg-primary-50 dark:bg-primary-900 space-y-2"
    >
      <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>已选 {{ selectedIds.size }} / {{ maxCompare }} 条</span>
        <span v-if="selectedIds.size > maxCompare" class="text-amber-600 dark:text-amber-400">
          最多选 {{ maxCompare }} 条
        </span>
      </div>
      <p
        v-if="mixedSelected"
        class="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 truncate"
      >
        <i class="ri-error-warning-line shrink-0"></i>
        AI 对比报告需同一部位
      </p>
      <div class="grid gap-1.5">
        <button
          class="w-full min-h-[40px] px-2 py-1.5 rounded-lg bg-primary-500 text-white text-sm font-medium
            disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-600 transition-colors flex items-center justify-center gap-1"
          :disabled="!canCompare"
          data-track-id="assessment_history_compare"
          @click="emit('compareSelected')"
        >
          <i class="ri-arrow-left-right-line mr-1"></i>开始对比
        </button>
        <button
          class="w-full min-h-[40px] px-2 py-1.5 rounded-lg text-red-500 text-sm
            disabled:opacity-40 disabled:cursor-not-allowed hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          :disabled="selectedIds.size === 0"
          @click="emit('deleteSelected')"
        >
          删除所选
        </button>
      </div>
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
      <div v-else-if="!items.length" class="flex flex-col items-center justify-center py-8 text-gray-400 dark:text-gray-500">
        <i class="ri-inbox-line text-3xl mb-2"></i>
        <p class="text-xs">暂无评估记录</p>
      </div>

      <!-- Items -->
      <div v-else class="space-y-0.5 px-2 py-2">
        <div
          v-for="item in items"
          :key="item.id"
          class="relative"
        >
          <div
            class="flex items-center"
            :class="!selectMode && isSwiped(item.id) ? '-translate-x-16' : 'translate-x-0'"
            @touchstart="emit('touchStart', $event)"
            @touchend="emit('touchEnd', $event, item.id)"
          >
            <!-- Checkbox -->
            <div v-if="selectMode" class="pr-2 shrink-0">
              <input
                type="checkbox"
                :checked="selectedIds.has(item.id)"
                @change="emit('toggleSelect', item.id)"
                class="w-4 h-4 rounded border-gray-300 text-primary-500 focus:ring-primary-400"
              />
            </div>

            <!-- Item content -->
            <button
              class="flex-1 min-w-0 flex items-center gap-2.5 py-2 px-2.5 rounded-lg bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left"
              @click="!selectMode && emit('viewDetail', item.id)"
            >
              <!-- Photo thumbnail -->
              <div class="w-10 h-10 rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-700 shrink-0 relative">
                <i class="absolute inset-0 flex items-center justify-center text-gray-400 dark:text-gray-500 ri-image-line"></i>
                <img
                  v-if="thumbUrl(item.imageUrl)"
                  :src="thumbUrl(item.imageUrl)"
                  class="relative w-full h-full object-cover"
                  alt="评估照片"
                  loading="lazy"
                  @error="($event.target as HTMLImageElement).style.display = 'none'"
                />
              </div>

              <!-- Meta -->
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-gray-800 dark:text-gray-200 truncate">
                  {{ PART_LABELS[item.bodySite] || item.bodySite }}
                </p>
                <div class="flex items-center gap-2 text-[10px] text-gray-400 dark:text-gray-500">
                  <span class="font-bold text-gray-700 dark:text-gray-200">{{ item.vasiScore }}</span>
                  <span>{{ item.date }}</span>
                  <span>{{ item.areaPercentage }}%</span>
                  <span
                    class="font-medium"
                    :class="item.stage === '好转' ? 'text-green-500' : item.stage === '扩散' || item.stage === '进展期' ? 'text-red-500' : 'text-amber-500'"
                  >{{ item.stage }}</span>
                </div>
              </div>
            </button>
          </div>

          <!-- Swipe delete button -->
          <button
            v-if="!selectMode && isSwiped(item.id)"
            class="absolute right-0 top-0 bottom-0 w-16 flex items-center justify-center bg-red-500 text-white rounded-r-lg"
            @click="emit('deleteSingle', item.id)"
            :disabled="deletingIds.has(item.id)"
          >
            <i class="ri-delete-bin-line"></i>
          </button>
        </div>
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
