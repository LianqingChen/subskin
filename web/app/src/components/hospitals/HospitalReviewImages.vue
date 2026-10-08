<script setup lang="ts">
import { computed, ref } from 'vue'
import { toProtectedFileUrl } from '@/utils/file-url'
import { detectPii } from '@/utils/piiCheck'
import { MAX_REVIEW_IMAGES, REVIEW_IMAGE_LABELS, type HospitalReviewImage } from '@/types/hospital'

/**
 * 评价凭证图：只允许「非病情」的就诊凭证（费用单/挂号单/处方/检查单）。
 * 图片无法自动脱敏，因此强制用户确认已遮盖姓名/手机号/病历号且不含病情照片。
 */
const props = defineProps<{ modelValue: HospitalReviewImage[]; confirmed: boolean; uploading?: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: HospitalReviewImage[]]
  'update:confirmed': [value: boolean]
  upload: [file: File, label: string]
  remove: [url: string]
}>()
const label = ref<string>(REVIEW_IMAGE_LABELS[0])
const input = ref<HTMLInputElement>()
const localError = ref('')

const remaining = computed(() => MAX_REVIEW_IMAGES - props.modelValue.length)
const piiWarning = computed(() => detectPii(props.modelValue.map(i => i.label).join(' ')))

function pick() {
  if (!remaining.value) return
  input.value?.click()
}
function onFile(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  target.value = ''
  if (!file) return
  localError.value = ''
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
    localError.value = '只支持 jpg / png / webp 格式的截图'
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    localError.value = '单张图片不能超过 5MB'
    return
  }
  emit('upload', file, label.value)
}
</script>

<template>
  <fieldset class="rounded-xl border border-dashed border-gray-200 p-4 dark:border-gray-700">
    <legend class="px-1 text-sm font-medium">就诊凭证（选填）</legend>
    <p class="text-xs leading-6 text-gray-500 dark:text-gray-400">
      可以拍或截 <strong>费用单、挂号单、处方、检查单</strong>，帮病友看清真实花费。
      <span class="text-amber-700 dark:text-amber-300">请勿上传病情/皮损照片</span>；上传前请遮盖姓名、手机号、病历号。
    </p>

    <div class="mt-3 flex flex-wrap items-center gap-2">
      <select v-model="label" class="min-h-11 rounded-xl border border-gray-200 bg-white px-3 text-xs dark:border-gray-700 dark:bg-gray-800">
        <option v-for="item in REVIEW_IMAGE_LABELS" :key="item" :value="item">{{ item }}</option>
      </select>
      <button type="button" :disabled="remaining <= 0 || uploading" class="min-h-11 rounded-xl border border-primary-200 px-4 text-xs text-primary-700 disabled:opacity-40 dark:border-primary-800 dark:text-primary-300" @click="pick">
        <i :class="uploading ? 'ri-loader-4-line animate-spin' : 'ri-image-add-line'" class="mr-1" />{{ uploading ? '上传中…' : `选择图片（还可传 ${remaining} 张）` }}
      </button>
      <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="onFile">
    </div>

    <div v-if="modelValue.length" class="mt-3 grid grid-cols-3 gap-2">
      <figure v-for="image in modelValue" :key="image.url" class="relative overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
        <img :src="toProtectedFileUrl(image.url)" :alt="`${image.label}凭证图`" class="h-24 w-full object-cover">
        <figcaption class="bg-gray-50 px-2 py-1 text-[11px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">{{ image.label }}</figcaption>
        <button type="button" class="absolute right-1 top-1 h-8 w-8 rounded-full bg-black/60 text-white" :aria-label="`删除${image.label}凭证图`" @click="emit('remove', image.url)"><i class="ri-close-line" /></button>
      </figure>
    </div>

    <p v-if="localError" class="mt-2 text-xs text-red-600 dark:text-red-400">{{ localError }}</p>
    <p v-if="piiWarning.length" class="mt-2 text-xs text-amber-700 dark:text-amber-300"><i class="ri-error-warning-line mr-1" />凭证图类型里出现了{{ piiWarning.join('、') }}，请确认图片内容已遮盖个人信息。</p>

    <label v-if="modelValue.length" class="mt-3 flex cursor-pointer items-start gap-2 text-xs leading-6 text-gray-700 dark:text-gray-200">
      <input :checked="confirmed" type="checkbox" class="mt-1.5 h-4 w-4 shrink-0 accent-primary-600" @change="emit('update:confirmed', ($event.target as HTMLInputElement).checked)">
      <span>我确认：图片<strong>不含病情/皮损照片</strong>，且已遮盖姓名、手机号、病历号等个人信息。未勾选无法发布。</span>
    </label>
  </fieldset>
</template>
