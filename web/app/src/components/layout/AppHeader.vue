<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NotificationDropdown from '@/components/layout/NotificationDropdown.vue'
import PageShareSheet from '@/components/common/PageShareSheet.vue'
import PageSharePoster from '@/components/common/PageSharePoster.vue'
import { toProtectedFileUrl } from '@/utils/file-url'
import { avatarInitial } from '@/utils/avatar'
import { useMainNav } from '@/composables/useMainNav'

const authStore = useAuthStore()
const showUserMenu = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const showShareSheet = ref(false)
const showSharePoster = ref(false)

const userName = computed(() => authStore.user?.username || '')
const userNameInitial = computed(() => avatarInitial(userName.value))
const userAvatar = computed(() => toProtectedFileUrl(authStore.user?.avatar_url || ''))
const avatarLoadError = ref(false)
const showAvatarImage = computed(() => !!userAvatar.value && !avatarLoadError.value)

watch(userAvatar, () => { avatarLoadError.value = false })

const route = useRoute()
const { navItems, isNavActive, currentLabel } = useMainNav()

function onAvatarError() {
  avatarLoadError.value = true
}

const isStaging = __APP_ENV__ === 'staging'

function handleLoginClick() {
  if (authStore.isLoggedIn) {
    showUserMenu.value = !showUserMenu.value
  } else {
    authStore.showLoginModal = true
  }
}

function handleLogout() {
  authStore.logout()
  showUserMenu.value = false
}

function handleClickOutside(event: MouseEvent) {
  if (!menuRef.value) return
  if (!menuRef.value.contains(event.target as Node)) {
    showUserMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})
onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const shareTitle = computed(() => {
  const path = route.path
  if (path === '/' || path === '') return 'SubSkin · 白癜风病友的AI记录和分享社区'
  if (path.startsWith('/assessment/exam') || route.query.tab === 'exam' || route.query.tab === 'report') return 'SubSkin · 体检解读'
  if (path.startsWith('/assessment') || path.startsWith('/tracker') || path.startsWith('/diary')) return 'SubSkin · 日记'
  if (path.startsWith('/community/reports')) return 'SubSkin · 白斑报告'
  if (path.startsWith('/hospitals')) return 'SubSkin · 就医经验'
  if (path.startsWith('/community') || path.startsWith('/discover')) return 'SubSkin · 分享'
  if (path.startsWith('/care')) return 'SubSkin · 调养'
  if (path.startsWith('/contribution')) return `SubSkin · ${currentLabel.value || '同行'}`
  if (path.startsWith('/profile')) return 'SubSkin · 个人中心'
  return 'SubSkin · 白癜风病友的AI记录和分享社区'
})

const shareUrl = computed(() => `${window.location.origin}${route.fullPath}`)

function handleShare() {
  showShareSheet.value = true
}

function onGeneratePoster() {
  showShareSheet.value = false
  showSharePoster.value = true
}
</script>

