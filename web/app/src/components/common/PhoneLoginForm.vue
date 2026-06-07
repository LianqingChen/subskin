<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { trackClick } from '@/composables/useTracking'
import { usePhoneHistory } from '@/composables/usePhoneHistory'

const authStore = useAuthStore()
const { phoneHistory, add: addPhoneToHistory } = usePhoneHistory()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'error', msg: string): void
}>()

type AuthView = 'code' | 'password' | 'register'
const phoneView = ref<AuthView>('code')
const loading = ref(false)
const countdown = ref(0)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const phoneForm = reactive({ phone: '', code: '', password: '', registerPassword: '' })
const agreedToTerms = ref(false)

const phoneViewOptions: { key: AuthView; label: string }[] = [
  { key: 'code', label: '快捷登录' },
  { key: 'password', label: '密码登录' },
  { key: 'register', label: '新人注册' },
]

function isValidPhone(phone: string) { return /^1[3-9]\d{9}$/.test(phone) }

function startCountdown(seconds = 60) {
  countdown.value = seconds
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0 && countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
  }, 1000)
}

function selectHistoryPhone(phone: string) {
  phoneForm.phone = phone
}

async function sendPhoneCode() {
  if (!isValidPhone(phoneForm.phone.trim())) { emit('error', '请输入有效的手机号'); return }
  try {
    await authStore.sendSmsCode(phoneForm.phone.trim())
    startCountdown()
    trackClick('login_phone_send_code', '手机号发送验证码')
  } catch (e: any) { emit('error', e?.response?.data?.detail || '发送失败，请重试') }
}

async function handlePhoneCodeLogin() {
  if (!isValidPhone(phoneForm.phone.trim())) { emit('error', '请输入有效的手机号'); return }
  if (phoneForm.code.trim().length < 6) { emit('error', '请输入6位验证码'); return }
  loading.value = true
  try { await authStore.loginByPhone(phoneForm.phone.trim(), phoneForm.code.trim()); addPhoneToHistory(phoneForm.phone.trim()); emit('close') }
  catch (e: any) { emit('error', e?.response?.data?.detail || '登录失败') }
  finally { loading.value = false }
}

async function handlePhonePasswordLogin() {
  if (!isValidPhone(phoneForm.phone.trim())) { emit('error', '请输入有效的手机号'); return }
  if (phoneForm.password.trim().length < 6) { emit('error', '请输入密码（至少6位）'); return }
  loading.value = true
  try { await authStore.loginByPhonePassword(phoneForm.phone.trim(), phoneForm.password.trim()); addPhoneToHistory(phoneForm.phone.trim()); emit('close') }
  catch (e: any) { emit('error', e?.response?.data?.detail || '登录失败') }
  finally { loading.value = false }
}

async function handlePhoneRegister() {
  if (!isValidPhone(phoneForm.phone.trim())) { emit('error', '请输入有效的手机号'); return }
  if (phoneForm.code.trim().length < 6) { emit('error', '请输入6位验证码'); return }
  if (phoneForm.registerPassword && phoneForm.registerPassword.length < 6) { emit('error', '密码至少6个字符'); return }
  loading.value = true
  try { await authStore.registerByPhone(phoneForm.phone.trim(), phoneForm.code.trim(), phoneForm.registerPassword || undefined); addPhoneToHistory(phoneForm.phone.trim()); emit('close') }
  catch (e: any) { emit('error', e?.response?.data?.detail || '注册失败') }
  finally { loading.value = false }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex gap-2 rounded-lg bg-gray-100 p-1">
      <button v-for="option in phoneViewOptions" :key="option.key" type="button"
        class="flex-1 rounded-md px-2 py-2.5 text-sm font-medium transition-colors"
        :class="phoneView === option.key ? 'bg-white text-primary-600 shadow-sm dark:text-primary-300' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-100'"
        @click.prevent="phoneView = option.key">{{ option.label }}</button>
    </div>

    <div>
      <label class="mb-1 block text-sm font-medium text-gray-700">手机号码</label>
      <input v-model="phoneForm.phone" type="tel" name="tel" autocomplete="tel-national" maxlength="11" placeholder="请输入手机号"
        class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
      <div v-if="phoneHistory.length > 0 && !phoneForm.phone" class="mt-2 flex flex-wrap items-center gap-1.5">
        <span class="text-xs text-gray-400 ">最近使用：</span>
        <button v-for="ph in phoneHistory" :key="ph" type="button"
          class="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600 transition-colors hover:bg-primary-50 hover:text-primary-600 dark:hover:bg-primary-900/30 dark:hover:text-primary-300"
          @click.prevent="selectHistoryPhone(ph)">
          {{ ph.slice(0, 3) }}****{{ ph.slice(-4) }}
        </button>
      </div>
      <p v-else-if="phoneHistory.length === 0 && !phoneForm.phone" class="mt-1 text-xs text-gray-400 ">点击输入框可选择浏览器保存的本机号码</p>
    </div>

    <template v-if="phoneView === 'code' || phoneView === 'register'">
      <div>
        <label class="mb-1 block text-sm font-medium text-gray-700">验证码</label>
        <div class="flex gap-2">
          <input v-model="phoneForm.code" type="text" maxlength="6" placeholder="6位验证码"
            class="flex-1 min-w-0 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
          <button type="button" :disabled="countdown > 0"
            class="shrink-0 rounded-lg bg-primary-50 px-3 py-2 text-sm font-medium text-primary-600 transition-colors hover:bg-primary-100 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-900/30 dark:text-primary-300"
            @click="sendPhoneCode">{{ countdown > 0 ? `${countdown}s` : '获取验证码' }}</button>
        </div>
      </div>
      <div v-if="phoneView === 'register'">
        <label class="mb-1 block text-sm font-medium text-gray-700">设置密码（可选）</label>
        <input v-model="phoneForm.registerPassword" type="password" placeholder="至少6位，留空则仅验证码登录"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
      </div>
    </template>

    <div v-else>
      <label class="mb-1 block text-sm font-medium text-gray-700">密码</label>
      <input v-model="phoneForm.password" type="password" placeholder="请输入密码"
        class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600" />
    </div>

    <button v-if="phoneView === 'code'" type="button"
      class="w-full rounded-lg bg-primary-600 py-2.5 font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading || !agreedToTerms" @click="handlePhoneCodeLogin">{{ loading ? '登录中...' : '登录' }}</button>
    <button v-else-if="phoneView === 'password'" type="button"
      class="w-full rounded-lg bg-primary-600 py-2.5 font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading || !agreedToTerms" @click="handlePhonePasswordLogin">{{ loading ? '登录中...' : '登录' }}</button>
    <button v-else type="button"
      class="w-full rounded-lg bg-primary-600 py-2.5 font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading || !agreedToTerms" @click="handlePhoneRegister">{{ loading ? '注册中...' : '注册并登录' }}</button>

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
      <template v-if="phoneView === 'register'">设置密码后可使用密码登录</template>
      <template v-else-if="phoneView === 'password'">已设置密码时可直接登录</template>
      <template v-else>新手机号将自动注册账号</template>
    </p>
  </div>
</template>
