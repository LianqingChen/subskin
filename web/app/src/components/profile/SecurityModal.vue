<script setup lang="ts">
/**
 * SecurityModal — 账号安全弹窗（绑定手机/邮箱、设置/重置密码）
 * 从 ProfilePage.vue 拆分而来
 */
import { isAxiosError } from 'axios'
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { type CredentialInfo } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  visible: boolean
  mode: 'bind-phone' | 'bind-email' | 'set-password' | 'reset-password'
  credentials: CredentialInfo[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'updated'): void
}>()

const authStore = useAuthStore()
const toast = useToast()

const isSaving = ref(false)
const errorMessage = ref('')
const countdown = ref(0)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const form = reactive({
  phone: '',
  email: '',
  code: '',
  password: '',
  confirmPassword: '',
  resetMethod: 'phone' as 'phone' | 'email',
})

const resettableCredentials = computed(() =>
  props.credentials.filter(
    (item): item is CredentialInfo & { cred_type: 'phone' | 'email' } =>
      item.cred_type === 'phone' || item.cred_type === 'email',
  ),
)

const selectedResetCredential = computed(
  () =>
    resettableCredentials.value.find((item) => item.cred_type === form.resetMethod) ??
    resettableCredentials.value[0] ??
    null,
)

const hasPasswordCredential = computed(() =>
  props.credentials.some((item) => item.cred_type === 'password'),
)

watch(
  () => props.visible,
  (visible) => {
    if (visible) resetForm()
  },
)

watch(resettableCredentials, (items) => {
  if (!items.length) return
  if (!items.some((item) => item.cred_type === form.resetMethod)) {
    form.resetMethod = items[0].cred_type
  }
}, { immediate: true })

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})

function getErrorDetail(error: unknown, fallback = '操作失败，请稍后重试') {
  if (isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail || fallback
  }
  return fallback
}

function resetForm() {
  errorMessage.value = ''
  form.phone = ''
  form.email = ''
  form.code = ''
  form.password = ''
  form.confirmPassword = ''
  form.resetMethod = resettableCredentials.value[0]?.cred_type ?? 'phone'
}

function startCountdown(seconds = 60) {
  countdown.value = seconds
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0 && countdownTimer) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

function maskPhone(phone: string) {
  return phone.replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2')
}

function maskEmail(email: string) {
  const atIndex = email.indexOf('@')
  if (atIndex < 0) return email
  const local = email.slice(0, atIndex)
  const domain = email.slice(atIndex + 1)
  if (local.length <= 2) return `***@${domain}`
  return `${local.slice(0, 2)}***@${domain}`
}

function getCredentialDisplay(credential: CredentialInfo) {
  if (credential.cred_type === 'phone') return maskPhone(credential.cred_id)
  if (credential.cred_type === 'email') return maskEmail(credential.cred_id)
  return credential.cred_id
}

async function sendCode() {
  errorMessage.value = ''
  try {
    if (props.mode === 'bind-phone') {
      if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
        errorMessage.value = '请输入有效的手机号'
        return
      }
      await authStore.sendSmsCode(form.phone.trim())
    } else if (props.mode === 'bind-email') {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
        errorMessage.value = '请输入有效的邮箱地址'
        return
      }
      await authStore.sendEmailCode(form.email.trim(), 'bind')
    } else if (props.mode === 'reset-password') {
      if (!selectedResetCredential.value) {
        errorMessage.value = '请先绑定手机号或邮箱'
        return
      }
      if (selectedResetCredential.value.cred_type === 'phone') {
        await authStore.sendSmsCode(selectedResetCredential.value.cred_id)
      } else {
        await authStore.sendEmailCode(selectedResetCredential.value.cred_id, 'reset')
      }
    }
    startCountdown()
    toast.success('验证码已发送，请注意查收')
  } catch (error) {
    errorMessage.value = getErrorDetail(error, '验证码发送失败，请稍后重试')
  }
}

