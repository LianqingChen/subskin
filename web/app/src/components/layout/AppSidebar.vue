<script setup lang="ts">
/**
 * 桌面侧边栏（≥1024px）：Logo、主导航、底部账号入口。
 * 1024–1279px 为图标+小标签窄栏（给 iPad 横屏让出内容宽度），≥1280px 为完整侧栏。
 * 手机/平板仍使用 AppHeader 顶栏 + BottomNav；宽度由 CSS 变量 --app-sidebar-w 统一提供，
 * 页面里的 fixed 底栏用 .app-fixed-x 避开侧边栏。
 */
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useMainNav } from '@/composables/useMainNav'
import { toProtectedFileUrl } from '@/utils/file-url'
import { avatarInitial } from '@/utils/avatar'

const authStore = useAuthStore()
const { navItems, isNavActive } = useMainNav()
const isStaging = __APP_ENV__ === 'staging'

const userName = computed(() => authStore.user?.username || '')
const userAvatar = computed(() => toProtectedFileUrl(authStore.user?.avatar_url || ''))
const avatarLoadError = ref(false)
watch(userAvatar, () => { avatarLoadError.value = false })
</script>

<template>
  <aside class="app-sidebar fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-gray-200/80 bg-white dark:border-gray-800 dark:bg-gray-900 lg:flex" aria-label="主导航">
    <router-link to="/" class="sidebar-brand flex shrink-0 flex-col items-center justify-center gap-1 no-underline xl:h-14 xl:flex-row xl:justify-start xl:gap-2.5 xl:px-5">
      <img src="/subskin_logo.png?v=b4e9d1" alt="SubSkin" class="h-8 w-8 rounded-lg" />
      <span class="hidden text-lg font-semibold tracking-tight text-gray-900 dark:text-gray-100 xl:inline">SubSkin</span>
      <span v-if="isStaging" class="rounded bg-slate-800 px-1 py-px text-[8px] font-semibold tracking-wide text-white xl:px-1.5 xl:py-0.5 xl:text-[10px]">STAGING</span>
    </router-link>

    <nav class="mt-1 flex flex-col gap-1 px-2 xl:mt-3 xl:px-3" aria-label="主导航">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="sidebar-link"
        :class="{ 'sidebar-link--active': isNavActive(item.path) }"
        :aria-current="isNavActive(item.path) ? 'page' : undefined"
        :data-track-id="`sidebar_nav_${item.label}`"
      >
        <i :class="item.iconClass" class="text-[22px]" aria-hidden="true"></i>
        <span class="sidebar-label">{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="mt-auto border-t border-gray-100 p-2 dark:border-gray-800 xl:p-3">
      <router-link
        v-if="authStore.isLoggedIn"
        to="/profile"
        class="sidebar-link"
        :class="{ 'sidebar-link--active': $route.path.startsWith('/profile') }"
        data-track-id="sidebar_profile"
      >
        <span class="relative flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary-100 text-xs font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300">
          <img v-if="userAvatar && !avatarLoadError" :src="userAvatar" alt="" class="absolute inset-0 h-full w-full object-cover" @error="avatarLoadError = true" />
          <template v-else>{{ avatarInitial(userName) }}</template>
        </span>
        <span class="sidebar-label min-w-0 truncate">{{ userName || '我的' }}</span>
      </router-link>
      <template v-else>
        <div class="xl:hidden">
          <button type="button" class="sidebar-link w-full" data-track-id="sidebar_login" @click="authStore.showLoginModal = true">
            <i class="ri-user-line text-[22px]" aria-hidden="true"></i>
            <span class="sidebar-label">登录</span>
          </button>
        </div>
        <button type="button" class="btn-primary hidden min-h-[44px] w-full text-sm xl:block" data-track-id="sidebar_login_full" @click="authStore.showLoginModal = true">登录 / 注册</button>
      </template>
      <p class="mt-3 hidden px-2 text-[11px] leading-5 text-gray-400 dark:text-gray-500 xl:block">
        <router-link to="/privacy" class="text-gray-400 no-underline hover:text-gray-600 dark:text-gray-500">隐私政策</router-link>
        <span class="mx-1">·</span>
        <router-link to="/terms" class="text-gray-400 no-underline hover:text-gray-600 dark:text-gray-500">服务条款</router-link>
      </p>
    </div>
  </aside>
</template>

<style scoped>
.app-sidebar {
  width: var(--app-sidebar-w);
}
.sidebar-brand {
  min-height: 4.25rem;
}
@media (min-width: 1280px) {
  .sidebar-brand {
    min-height: 0;
  }
}
/* 窄栏：图标在上、小标签在下（与手机底部导航一致）；完整侧栏：图标在左、标签在右 */
.sidebar-link {
  @apply flex min-h-[56px] flex-col items-center justify-center gap-0.5 rounded-xl px-1 text-gray-600 no-underline transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-800 dark:hover:text-white xl:min-h-[48px] xl:flex-row xl:justify-start xl:gap-3 xl:px-3;
}
.sidebar-label {
  @apply text-[11px] leading-4 xl:text-[15px] xl:leading-normal;
}
.sidebar-link--active {
  @apply bg-primary-50 font-semibold text-primary-700 hover:bg-primary-50 hover:text-primary-700 dark:bg-primary-900 dark:text-primary-200;
}
</style>
