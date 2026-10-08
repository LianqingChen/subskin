<script setup lang="ts">
import { computed, ref } from 'vue'
import { usePWA } from '@/composables/usePWA'

const { isInstallable, isOffline, showUpdateBanner, showInstallGuide, closeInstallGuide, installApp, dismissInstall, dismissInstallLong, dismissUpdate, updateApp } = usePWA()

const isUpdating = ref(false)
const isStaging = __APP_ENV__ === 'staging'

// 平台识别：给出对应的安装指引
const platform = computed<'ios' | 'android' | 'desktop'>(() => {
  const ua = navigator.userAgent
  // iPadOS Safari 默认伪装成 Mac UA，用触控点数区分
  if (/iphone|ipad|ipod/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return 'ios'
  if (/android/i.test(ua)) return 'android'
  return 'desktop'
})

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
      :class="['fixed top-0 left-0 right-0 z-[60] text-white md:top-auto md:bottom-6 md:left-auto md:right-6 md:rounded-xl md:shadow-lg', isStaging ? 'bg-slate-700' : 'bg-primary-600']"
    >
      <div class="w-full max-w-6xl mx-auto px-4 py-2 flex items-center justify-between gap-4 md:py-2.5">
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
    class="app-fixed-x fixed z-50 bg-amber-500 text-white text-center text-sm py-2 px-4 transition-all duration-300"
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
      v-if="isInstallable && !showUpdateBanner && platform !== 'desktop'"
      class="fixed bottom-20 md:bottom-6 left-4 right-4 md:left-auto md:right-6 md:w-80 z-50 bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 p-4"
    >
      <div class="flex items-start gap-3">
        <img src="/subskin_logo.png?v=b4e9d1" alt="SubSkin" class="w-12 h-12 rounded-xl flex-shrink-0" />
        <div class="flex-1 min-w-0">
          <h3 class="font-semibold text-gray-900 dark:text-gray-100 text-sm">添加到桌面，体验更流畅</h3>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">像原生应用一样使用，随时快速打开</p>
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
          class="text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 p-2 -mt-1 -mr-1 min-w-[36px] min-h-[36px]"
          aria-label="关闭"
          title="关闭"
          @click="dismissInstallLong"
        >
          <i class="ri-close-line text-lg"></i>
        </button>
      </div>
    </div>
  </Transition>

  <!-- 安装指引弹层（浏览器未提供原生安装入口时展示） -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="showInstallGuide"
        class="fixed inset-0 z-[120] flex items-end sm:items-center justify-center bg-black/50"
        @click.self="closeInstallGuide"
      >
        <div class="w-full sm:max-w-md bg-white dark:bg-gray-800 rounded-t-2xl sm:rounded-2xl p-5 pb-6 safe-bottom shadow-xl">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
              <i class="ri-smartphone-line text-primary-600 dark:text-primary-400"></i> 安装 SubSkin 到手机
            </h3>
            <button
              type="button"
              class="w-9 h-9 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
              aria-label="关闭"
              @click="closeInstallGuide"
            >
              <i class="ri-close-line text-lg"></i>
            </button>
          </div>

          <!-- iOS Safari -->
          <ol v-if="platform === 'ios'" class="install-guide-list">
            <li>点浏览器底部中间「分享」按钮</li>
            <li>向下滑动，选择「<strong>添加到主屏幕</strong>」</li>
            <li>点右上角「添加」，即可从主屏幕图标打开</li>
          </ol>

          <!-- Android -->
          <ol v-else-if="platform === 'android'" class="install-guide-list">
            <li>点浏览器右上角「<strong>⋮</strong>」菜单</li>
            <li>选择「<strong>安装应用</strong>」或「添加到主屏幕」</li>
            <li>按提示安装后，即可从主屏幕图标打开</li>
          </ol>

          <!-- Desktop -->
          <ol v-else class="install-guide-list">
            <li>看浏览器地址栏右侧是否有「安装」图标 <span class="guide-icon">⊕</span></li>
            <li>点击该图标并确认安装</li>
            <li>或使用菜单中的「安装 SubSkin」选项</li>
          </ol>

          <p class="mt-3 text-xs text-gray-400 dark:text-gray-500 leading-relaxed">
            提示：若菜单中没有安装选项，可能浏览器暂时不满足安装条件（如刚清除过站点数据），稍后重新打开一般即可。
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.install-guide-list {
  list-style: none;
  counter-reset: step;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.install-guide-list li {
  counter-increment: step;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

html.dark .install-guide-list li {
  color: #cbd5e1;
}

.install-guide-list li::before {
  content: counter(step);
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  margin-top: 1px;
  border-radius: 50%;
  background: var(--color-primary-500);
  color: white;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.guide-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 1.5px solid #64748b;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1;
  vertical-align: -4px;
}
</style>
