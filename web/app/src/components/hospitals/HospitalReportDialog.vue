<script setup lang="ts">
import HospitalDialog from './HospitalDialog.vue'
import type { HospitalReview, ReviewReportReason } from '@/types/hospital'

/** 举报评价弹窗：目录页与详情页共用。 */
defineProps<{
  review: HospitalReview
  reasons: { id: ReviewReportReason; label: string }[]
  reason: ReviewReportReason
}>()
const emit = defineEmits<{ 'update:reason': [value: ReviewReportReason]; submit: []; close: [] }>()
</script>

<template>
  <HospitalDialog title="举报这条评价" @close="emit('close')">
    <div class="space-y-4">
      <p class="text-sm leading-6 text-gray-600 dark:text-gray-300">
        请选择最符合的原因。我们只依据<RouterLink class="underline" to="/hospitals/rules">社区公约</RouterLink>审核评价本身，不判断医疗行为是否有过错。
      </p>
      <fieldset>
        <legend class="sr-only">举报原因</legend>
        <div class="space-y-2">
          <label
            v-for="item in reasons" :key="item.id"
            class="flex min-h-11 items-center gap-2 rounded-xl border px-3 text-sm"
            :class="reason === item.id ? 'border-primary-500 bg-primary-50 dark:bg-primary-900' : 'border-gray-200 dark:border-gray-700'"
          >
            <input :checked="reason === item.id" type="radio" :value="item.id" @change="emit('update:reason', item.id)">
            <span>{{ item.label }}</span>
          </label>
        </div>
      </fieldset>
      <p class="text-xs leading-6 text-gray-500 dark:text-gray-400">
        同一评价你只能举报一次。若你是被评价的医院或医护人员，建议走<RouterLink class="underline" to="/hospitals/appeal">评价申诉</RouterLink>，可以留下依据并要求更正。
      </p>
      <div class="flex gap-3">
        <button class="min-h-11 flex-1 rounded-xl border border-gray-200 px-4 text-sm dark:border-gray-700" @click="emit('close')">取消</button>
        <button class="min-h-11 flex-1 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white" @click="emit('submit')">提交举报</button>
      </div>
    </div>
  </HospitalDialog>
</template>
