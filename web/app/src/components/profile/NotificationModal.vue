<script setup lang="ts">
import { ref } from 'vue'

function createStoredBoolean(key: string, defaultValue: boolean) {
  const stored = localStorage.getItem(key)
  const val = ref(stored !== null ? stored === 'true' : defaultValue)
  return {
    get value() { return val.value },
    set value(v: boolean) {
      val.value = v
      localStorage.setItem(key, String(v))
    }
  }
}

const STORAGE_KEYS = {
  assessmentReminder: 'subskin_assessment_reminder',
  communityNotification: 'subskin_community_notification',
  treatmentNotification: 'subskin_treatment_notification',
} as const

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>()

const assessmentReminder = createStoredBoolean(STORAGE_KEYS.assessmentReminder, false)
const communityNotification = createStoredBoolean(STORAGE_KEYS.communityNotification, true)
const treatmentNotification = createStoredBoolean(STORAGE_KEYS.treatmentNotification, true)
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center" @click.self="emit('update:modelValue', false)">
      <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4 max-h-[90dvh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-semibold text-gray-900"><i class="ri-notification-3-line"></i> 通知设置</h2>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="emit('update:modelValue', false)">&times;</button>
        </div>
        <div class="p-6 space-y-4">
          <div class="flex items-start justify-between gap-4">
            <div><h3 class="text-sm font-medium text-gray-900">评估提醒</h3><p class="text-xs text-gray-500  mt-1">定期提醒进行VASI评估</p></div>
            <button type="button" class="setting-switch" :class="assessmentReminder.value ? 'setting-switch-on' : 'setting-switch-off'" @click="assessmentReminder.value = !assessmentReminder.value"><span class="setting-switch-thumb" :class="assessmentReminder.value ? 'translate-x-7' : 'translate-x-0'" /></button>
          </div>
          <div class="flex items-start justify-between gap-4">
            <div><h3 class="text-sm font-medium text-gray-900">社区互动通知</h3><p class="text-xs text-gray-500  mt-1">有人评论或点赞你的帖子时通知</p></div>
            <button type="button" class="setting-switch" :class="communityNotification.value ? 'setting-switch-on' : 'setting-switch-off'" @click="communityNotification.value = !communityNotification.value"><span class="setting-switch-thumb" :class="communityNotification.value ? 'translate-x-7' : 'translate-x-0'" /></button>
          </div>
          <div class="flex items-start justify-between gap-4">
            <div><h3 class="text-sm font-medium text-gray-900">治疗进展通知</h3><p class="text-xs text-gray-500  mt-1">有新的白癜风治疗研究进展时通知</p></div>
            <button type="button" class="setting-switch" :class="treatmentNotification.value ? 'setting-switch-on' : 'setting-switch-off'" @click="treatmentNotification.value = !treatmentNotification.value"><span class="setting-switch-thumb" :class="treatmentNotification.value ? 'translate-x-7' : 'translate-x-0'" /></button>
          </div>
          <p class="text-xs text-gray-400 ">通知功能将在后续版本中支持推送</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>
