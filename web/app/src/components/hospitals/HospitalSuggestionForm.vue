<script setup lang="ts">
import { ref } from 'vue'
import type { HospitalSuggestion } from '@/types/hospital'
const props = defineProps<{ hospitalName?: string; draft?: HospitalSuggestion }>()
const emit = defineEmits<{ save: [suggestion: HospitalSuggestion] }>()
const form = ref<HospitalSuggestion>({ name: props.hospitalName ?? props.draft?.name ?? '', city: props.draft?.city ?? '', source: props.draft?.source ?? '', note: props.draft?.note ?? '' })
</script>
<template>
  <form class="space-y-4" @submit.prevent="emit('save', { ...form })">
    <p class="rounded-xl bg-primary-50 p-3 text-xs leading-6 text-primary-800 dark:bg-primary-900 dark:text-primary-200">先保存一份本机补充资料。此版本不会提交给平台，也不会直接修改地图；正式收录需核实医院资质与官方来源。</p>
    <label class="block text-sm">医院全称<input v-model.trim="form.name" required maxlength="100" class="hospital-input" /></label>
    <label class="block text-sm">省份、城市和院区<input v-model.trim="form.city" required maxlength="100" class="hospital-input" placeholder="例如：江苏省南京市 · 具体院区" /></label>
    <label class="block text-sm">官方资料链接<input v-model.trim="form.source" type="url" maxlength="500" class="hospital-input" placeholder="https://" /></label>
    <label class="block text-sm">补充或纠错内容<textarea v-model.trim="form.note" required maxlength="1000" rows="4" class="hospital-input" placeholder="请注明需要补充或更新的信息，不填写个人联系方式。" /></label>
    <button type="submit" class="min-h-11 w-full rounded-xl bg-primary-600 px-4 py-3 text-sm text-white">保存本机补充草稿</button>
  </form>
</template>
<style scoped>
.hospital-input { @apply mt-2 block min-h-11 w-full min-w-0 rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100; }
</style>
