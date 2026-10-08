<script setup lang="ts">
import { ref } from 'vue'
import type { ActionCard } from '@/types'

defineProps<{ card: ActionCard; saved?: boolean }>()
const emit = defineEmits<{ (e: 'confirm', action: 'save' | 'share' | 'discard'): void }>()

// 公开分享需二次确认（明确告知将公开展示）
const confirmingShare = ref(false)

function onShareClick() {
  if (confirmingShare.value) {
    emit('confirm', 'share')
    confirmingShare.value = false
  } else {
    confirmingShare.value = true
  }
}
</script>

<template>
  <div class="mt-2 rounded-xl border border-primary-100 dark:border-primary-900/50 bg-primary-50/60 dark:bg-primary-900/20 p-3 text-left">
    <!-- VASI 评估卡片 -->
    <template v-if="card.type === 'vasi'">
      <div class="flex items-center gap-2 mb-2">
        <i class="ri-focus-3-line text-primary-600 dark:text-primary-400"></i>
        <span class="text-xs font-medium text-gray-800 dark:text-gray-200">VASI 评估结果</span>
      </div>
      <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
        评分：<span class="font-semibold">{{ card.vasiScore }} 分</span>（{{ card.classification }}）·
        部位：{{ card.bodySite }} · 分期：{{ card.stage }} · 面积约 {{ card.areaPercentage }}%
      </p>
    </template>

    <!-- 体检报告解读卡片 -->
    <template v-else-if="card.type === 'report'">
      <div class="flex items-center gap-2 mb-2">
        <i class="ri-microscope-line text-primary-600 dark:text-primary-400"></i>
        <span class="text-xs font-medium text-gray-800 dark:text-gray-200">{{ card.title || '体检报告解读' }}</span>
      </div>
      <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed line-clamp-3">{{ card.summary }}</p>
    </template>

    <!-- 日记草稿卡片 -->
    <template v-else>
      <div class="flex items-center gap-2 mb-2">
        <i class="ri-file-edit-line text-primary-600 dark:text-primary-400"></i>
        <span class="text-xs font-medium text-gray-800 dark:text-gray-200">{{ card.title || '病情日记草稿' }}</span>
      </div>
      <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed line-clamp-3">{{ card.content }}</p>
    </template>

    <!-- 操作按钮：用户逐次确认后才落库 -->
    <div v-if="saved" class="mt-2.5 flex items-center gap-1.5 text-xs text-primary-600 dark:text-primary-400">
      <i class="ri-check-line"></i> 已保存
    </div>
    <div v-else class="mt-2.5 flex flex-wrap gap-1.5">
      <template v-if="card.type === 'diary'">
        <button type="button" class="px-3 py-1.5 min-h-[36px] rounded-lg text-xs bg-primary-500 text-white hover:bg-primary-600 transition-colors" @click="emit('confirm', 'save')">
          <i class="ri-lock-line mr-0.5"></i>仅自己存档
        </button>
        <button type="button" class="px-3 py-1.5 min-h-[36px] rounded-lg text-xs border border-primary-300 dark:border-primary-700 text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/40 transition-colors" @click="onShareClick">
          <i class="ri-global-line mr-0.5"></i>{{ confirmingShare ? '确认公开分享？' : '发布到发现' }}
        </button>
        <button type="button" class="px-3 py-1.5 min-h-[36px] rounded-lg text-xs text-gray-400 hover:text-gray-600 transition-colors" @click="emit('confirm', 'discard')">
          不保存
        </button>
      </template>
      <template v-else>
        <button type="button" class="px-3 py-1.5 min-h-[36px] rounded-lg text-xs bg-primary-500 text-white hover:bg-primary-600 transition-colors" @click="emit('confirm', 'save')">
          保存
        </button>
        <button type="button" class="px-3 py-1.5 min-h-[36px] rounded-lg text-xs text-gray-400 hover:text-gray-600 transition-colors" @click="emit('confirm', 'discard')">
          跳过
        </button>
      </template>
    </div>
  </div>
</template>