async function submit() {
  errorMessage.value = ''

  if (props.mode === 'set-password' || props.mode === 'reset-password') {
    if (form.password.trim().length < 6) {
      errorMessage.value = '密码至少6个字符'
      return
    }
    if (form.password !== form.confirmPassword) {
      errorMessage.value = '两次输入的密码不一致'
      return
    }
  }

  isSaving.value = true
  try {
    if (props.mode === 'bind-phone') {
      if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
        errorMessage.value = '请输入有效的手机号'
        return
      }
      if (form.code.trim().length < 6) {
        errorMessage.value = '请输入6位验证码'
        return
      }
      await authStore.bindPhone(form.phone.trim(), form.code.trim())
      toast.success('手机号绑定成功')
    } else if (props.mode === 'bind-email') {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
        errorMessage.value = '请输入有效的邮箱地址'
        return
      }
      if (form.code.trim().length < 6) {
        errorMessage.value = '请输入6位验证码'
        return
      }
      await authStore.bindEmail(form.email.trim(), form.code.trim())
      toast.success('邮箱绑定成功')
    } else if (props.mode === 'set-password') {
      await authStore.setPassword(form.password.trim())
      toast.success(hasPasswordCredential.value ? '密码已更新' : '密码设置成功')
    } else {
      if (!selectedResetCredential.value) {
        errorMessage.value = '请先绑定手机号或邮箱'
        return
      }
      if (form.code.trim().length < 6) {
        errorMessage.value = '请输入6位验证码'
        return
      }
      await authStore.resetPassword(
        selectedResetCredential.value.cred_id,
        selectedResetCredential.value.cred_type,
        form.code.trim(),
        form.password.trim(),
      )
      toast.success('密码已重置')
    }
    emit('updated')
    emit('close')
  } catch (error) {
    errorMessage.value = getErrorDetail(error, '操作失败，请稍后重试')
  } finally {
    isSaving.value = false
  }
}

function close() {
  if (isSaving.value) return
  emit('close')
}

const title = computed(() => {
  switch (props.mode) {
    case 'bind-phone': return '绑定手机号'
    case 'bind-email': return '绑定邮箱'
    case 'set-password': return '设置密码'
    case 'reset-password': return '修改密码'
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center"
      @click.self="close"
    >
      <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4 max-h-[90dvh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-semibold text-gray-900">{{ title }}</h2>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="close">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div
            v-if="errorMessage"
            class="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
          >
            {{ errorMessage }}
          </div>

          <template v-if="mode === 'bind-phone'">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">手机号</label>
              <input
                v-model="form.phone"
                type="tel"
                maxlength="11"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
                placeholder="请输入手机号"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
              <div class="flex gap-3">
                <input
                  v-model="form.code"
                  type="text"
                  maxlength="6"
                  inputmode="numeric"
                  class="flex-1 min-h-[44px] px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
                  placeholder="6位验证码"
                />
                <button
                  type="button"
                  class="min-h-[44px] rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="countdown > 0 || isSaving"
                  @click="sendCode"
                >
                  {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
                </button>
              </div>
            </div>
          </template>

          <template v-else-if="mode === 'bind-email'">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
              <input
                v-model="form.email"
                type="email"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
                placeholder="请输入邮箱地址"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
              <div class="flex gap-3">
                <input
                  v-model="form.code"
                  type="text"
                  maxlength="6"
                  inputmode="numeric"
                  class="flex-1 min-h-[44px] px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
                  placeholder="6位验证码"
                />
                <button
                  type="button"
                  class="min-h-[44px] rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="countdown > 0 || isSaving"
                  @click="sendCode"
                >
                  {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
                </button>
              </div>
            </div>
          </template>

          <template v-else>
            <div v-if="mode === 'reset-password'" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">找回方式</label>
                <div class="flex gap-2 rounded-lg bg-gray-100 p-1">
                  <button
                    v-for="credential in resettableCredentials"
                    :key="credential.id"
                    type="button"
                    class="flex-1 rounded-md px-3 py-2.5 text-sm font-medium transition-colors"
                    :class="form.resetMethod === credential.cred_type
                      ? 'bg-white text-primary-600 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'"
                    @click="form.resetMethod = credential.cred_type"
                  >
                    {{ credential.cred_type === 'phone' ? '手机号' : '邮箱' }}
                  </button>
                </div>
              </div>

              <div class="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600">
                <p>验证码将发送至：{{ selectedResetCredential ? getCredentialDisplay(selectedResetCredential) : '暂无可用凭证' }}</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
                <div class="flex gap-3">
                  <input
                    v-model="form.code"
                    type="text"
                    maxlength="6"
                    inputmode="numeric"
                    class="flex-1 min-h-[44px] px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
                    placeholder="6位验证码"
                  />
                  <button
                    type="button"
                    class="min-h-[44px] rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="countdown > 0 || isSaving || !selectedResetCredential"
                    @click="sendCode"
                  >
                    {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
                  </button>
                </div>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{{ mode === 'reset-password' ? '新密码' : '密码' }}</label>
              <input
                v-model="form.password"
                type="password"
                maxlength="128"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
                placeholder="至少6位字符"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
              <input
                v-model="form.confirmPassword"
                type="password"
                maxlength="128"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white text-gray-900"
                placeholder="请再次输入密码"
              />
            </div>
          </template>

          <div class="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              class="btn-primary min-h-[44px]"
              :disabled="isSaving || (mode === 'reset-password' && resettableCredentials.length === 0)"
              @click="submit"
            >
              {{ isSaving ? '提交中...' : '确认' }}
            </button>
            <button
              type="button"
              class="btn-ghost min-h-[44px]"
              :disabled="isSaving"
              @click="close"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
