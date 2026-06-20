<template>
  <div class="min-h-screen bg-gray-50 flex flex-col" @click.capture="handleGlobalClick">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white dark:focus:bg-gray-900 focus:text-primary-600 dark:focus:text-primary-400">跳转到主要内容</a>
    <AppHeader />
    <main id="main-content" class="flex-1 flex flex-col min-h-0 overflow-hidden main-content">
      <router-view v-slot="{ Component, route: currentRoute }">
        <keep-alive :include="['CommunityPage']">
          <component :is="Component" :key="currentRoute.path" />
        </keep-alive>
      </router-view>
    </main>
    <BottomNav />
    <PWABanners />
    <ToastContainer />
    <LoginModal v-if="authStore.showLoginModal" @close="authStore.showLoginModal = false" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useSwipeNavigation } from '@/composables/useSwipe'
import { useWechatShare } from '@/composables/useWechatShare'
import { useToast } from '@/composables/useToast'
import AppHeader from '@/components/layout/AppHeader.vue'
import BottomNav from '@/components/layout/BottomNav.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import PWABanners from '@/components/common/PWABanners.vue'
import LoginModal from '@/components/common/LoginModal.vue'

const route = useRoute()
const authStore = useAuthStore()
const toast = useToast()
useThemeStore()
useSwipeNavigation()
useWechatShare().initWxConfig()
authStore.initFromStorage()
if (authStore.isLoggedIn) {
  authStore.fetchUser()
}

onMounted(() => {
  window.addEventListener('pwa-installed', () => {
    toast.success('SubSkin 已添加到桌面')
  })
})

if (typeof navigator !== 'undefined' && /iPad|iPhone|iPod/.test(navigator.userAgent)) {
  document.documentElement.dataset.ios = ''
}

// Dynamic title & canonical per route
const pageTitles: Record<string, string> = {
  '/': 'SubSkin - AI赋能的白癜风知识库与社区平台',
  '/assessment': '白斑VASI测评 - SubSkin',
  '/tracker': '白斑VASI测评 - SubSkin',
  '/report': '体检报告AI解读 - SubSkin',
  '/community': '社区动态 - SubSkin',
  '/profile': '个人中心 - SubSkin',
  '/photo-guide': '拍照指南 - SubSkin',
  '/encyclopedia': '小白百科 - SubSkin',
  '/privacy': '隐私政策 - SubSkin',
  '/terms': '服务条款 - SubSkin',
  '/messages': '消息 - SubSkin',
  '/contacts': '通讯录 - SubSkin',
}

function updateMeta(path: string) {
  // Title
  const baseTitle = 'SubSkin更懂你'
  const matchedTitle = pageTitles[path] || Object.entries(pageTitles).find(([key]) =>
    key !== '/' && path.startsWith(key)
  )?.[1] || baseTitle
  document.title = matchedTitle

  // Canonical
  let canonical = document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null
  if (!canonical) {
    canonical = document.createElement('link')
    canonical.rel = 'canonical'
    document.head.appendChild(canonical)
  }
  canonical.href = `https://www.subskin.cn${path}`

  // OG tags
  const ogTitle = document.querySelector('meta[property="og:title"]') as HTMLMetaElement | null
  const ogUrl = document.querySelector('meta[property="og:url"]') as HTMLMetaElement | null
  if (ogTitle) ogTitle.content = matchedTitle
  if (ogUrl) ogUrl.content = `https://www.subskin.cn${path}`
}

watch(() => route.path, updateMeta, { immediate: true })

function handleGlobalClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const tracked = target.closest('[data-track-id]') as HTMLElement | null
  const trackId = tracked?.dataset.trackId
  if (trackId) {
    import('@/composables/useTracking').then(({ trackClick }) => {
      trackClick(trackId, tracked.dataset.trackText || tracked.textContent?.trim()?.slice(0, 100))
    })
  }
}
</script>

<style scoped>
.main-content {
  padding-bottom: calc(54px + env(safe-area-inset-bottom, 0px));
}
@media (min-width: 768px) {
  .main-content {
    padding-bottom: 0;
  }
}
</style>
