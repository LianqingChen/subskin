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
  wifiUploadOnly: 'subskin_wifi_upload_only',
  autoCompressPhotos: 'subskin_auto_compress_photos',
} as const

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>()

const wifiUploadOnly = createStoredBoolean(STORAGE_KEYS.wifiUploadOnly, false)
const autoCompressPhotos = createStoredBoolean(STORAGE_KEYS.autoCompressPhotos, true)
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center" @click.self="emit('update:modelValue', false)">
      <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4 max-h-[90dvh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-semibold text-gray-900"><i class="ri-camera-line"></i> 照片权限</h2>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="emit('update:modelValue', false)">&times;</button>
        </div>
        <div class="p-6 space-y-4">
          <div class="flex items-start justify-between gap-4">
            <div><h3 class="text-sm font-medium text-gray-900">仅Wi-Fi上传图片</h3><p class="text-xs text-gray-500  mt-1">使用移动数据时不自动上传图片</p></div>
            <button type="button" class="setting-switch" :class="wifiUploadOnly.value ? 'setting-switch-on' : 'setting-switch-off'" @click="wifiUploadOnly.value = !wifiUploadOnly.value"><span class="setting-switch-thumb" :class="wifiUploadOnly.value ? 'translate-x-7' : 'translate-x-0'" /></button>
          </div>
          <div class="flex items-start justify-between gap-4">
            <div><h3 class="text-sm font-medium text-gray-900">照片自动压缩</h3><p class="text-xs text-gray-500  mt-1">上传前自动压缩图片以节省流量</p></div>
            <button type="button" class="setting-switch" :class="autoCompressPhotos.value ? 'setting-switch-on' : 'setting-switch-off'" @click="autoCompressPhotos.value = !autoCompressPhotos.value"><span class="setting-switch-thumb" :class="autoCompressPhotos.value ? 'translate-x-7' : 'translate-x-0'" /></button>
          </div>
          <div class="rounded-xl bg-primary-50 dark:bg-primary-900/20 p-4 text-sm text-gray-600 leading-6">你的照片仅存储在你的账户中，不会公开显示（除非你主动分享）</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
