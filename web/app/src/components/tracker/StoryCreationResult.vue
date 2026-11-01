<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AssessmentResult } from '@/types/assessment'
import { journalSummary } from '@/utils/assessment-story/summary'
import AssessmentStoryCard from './AssessmentStoryCard.vue'
const props = defineProps<{ result: AssessmentResult; skin?: string | null; lesion?: string | null; saved?: boolean; busy?: boolean; autoStart?: boolean }>()
const emit = defineEmits<{ adjust: []; restart: [] }>()
const started = ref(props.autoStart === true)
const summary = computed(() => journalSummary(props.result))
const ready = computed(() => !!props.saved && summary.value.reviewed && !!summary.value.revision && !!props.lesion)
watch(() => [props.result.id, summary.value.revision], () => { started.value = props.autoStart === true })
</script>
<template>
  <section class="space-y-4" aria-label="创作作品">
    <AssessmentStoryCard v-if="ready && started" :key="result.id" :result="result" :skin="skin" :lesion="lesion" :saved="saved" />
    <div v-else class="card p-5">
      <h2 class="section-title">我的轮廓故事</h2><p class="mt-2 text-sm text-gray-600 dark:text-gray-300">把你的白斑轮廓变成一幅画</p>
      <p class="mt-3 text-xs leading-5 text-gray-500 dark:text-gray-400">{{ ready ? '使用这条记录中已确认的轮廓创作，照片不会自动公开。' : '先确认照片中的白斑范围，让画面保留属于你的形状。' }}</p>
      <button v-if="ready" type="button" class="btn-primary mt-4 min-h-[48px] w-full" data-track-id="story_start" @click="started = true">生成我的作品</button>
      <button v-else type="button" :disabled="busy" class="btn-primary mt-4 min-h-[48px] w-full disabled:opacity-40" @click="emit('adjust')">确认轮廓后创作</button>
    </div>
    <div class="flex flex-wrap items-center justify-between gap-2 text-sm"><button type="button" class="min-h-[44px] px-2 text-primary-700 dark:text-primary-300" :disabled="busy" @click="emit('restart')">再拍一张</button><router-link :to="{ name: 'vasi-detail', params: { id: result.id } }" class="inline-flex min-h-[44px] items-center px-2 text-gray-500 dark:text-gray-400">查看照片记录<i class="ri-arrow-right-s-line" aria-hidden="true"></i></router-link></div>
  </section>
</template>
