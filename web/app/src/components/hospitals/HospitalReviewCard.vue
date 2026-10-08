<script setup lang="ts">
import { computed } from 'vue'
import { toProtectedFileUrl } from '@/utils/file-url'
import { EXPERIENCE_LEVELS } from '@/utils/reviewRiskRules'
import { COMPLETE_DETAIL_SCORE, type HospitalReview } from '@/types/hospital'

/** 一条公开评价：作者、时间、6 维体验档位、效果自述、凭证徽标与正文分开显示。 */
const props = defineProps<{ review: HospitalReview; showHospital?: boolean; reported?: boolean }>()
const emit = defineEmits<{
  remove: [id: number]
  helpful: [review: HospitalReview]
  report: [review: HospitalReview]
  appeal: [review: HospitalReview]
}>()

const TARGET_LABELS: Record<string, { label: string; icon: string }> = {
  hospital: { label: '医院评价', icon: 'ri-hospital-line' },
  doctor: { label: '医生评价', icon: 'ri-user-heart-line' },
  treatment: { label: '治疗方案', icon: 'ri-capsule-line' },
  experience: { label: '治疗经历', icon: 'ri-book-open-line' },
}
const meta = computed(() => TARGET_LABELS[props.review.target] ?? TARGET_LABELS.hospital)

const LEVEL_STYLE: Record<string, string> = {
  satisfied: 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300',
  neutral: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  unsatisfied: 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  na: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
}
const LEVEL_LABEL: Record<string, string> = Object.fromEntries(
  EXPERIENCE_LEVELS.map(item => [item.key, item.label]),
)

const experienceEntries = computed(() =>
  Object.entries(props.review.experienceScores ?? {}).map(([dimension, level]) => ({
    dimension,
    level,
    label: LEVEL_LABEL[level] ?? level,
    style: LEVEL_STYLE[level] ?? LEVEL_STYLE.na,
  })),
)

const dateText = computed(() => {
  if (!props.review.createdAt) return ''
  const date = new Date(props.review.createdAt)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN')
})
/** 时间衰减标注：白癜风疗程长，超过 18 个月的旧评价最容易失真（对齐好大夫做法） */
const isStale = computed(() => {
  if (!props.review.createdAt) return false
  const created = new Date(props.review.createdAt)
  if (Number.isNaN(created.getTime())) return false
  return Date.now() - created.getTime() > 1000 * 60 * 60 * 24 * 540
})
const initial = computed(() => props.review.authorName.trim().charAt(0) || '白')
const isComplete = computed(() => props.review.detailScore >= COMPLETE_DETAIL_SCORE)
const restricted = computed(() => props.review.moderationStatus === 'restricted')
const blocked = computed(() => props.review.moderationStatus === 'blocked')
</script>

