<template>
  <div class="min-h-dvh bg-gray-50 dark:bg-gray-950 flex flex-col overflow-x-clip" @click.capture="handleGlobalClick">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white dark:focus:bg-gray-900 focus:text-primary-600 dark:focus:text-primary-400">跳转到主要内容</a>
    <AppSidebar />
    <div class="app-shell flex flex-1 flex-col min-w-0">
    <AppHeader />
    <main id="main-content" class="flex-1 flex flex-col min-h-0 main-content">
      <router-view v-slot="{ Component, route: currentRoute }">
        <keep-alive :include="['CommunityPage']">
          <component :is="Component" :key="currentRoute.path" />
        </keep-alive>
      </router-view>
    </main>
    <!-- 全站统一页脚声明（所有页面底端只放这一句话）。
         首页（智能问答）底部有 fixed 输入栏，声明改由 ChatAssistantPage 渲染在输入栏上方，
         避免与输入栏重叠；测评页(/assessment)声明由 Step1 功能卡片底部承载（体检解读自带声明）；
         其余页面统一使用全局页脚。 -->
    <GlobalFooter v-if="route.path !== '/' && route.path !== '/assessment'" />
    </div>
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
import AppSidebar from '@/components/layout/AppSidebar.vue'
import BottomNav from '@/components/layout/BottomNav.vue'
import GlobalFooter from '@/components/layout/GlobalFooter.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import PWABanners from '@/components/common/PWABanners.vue'
import LoginModal from '@/components/common/LoginModal.vue'

const route = useRoute()
const authStore = useAuthStore()
const toast = useToast()
useThemeStore()
useSwipeNavigation()
const wechatShare = useWechatShare()
wechatShare.initWxConfig()
authStore.initFromStorage()
if (authStore.isLoggedIn) {
  authStore.fetchUser()
}

onMounted(() => {
  window.addEventListener('pwa-installed', () => {
    toast.success('SubSkin 已添加到桌面')
  })

  // 会话过期（refresh token 失效）时由 api 广播：清理本地会话并弹登录框。
  // 节流 3s，避免并发 401 触发多个事件反复弹窗。
  let lastSessionExpiredAt = 0
  window.addEventListener('subskin:session-expired', () => {
    const now = Date.now()
    if (now - lastSessionExpiredAt < 3000) return
    lastSessionExpiredAt = now
    authStore.logout().finally(() => {
      toast.show('登录已过期，请重新登录')
      authStore.showLoginModal = true
    })
  })
})

if (typeof navigator !== 'undefined' && /iPad|iPhone|iPod/.test(navigator.userAgent)) {
  document.documentElement.dataset.ios = ''
}

// Dynamic title & canonical per route
const pageTitles: Record<string, string> = {
  '/': 'SubSkin - 白癜风病友的AI记录和分享社区',
  '/assessment': '记录 - SubSkin',
  '/community': '发现 - SubSkin',
  '/profile': '个人中心 - SubSkin',
  '/photo-guide': '拍照指南 - SubSkin',
  '/privacy': '隐私政策 - SubSkin',
  '/terms': '服务条款 - SubSkin',
}

function updateMeta(path: string) {
  // Title
  const baseTitle = 'SubSkin - 白癜风病友的AI记录和分享社区'
  const queryTitle = path === '/assessment' && route.query.tab === 'report'
    ? '体检报告解读 - SubSkin'
    : ''
  const matchedTitle = queryTitle
    || (route.meta.title ? `${String(route.meta.title)} - SubSkin` : '')
    || pageTitles[path]
    || Object.entries(pageTitles).find(([key]) =>
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
  if (ogUrl) ogUrl.content = `https://www.subskin.cn${route.fullPath}`
  wechatShare.setShareData({
    title: matchedTitle,
    desc: '白癜风病友的AI记录和分享社区。',
    link: `${window.location.origin}${route.fullPath}`,
    imgUrl: `${window.location.origin}/og-image.png`,
  })
}

watch(() => route.fullPath, () => updateMeta(route.path), { immediate: true })

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
/* 底部导航避让间距已由 GlobalFooter 内部 spacer 承担，main 不再加 padding-bottom，
   避免与页脚重复留白。 */
/* 桌面端为左侧固定侧边栏让出宽度 */
.app-shell {
  padding-left: var(--app-sidebar-w);
}
/* overflow-x: hidden 会让 main 成为滚动容器，内部 position: sticky 全部失效；
   clip 只裁切不建滚动容器。旧 iOS / 微信 WebView 不支持 clip 时回退 hidden */
.main-content {
  overflow-x: clip;
}
@supports not (overflow: clip) {
  .main-content {
    overflow-x: hidden;
  }
}
</style>
