<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useImStore } from '@/stores/im'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables/useNotifications'

const imStore = useImStore()
const authStore = useAuthStore()
const router = useRouter()
const { unreadCount, notifications, loading: notifLoading, fetchNotifications, markRead } = useNotifications()

const showNotifications = ref(false)

onMounted(async () => {
  if (authStore.isLoggedIn) {
    await Promise.all([
      imStore.loadConversations(),
      fetchNotifications(),
    ])
    imStore.initWS()
  }
})

function openChat(convId: number) {
  router.push(`/chat/${convId}`)
}

async function handleNotificationClick(n: any) {
  await markRead(n.id)
  if (n.type === 'message' && n.ref_id) {
    router.push(`/chat/${n.ref_id}`)
  }
}

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
}
</script>

<template>
  <div class="min-h-screen bg-[#F5F7FA] safe-bottom relative">
    <!-- Header -->
    <header
      class="sticky top-0 bg-[#F5F7FA] border-b dark:border-gray-700 z-20 px-4 py-3 flex justify-between items-center"
    >
      <h1 class="text-lg font-bold text-gray-900 dark:text-white">消息</h1>
      <div v-if="authStore.isLoggedIn" class="flex items-center gap-1">
        <!-- Notification bell -->
        <button
          class="relative flex items-center justify-center w-9 h-9 rounded-full hover:bg-gray-100 transition-colors"
          :class="{ 'bg-gray-100': showNotifications }"
          title="通知"
          @click="toggleNotifications"
        >
          <i class="ri-notification-3-line text-xl text-gray-600"></i>
          <span
            v-if="unreadCount > 0"
            class="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center"
          >
            {{ unreadCount > 99 ? '99+' : unreadCount }}
          </span>
        </button>
        <!-- Contacts -->
        <router-link
          to="/contacts"
          class="flex items-center justify-center w-9 h-9 rounded-full hover:bg-gray-100 transition-colors"
          title="通讯录"
        >
          <i class="ri-contacts-book-line text-xl text-gray-600"></i>
        </router-link>
      </div>
    </header>

    <!-- Notification dropdown panel -->
    <div
      v-if="showNotifications"
      class="absolute left-0 right-0 bg-[#F5F7FA] shadow-lg border-b dark:border-gray-700 z-10 max-h-[60vh] overflow-y-auto"
    >
      <!-- Panel header -->
      <div class="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 dark:border-gray-700">
        <span class="text-sm font-medium text-gray-900 dark:text-white">系统通知</span>
        <button
          class="w-7 h-7 rounded-full flex items-center justify-center hover:bg-gray-100 transition-colors"
          @click="showNotifications = false"
        >
          <i class="ri-close-line text-gray-400 "></i>
        </button>
      </div>
      <!-- Notification list -->
      <div v-if="notifLoading" class="text-center py-10 text-gray-400 ">
        <i class="ri-loader-4-line animate-spin text-xl block mb-2"></i>
        <span class="text-sm">加载中...</span>
      </div>
      <div v-else-if="!notifications.length" class="flex flex-col items-center justify-center py-10 text-gray-400 ">
        <i class="ri-notification-3-line text-3xl mb-2"></i>
        <p class="text-sm">暂无通知</p>
      </div>
      <div v-else class="divide-y divide-gray-100 dark:divide-gray-700">
        <div
          v-for="n in notifications"
          :key="n.id"
          @click="handleNotificationClick(n)"
          class="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
          :class="{ 'bg-primary-50/50 dark:bg-primary-900/10': !n.is_read }"
        >
          <span
            v-if="!n.is_read"
            class="w-2 h-2 rounded-full bg-primary-500 mt-1.5 flex-shrink-0"
          ></span>
          <span v-else class="w-2 flex-shrink-0"></span>
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ n.title }}</div>
            <div v-if="n.content" class="text-xs text-gray-500  mt-0.5 line-clamp-2">{{ n.content }}</div>
            <div class="text-[11px] text-gray-400  mt-1">{{ new Date(n.created_at).toLocaleString('zh-CN') }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 未登录 -->
    <div v-if="!authStore.isLoggedIn" class="flex flex-col items-center justify-center py-20 text-gray-400 ">
      <i class="ri-lock-line text-5xl text-gray-300  block mb-4"></i>
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">登录后查看消息</h2>
      <p class="text-sm text-gray-500  mb-6">登录后才能查看聊天和通知</p>
      <button
        class="inline-flex items-center gap-1.5 px-6 py-2.5 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors min-h-[44px]"
        @click="authStore.showLoginModal = true"
      >
        <i class="ri-login-box-line"></i>
        去登录
      </button>
    </div>

    <!-- 已登录：好友聊天列表 -->
    <template v-else>
      <div v-if="imStore.conversations.length" class="divide-y divide-gray-100 dark:divide-gray-700">
        <div
          v-for="conv in imStore.conversations"
          :key="conv.id"
          @click="openChat(conv.id)"
          class="flex items-center gap-3 p-4 bg-[#F5F7FA] hover:bg-gray-50 dark:hover:bg-gray-750 active:bg-gray-100 dark:active:bg-gray-700 cursor-pointer"
        >
          <div
            class="w-12 h-12 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-300 font-bold flex-shrink-0"
          >
            {{ conv.peer_user?.username?.[0] || conv.name?.[0] || '?' }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex justify-between items-baseline">
              <span class="font-medium truncate text-gray-900 dark:text-white">
                {{ conv.peer_user?.username || conv.name || '私聊' }}
              </span>
              <span class="text-xs text-gray-400  flex-shrink-0 ml-2">
                {{ conv.last_message?.created_at?.slice(11, 16) }}
              </span>
            </div>
            <div class="flex justify-between items-center mt-1">
              <span class="text-sm text-gray-500  truncate">
                {{
                  conv.last_message?.is_recalled
                    ? '[消息已撤回]'
                    : conv.last_message?.content || '[图片]'
                }}
              </span>
              <span
                v-if="conv.unread_count"
                class="bg-red-500 text-white text-xs min-w-[20px] h-5 px-1 rounded-full flex items-center justify-center flex-shrink-0 ml-2"
              >
                {{ conv.unread_count > 99 ? '99+' : conv.unread_count }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div
        v-else
        class="flex flex-col items-center justify-center py-20 text-gray-400 "
      >
        <i class="ri-chat-3-line text-5xl mb-4"></i>
        <p class="text-lg">暂无消息</p>
        <p class="text-sm mt-1 mb-6">添加好友，开始聊天吧</p>
        <router-link
          to="/contacts"
          class="btn-primary px-5 py-2.5 rounded-full text-sm font-medium flex items-center gap-2"
        >
          <i class="ri-contacts-book-line"></i>
          查找好友
        </router-link>
      </div>
    </template>
  </div>
</template>