<template>
  <article
    class="rounded-2xl border bg-white p-4 dark:bg-gray-900"
    :class="restricted || blocked ? 'border-amber-200 dark:border-amber-800/60' : 'border-gray-200 dark:border-gray-800'"
  >
    <header class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
      <span class="inline-flex items-center gap-1 rounded-md bg-primary-50 px-2 py-1 text-primary-700 dark:bg-primary-900 dark:text-primary-300"><i :class="meta.icon" />{{ meta.label }}</span>
      <span v-if="showHospital && review.hospitalName" class="truncate">{{ review.hospitalCity }} · {{ review.hospitalName }}</span>
      <span v-if="review.visitMonth">就诊于 {{ review.visitMonth }}</span>
      <span v-if="isStale" class="rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-800 dark:text-gray-400">时间较早 · 仅供参考</span>
      <span v-if="review.moderationStatus === 'flagged'" class="rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">待复核</span>
      <span v-if="restricted" class="rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">复核中 · 排序靠后</span>
      <span v-if="isComplete" class="rounded-md bg-primary-50 px-1.5 py-0.5 text-[10px] text-primary-700 dark:bg-primary-900 dark:text-primary-300"><i class="ri-file-check-line mr-0.5" />完整分享</span>
    </header>

    <!-- 作者可见的受限/驳回原因（其他病友看不到） -->
    <p v-if="review.isMine && review.restrictedReason" class="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-6 text-amber-800 dark:bg-amber-900/25 dark:text-amber-200">
      <i class="ri-error-warning-line mr-1" />{{ review.restrictedReason }}
      <button class="ml-1 underline" @click="emit('appeal', review)">我觉得被误判了</button>
    </p>

    <div v-if="review.doctorName || review.treatmentName" class="mt-3 rounded-xl bg-gray-50 px-3 py-2 text-xs leading-6 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
      <template v-if="review.doctorName"><i class="ri-user-heart-line mr-1" />{{ review.doctorName }}<template v-if="review.doctorTitle"> · {{ review.doctorTitle }}</template></template>
      <template v-if="review.treatmentName"><span v-if="review.doctorName"> ｜ </span><i class="ri-capsule-line mr-1" />{{ review.treatmentName }}<template v-if="review.treatmentDetail">（{{ review.treatmentDetail }}）</template></template>
    </div>

    <p class="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-gray-800 dark:text-gray-100">{{ review.content }}</p>

    <!-- 6 维体验档位（替代旧的 1-5 星平均分） -->
    <div v-if="experienceEntries.length" class="mt-3 flex flex-wrap gap-1.5">
      <span
        v-for="entry in experienceEntries" :key="entry.dimension"
        class="rounded-lg px-2 py-1 text-[11px]" :class="entry.style"
      >{{ entry.dimension }} · {{ entry.label }}</span>
    </div>
    <div v-if="review.tags.length" class="mt-2 flex flex-wrap gap-1.5">
      <span v-for="tag in review.tags" :key="tag" class="rounded-md bg-gray-100 px-2 py-1 text-[11px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">{{ tag }}</span>
    </div>

    <!-- 凭证徽标：原图仅作者可见（含姓名/手机号/病历号，属敏感个人信息） -->
    <p v-if="review.credentialLabels.length" class="mt-3 inline-flex items-center gap-1 rounded-lg bg-gray-50 px-2 py-1 text-[11px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
      <i class="ri-attachment-2" aria-hidden="true" />已上传{{ review.credentialLabels.join('、') }}
      <span class="text-gray-400">（仅本人可见，用于自证）</span>
    </p>
    <div v-if="review.images.length" class="mt-3 grid grid-cols-3 gap-2 md:max-w-md">
      <figure v-for="image in review.images" :key="image.url" class="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
        <a :href="toProtectedFileUrl(image.url)" target="_blank" rel="noopener noreferrer">
          <img :src="toProtectedFileUrl(image.url)" :alt="`${image.label}凭证图（仅本人可见）`" class="h-24 w-full object-cover" loading="lazy">
        </a>
        <figcaption class="bg-gray-50 px-2 py-1 text-[11px] text-gray-500 dark:bg-gray-800 dark:text-gray-400">{{ image.label }} · 仅本人可见</figcaption>
      </figure>
    </div>

    <dl v-if="review.duration || review.cost || review.outcome" class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
      <div v-if="review.duration" class="flex gap-1"><dt>治疗时长</dt><dd class="text-gray-700 dark:text-gray-200">{{ review.duration }}</dd></div>
      <div v-if="review.cost" class="flex gap-1"><dt>每月自付</dt><dd class="text-gray-700 dark:text-gray-200">{{ review.cost }}</dd></div>
      <div v-if="review.outcome" class="flex gap-1"><dt>我的感受</dt><dd class="text-gray-700 dark:text-gray-200">{{ review.outcome }}</dd></div>
    </dl>

    <footer class="mt-3 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3 text-xs text-gray-400 dark:border-gray-800">
      <span class="flex h-7 w-7 items-center justify-center rounded-full bg-gray-100 text-[11px] text-gray-500 dark:bg-gray-800 dark:text-gray-300">{{ initial }}</span>
      <span class="truncate">{{ review.authorName }}</span>
      <time v-if="dateText" :datetime="review.createdAt">{{ dateText }}</time>
      <span class="ml-auto flex items-center gap-1">
        <button
          v-if="!review.isMine" :aria-pressed="review.isHelpful"
          class="min-h-11 rounded-lg px-3 text-xs"
          :class="review.isHelpful ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'text-gray-500 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800'"
          @click="emit('helpful', review)"
        ><i :class="review.isHelpful ? 'ri-thumb-up-fill' : 'ri-thumb-up-line'" class="mr-1" />有用<template v-if="review.helpfulCount"> {{ review.helpfulCount }}</template></button>
        <span v-else-if="review.helpfulCount" class="text-xs text-gray-400"><i class="ri-thumb-up-line mr-1" />{{ review.helpfulCount }} 人觉得有用</span>
        <button v-if="review.isMine" class="min-h-11 px-2 text-gray-500 underline" @click="emit('remove', review.id)">删除我的评价</button>
        <button
          v-else-if="!reported" class="min-h-11 px-2 text-gray-400 hover:text-amber-600"
          @click="emit('report', review)"
        ><i class="ri-flag-line mr-1" />举报</button>
        <span v-else class="px-2 text-gray-400">已举报</span>
      </span>
    </footer>
    <p class="mt-2 text-[11px] leading-5 text-gray-400">
      病友个人经历与感受，不代表医疗水平，也不算疗效；诊疗请遵医嘱。「我已就诊」凭证只用于作者自证，不对外公开。
    </p>
  </article>
</template>
