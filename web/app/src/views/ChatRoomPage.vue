<script setup lang="ts">
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useImStore } from '@/stores/im'
import { useAuthStore } from '@/stores/auth'
import { imApi } from '@/api/im'

const imStore = useImStore()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const convId = computed(() => Number(route.params.id))
const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const loadingMore = ref(false)
const showMentionList = ref(false)
const mentionFilter = ref('')
const groupMembers = ref<any[]>([])
const isRecording = ref(false)

const currentConversation = computed(() =>
  imStore.conversations.find((c) => c.id === convId.value),
)

const isGroupChat = computed(() => currentConversation.value?.type === 'group')

const chatName = computed(() => {
  const conv = currentConversation.value
  if (!conv) return ''
  return isGroupChat.value ? conv.name || '群聊' : conv.peer_user?.username || '私聊'
})

onMounted(async () => {
  if (convId.value) {
    await imStore.openConversation(convId.value)
    await nextTick()
    scrollToBottom()
    if (isGroupChat.value) {
      await loadGroupMembers()
    }
  }
})

watch(convId, async () => {
  if (convId.value) {
    await imStore.openConversation(convId.value)
    await nextTick()
    scrollToBottom()
    if (isGroupChat.value) {
      await loadGroupMembers()
    }
  }
})

async function loadGroupMembers() {
  try {
    const res = await imApi.getGroupMembers(convId.value)
    groupMembers.value = res.data.items
  } catch {
    groupMembers.value = []
  }
}

const filteredMembers = computed(() => {
  if (!mentionFilter.value) return groupMembers.value.slice(0, 8)
  const q = mentionFilter.value.toLowerCase()
  return groupMembers.value.filter((m: any) =>
    m.username?.toLowerCase().includes(q),
  )
})

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return
  await imStore.sendMessage(text)
  inputText.value = ''
  showMentionList.value = false
  await nextTick()
  scrollToBottom()
}

