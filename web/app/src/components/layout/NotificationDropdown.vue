<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { notificationApi, type NotificationItem } from '@/api/notifications'

const router = useRouter()
const isStaging = __APP_ENV__ === 'staging'
const notifications = ref<NotificationItem[]>([])
const unreadCount = ref(0)
const loading = ref(false)
const open = ref(false)
const panelRef = ref<HTMLElement | null>(null)
const btnRef = ref<HTMLElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

// Dynamic positioning
const DROPDOWN_WIDTH = 320 // 20rem = 320px
const VIEWPORT_PAD = 8     // px from viewport edge

function updateDropdownPosition() {
  const btn = btnRef.value
  const dropdown = dropdownRef.value
  if (!btn || !dropdown) return

  const btnRect = btn.getBoundingClientRect()
  const vw = window.innerWidth
  const vh = window.innerHeight
  const isMobile = vw < 768

  let left: number
  let width: number

  if (isMobile) {
    // Full-width dropdown on mobile, centered with viewport padding
    width = vw - VIEWPORT_PAD * 2
    left = VIEWPORT_PAD
  } else {
    // Desktop: right-aligned to bell button
    width = DROPDOWN_WIDTH
    left = btnRect.right - width

    // Clamp within viewport
    if (left < VIEWPORT_PAD) left = VIEWPORT_PAD
    if (left + width > vw - VIEWPORT_PAD) left = vw - width - VIEWPORT_PAD
  }

  dropdown.style.position = 'fixed'
  dropdown.style.left = `${left}px`
  dropdown.style.top = `${btnRect.bottom + 4}px`
  dropdown.style.width = `${width}px`
  dropdown.style.maxHeight = `${Math.min(400, vh - btnRect.bottom - 16)}px`
}

const TYPE_ICONS: Record<string, string> = {
  like: '❤️',
  comment: '💬',
  follow: '👤',
  bookmark: '⭐',
  collect: '⭐',
  friend_accepted: '🤝',
  system: '📢',
  moderation: '⚠️',
}

function typeIcon(type: string) {
  return TYPE_ICONS[type] || '🔔'
}

function timeAgo(iso: string) {
  const ms = Date.now() - new Date(iso).getTime()
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return '刚刚'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}分钟前`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour}小时前`
  const day = Math.floor(hour / 24)
  if (day < 30) return `${day}天前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

async function fetchUnreadCount() {
  try {
    const { unread_count } = await notificationApi.getUnreadCount()
    unreadCount.value = unread_count
  } catch {}
}

async function fetchList() {
  loading.value = true
  try {
    const res = await notificationApi.list(false, 20, 0)
    notifications.value = res.items
    unreadCount.value = res.unread_count
  } catch {}
  loading.value = false
}

async function markOne(n: NotificationItem) {
  if (n.is_read) return
  try {
    await notificationApi.markRead(n.id)
    n.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch {}
}

async function markAll() {
  try {
    await notificationApi.markAllRead()
    notifications.value.forEach((n) => (n.is_read = true))
    unreadCount.value = 0
  } catch {}
}

function handleClick(n: NotificationItem) {
  markOne(n)
  if (n.ref_type === 'post' && n.ref_id) {
    router.push(`/community/${n.ref_id}`)
  } else if (n.ref_type === 'user' && n.ref_id) {
    router.push(`/profile?uid=${n.ref_id}`)
  }
  open.value = false
}

async function toggle() {
  open.value = !open.value
  if (open.value) {
    fetchList()
    await nextTick()
    updateDropdownPosition()
  }
}

function closeOnClickOutside(e: MouseEvent) {
  if (panelRef.value && !panelRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

function onScroll() {
  if (open.value) updateDropdownPosition()
}

onMounted(() => {
  fetchUnreadCount()
  pollTimer = setInterval(fetchUnreadCount, 30000)
  document.addEventListener('click', closeOnClickOutside)
  window.addEventListener('scroll', onScroll, true)
  window.addEventListener('resize', onScroll)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('click', closeOnClickOutside)
  window.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', onScroll)
})
</script>

<template>
  <div ref="panelRef" class="relative">
    <!-- Bell button -->
    <button
      ref="btnRef"
      :class="['relative p-2 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center', isStaging ? 'text-slate-300 hover:text-white hover:bg-slate-700' : 'text-gray-500  hover:bg-gray-100 dark:hover:bg-gray-300']"
      aria-label="通知"
      @click.stop="toggle"
    >
      <svg class="w-[19px] h-[19px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      <!-- Unread badge -->
      <span
        v-if="unreadCount > 0"
        class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1 leading-none"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <!-- Dropdown (Teleport to body for reliable fixed positioning) -->
    <Teleport to="body">
      <Transition name="notif-drop">
        <div
          v-if="open"
          ref="dropdownRef"
          class="bg-white rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden z-[60]"
          @vue:mounted="updateDropdownPosition"
        >
          <!-- Header -->
          <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
            <span class="text-sm font-semibold text-gray-800">通知</span>
            <button
              v-if="unreadCount > 0"
              class="text-xs text-blue-500 hover:text-blue-700 dark:text-blue-400"
              @click.stop="markAll"
            >
              全部已读
            </button>
          </div>

          <!-- List -->
          <div class="overflow-y-auto" style="max-height: 350px">
            <div v-if="loading" class="flex items-center justify-center py-8">
              <span class="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>

            <div v-else-if="notifications.length === 0" class="py-10 text-center">
              <span class="text-4xl">🔔</span>
              <p class="text-sm text-gray-400 mt-2">暂无通知</p>
            </div>

            <button
              v-for="n in notifications"
              :key="n.id"
              class="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors border-b border-gray-50 dark:border-gray-700/50 last:border-b-0"
              :class="{ 'bg-blue-50/50 dark:bg-blue-900/10': !n.is_read }"
              @click="handleClick(n)"
            >
              <!-- Actor avatar or type icon -->
              <div class="shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-lg"
                :class="n.is_read ? 'bg-gray-100' : 'bg-blue-100 dark:bg-blue-900/30'">
                <img
                  v-if="n.actor?.avatar_url"
                  :src="n.actor.avatar_url"
                  :alt="n.actor.username"
                  class="w-full h-full rounded-full object-cover"
                />
                <span v-else>{{ typeIcon(n.type) }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-800 leading-snug">
                  <span v-if="n.actor" class="font-medium">{{ n.actor.username }}</span>
                  {{ n.type === 'follow' && n.actor ? '' : ' ' }}{{ n.title }}
                </p>
                <p v-if="n.body" class="text-xs text-gray-500  mt-0.5 line-clamp-1">{{ n.body }}</p>
                <p class="text-[10px] text-gray-400 mt-1">{{ timeAgo(n.created_at) }}</p>
              </div>
              <!-- Unread dot -->
              <span v-if="!n.is_read" class="shrink-0 w-2 h-2 rounded-full bg-blue-500 mt-1.5" />
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.notif-drop-enter-active,
.notif-drop-leave-active {
  transition: all 0.15s ease;
}
.notif-drop-enter-from,
.notif-drop-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}
</style>