<template>
  <header :class="['app-header surface-glass sticky top-0 z-50 border-b border-gray-200/80 dark:border-gray-800/90', isStaging ? 'app-header--staging' : '']">
    <div class="relative mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
      <router-link to="/" class="flex items-center gap-2 no-underline shrink-0 lg:hidden">
        <img src="/subskin_logo.png?v=e5a1c9" alt="SubSkin" class="h-8 w-8 rounded-lg ring-1 ring-gray-900/5 dark:ring-white/10" />
        <span class="text-lg font-semibold tracking-tight text-gray-900 dark:text-gray-100">SubSkin</span>
        <span v-if="isStaging" class="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-white">STAGING</span>
      </router-link>
      <!-- 桌面端 Logo 与主导航在侧边栏，顶栏左侧显示当前模块名 -->
      <h2 class="hidden lg:block text-base font-semibold tracking-tight text-gray-900 dark:text-gray-100">{{ currentLabel }}</h2>

      <nav class="hidden md:flex lg:hidden items-center gap-1" aria-label="主导航">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          active-class="nv-disabled"
          exact-active-class="nv-disabled"
          :class="{ 'router-link-active': isNavActive(item.path) }"
          :data-track-id="`header_nav_${item.label}`"
        >
          <i :class="item.iconClass" class="nav-icon-svg" aria-hidden="true"></i>
          {{ item.label }}
        </router-link>
      </nav>

      <div class="flex items-center gap-1">
        <button type="button"
          class="header-icon-btn"
          aria-label="分享"
          title="分享"
          data-track-id="header_btn_share"
          @click="handleShare"
        >
          <i class="ri-share-forward-line text-[19px]" aria-hidden="true"></i>
        </button>

        <!-- Notification bell -->
        <NotificationDropdown v-if="authStore.isLoggedIn" />

        <button type="button"
          v-if="!authStore.isLoggedIn"
          class="btn-primary text-sm px-4 py-1.5 min-h-[36px] ml-1 lg:hidden"
          data-track-id="header_btn_login"
          @click="authStore.showLoginModal = true"
        >
          登录
        </button>
        <div v-else class="relative" ref="menuRef">
          <button type="button" class="flex items-center gap-2 px-1.5 py-1 rounded-full transition-colors duration-150 hover:bg-gray-100 dark:hover:bg-gray-800" data-track-id="header_btn_user_menu" @click.stop="handleLoginClick">
            <div v-if="showAvatarImage" class="w-8 h-8 rounded-full overflow-hidden bg-primary-100 dark:bg-primary-900 relative ring-1 ring-gray-900/5 dark:ring-white/10">
              <img :src="userAvatar" :alt="`${userName || '用户'}头像`" class="absolute inset-0 w-full h-full object-cover" @error="onAvatarError" />
            </div>
            <div v-else class="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-sm font-medium ring-1 ring-primary-500/20">
              {{ userNameInitial }}
            </div>
          </button>
          <div
            v-if="showUserMenu"
            class="absolute right-0 top-10 bg-white dark:bg-gray-900 rounded-xl shadow-lg border border-gray-200/90 dark:border-gray-700/90 py-1.5 min-w-[160px] z-50"
            @click="showUserMenu = false"
          >
            <router-link to="/profile" class="flex items-center gap-2 px-3.5 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 no-underline transition-colors" data-track-id="header_link_profile">
              <i class="ri-user-line text-gray-400 dark:text-gray-500" aria-hidden="true"></i>个人中心
            </router-link>
            <router-link to="/privacy" class="flex items-center gap-2 px-3.5 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 no-underline transition-colors" data-track-id="header_link_privacy">
              <i class="ri-shield-keyhole-line text-gray-400 dark:text-gray-500" aria-hidden="true"></i>隐私政策
            </router-link>
            <div class="my-1 border-t border-gray-100 dark:border-gray-800"></div>
            <button type="button" class="w-full flex items-center gap-2 text-left px-3.5 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors" data-track-id="header_btn_logout" @click="handleLogout">
              <i class="ri-logout-box-r-line" aria-hidden="true"></i>退出登录
            </button>
          </div>
        </div>
      </div>
    </div>

  </header>

  <!-- Global share sheet & poster -->
  <PageShareSheet
    :visible="showShareSheet"
    :title="shareTitle"
    :url="shareUrl"
    @close="showShareSheet = false"
    @generate-poster="onGeneratePoster"
  />
  <PageSharePoster
    :visible="showSharePoster"
    :pageTitle="shareTitle"
    :pageUrl="shareUrl"
    @close="showSharePoster = false"
  />
</template>

<style scoped>
/* 测试环境：顶部一条深蓝色条 + Logo 旁 STAGING 标识，与正式环境的白色顶栏区分 */
.app-header--staging {
  box-shadow: inset 0 3px 0 0 #1e293b;
}

.header-icon-btn {
  @apply min-w-[40px] min-h-[40px] p-2 rounded-full flex items-center justify-center text-gray-500 transition-colors duration-150 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-800;
}

.nav-link {
  @apply px-3 py-2 rounded-lg text-sm text-gray-600 dark:text-gray-300 no-underline flex items-center gap-1.5 transition-colors duration-150 hover:text-gray-900 hover:bg-gray-100 dark:hover:text-white dark:hover:bg-gray-800;
}

.nav-link.router-link-active {
  @apply text-primary-700 bg-primary-50 font-semibold dark:text-primary-200 dark:bg-primary-900;
}

.nav-icon-svg {
  @apply text-lg shrink-0;
}
</style>