async function loadMore() {
  if (loadingMore.value || !imStore.currentMessages.length) return
  loadingMore.value = true
  const firstId = imStore.currentMessages[0]?.id
  try {
    const res = await imApi.getMessages(convId.value, firstId)
    if (res.data.items.length) {
      imStore.currentMessages = [...res.data.items, ...imStore.currentMessages]
    }
  } finally {
    loadingMore.value = false
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function formatTime(dateStr?: string) {
  if (!dateStr) return ''
  return dateStr.slice(11, 16)
}

function isSelf(senderId: number) {
  return senderId === authStore.user?.id
}

function handleInput() {
  if (!isGroupChat.value) return
  const text = inputText.value
  const lastAtIndex = text.lastIndexOf('@')
  if (lastAtIndex >= 0) {
    const afterAt = text.slice(lastAtIndex + 1)
    if (!afterAt.includes(' ') && afterAt.length <= 20) {
      mentionFilter.value = afterAt
      showMentionList.value = true
      return
    }
  }
  showMentionList.value = false
}

function selectMention(member: any) {
  const text = inputText.value
  const lastAtIndex = text.lastIndexOf('@')
  inputText.value = text.slice(0, lastAtIndex) + `@${member.username} `
  showMentionList.value = false
}

function goToGroupInfo() {
  router.push(`/group/${convId.value}`)
}
</script>

<template>
  <div
    class="chat-room flex flex-col bg-[#F5F7FA] h-[calc(100dvh-3.5rem)] pb-14 md:pb-0"
  >
    <!-- Header -->
    <header
      class="sticky top-0 bg-[#F5F7FA] border-b dark:border-gray-700 z-10 px-4 py-3 flex items-center gap-3"
    >
      <button
        @click="router.back()"
        class="p-2 -ml-2 rounded-lg hover:bg-gray-100 text-gray-600"
      >
        <i class="ri-arrow-left-line text-xl"></i>
      </button>
      <h1
        class="text-lg font-bold text-gray-900 dark:text-white flex-1 truncate"
      >
        {{ chatName }}
      </h1>
      <button
        v-if="isGroupChat"
        @click="goToGroupInfo"
        class="p-2 rounded-lg hover:bg-gray-100 text-gray-500 "
      >
        <i class="ri-group-line text-xl"></i>
      </button>
    </header>

    <!-- Messages -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto px-4 py-3 space-y-3"
    >
      <div
        v-if="loadingMore"
        class="text-center text-sm text-gray-400 py-2"
      >
        加载中...
      </div>
      <button
        v-else-if="imStore.currentMessages.length >= 50"
        @click="loadMore"
        class="block mx-auto text-sm text-primary-600 dark:text-primary-400 py-2"
      >
        加载更多消息
      </button>

      <div
        v-for="msg in imStore.currentMessages"
        :key="msg.id"
        class="flex"
        :class="
          msg.msg_type === 'system'
            ? 'justify-center'
            : isSelf(msg.sender_id)
              ? 'justify-end'
              : 'justify-start'
        "
      >
        <!-- System message -->
        <div
          v-if="msg.msg_type === 'system'"
          class="text-center text-xs text-gray-400  py-1 px-3 bg-gray-100 rounded-full"
        >
          {{ msg.content }}
        </div>

        <!-- Normal message bubble -->
        <template v-else>
          <div class="max-w-[75%]">
            <div
              v-if="!isSelf(msg.sender_id) && isGroupChat"
              class="text-xs text-gray-400  mb-1"
            >
              {{ msg.sender_name }}
            </div>
            <div
              class="rounded-2xl px-4 py-2.5 break-words"
              :class="
                isSelf(msg.sender_id)
                  ? 'bg-primary-500 text-white rounded-br-md'
                  : 'bg-[#F5F7FA] text-gray-900 dark:text-white rounded-bl-md shadow-sm'
              "
            >
              <!-- Recalled -->
              <span
                v-if="msg.is_recalled"
                class="text-gray-400  text-sm italic"
              >
                消息已撤回
              </span>

              <!-- Share post card -->
              <div
                v-else-if="msg.msg_type === 'share_post'"
                class="cursor-pointer"
                @click="
                  router.push(`/community/${msg.metadata?.post_id}`)
                "
              >
                <div class="flex items-center gap-2 text-sm opacity-80 mb-1">
                  <i class="ri-share-forward-line"></i>
                  <span>分享的帖子</span>
                </div>
                <div class="font-medium text-sm">
                  {{ msg.metadata?.title || '帖子' }}
                </div>
              </div>

              <!-- Voice -->
              <div
                v-else-if="msg.msg_type === 'voice'"
                class="flex items-center gap-2 cursor-pointer"
              >
                <i class="ri-volume-up-line"></i>
                <span class="text-sm"
                  >语音消息 {{ msg.metadata?.duration || '' }}s</span
                >
              </div>

              <!-- Image -->
              <div v-else-if="msg.msg_type === 'image'">
                <img
                  :src="msg.metadata?.image_url"
                  class="max-w-full rounded-lg"
                  alt=""
                />
              </div>

              <!-- Text -->
              <span v-else class="text-sm whitespace-pre-wrap">{{
                msg.content
              }}</span>
            </div>
            <div class="text-xs text-gray-400  mt-0.5">
              {{ formatTime(msg.created_at) }}
            </div>
          </div>
</template>
      </div>
    </div>

    <!-- @ Mention dropdown -->
    <div
      v-if="showMentionList && filteredMembers.length"
      class="bg-[#F5F7FA] border dark:border-gray-700 rounded-xl shadow-lg mx-4 mb-1 max-h-48 overflow-y-auto"
    >
      <button
        v-for="member in filteredMembers"
        :key="member.user_id"
        @click="selectMention(member)"
        class="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-gray-50 text-left"
      >
        <div
          class="w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-300 text-xs font-bold"
        >
          {{ member.username?.[0] || '?' }}
        </div>
        <span class="text-sm text-gray-900 dark:text-white">{{
          member.username
        }}</span>
      </button>
    </div>

    <!-- Input -->
    <div
      class="sticky bottom-0 bg-[#F5F7FA] border-t dark:border-gray-700 px-4 py-3 safe-bottom"
    >
      <div class="flex items-end gap-2">
        <button
          class="p-2 rounded-lg hover:bg-gray-100 text-gray-500 "
        >
          <i class="ri-image-line text-xl"></i>
        </button>
        <button
          class="p-2 rounded-lg hover:bg-gray-100 text-gray-500 "
          :class="{ 'text-red-500': isRecording }"
        >
          <i class="ri-mic-line text-xl"></i>
        </button>
        <div class="flex-1 relative">
          <textarea
            v-model="inputText"
            @keydown.enter.exact.prevent="sendMessage"
            @input="handleInput"
            :placeholder="isGroupChat ? '输入消息，@提及成员...' : '输入消息...'"
            rows="1"
            class="w-full resize-none rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 px-4 py-2.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <button
          @click="sendMessage"
          :disabled="!inputText.trim()"
          class="p-2.5 rounded-xl bg-primary-500 text-white disabled:opacity-40 hover:bg-primary-600 transition-colors"
        >
          <i class="ri-send-plane-2-fill text-lg"></i>
        </button>
      </div>
    </div>
  </div>
</template>
