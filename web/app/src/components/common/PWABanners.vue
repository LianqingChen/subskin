<script setup lang="ts">
import { ref } from 'vue'
import { usePWA } from '@/composables/usePWA'

const { isInstallable, isOffline, showUpdateBanner, installApp, dismissInstall, dismissInstallLong, dismissUpdate, updateApp } = usePWA()

const isUpdating = ref(false)
const isStaging = __APP_ENV__ === 'staging'

async function handleUpdate() {
  if (isUpdating.value) return
  isUpdating.value = true
  await updateApp()
}
</script>

<template>
  <!-- Update available banner -->
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="-translate-y-full opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="-translate-y-full opacity-0"
  >
    <div
      v-if="showUpdateBanner"
      :class="['fixed top-0 left-0 right-0 z-[60] text-white', isStaging ? 'bg-slate-700' : 'bg-primary-600']"
    >
      <div class="max-w-6xl mx-auto px-4 py-2 flex items-center justify-between">
        <span class="text-sm whitespace-nowrap">
          <i class="ri-refresh-line"></i>
          {{ isStaging ? '测试环境有新版本可用' : '有新版本可用' }}
        </span>
        <div class="flex items-center gap-3">
          <button type="button"
            :class="['text-xs font-semibold py-1 px-3 rounded-lg transition-colors leading-tight text-center disabled:opacity-60', isStaging ? 'bg-white text-slate-700 hover:bg-slate-50' : 'bg-white text-primary-600 hover:bg-primary-50']"
            :disabled="isUpdating"
            @click="handleUpdate"
          >
            <span v-if="isUpdating" class="inline-flex items-center gap-1">
              <svg class="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              更新中
            </span>
            <span v-else>更新</span>
          </button>
          <button type="button"
            v-if="!isUpdating"
            class="text-white/70 hover:text-white text-sm transition-colors"
            @click="dismissUpdate"
          >
            稍后
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- Offline banner -->
  <div
    v-if="isOffline"
    :class="showUpdateBanner ? 'top-10' : 'top-0'"
    class="fixed left-0 right-0 z-50 bg-amber-500 text-white text-center text-sm py-2 px-4 transition-all duration-300"
  >
    <i class="ri-signal-wifi-off-line"></i> 网络连接已断开，部分功能可能不可用
  </div>

  <!-- Install prompt banner -->
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="translate-y-full opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="translate-y-full opacity-0"
  >
    <div
      v-if="isInstallable"
      class="fixed bottom-20 md:bottom-6 left-4 right-4 md:left-auto md:right-6 md:w-80 z-50 bg-white rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 p-4"
    >
      <div class="flex items-start gap-3">
        <img src="/subskin_logo.png?v=b4e9d1" alt="SubSkin" class="w-12 h-12 rounded-xl flex-shrink-0" />
        <div class="flex-1 min-w-0">
          <h3 class="font-semibold text-gray-900 text-sm">添加到桌面，体验更流畅</h3>
          <p class="text-xs text-gray-500  mt-0.5">像原生应用一样使用，随时快速打开</p>
          <div class="flex items-center gap-2 mt-3">
            <button type="button"
              class="flex-1 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors"
              @click="installApp"
            >
              添加到桌面
            </button>
            <button type="button"
              class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm px-3 py-2 transition-colors"
              @click="dismissInstall"
            >
              稍后
            </button>
          </div>
        </div>
        <button type="button"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 p-1 -mt-1 -mr-1"
          aria-label="关闭"
          title="关闭"
          @click="dismissInstallLong"
        >
          ✕
        </button>
      </div>
    </div>
  </Transition>
</template>