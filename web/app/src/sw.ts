/**
 * SubSkin Service Worker（injectManifest 模式）
 *
 * 在 workbox 预缓存/离线能力之上增加 Web Push 处理（用药提醒）：
 * - push 事件 → 系统通知
 * - notificationclick → 聚焦/打开网站
 * 其余缓存策略与原 generateSW 配置保持一致：
 *   - 预缓存静态资源；SPA 导航回退 index.html（排除 /wiki-content、/version.json）
 *   - /api/*、/uploads/*、/version.json 一律 NetworkOnly（用户 L3 数据绝不缓存）
 */

import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { NetworkOnly } from 'workbox-strategies'
import { clientsClaim } from 'workbox-core'

// 浏览器主线程 TS lib 不含完整 ServiceWorkerGlobalScope 类型，这里按需声明
interface PushLikeEvent extends Event {
  data?: { json: () => unknown; text: () => string } | null
  waitUntil(promise: Promise<unknown>): void
}

interface NotificationClickLikeEvent extends Event {
  notification: { close(): void }
  waitUntil(promise: Promise<unknown>): void
}

declare let self: {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>
  skipWaiting(): void
  addEventListener(type: 'message', listener: (event: { data?: { type?: string } }) => void): void
  addEventListener(type: 'push', listener: (event: PushLikeEvent) => void): void
  addEventListener(type: 'notificationclick', listener: (event: NotificationClickLikeEvent) => void): void
  registration: {
    showNotification(title: string, options?: NotificationOptions & { vibrate?: number[] }): Promise<void>
  }
  clients: {
    matchAll(options: { type: string; includeUncontrolled: boolean }): Promise<Array<{ focus(): void }>>
    openWindow(url: string): Promise<unknown>
  }
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

cleanupOutdatedCaches()
clientsClaim()

precacheAndRoute(self.__WB_MANIFEST)

// SPA 导航回退
const navigationHandler = createHandlerBoundToURL('index.html')
registerRoute(
  new NavigationRoute(navigationHandler, {
    denylist: [/^\/wiki-content/, /^\/version\.json/],
  }),
)

// 隐私红线：API 与用户上传内容绝不缓存
registerRoute(/^https?:\/\/.*\/api\/.*/i, new NetworkOnly())
registerRoute(/^https?:\/\/.*\/uploads\/.*/i, new NetworkOnly())
registerRoute(/^https?:\/\/.*\/version\.json/i, new NetworkOnly())

// ── Web Push：用药提醒 ──
self.addEventListener('push', (event) => {
  let data: { title?: string; body?: string; tag?: string } = {}
  try {
    if (event.data) {
      data = event.data.json() as { title?: string; body?: string; tag?: string }
    }
  } catch {
    try {
      data = { title: 'SubSkin 提醒', body: event.data?.text() || '' }
    } catch {
      data = { title: 'SubSkin 提醒', body: '' }
    }
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'SubSkin 提醒', {
      body: data.body || '',
      icon: '/subskin_logo.png',
      badge: '/subskin_logo.png',
      tag: data.tag || 'subskin-reminder',
      vibrate: [200, 100, 200],
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          client.focus()
          return
        }
        return self.clients.openWindow('/')
      }),
  )
})
