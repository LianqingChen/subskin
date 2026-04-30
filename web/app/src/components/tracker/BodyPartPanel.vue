<script setup lang="ts">
import { ref, computed } from 'vue'
import type { AssessmentSnapshot } from './DigitalHuman.vue'

const props = defineProps<{
  part: string | null
  assessment: AssessmentSnapshot | null
  history: Array<{
    id: number
    date: string
    vasiScore: number
    areaPercentage: number
    stage: string
    classification?: string
  }>
  loading?: boolean
}>()

const emit = defineEmits<{
  'take-photo': []
  'upload-photo': []
  'close': []
  'view-detail': [id: number]
}>()

const showChooser = ref(false)

const PART_LABELS: Record<string, string> = {
  face: '面部', neck: '颈部', hands: '手部',
  trunk: '躯干', arms: '上肢', legs: '下肢', feet: '足部',
}

const partLabel = computed(() => props.part ? (PART_LABELS[props.part] || props.part) : '')

const scoreLevel = computed(() => {
  const s = props.assessment?.vasiScore ?? 0
  if (s < 10) return { label: '轻度', color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-900/20' }
  if (s < 25) return { label: '中度', color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-900/20' }
  if (s < 50) return { label: '中重度', color: 'text-orange-600', bg: 'bg-orange-50 dark:bg-orange-900/20' }
  return { label: '重度', color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-900/20' }
})

const stageBadge = computed(() => {
  const s = props.assessment?.stage || ''
  if (s.includes('好转')) return { label: s, color: 'text-green-700 bg-green-100 dark:bg-green-900/30' }
  if (s.includes('扩散') || s.includes('进展')) return { label: s, color: 'text-red-700 bg-red-100 dark:bg-red-900/30' }
  return { label: s, color: 'text-amber-700 bg-amber-100 dark:bg-amber-900/30' }
})

const areaPercent = computed(() => props.assessment?.areaPercentage ?? 0)

function chooseCamera() {
  showChooser.value = false
  emit('take-photo')
}

function chooseGallery() {
  showChooser.value = false
  emit('upload-photo')
}
</script>

<template>
  <div v-if="part" class="card p-5 flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <i class="ri-focus-3-line text-primary-500"></i>
        {{ partLabel }}
      </h3>
      <button
        class="w-8 h-8 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        @click="emit('close')"
      >
        <i class="ri-close-line"></i>
      </button>
    </div>

    <!-- Current Assessment -->
    <template v-if="assessment">
      <div class="grid grid-cols-3 gap-3">
        <div class="text-center p-3 rounded-xl" :class="scoreLevel.bg">
          <div class="text-xl font-bold" :class="scoreLevel.color">{{ assessment.vasiScore }}</div>
          <div class="text-[10px] text-gray-500 mt-0.5">VASI评分</div>
        </div>
        <div class="text-center p-3 rounded-xl bg-gray-50 dark:bg-gray-800">
          <div class="text-xl font-bold text-gray-700 dark:text-gray-300">{{ areaPercent }}%</div>
          <div class="text-[10px] text-gray-500 mt-0.5">白斑面积</div>
        </div>
        <div class="text-center p-3 rounded-xl flex items-center justify-center">
          <span class="text-xs font-medium px-2.5 py-1 rounded-full" :class="stageBadge.color">
            {{ stageBadge.label }}
          </span>
        </div>
      </div>

      <div class="space-y-1">
        <div class="flex justify-between text-[10px] text-gray-400">
          <span>轻度 0</span>
          <span>重度 100</span>
        </div>
        <div class="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="{
              'bg-green-500': assessment.vasiScore < 10,
              'bg-amber-500': assessment.vasiScore >= 10 && assessment.vasiScore < 25,
              'bg-orange-500': assessment.vasiScore >= 25 && assessment.vasiScore < 50,
              'bg-red-500': assessment.vasiScore >= 50,
            }"
            :style="{ width: Math.min(100, assessment.vasiScore) + '%' }"
          />
        </div>
      </div>
    </template>

    <div v-else class="text-center py-6 text-gray-400 dark:text-gray-500">
      <i class="ri-camera-line text-3xl block mb-2"></i>
      <p class="text-sm">该部位暂无评估记录</p>
      <p class="text-xs mt-1">拍照或上传照片开始评估</p>
    </div>

    <!-- Combined Action Button -->
    <div class="relative">
      <button
        class="btn-primary w-full py-3 text-base flex items-center justify-center gap-2 min-h-[48px]"
        @click="showChooser = !showChooser"
      >
        <i class="ri-camera-line text-lg"></i> 拍照评估
      </button>

      <!-- Chooser dropdown -->
      <div
        v-if="showChooser"
        class="absolute left-0 right-0 top-full mt-2 p-3 rounded-xl bg-white dark:bg-gray-800 shadow-xl border border-gray-200 dark:border-gray-700 z-20 flex gap-2"
      >
        <button
          class="flex-1 flex flex-col items-center gap-2 p-4 rounded-xl hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors border border-transparent hover:border-primary-200 dark:hover:border-primary-800"
          @click="chooseCamera"
        >
          <div class="w-12 h-12 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
            <i class="ri-camera-line text-2xl text-primary-600 dark:text-primary-400"></i>
          </div>
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">拍照</span>
          <span class="text-[10px] text-gray-400">使用相机拍摄</span>
        </button>
        <button
          class="flex-1 flex flex-col items-center gap-2 p-4 rounded-xl hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors border border-transparent hover:border-primary-200 dark:hover:border-primary-800"
          @click="chooseGallery"
        >
          <div class="w-12 h-12 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
            <i class="ri-image-line text-2xl text-primary-600 dark:text-primary-400"></i>
          </div>
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">相册选择</span>
          <span class="text-[10px] text-gray-400">从图库上传</span>
        </button>
      </div>
    </div>

    <!-- Per-part History -->
    <div v-if="history.length > 0">
      <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-1.5">
        <i class="ri-history-line"></i> {{ partLabel }}评估历史
      </h4>
      <div class="space-y-2">
        <div
          v-for="record in history.slice(0, 5)"
          :key="record.id"
          class="flex items-center gap-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-800 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          @click="emit('view-detail', record.id)"
        >
          <div class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
            :class="{
              'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': record.stage.includes('好转'),
              'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': record.stage.includes('扩散') || record.stage.includes('进展'),
              'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400': true,
            }"
          >{{ record.vasiScore }}</div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 text-sm">
              <span class="text-gray-400 dark:text-gray-500 text-xs">{{ record.date }}</span>
              <span class="text-[11px] px-1.5 py-0.5 rounded-full"
                :class="{
                  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': record.stage.includes('好转'),
                  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': record.stage.includes('扩散') || record.stage.includes('进展'),
                  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400': true,
                }"
              >{{ record.stage }}</span>
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              面积 {{ record.areaPercentage }}%
              <span v-if="record.classification" class="ml-2">· {{ record.classification }}型</span>
            </div>
          </div>
          <i class="ri-arrow-right-s-line text-gray-400"></i>
        </div>
      </div>
    </div>
  </div>
</template>
