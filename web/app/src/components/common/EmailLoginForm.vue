<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { trackClick } from '@/composables/useTracking'

const authStore = useAuthStore()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'error', msg: string): void
}>()

type AuthView = 'code' | 'password' | 'register'
const emailView = ref<AuthView>('code')
const loading = ref(false)
const countdown = ref(0)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const emailForm = reactive({ email: '', code: '', password: '', registerPassword: '' })
const agreedToTerms = ref(false)

const emailViewOptions: { key: AuthView; label: string }[] = [
  { key: 'code', label: '快捷登录' },
  { key: 'password', label: '密码登录' },
  { key: 'register', label: '新人注册' },
]

function isValidEmail(email: string) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) }

function startCountdown(seconds = 60) {
  countdown.value = seconds
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0 && countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
  }, 1000)
}

async function sendEmailCode() {
  if (!isValidEmail(emailForm.email.trim())) { emit('error', '请输入有效的邮箱地址'); return }
  try {
    const purpose = emailView.value === 'register' ? 'register' as const : 'login' as const
    await authStore.sendEmailCode(emailForm.email.trim(), purpose)
    startCountdown()
    trackClick('login_email_send_code', '邮箱发送验证码')
  } catch (e: any) { emit('error', e?.response?.data?.detail || '发送失败，请重试') }
}

async function handleEmailCodeLogin() {
  if (!isValidEmail(emailForm.email.trim())) { emit('error', '请输入有效的邮箱地址'); return }
  if (emailForm.code.trim().length < 6) { emit('error', '请输入6位验证码'); return }
  loading.value = true
  try { await authStore.loginByEmail(emailForm.email.trim(), emailForm.code.trim()); emit('close') }
  catch (e: any) { emit('error', e?.response?.data?.detail || '登录失败') }
  finally { loading.value = false }
}

async function handleEmailPasswordLogin() {
  if (!isValidEmail(emailForm.email.trim())) { emit('error', '请输入有效的邮箱地址'); return }
  if (emailForm.password.trim().length < 6) { emit('error', '请输入密码（至少6位）'); return }
  loading.value = true
  try { await authStore.loginByEmailPassword(emailForm.email.trim(), emailForm.password.trim()); emit('close') }
  catch (e: any) { emit('error', e?.response?.data?.detail || '登录失败') }
  finally { loading.value = false }
}

async function handleEmailRegister() {
  if (!isValidEmail(emailForm.email.trim())) { emit('error', '请输入有效的邮箱地址'); return }
  if (emailForm.code.trim().length < 6) { emit('error', '请输入6位验证码'); return }
  if (emailForm.registerPassword && emailForm.registerPassword.length < 6) { emit('error', '密码至少6个字符'); return }
  loading.value = true
  try { await authStore.registerByEmail(emailForm.email.trim(), emailForm.code.trim(), emailForm.registerPassword); emit('close') }
  catch (e: any) { emit('error', e?.response?.data?.detail || '注册失败') }
  finally { loading.value = false }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex gap-2 rounded-lg bg-gray-100 p-1">
      <button v-for="option in emailViewOptions" :key="option.key" type="button"
        class="flex-1 rounded-md px-2 py-2.5 text-sm font-medium transition-colors"
        :class="emailView === option.key ? 'bg-white text-primary-600 shadow-sm dark:text-primary-300' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-100'"
        @click.prevent="emailView = option.key">{{ option.label }}</button>
    </div>

    <div>
      <label class="mb-1 block text-sm font-medium text-gray-700">邮箱地址</label>
      <input v-model="emailForm.email" type="email" placeholder="请输入邮箱"
        class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
    </div>

    <template v-if="emailView === 'code' || emailView === 'register'">
      <div>
        <label class="mb-1 block text-sm font-medium text-gray-700">验证码</label>
        <div class="flex gap-2">
          <input v-model="emailForm.code" type="text" maxlength="6" placeholder="6位验证码"
            class="flex-1 min-w-0 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
          <button type="button" :disabled="countdown > 0"
            class="shrink-0 rounded-lg bg-primary-50 px-3 py-2 text-sm font-medium text-primary-600 transition-colors hover:bg-primary-100 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-900/30 dark:text-primary-300"
            @click="sendEmailCode">{{ countdown > 0 ? `${countdown}s` : '获取验证码' }}</button>
        </div>
      </div>
      <div v-if="emailView === 'register'">
        <label class="mb-1 block text-sm font-medium text-gray-700">设置密码（可选）</label>
        <input v-model="emailForm.registerPassword" type="password" placeholder="至少6位，留空则仅验证码登录"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
      </div>
    </template>

    <div v-else>
      <label class="mb-1 block text-sm font-medium text-gray-700">密码</label>
      <input v-model="emailForm.password" type="password" placeholder="请输入密码"
        class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
    </div>

    <button v-if="emailView === 'code'" type="button"
      class="w-full rounded-lg bg-primary-600 py-2.5 font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading || !agreedToTerms" @click="handleEmailCodeLogin">{{ loading ? '登录中...' : '登录' }}</button>
    <button v-else-if="emailView === 'password'" type="button"
      class="w-full rounded-lg bg-primary-600 py-2.5 font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading || !agreedToTerms" @click="handleEmailPasswordLogin">{{ loading ? '登录中...' : '登录' }}</button>
    <button v-else type="button"
      class="w-full rounded-lg bg-primary-600 py-2.5 font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading || !agreedToTerms" @click="handleEmailRegister">{{ loading ? '注册中...' : '注册并登录' }}</button>

    <label class="flex items-start gap-2 cursor-pointer min-h-[44px] pt-1">
      <input v-model="agreedToTerms" type="checkbox" class="mt-0.5 w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
      <span class="text-xs text-gray-500  leading-relaxed">
        已阅读并同意
        <a href="/privacy" target="_blank" class="text-primary-600 dark:text-primary-400 hover:underline" @click.stop>隐私政策</a>
        和
        <a href="/terms" target="_blank" class="text-primary-600 dark:text-primary-400 hover:underline" @click.stop>服务条款</a>
      </span>
    </label>

    <p class="text-center text-xs text-gray-400 ">
      <template v-if="emailView === 'register'">邮箱注册需设置密码</template>
      <template v-else-if="emailView === 'password'">已设置邮箱密码可直接登录</template>
      <template v-else>新邮箱将自动注册账号</template>
    </p>
  </div>
</template>
