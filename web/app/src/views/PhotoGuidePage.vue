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
  <div class="page-narrow py-5 pb-8 md:py-8 md:pb-12">
    <div class="mb-6 flex items-start gap-3">
      <button
        type="button"
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-gray-600 ring-1 ring-gray-200 transition-colors hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700 dark:hover:bg-gray-700"
        aria-label="返回"
        @click="router.back()"
      >
        <i class="ri-arrow-left-line" aria-hidden="true"></i>
      </button>
      <div class="min-w-0">
        <h1 class="page-title">拍照技巧指南</h1>
        <p class="page-subtitle">照片质量直接影响记录的准确度，按下面的建议拍，前后对比才可靠。</p>
      </div>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <section class="card p-5 md:p-6" aria-labelledby="guide-good">
        <h2 id="guide-good" class="mb-4 flex items-center gap-2 text-base font-semibold text-gray-900 dark:text-gray-100">
          <span class="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300"><i class="ri-check-line text-lg" aria-hidden="true"></i></span>
          这样拍更准
        </h2>
        <ul class="space-y-3">
          <li v-for="(item, i) in goodExamples" :key="i" class="flex items-start gap-2 text-sm leading-6 text-gray-700 dark:text-gray-300">
            <i class="ri-checkbox-circle-fill mt-1 shrink-0 text-emerald-500" aria-hidden="true"></i>
            <span>{{ item }}</span>
          </li>
        </ul>
      </section>

      <section class="card p-5 md:p-6" aria-labelledby="guide-bad">
        <h2 id="guide-bad" class="mb-4 flex items-center gap-2 text-base font-semibold text-gray-900 dark:text-gray-100">
          <span class="flex h-8 w-8 items-center justify-center rounded-full bg-rose-50 text-rose-600 dark:bg-rose-900 dark:text-rose-300"><i class="ri-close-line text-lg" aria-hidden="true"></i></span>
          常见错误
        </h2>
        <ul class="space-y-3">
          <li v-for="(item, i) in badExamples" :key="i" class="flex items-start gap-2 text-sm leading-6 text-gray-700 dark:text-gray-300">
            <i class="ri-close-circle-fill mt-1 shrink-0 text-rose-500" aria-hidden="true"></i>
            <span>{{ item }}</span>
          </li>
        </ul>
      </section>
    </div>

    <div class="mt-8 flex justify-center">
      <button
        type="button"
        class="btn-primary min-h-[48px] w-full rounded-xl px-8 text-base sm:w-auto"
        @click="router.push({ name: 'assessment' })"
      >
        <i class="ri-camera-line mr-1" aria-hidden="true"></i> 开始拍照
      </button>
    </div>
  </div>
</template>
