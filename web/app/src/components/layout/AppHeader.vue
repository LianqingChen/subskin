<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NotificationDropdown from '@/components/layout/NotificationDropdown.vue'
import PageShareSheet from '@/components/common/PageShareSheet.vue'
import PageSharePoster from '@/components/common/PageSharePoster.vue'
import { toProtectedFileUrl } from '@/utils/file-url'

const authStore = useAuthStore()
const showUserMenu = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const showShareSheet = ref(false)
const showSharePoster = ref(false)

const userName = computed(() => authStore.user?.username || '')
const userAvatar = computed(() => toProtectedFileUrl(authStore.user?.avatar_url || ''))
const avatarLoadError = ref(false)
const showAvatarImage = computed(() => !!userAvatar.value && !avatarLoadError.value)

watch(userAvatar, () => { avatarLoadError.value = false })

const route = useRoute()

function isNavActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  if (path === '/assessment') return route.path === '/assessment' || route.path.startsWith('/assessment/') || route.path.startsWith('/tracker')
  if (path === '/report') return route.path === '/report' || route.path.startsWith('/report/')
  if (path === '/profile') return route.path === '/profile' || route.path.startsWith('/profile/')
  return route.path === path || route.path.startsWith(path + '/')
}

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
  if (path === '/' || path === '') return 'SubSkin · 白癜风智能助手'
  if (path.startsWith('/assessment') || path.startsWith('/tracker')) return 'SubSkin · 白斑面积评估'
  if (path.startsWith('/report')) return 'SubSkin · 体检报告解读'
  if (path.startsWith('/community')) return 'SubSkin · 白友社区'
  if (path.startsWith('/profile')) return 'SubSkin · 我的主页'
  if (path.startsWith('/encyclopedia')) return 'SubSkin · 白癜风百科'
  return 'SubSkin · 白癜风智能助手'
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
  <header :class="[
    'sticky top-0 z-50 shadow-sm transition-colors duration-200',
    isStaging
      ? 'bg-slate-800 border-b border-slate-700'
      : 'bg-white border-b border-gray-200'
  ]">
    <div :class="['max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between relative', { 'staging-nav': isStaging }]">
      <router-link to="/" class="flex items-center gap-2 no-underline shrink-0">
        <img src="/subskin_logo.png?v=b4e9d1" alt="SubSkin" class="h-8 w-8 rounded" />
        <span :class="['text-lg font-semibold', isStaging ? 'text-white' : 'text-gray-900']">SubSkin</span>
      </router-link>

      <nav class="hidden md:flex items-center gap-1">
        <router-link to="/" class="nav-link" active-class="nv-disabled" exact-active-class="nv-disabled" :class="{ 'router-link-active': isNavActive('/') }" data-track-id="header_nav_问答">
          <i class="ri-robot-3-line nav-icon-svg"></i>
          问答
        </router-link>
        <router-link to="/assessment" class="nav-link" active-class="nv-disabled" exact-active-class="nv-disabled" :class="{ 'router-link-active': isNavActive('/assessment') }" data-track-id="header_nav_测评">
          <i class="ri-focus-3-line nav-icon-svg"></i>
          测评
        </router-link>
        <router-link to="/report" class="nav-link" active-class="nv-disabled" exact-active-class="nv-disabled" :class="{ 'router-link-active': isNavActive('/report') }" data-track-id="header_nav_报告">
          <i class="ri-heart-pulse-line nav-icon-svg"></i>
          报告
        </router-link>
        <router-link to="/community" class="nav-link" active-class="nv-disabled" exact-active-class="nv-disabled" :class="{ 'router-link-active': isNavActive('/community') }" data-track-id="header_nav_白友圈">
          <i class="ri-compass-3-line nav-icon-svg"></i>
          白友圈
        </router-link>
        <router-link to="/profile" class="nav-link" active-class="nv-disabled" exact-active-class="nv-disabled" :class="{ 'router-link-active': isNavActive('/profile') }" data-track-id="header_nav_我的">
          <i class="ri-user-3-line nav-icon-svg"></i>
          我的
        </router-link>
      </nav>

      <div class="flex items-center gap-2">
        <button type="button"
          :class="['p-2 rounded-lg transition-colors duration-150 min-w-[44px] min-h-[44px] flex items-center justify-center', isStaging ? 'text-slate-300 hover:text-white hover:bg-slate-700' : 'text-gray-500 hover:bg-gray-100']"
          aria-label="分享"
          title="分享"
          data-track-id="header_btn_share"
          @click="handleShare"
        >
          <svg class="w-[19px] h-[19px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
          </svg>
        </button>

        <!-- Notification bell -->
        <NotificationDropdown v-if="authStore.isLoggedIn" />

        <button type="button"
          v-if="!authStore.isLoggedIn"
          class="btn-primary text-sm px-3 py-1.5"
          data-track-id="header_btn_login"
          @click="authStore.showLoginModal = true"
        >
          登录
        </button>
        <div v-else class="relative" ref="menuRef">
          <button type="button" :class="['flex items-center gap-2 px-2 py-1 rounded-lg transition-colors duration-150', isStaging ? 'hover:bg-slate-700' : 'hover:bg-gray-100']" data-track-id="header_btn_user_menu" @click.stop="handleLoginClick">
            <div v-if="showAvatarImage" class="w-8 h-8 rounded-full overflow-hidden bg-primary-100 dark:bg-primary-900 relative">
              <img :src="userAvatar" :alt="`${userName || '用户'}头像`" class="absolute inset-0 w-full h-full object-cover" @error="onAvatarError" />
            </div>
            <div v-else class="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-sm font-medium">
              {{ userName.charAt(0).toUpperCase() }}
            </div>
          </button>
          <div
            v-if="showUserMenu"
            class="absolute right-0 top-10 bg-white rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 min-w-[160px] z-50"
            @click="showUserMenu = false"
          >
            <router-link to="/profile" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:hover:bg-gray-300 no-underline" data-track-id="header_link_profile">
              个人中心
            </router-link>
            <router-link to="/privacy" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:hover:bg-gray-300 no-underline" data-track-id="header_link_privacy">
              隐私政策
            </router-link>
            <button type="button" class="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20" data-track-id="header_btn_logout" @click="handleLogout">
              退出登录
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
.nav-link {
  @apply px-3 py-2.5 rounded-lg text-sm text-primary-600 dark:text-primary-400 no-underline flex items-center gap-1.5 transition-colors duration-150 hover:text-primary-500 dark:hover:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900;
}

.nav-link.router-link-active {
  @apply text-primary-700 dark:text-primary-200 bg-primary-100 dark:bg-primary-800 font-semibold shadow-[inset_0_-2px_0_0_var(--color-primary-500)];
}

.nav-icon-svg {
  @apply text-lg shrink-0;
}

/* Staging: dark-blue nav bar with light text */
.staging-nav .nav-link {
  @apply text-slate-200 hover:text-white hover:bg-slate-700;
}
.staging-nav .nav-link.router-link-active {
  @apply text-white bg-slate-700 shadow-[inset_0_-2px_0_0_#60a5fa];
}
.staging-nav .btn-primary {
  @apply bg-blue-500 hover:bg-blue-400 text-white;
}
.staging-nav .staging-text-muted {
  @apply text-slate-300 hover:text-white hover:bg-slate-700;
}
</style>
