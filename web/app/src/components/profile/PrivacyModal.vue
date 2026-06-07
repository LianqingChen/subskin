<script setup lang="ts">
import { ref, watch } from 'vue'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { usePrivacyStore } from '@/stores/privacy'

const STORAGE_KEYS = {
  defaultPostPrivate: 'subskin_default_post_private',
  shareTracking: 'subskin_share_tracking',
} as const

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>()

const authStore = useAuthStore()
const privacyStore = usePrivacyStore()
const defaultPostPrivate = ref(false)
const shareTracking = ref(false)
const phoneDiscoverable = ref(true)

function readDefaults() {
  defaultPostPrivate.value = localStorage.getItem(STORAGE_KEYS.defaultPostPrivate) === 'true'
  shareTracking.value = localStorage.getItem(STORAGE_KEYS.shareTracking) === 'true'
  phoneDiscoverable.value = privacyStore.privacyMode
}

watch(() => props.modelValue, async (open) => {
  if (!open) return
  readDefaults()
  if (authStore.isLoggedIn) {
    try {
      const res = await apiClient.get('/user/phone-discoverable')
      phoneDiscoverable.value = res.data.phone_discoverable
    } catch { /* keep default */ }
  }
})

watch(() => privacyStore.privacyMode, () => {
  if (props.modelValue) readDefaults()
})

function toggleDefaultPostPrivate() {
  defaultPostPrivate.value = !defaultPostPrivate.value
  localStorage.setItem(STORAGE_KEYS.defaultPostPrivate, String(defaultPostPrivate.value))
}

function toggleShareTracking() {
  shareTracking.value = !shareTracking.value
  localStorage.setItem(STORAGE_KEYS.shareTracking, String(shareTracking.value))
}

async function togglePhoneDiscoverable() {
  const newVal = !phoneDiscoverable.value
  if (authStore.isLoggedIn) {
    try {
      await apiClient.put('/user/phone-discoverable', { phone_discoverable: newVal })
      phoneDiscoverable.value = newVal
    } catch { /* revert on failure */ }
  } else {
    phoneDiscoverable.value = newVal
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center" @click.self="emit('update:modelValue', false)">
      <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4 max-h-[90dvh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-semibold text-gray-900"><i class="ri-lock-line"></i> 隐私设置</h2>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="emit('update:modelValue', false)">&times;</button>
        </div>
        <div class="p-6 space-y-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <h3 class="text-sm font-medium text-gray-900">允许通过手机号找到我</h3>
              <p class="text-xs text-gray-500  mt-1">关闭后，他人无法通过通讯录匹配到你的手机号</p>
            </div>
            <button type="button" class="setting-switch"
              :class="phoneDiscoverable ? 'setting-switch-on' : 'setting-switch-off'"
              @click="togglePhoneDiscoverable">
              <span class="setting-switch-thumb" :class="phoneDiscoverable ? 'translate-x-7' : 'translate-x-0'" />
            </button>
          </div>
          <div class="flex items-start justify-between gap-4">
            <div>
              <h3 class="text-sm font-medium text-gray-900">社区帖子默认私密</h3>
              <p class="text-xs text-gray-500  mt-1">发布日记时默认设为仅自己可见</p>
            </div>
            <button type="button" class="setting-switch"
              :class="defaultPostPrivate ? 'setting-switch-on' : 'setting-switch-off'"
              @click="toggleDefaultPostPrivate">
              <span class="setting-switch-thumb" :class="defaultPostPrivate ? 'translate-x-7' : 'translate-x-0'" />
            </button>
          </div>
          <div class="flex items-start justify-between gap-4">
            <div>
              <h3 class="text-sm font-medium text-gray-900">允许他人查看我的追踪数据</h3>
              <p class="text-xs text-gray-500  mt-1">其他用户可以查看你的VASI评估趋势</p>
            </div>
            <button type="button" class="setting-switch"
              :class="shareTracking ? 'setting-switch-on' : 'setting-switch-off'"
              @click="toggleShareTracking">
              <span class="setting-switch-thumb" :class="shareTracking ? 'translate-x-7' : 'translate-x-0'" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
