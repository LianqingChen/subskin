<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { detectPii } from '@/utils/piiCheck'

/**
 * 隐私与数据面板：AI 数据授权开关 + 账户注销（被遗忘权）。
 * 2026-08-30 隐私加固新增。
 */
const props = defineProps<{ active: boolean }>()

const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()

const aiData = ref(false)
const medicalPhoto = ref(false)
const loading = ref(false)

// ── 注销状态 ──
const showDelete = ref(false)
const deleteConfirm = ref('')
const deletePassword = ref('')
const deleting = ref(false)

async function loadStatus() {
  if (!authStore.isLoggedIn) return
  loading.value = true
  try {
    const res = await apiClient.get('/consent/status')
    aiData.value = Boolean(res.data.ai_data)
    medicalPhoto.value = Boolean(res.data.medical_photo)
  } catch {
    /* 保持默认关闭 */
  } finally {
    loading.value = false
  }
}

watch(
  () => props.active,
  (open) => {
    if (open) loadStatus()
  },
)

async function toggleConsent(type: 'ai_data' | 'medical_photo', current: boolean) {
  const next = !current
  try {
    if (next) {
      await apiClient.post('/consent/record', {
        consent_type: type,
        version: '1.0',
        platform: 'web',
        source: 'settings',
      })
    } else {
      await apiClient.post('/consent/revoke', { consent_type: type })
    }
    if (type === 'ai_data') aiData.value = next
    else medicalPhoto.value = next
    toast.show(next ? '已开启授权' : '已关闭授权', 'success')
  } catch {
    toast.show('操作失败，请稍后重试', 'error')
  }
}

async function handleDeleteAccount() {
  if (deleteConfirm.value !== 'DELETE') {
    toast.show('请输入 DELETE 以确认注销', 'warning')
    return
  }
  if (!deletePassword.value) {
    toast.show('请输入登录密码验证身份', 'warning')
    return
  }
  if (detectPii(deletePassword.value).length) {
    toast.show('密码格式有误', 'warning')
    return
  }
  deleting.value = true
  try {
    await apiClient.post('/user/delete-account', {
      confirm: 'DELETE',
      password: deletePassword.value,
    })
    toast.show('账户已注销，个人数据已删除', 'success')
    authStore.logout()
    router.push('/')
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    toast.show(detail || '注销失败，请稍后重试', 'error')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <section aria-label="数据授权与账户">
    <div class="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
        <i class="ri-shield-keyhole-line" aria-hidden="true"></i> 数据授权
      </h3>

      <div class="flex items-start justify-between gap-4">
        <div>
          <h4 class="text-sm font-medium text-gray-900 dark:text-gray-100">AI 使用我的健康记录</h4>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            开启后，智能问答可参考你的病情档案、日记摘要等提供个性化回答；关闭后仅通用问答，数据不外送
          </p>
        </div>
        <button
          type="button"
          class="setting-switch"
          :class="aiData ? 'setting-switch-on' : 'setting-switch-off'"
          :aria-label="'AI 使用我的健康记录' + (aiData ? '，已开启' : '，已关闭')"
          @click="toggleConsent('ai_data', aiData)"
        >
          <span
            class="setting-switch-thumb"
            :class="aiData ? 'translate-x-7' : 'translate-x-0'"
          />
        </button>
      </div>

      <div class="flex items-start justify-between gap-4 mt-4">
        <div>
          <h4 class="text-sm font-medium text-gray-900 dark:text-gray-100">AI 处理我的体检报告</h4>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            开启后才能使用体检报告智能解读功能；关闭后报告仅自己可见、不外送
          </p>
        </div>
        <button
          type="button"
          class="setting-switch"
          :class="medicalPhoto ? 'setting-switch-on' : 'setting-switch-off'"
          :aria-label="'AI 处理我的体检报告' + (medicalPhoto ? '，已开启' : '，已关闭')"
          @click="toggleConsent('medical_photo', medicalPhoto)"
        >
          <span
            class="setting-switch-thumb"
            :class="medicalPhoto ? 'translate-x-7' : 'translate-x-0'"
          />
        </button>
      </div>
    </div>

    <div class="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
        <i class="ri-delete-bin-line" aria-hidden="true"></i> 注销账户
      </h3>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        注销后将删除你的全部个人数据：帖子与图片、日记、测评记录、体检报告、病情档案等，
        <strong>不可恢复</strong>。
      </p>
      <button
        v-if="!showDelete"
        class="mt-3 text-sm text-red-600 dark:text-red-400 hover:underline"
        @click="showDelete = true"
      >
        我要注销账户 →
      </button>

      <div v-else class="mt-3 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 space-y-3">
        <label class="block text-sm text-red-800 dark:text-red-300">
          请输入 <code class="font-mono font-bold">DELETE</code> 确认：
          <input
            v-model="deleteConfirm"
            type="text"
            class="mt-1 w-full rounded-md border border-red-300 dark:border-red-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm min-w-0"
            placeholder="DELETE"
          />
        </label>
        <label class="block text-sm text-red-800 dark:text-red-300">
          登录密码（验证身份）：
          <input
            v-model="deletePassword"
            type="password"
            autocomplete="current-password"
            class="mt-1 w-full rounded-md border border-red-300 dark:border-red-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm min-w-0"
            placeholder="••••••••"
          />
        </label>
        <p class="text-xs text-red-600 dark:text-red-400">
          使用手机验证码登录且未设置密码的用户，请先在「账号与安全」设置密码后再注销。
        </p>
        <div class="flex justify-end gap-2">
          <button class="btn-ghost px-4 py-2 text-sm" @click="showDelete = false">取消</button>
          <button
            class="px-4 py-2 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
            :disabled="deleting"
            @click="handleDeleteAccount"
          >
            {{ deleting ? '注销中...' : '确认注销' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
