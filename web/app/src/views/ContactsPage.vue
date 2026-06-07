<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { imApi } from '@/api/im'
import { useAuthStore } from '@/stores/auth'
import { hashContacts, readDeviceContacts } from '@/utils/contacts'
import type { ContactEntry } from '@/utils/contacts'

const router = useRouter()
const authStore = useAuthStore()

const friends = ref<any[]>([])
const requests = ref<{ received: any[]; sent: any[] }>({ received: [], sent: [] })
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const friendMessage = ref('')

const suggestedUsers = ref<any[]>([])
const matching = ref(false)
const contactsImported = ref(false)
const contactEntries = ref<ContactEntry[]>([])
const showManualInput = ref(false)
const manualPhones = ref('')

onMounted(async () => {
  if (authStore.isLoggedIn) {
    await Promise.all([loadFriends(), loadRequests()])
  }
})

async function loadFriends() {
  try {
    const res = await imApi.getFriends()
    friends.value = res.data.items
  } catch (e) {
    console.error('load friends failed', e)
  }
}

async function loadRequests() {
  try {
    const res = await imApi.getFriendRequests()
    requests.value = res.data
  } catch (e) {
    console.error('load requests failed', e)
  }
}

const pendingCount = computed(() => requests.value.received?.length || 0)

const sortedFriends = computed(() =>
  [...friends.value].sort((a, b) =>
    (a.username || '').localeCompare(b.username || ''),
  ),
)

async function startChat(userId: number) {
  try {
    const res = await imApi.createPrivateChat(userId)
    router.push(`/chat/${res.data.conversation_id}`)
  } catch (e) {
    console.error('create chat failed', e)
  }
}

async function acceptRequest(reqId: number) {
  try {
    await imApi.acceptRequest(reqId)
    await loadRequests()
    await loadFriends()
  } catch (e) {
    console.error('accept failed', e)
  }
}

async function declineRequest(reqId: number) {
  try {
    await imApi.declineRequest(reqId)
    await loadRequests()
  } catch (e) {
    console.error('decline failed', e)
  }
}

async function sendFriendRequest(userId: number) {
  try {
    await imApi.sendFriendRequest(userId, friendMessage.value || undefined)
    friendMessage.value = ''
    await loadRequests()
    suggestedUsers.value = suggestedUsers.value.filter(
      (u: any) => u.user_id !== userId,
    )
  } catch (e: any) {
    alert(e.response?.data?.detail || '发送失败')
  }
}

async function searchUsers() {
  if (!searchQuery.value.trim() || searchQuery.value.trim().length < 2) {
    searchResults.value = []
    return
  }
  try {
    const res = await imApi.searchUsers(searchQuery.value.trim())
    searchResults.value = res.data.items
  } catch (e) {
    searchResults.value = []
  }
}

async function matchByContacts(deviceContacts: Array<{ name?: string; phone: string }>) {
  contactEntries.value = await hashContacts(deviceContacts)
  if (!contactEntries.value.length) {
    contactsImported.value = true
    suggestedUsers.value = []
    return
  }
  const hashes = contactEntries.value.map((c) => ({
    hash: c.hash,
    name: c.name || undefined,
  }))
  const res = await imApi.matchContacts(hashes)
  suggestedUsers.value = res.data.items.filter(
    (u: any) => !u.is_friend && !u.request_pending,
  )
  contactsImported.value = true
}

async function doMatchContacts() {
  matching.value = true
  try {
    const deviceContacts = await readDeviceContacts()
    if (deviceContacts && deviceContacts.length > 0) {
      await matchByContacts(deviceContacts)
    } else {
      contactsImported.value = true
      suggestedUsers.value = []
    }
  } catch (e) {
    console.error('match contacts failed', e)
  } finally {
    matching.value = false
  }
}

async function submitManualPhones() {
  const phoneList = manualPhones.value
    .split(/[,，\n]/)
    .map((p) => p.trim())
    .filter((p) => p.length >= 5)
  if (!phoneList.length) return

  matching.value = true
  showManualInput.value = false
  try {
    await matchByContacts(phoneList.map((p) => ({ phone: p })))
  } catch (e) {
    console.error('manual match failed', e)
  } finally {
    matching.value = false
    manualPhones.value = ''
  }
}
</script>

