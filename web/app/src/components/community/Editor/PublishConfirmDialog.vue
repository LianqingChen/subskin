<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 px-4"
      role="dialog"
      aria-modal="true"
      aria-label="公开发布确认"
      @click.self="emit('cancel')"
    >
      <div class="card dark:bg-gray-800 w-full max-w-md max-h-[85dvh] overflow-y-auto p-5 shadow-xl">
        <div class="mb-3 flex items-center gap-2">
          <i class="ri-shield-keyhole-line text-lg text-primary-600 dark:text-primary-400" aria-hidden="true"></i>
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">确认公开发布</h3>
        </div>

        <section v-if="preview" aria-label="分享内容预览" class="mb-4 space-y-2">
          <h4 class="text-sm font-medium">{{ preview.title }}</h4>
          <div class="grid grid-cols-3 gap-2"><img v-for="(image, index) in preview.images" :key="image" :src="image" :alt="preview.images.length === 3 ? ['创意卡', '确认标注图', '原始照片'][index] : ['确认标注图', '原始照片'][index]" class="h-28 w-full rounded-lg bg-gray-50 object-contain dark:bg-gray-900" /></div>
          <p class="text-xs leading-5 text-gray-500 dark:text-gray-400">{{ preview.summary }}</p>
          <p class="text-xs text-primary-700 dark:text-primary-300">将一起公开分享以上图片，含原始皮肤照片。</p>
        </section>
        <p class="text-sm leading-6 text-gray-600 dark:text-gray-300">
          发布后，该内容将<strong>对所有用户可见</strong>。请确认文中不包含手机号、住址、
          病历号等个人隐私信息；病情照片是否公开由你自己决定。
        </p>

        <div
          v-if="piiLabels.length"
          class="mt-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 p-3"
        >
          <div class="flex items-start gap-2">
            <i class="ri-error-warning-line mt-0.5 text-amber-600 dark:text-amber-400" aria-hidden="true"></i>
            <p class="text-sm leading-6 text-amber-800 dark:text-amber-300">
              检测到内容可能包含：<strong>{{ piiLabels.join('、') }}</strong>。
              系统将自动脱敏后再发布，以保护你的隐私。
            </p>
          </div>
          <label class="mt-2 flex cursor-pointer items-start gap-2 text-sm text-amber-900 dark:text-amber-200">
            <input
              v-model="keepOriginal"
              type="checkbox"
              class="mt-0.5 h-4 w-4 accent-amber-600"
            />
            我了解风险，确认保留原文发布（不推荐）
          </label>
        </div>

        <p class="mt-3 text-xs leading-5 text-gray-400 dark:text-gray-500">
          发布后你可以随时删除帖子；若需转为私密请先发布再在帖子设置中调整。
        </p>

        <div class="mt-4 flex justify-end gap-2">
          <button
            class="btn-ghost px-4 py-2 text-sm"
            @click="emit('cancel')"
          >
            取消
          </button>
          <button
            class="btn-primary px-4 py-2 text-sm"
            @click="emit('confirm', { confirmPii: keepOriginal })"
          >
            <i class="ri-global-line mr-1" aria-hidden="true"></i>确认公开
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  piiLabels: string[]
  preview?: { title: string; summary: string; images: string[] }
}>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'confirm', payload: { confirmPii: boolean }): void
}>()

const keepOriginal = ref(false)
</script>
