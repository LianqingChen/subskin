<script setup lang="ts">
import { computed } from 'vue'
import type { AssessmentResult } from '@/types/assessment'
import { useAssessmentStory } from '@/composables/useAssessmentStory'
import { useStoryShare } from '@/composables/useStoryShare'
import { STORY_THEMES } from '@/utils/assessment-story/content'
import { journalSummary } from '@/utils/assessment-story/summary'
import StoryPeelPreview from './StoryPeelPreview.vue'
const props = defineProps<{ result: AssessmentResult; skin?: string | null; lesion?: string | null; saved?: boolean }>()
const creative = useAssessmentStory(props), share = useStoryShare()
const disabled = computed(() => creative.loading.value || share.busy.value || !creative.blob.value)
function publish() {
  const revision = journalSummary(props.result).revision, id = props.result.id, theme = creative.selectedTheme.value
  if (props.skin && props.lesion) void share.community(props.result, props.skin, props.lesion, creative.blob.value, creative.title.value,
    () => creative.selectedTheme.value === theme && props.result.id === id && journalSummary(props.result).revision === revision && !!props.saved)
}
</script>
<template>
  <section aria-label="我的轮廓故事" class="overflow-hidden rounded-2xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
    <header class="mb-3 flex items-center justify-between gap-2"><h2 class="whitespace-nowrap text-base font-semibold">我的轮廓故事</h2><span v-if="creative.story.value" class="text-xs text-gray-400">{{ creative.drawing.value ? '画面生成中' : creative.enhancing.value ? '文案生成中' : creative.artGenerated.value ? 'AI 图案 · AI 文案' : creative.story.value.source === 'ai' ? 'AI 文案' : '模板创意' }}</span></header>
    <div role="group" aria-label="选择创意风格" class="mb-3 grid grid-cols-3 gap-2">
      <button v-for="item in STORY_THEMES" :key="item.id" type="button" :disabled="share.busy.value" :aria-pressed="creative.selectedTheme.value === item.id" class="flex min-h-[44px] items-center justify-center gap-1 whitespace-nowrap rounded-lg border px-1 text-xs transition-colors disabled:opacity-50" :class="creative.selectedTheme.value === item.id ? 'border-primary-500 bg-primary-50 font-medium text-primary-800 dark:border-primary-400 dark:bg-primary-900 dark:text-primary-200' : 'border-gray-200 text-gray-500 dark:border-gray-600 dark:text-gray-300'" @click="creative.selectedTheme.value = item.id"><i :class="item.icon" aria-hidden="true"></i>{{ item.id === 'sky' ? '云朵' : item.id === 'island' ? '海岛' : '星光' }}</button>
    </div>
    <div v-if="creative.loading.value" role="status" class="flex aspect-[3/4] max-h-[480px] items-center justify-center gap-2 rounded-xl bg-primary-50 text-sm text-primary-700 dark:bg-primary-900 dark:text-primary-200"><i class="ri-loader-4-line animate-spin" aria-hidden="true"></i>正在把轮廓写成风景…</div>
    <StoryPeelPreview v-else-if="creative.url.value" :image="result.imageUrl" :skin="skin" :lesion="lesion" :poster="creative.url.value" :title="creative.title.value" :artwork="creative.peelArtwork.value" :selection="`${result.id}:${creative.selectedTheme.value}:${creative.story.value?.revision}`" />
    <div v-else role="status" class="rounded-xl bg-gray-50 p-4 text-sm leading-6 text-gray-500 dark:bg-gray-900 dark:text-gray-300">
      <p>{{ creative.error.value }}</p>
      <router-link v-if="creative.needsConsent.value" to="/profile" class="inline-flex min-h-[44px] items-center text-primary-700 dark:text-primary-300">前往隐私设置</router-link>
      <button v-else type="button" class="min-h-[44px] text-primary-700 dark:text-primary-300" @click="creative.load">重新生成</button>
    </div>
    <p v-if="creative.url.value && creative.notice.value" role="status" class="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">
      {{ creative.notice.value }}
      <router-link v-if="creative.needsConsent.value" to="/profile" class="inline-flex min-h-[44px] items-center text-primary-700 dark:text-primary-300">隐私设置</router-link>
      <button v-else type="button" :disabled="creative.enhancing.value" class="min-h-[44px] px-2 text-primary-700 dark:text-primary-300" @click="creative.load">重试文案</button>
    </p>
    <p v-if="creative.drawing.value" role="status" class="mt-2 text-xs text-primary-700 dark:text-primary-300"><i class="ri-loader-4-line mr-1 inline-block animate-spin" aria-hidden="true"></i>正在依照轮廓创作画面，可能需要几分钟，当前创意仍可保存</p>
    <p v-else-if="creative.artNotice.value" role="status" class="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">{{ creative.artNotice.value }}<button type="button" class="min-h-[44px] px-2 text-primary-700 dark:text-primary-300" @click="creative.retryArtwork">重试画面</button></p>
    <button type="button" class="btn-primary mt-4 min-h-[44px] w-full rounded-xl text-sm" :disabled="share.busy.value || creative.loading.value || !creative.blob.value || !skin || !lesion" @click="publish"><i class="ri-share-forward-line mr-1" aria-hidden="true"></i>{{ share.busy.value ? '正在准备分享…' : '发布到发现' }}</button>
    <div class="mt-2 grid grid-cols-2 gap-2">
      <button type="button" class="btn-ghost min-h-[44px] rounded-xl text-sm" :disabled="disabled" @click="share.download(creative.url.value)"><i class="ri-download-line mr-1" aria-hidden="true"></i>保存图片</button>
      <button type="button" class="btn-ghost min-h-[44px] rounded-xl text-sm" :disabled="disabled" @click="creative.blob.value && share.systemShare(creative.blob.value, creative.title.value, creative.url.value)"><i class="ri-share-line mr-1" aria-hidden="true"></i>更多分享</button>
    </div>
    <p class="mt-1 text-center text-xs leading-5 text-gray-400">站内分享含照片与标注，保存图片仅含创意卡</p>
  </section>
</template>