<template>
  <div class="min-h-screen bg-[#F5F7FA] safe-bottom">
    <header
      class="sticky top-0 bg-[#F5F7FA] border-b dark:border-gray-700 z-10 px-4 py-3 flex justify-between items-center"
    >
      <div class="flex items-center gap-3">
        <button
          @click="router.back()"
          class="p-2 -ml-2 rounded-lg hover:bg-gray-100 text-gray-600"
        >
          <i class="ri-arrow-left-line text-xl"></i>
        </button>
        <h1 class="text-lg font-bold text-gray-900 dark:text-white">通讯录</h1>
      </div>
    </header>

    <div v-if="!authStore.isLoggedIn" class="max-w-6xl mx-auto px-4 py-20 text-center">
      <i class="ri-lock-line text-5xl text-gray-300  block mb-4"></i>
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">登录后查找好友</h2>
      <p class="text-sm text-gray-500  mb-6">登录后才能匹配通讯录、搜索用户和添加好友</p>
      <button
        class="inline-flex items-center gap-1.5 px-6 py-2.5 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors min-h-[44px]"
        @click="authStore.showLoginModal = true"
      >
        <i class="ri-login-box-line"></i>
        去登录
      </button>
    </div>

    <div v-else class="max-w-6xl mx-auto px-4 py-4 space-y-5">
      <!-- 可能认识的人 -->
      <section>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-gray-500  flex items-center gap-1.5">
            <i class="ri-user-search-line"></i>
            可能认识的人
          </h2>
          <span
            v-if="suggestedUsers.length"
            class="text-xs text-gray-400 "
          >
            {{ suggestedUsers.length }} 位白友
          </span>
        </div>

        <!-- Loading -->
        <div v-if="matching" class="text-center py-8 text-gray-400 ">
          <i class="ri-loader-4-line animate-spin text-2xl block mb-2"></i>
          <span class="text-sm">正在匹配通讯录...</span>
        </div>

        <!-- Initial state: show match button -->
        <div
          v-else-if="!contactsImported"
          class="bg-[#F5F7FA] rounded-2xl p-6 text-center"
        >
          <i class="ri-contacts-book-2-line text-4xl text-primary-400 mb-3 block"></i>
          <p class="text-sm text-gray-600  mb-4">
            授权通讯录，发现已经在使用 SubSkin 的白友
          </p>
          <p class="text-xs text-gray-400  mb-5">
            <i class="ri-shield-keyhole-line"></i>
            手机号仅在本地加密，不会上传原文
          </p>
          <button
            @click="doMatchContacts"
            class="px-6 py-2.5 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors min-h-[44px]"
          >
            <i class="ri-contacts-book-line mr-1"></i>
            匹配通讯录
          </button>
          <div class="mt-3">
            <button
              @click="showManualInput = true"
              class="text-xs text-gray-400  hover:text-primary-500 transition-colors min-h-[44px] px-3"
            >
              <i class="ri-edit-line mr-0.5"></i>
              手动输入手机号
            </button>
          </div>
        </div>

        <!-- Results -->
        <div
          v-else-if="suggestedUsers.length"
          class="space-y-2"
        >
          <div
            v-for="user in suggestedUsers"
            :key="user.user_id"
            class="flex items-center justify-between bg-[#F5F7FA] rounded-xl p-3"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div
                class="w-11 h-11 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-300 font-bold flex-shrink-0"
              >
                {{ user.username?.[0] || '?' }}
              </div>
              <div class="min-w-0">
                <div class="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {{ user.username }}
                </div>
                <div
                  v-if="user.contact_name && user.contact_name !== user.username"
                  class="text-xs text-gray-400  truncate"
                >
                  通讯录：{{ user.contact_name }}
                </div>
              </div>
            </div>
            <button
              @click="sendFriendRequest(user.user_id)"
              class="text-xs px-4 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 flex-shrink-0 transition-colors min-h-[44px]"
            >
              加好友
            </button>
          </div>
          <div class="text-center pt-2">
            <button
              @click="doMatchContacts"
              class="text-xs text-gray-400  hover:text-primary-500 transition-colors min-h-[44px] px-3"
            >
              <i class="ri-refresh-line mr-0.5"></i>
              重新匹配
            </button>
          </div>
        </div>

        <!-- No results -->
        <div
          v-else
          class="bg-[#F5F7FA] rounded-2xl p-5 text-center text-gray-400 "
        >
          <i class="ri-user-search-line text-3xl mb-2 block"></i>
          <p class="text-sm">暂未发现通讯录中的白友</p>
          <p class="text-xs mt-1">试试通过用户名搜索</p>
          <div class="mt-3 flex justify-center gap-4">
            <button
              @click="doMatchContacts"
              class="text-xs text-primary-500 hover:text-primary-600 min-h-[44px] px-2"
            >
              <i class="ri-refresh-line mr-0.5"></i>重新匹配
            </button>
            <button
              @click="showManualInput = true"
              class="text-xs text-gray-400  hover:text-primary-500 min-h-[44px] px-2"
            >
              <i class="ri-edit-line mr-0.5"></i>手动输入
            </button>
          </div>
        </div>
      </section>

      <!-- 搜索用户 -->
      <section>
        <h2 class="text-sm font-semibold text-gray-500  mb-3 flex items-center gap-1.5">
          <i class="ri-search-line"></i>
          搜索用户
        </h2>
        <div class="bg-[#F5F7FA] rounded-2xl p-4">
          <div class="relative">
            <i class="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
            <input
              v-model="searchQuery"
              @input="searchUsers"
              placeholder="输入用户名搜索..."
              class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 pl-9 pr-3 py-2.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div v-if="searchResults.length" class="mt-3 space-y-2">
            <div
              v-for="user in searchResults"
              :key="user.user_id"
              class="flex items-center justify-between py-2"
            >
              <div class="flex items-center gap-2">
                <div
                  class="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-300 text-sm font-bold"
                >
                  {{ user.username?.[0] || '?' }}
                </div>
                <span class="text-sm text-gray-900 dark:text-white">{{
                  user.username
                }}</span>
              </div>
              <span
                v-if="user.is_friend"
                class="text-xs text-gray-400 "
              >
                已是好友
              </span>
              <span
                v-else-if="user.request_pending"
                class="text-xs text-yellow-500"
              >
                已申请
              </span>
              <button
                v-else
                @click="sendFriendRequest(user.user_id)"
                class="text-xs px-3 py-1.5 rounded-lg bg-primary-500 text-white hover:bg-primary-600 min-h-[44px]"
              >
                加好友
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 好友请求 -->
      <section v-if="pendingCount">
        <h2 class="text-sm font-semibold text-gray-500  mb-3 flex items-center gap-1.5">
          <i class="ri-user-follow-line text-orange-500"></i>
          待处理请求 ({{ pendingCount }})
        </h2>
        <div class="space-y-2">
          <div
            v-for="req in requests.received"
            :key="req.id"
            class="flex items-center justify-between bg-[#F5F7FA] rounded-xl p-3"
          >
            <div class="flex items-center gap-2">
              <div
                class="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-300 text-sm font-bold"
              >
                {{ req.user?.username?.[0] || '?' }}
              </div>
              <div>
                <div class="text-sm font-medium text-gray-900 dark:text-white">
                  {{ req.user?.username }}
                </div>
                <div
                  v-if="req.message"
                  class="text-xs text-gray-400 "
                >
                  {{ req.message }}
                </div>
              </div>
            </div>
            <div class="flex gap-2">
              <button
                @click="acceptRequest(req.id)"
                class="text-xs px-3 py-1.5 rounded-lg bg-primary-500 text-white hover:bg-primary-600 min-h-[44px]"
              >
                接受
              </button>
              <button
                @click="declineRequest(req.id)"
                class="text-xs px-3 py-1.5 rounded-lg bg-gray-200  text-gray-700 hover:bg-gray-300 dark:hover:bg-gray-300 min-h-[44px]"
              >
                拒绝
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 好友列表 -->
      <section>
        <h2 class="text-sm font-semibold text-gray-500  mb-3 flex items-center gap-1.5">
          <i class="ri-contacts-line"></i>
          我的好友 ({{ friends.length }})
        </h2>
        <div v-if="sortedFriends.length" class="space-y-1">
          <div
            v-for="friend in sortedFriends"
            :key="friend.id"
            @click="startChat(friend.id)"
            class="flex items-center gap-3 p-3 rounded-xl hover:bg-[#F5F7FA] cursor-pointer transition-colors"
          >
            <div
              class="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-300 font-bold"
            >
              {{ friend.username?.[0] || '?' }}
            </div>
            <div class="flex-1 min-w-0">
              <span class="text-sm font-medium text-gray-900 dark:text-white">
                {{ friend.username }}
              </span>
            </div>
            <i class="ri-chat-3-line text-gray-400 "></i>
          </div>
        </div>
        <div
          v-else
          class="py-12 text-center text-gray-400 "
        >
          <i class="ri-contacts-line text-4xl mb-2 block"></i>
          <p class="text-sm">暂无好友</p>
          <p class="text-xs mt-1">匹配通讯录或搜索用户名添加好友</p>
        </div>
      </section>
    </div>

    <!-- Manual phone input dialog -->
    <Teleport to="body">
      <div
        v-if="showManualInput"
        class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center"
        @click.self="showManualInput = false"
      >
        <div
          class="bg-[#F5F7FA] w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4"
        >
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h2 class="text-lg font-semibold text-gray-900">
              手动输入手机号
            </h2>
            <button
              class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl leading-none"
              @click="showManualInput = false"
            >
              &times;
            </button>
          </div>
          <div class="p-6 space-y-4">
            <p class="text-sm text-gray-500 ">
              输入对方的手机号来查找白友。多个手机号用逗号分隔。
            </p>
            <p class="text-xs text-gray-400 ">
              <i class="ri-shield-keyhole-line"></i>
              手机号仅在本地加密，不会上传原文
            </p>
            <textarea
              v-model="manualPhones"
              rows="3"
              placeholder="13800138000, 13900139001"
              class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
            ></textarea>
            <button
              @click="submitManualPhones"
              :disabled="matching"
              class="w-full py-2.5 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 disabled:opacity-50 transition-colors min-h-[44px]"
            >
              {{ matching ? '匹配中...' : '查找白友' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
