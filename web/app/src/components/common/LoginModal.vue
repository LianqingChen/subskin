<script setup lang="ts">
import { ref } from 'vue'
import PhoneLoginForm from '@/components/common/PhoneLoginForm.vue'
import EmailLoginForm from '@/components/common/EmailLoginForm.vue'

const emit = defineEmits<{ close: [] }>()

type LoginMethod = 'phone' | 'email'
const activeMethod = ref<LoginMethod>('phone')
const errorMessage = ref('')

const tabs: { key: LoginMethod; label: string; icon: string }[] = [
  { key: 'phone', label: '手机', icon: 'ri-smartphone-line' },
  { key: 'email', label: '邮箱', icon: 'ri-mail-line' },
]

function handleFormError(msg: string) { errorMessage.value = msg }

function handleFormClose() {
  errorMessage.value = ''
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <!-- 手机端底部抽屉，平板/桌面居中弹窗 -->
    <div class="fixed inset-0 z-[70] flex items-end justify-center bg-black/50 backdrop-blur-[2px] sm:items-center sm:p-4" @click.self="emit('close')">
      <div class="max-h-[92vh] max-h-[92dvh] w-full overflow-y-auto rounded-t-2xl border border-gray-200/80 bg-white pb-[env(safe-area-inset-bottom,0px)] shadow-xl dark:border-gray-800 dark:bg-gray-900 sm:max-w-sm sm:rounded-2xl sm:pb-0" role="dialog" aria-modal="true">
        <div class="flex items-center justify-between px-6 pt-5 pb-3">
          <h2 class="text-lg font-semibold tracking-tight text-gray-900 dark:text-gray-100">{{ activeMethod === 'phone' ? '手机登录 / 注册' : '邮箱登录 / 注册' }}</h2>
          <button type="button" class="-mr-2 flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200" aria-label="关闭" @click="emit('close')">
            <i class="ri-close-line text-xl" aria-hidden="true"></i>
          </button>
        </div>

        <div class="flex border-b border-gray-200/80 dark:border-gray-800">
          <button v-for="tab in tabs" :key="tab.key" type="button"
            class="flex-1 border-b-2 px-2 py-2.5 text-sm font-medium transition-colors"
            :class="activeMethod === tab.key ? 'border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-300' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'"
            @click.prevent="activeMethod = tab.key; errorMessage = ''">
            <span class="inline-flex items-center gap-1.5">
              <i :class="tab.icon" class="text-base shrink-0" aria-hidden="true"></i>
              {{ tab.label }}
            </span>
          </button>
        </div>

        <div class="space-y-4 p-6">
          <div v-if="errorMessage"
            class="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300">{{ errorMessage }}</div>

          <PhoneLoginForm v-if="activeMethod === 'phone'" @close="handleFormClose" @error="handleFormError" />
          <EmailLoginForm v-else @close="handleFormClose" @error="handleFormError" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
