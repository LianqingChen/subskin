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
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="emit('close')">
      <div class="w-full max-w-sm overflow-hidden rounded-2xl bg-white shadow-xl">
        <div class="flex items-center justify-between px-6 pt-5 pb-3">
          <h2 class="text-lg font-semibold text-gray-900">{{ activeMethod === 'phone' ? '手机登录 / 注册' : '邮箱登录 / 注册' }}</h2>
          <button class="rounded-full p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" @click="emit('close')">
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
          </button>
        </div>

        <div class="flex border-b border-gray-200 dark:border-gray-700">
          <button v-for="tab in tabs" :key="tab.key" type="button"
            class="flex-1 border-b-2 px-2 py-3 text-sm font-medium transition-colors"
            :class="activeMethod === tab.key ? 'border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-300' : 'border-transparent text-gray-500 hover:text-gray-700  dark:hover:text-gray-200'"
            @click.prevent="activeMethod = tab.key; errorMessage = ''">
            <span class="inline-flex items-center gap-1.5">
              <svg v-if="tab.key === 'phone'" class="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.58 2.81.7A2 2 0 0 1 22 16.92z" /></svg>
              <svg v-else class="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><polyline points="2,4 12,13 22,4" /></svg>
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

        <div class="border-t border-gray-100 px-6 pb-4 pt-2 dark:border-gray-700">
          <p class="text-center text-xs text-gray-400 ">
            登录即表示同意
            <router-link to="/terms" class="text-primary-600 hover:underline dark:text-primary-300" @click="emit('close')">服务条款</router-link>
            和
            <router-link to="/privacy" class="text-primary-600 hover:underline dark:text-primary-300" @click="emit('close')">隐私政策</router-link>
          </p>
        </div>
      </div>
    </div>
  </Teleport>
</template>
