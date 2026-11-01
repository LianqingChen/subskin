<script setup lang="ts">
import PhotoCaptureEntry from './PhotoCaptureEntry.vue'
defineProps<{ bodySite: string; loggedIn: boolean }>()
const emit = defineEmits<{ select: [string]; camera: []; files: [File[]]; login: []; history: [] }>()
</script>
<template>
  <section class="space-y-5 py-5 md:py-6" aria-labelledby="story-intro-title">
    <header><h2 id="story-intro-title" class="page-title">我的轮廓故事</h2><p class="mt-2 text-sm text-gray-600 dark:text-gray-300">把你的白斑轮廓变成一幅画</p></header>
    <p class="text-sm leading-6 text-gray-500 dark:text-gray-400">从一张照片开始。确认你的轮廓后，把它化作云朵、海岛或星光。</p>
    <ol aria-label="创作步骤" class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"><li class="font-medium text-primary-700 dark:text-primary-300">1 添加照片</li><li aria-hidden="true"><i class="ri-arrow-right-s-line"></i></li><li>2 确认轮廓</li><li aria-hidden="true"><i class="ri-arrow-right-s-line"></i></li><li>3 生成作品</li></ol>
    <div class="card p-5 sm:p-6"><PhotoCaptureEntry creative :body-site="bodySite" :logged-in="loggedIn" @select="emit('select', $event)" @camera="emit('camera')" @files="emit('files', $event)" @login="emit('login')" /></div>
    <p class="text-xs leading-5 text-gray-500 dark:text-gray-400">确认后，照片会保存到你的私人日记记录。生成作品不会自动公开照片。</p>
    <button type="button" class="min-h-[44px] text-sm text-primary-700 dark:text-primary-300" data-track-id="story_existing_record" @click="emit('history')">已拍过照片？用已有记录创作<i class="ri-arrow-right-s-line ml-1" aria-hidden="true"></i></button>
  </section>
</template>
