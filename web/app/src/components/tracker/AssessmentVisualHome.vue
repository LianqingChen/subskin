<script setup lang="ts">
import { computed, ref } from 'vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import PhotoCaptureEntry from './PhotoCaptureEntry.vue'
import { toProtectedFileUrl } from '@/utils/file-url'
import type { ObservationRecord } from './AssessmentRecords.vue'
const props = defineProps<{ bodySite: string; recent: ObservationRecord[]; loggedIn: boolean; loading: boolean }>()
const emit = defineEmits<{ select: [string]; camera: []; files: [File[]]; history: []; login: [] }>()
const recording = ref(false)
const recent = computed(() => [...props.recent].sort((a, b) => (b.date || '').localeCompare(a.date || '')).slice(0, 3))
</script>
<template>
  <div class="grid items-start gap-4 py-5 md:py-6 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)] lg:gap-6">
    <section aria-labelledby="diary-start-heading" class="card min-w-0 p-5 sm:p-6">
      <template v-if="!recording">
        <h2 id="diary-start-heading" class="text-base font-semibold tracking-tight text-gray-900 sm:text-lg dark:text-gray-100">记下今天的皮肤状态</h2>
        <p class="mt-2 text-sm leading-6 text-gray-500 dark:text-gray-400">留一张照片，慢慢看见变化。</p>
        <button type="button" data-track-id="diary_start_record" class="btn-primary mt-5 min-h-[48px] w-full" @click="recording = true"><i class="ri-camera-line mr-2" aria-hidden="true"></i>拍照记录</button>
      </template>
      <template v-else>
        <header class="mb-3 flex items-center justify-between gap-3"><h2 id="diary-start-heading" class="text-base font-semibold tracking-tight text-gray-900 sm:text-lg dark:text-gray-100">添加一张照片</h2><button type="button" class="min-h-[44px] px-2 text-sm text-gray-500 dark:text-gray-400" @click="recording = false">收起</button></header>
        <PhotoCaptureEntry :body-site="bodySite" :logged-in="loggedIn" @select="emit('select', $event)" @camera="emit('camera')" @files="emit('files', $event)" @login="emit('login')" />
      </template>
    </section>
    <section aria-label="最近记录" class="card min-w-0 p-5 sm:p-6 lg:col-start-2 lg:row-start-1 lg:row-span-2">
      <header class="mb-1 flex min-h-[44px] items-center justify-between gap-3"><h2 class="text-base font-semibold">最近记录</h2><button type="button" class="min-h-[44px] px-2 text-xs text-gray-500 dark:text-gray-400" @click="emit('history')">{{ loggedIn ? '全部记录' : '登录查看' }}<i class="ri-arrow-right-s-line ml-1" aria-hidden="true"></i></button></header>
      <p v-if="loading" role="status" class="py-4 text-sm text-gray-500 dark:text-gray-400">正在加载记录…</p>
      <div v-else-if="loggedIn && recent.length" class="divide-y divide-gray-200 dark:divide-gray-800">
        <router-link v-for="item in recent" :key="item.id" :to="{ name: 'vasi-detail', params: { id: item.id } }" class="flex min-h-[68px] items-center gap-3 py-3 text-gray-900 dark:text-gray-100" :aria-label="`查看${item.observation?.label || item.bodySite}的记录`">
          <img v-if="item.imageUrl" :src="toProtectedFileUrl(item.imageUrl)" alt="记录照片缩略图" class="h-11 w-11 shrink-0 rounded-lg object-cover" />
          <span class="min-w-0 flex-1"><span class="block truncate text-sm font-medium">{{ item.observation?.label || item.bodySite }}</span><time :datetime="item.date" class="mt-1 block text-xs tabular-nums text-gray-500 dark:text-gray-400">{{ item.date }}</time></span>
          <i class="ri-arrow-right-s-line text-gray-400" aria-hidden="true"></i>
        </router-link>
      </div>
      <p v-else class="py-4 text-sm leading-6 text-gray-500 dark:text-gray-400">{{ loggedIn ? '第一张照片，就是记录的开始。' : '照片记录仅自己可见，登录后可查看。' }}</p>
    </section>
    <router-link :to="{ name: 'assessment-story' }" data-track-id="diary_story_entry" class="card flex min-h-[76px] min-w-0 items-center gap-3 px-5 py-4 text-primary-700 hover:border-primary-300 sm:px-6 lg:col-start-1 dark:text-primary-300 dark:hover:border-primary-700">
      <i class="ri-sparkling-line text-xl" aria-hidden="true"></i><span class="min-w-0 flex-1"><span class="block text-sm font-medium">我的轮廓故事</span><span class="mt-1 block text-xs leading-5 text-gray-500 dark:text-gray-400">把你的白斑轮廓变成一幅画</span></span><i class="ri-arrow-right-s-line" aria-hidden="true"></i>
    </router-link>
    <MedicalDisclaimer class="lg:col-span-2" variant="inline" message="照片记录仅供参考，不构成医疗建议" />
  </div>
</template>
