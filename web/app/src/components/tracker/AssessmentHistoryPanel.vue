<script setup lang="ts">
/**
 * AssessmentHistoryPanel — 评估历史侧边栏
 *
 * 桌面端：固定在左侧（w-52）
 * 移动端：底部抽屉/面板（通过父组件控制显示）
 */
import { PART_LABELS } from '@/constants/bodySites'

const props = defineProps<{
  items: Array<{
    id: number
    date: string
    bodySite: string
    vasiScore: number
    areaPercentage: number
    stage: string
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

function isSwiped(id: number) { return props.swipedId === id }
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
          class="text-sm text-red-500 hover:text-red-600 min-h-[40px] px-2 py-1"
          :disabled="selectedIds.size < 2"
          @click="emit('compareSelected')"
        >
          对比({{ selectedIds.size }})
        </button>
        <button
          v-if="selectMode"
          class="text-sm text-red-500 hover:text-red-600 min-h-[40px] px-2 py-1"
          :disabled="selectedIds.size === 0"
          @click="emit('deleteSelected')"
        >
          删除
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
              <!-- Score badge -->
              <div
                class="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-xs font-bold"
                :class="item.stage === '稳定期' || item.stage === '好转'
                  ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                  : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'"
              >
                {{ item.vasiScore }}
              </div>

              <!-- Meta -->
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-gray-800 dark:text-gray-200 truncate">
                  {{ PART_LABELS[item.bodySite] || item.bodySite }}
                </p>
                <div class="flex items-center gap-2 text-[10px] text-gray-400 dark:text-gray-500">
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
