<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goodExamples = [
  '光线均匀、白斑清晰可见',
  '手机正对皮肤，距离约30cm',
  '照片中包含参考物（硬币/尺子）以便精确测量',
  '对焦清晰，避免手抖',
]

const badExamples = [
  '光线过暗或过亮（过曝）',
  '角度倾斜或距离太远',
  '闪光灯直射皮肤',
  '照片模糊或白斑被遮挡',
]
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-6">
    <div class="flex items-center gap-3 mb-6">
      <button
        class="w-9 h-9 rounded-full flex items-center justify-center bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
        @click="router.back()"
      >
        <i class="ri-arrow-left-line"></i>
      </button>
      <h1 class="text-xl font-bold text-gray-900">拍照技巧指南</h1>
    </div>

    <div class="grid md:grid-cols-2 gap-6">
      <div class="card p-6 border-l-4 border-green-500">
        <h2 class="text-lg font-semibold text-green-700 dark:text-green-400 mb-4 flex items-center gap-2">
          <i class="ri-check-line text-xl"></i> 好的拍照示例
        </h2>
        <ul class="space-y-3">
          <li v-for="(item, i) in goodExamples" :key="i" class="flex items-start gap-2 text-sm text-gray-700">
            <i class="ri-checkbox-circle-fill text-green-500 mt-0.5 flex-shrink-0"></i>
            <span>{{ item }}</span>
          </li>
        </ul>
      </div>

      <div class="card p-6 border-l-4 border-red-500">
        <h2 class="text-lg font-semibold text-red-700 dark:text-red-400 mb-4 flex items-center gap-2">
          <i class="ri-close-line text-xl"></i> 常见错误
        </h2>
        <ul class="space-y-3">
          <li v-for="(item, i) in badExamples" :key="i" class="flex items-start gap-2 text-sm text-gray-700">
            <i class="ri-close-circle-fill text-red-500 mt-0.5 flex-shrink-0"></i>
            <span>{{ item }}</span>
          </li>
        </ul>
      </div>
    </div>

    <div class="mt-8 text-center">
      <button
        class="btn-primary px-8 py-3 text-base"
        @click="router.push({ name: 'assessment' })"
      >
        <i class="ri-camera-line mr-1"></i> 开始拍照
      </button>
    </div>

    <p class="text-xs text-gray-400  text-center mt-6">
      <i class="ri-error-warning-line"></i> 照片质量直接影响评估准确度，请尽量按照以上建议拍摄
    </p>
  </div>
</template>
