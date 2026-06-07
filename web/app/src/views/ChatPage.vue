<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { chatApi, SSEStreamReader } from '@/api/chat'
import { useToast } from '@/composables/useToast'
import { trackEvent } from '@/composables/useTracking'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import SuggestionChips from '@/components/chat/SuggestionChips.vue'

import type { Source } from '@/types'

const authStore = useAuthStore()
const chatStore = useChatStore()
const route = useRoute()
const toast = useToast()


const messagesContainer = ref<HTMLElement | null>(null)
const guestRemaining = ref<number | null>(null)
const guestLimit = 3
const currentSources = ref<Source[]>([])
const activeStream = ref<{ cancel: () => void } | null>(null)
const showHistoryPanel = ref(false)
const sidebarCollapsed = ref(false)

const suggestions = [
  '白癜风会传染吗？',
  '最新管理方法有什么进展？',
  '日常饮食需要注意什么？',
  '308激光治疗效果怎么样？',
  '我刚确诊，该怎么办？',
  '白癜风会遗传给孩子吗？',
]

const isWelcome = computed(() => chatStore.messages.length === 0)

const isGuestQuotaExceeded = computed(() => {
  if (authStore.isLoggedIn) return false
  return guestRemaining.value !== null && guestRemaining.value <= 0
})

const maxQuestionLength = computed(() => authStore.isLoggedIn ? 2000 : 200)

async function fetchGuestQuota() {
  if (authStore.isLoggedIn) return
  try {
    const quota = await chatApi.getGuestQuota()
    guestRemaining.value = quota.remaining
  } catch {
    guestRemaining.value = guestLimit
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function handleSend(text: string, isVoice: boolean = false, files?: Array<{ file: File; preview?: string; id: string }>) {
  if (!text.trim() && (!files || files.length === 0)) return

  if (isGuestQuotaExceeded.value) {
    chatStore.addMessage('assistant', '今日免费体验次数已用完，请登录后继续使用AI助手，解锁更多功能。')
    authStore.showLoginModal = true
    return
  }

  // Upload files first and collect attachment info
  const attachments: Array<{ id: string; type: 'image' | 'document'; url: string; name: string; size: number; mimeType: string; thumbnailUrl?: string }> = []
  const attachmentIds: string[] = []

  if (files && files.length > 0 && authStore.isLoggedIn) {
    for (const f of files) {
      try {
        const result = await chatApi.uploadTemp(f.file)
        attachmentIds.push(result.temp_id)
        attachments.push({
          id: result.temp_id,
          type: f.file.type.startsWith('image/') ? 'image' : 'document',
          url: result.temp_url,
          name: f.file.name,
          size: result.size,
          mimeType: result.mime_type,
          thumbnailUrl: f.preview,
        })
      } catch (e: any) {
        toast.error(`文件 ${f.file.name} 上传失败`)
      }
    }
  }

  chatStore.addMessage('user', text || '(上传了附件)', undefined, isVoice, attachments.length > 0 ? attachments : undefined)
  trackEvent({ event_type: 'chat_message_sent' })
  currentSources.value = []
  scrollToBottom()

  chatStore.isLoading = true
  const thinkingMsgId = chatStore.addThinkingMessage(isVoice)

  try {
    let stream
    if (authStore.isLoggedIn) {
      if (attachmentIds.length > 0) {
        stream = chatApi.streamAskWithAttachments(text, chatStore.conversationId, attachmentIds)
      } else {
        stream = chatApi.streamAsk(text, chatStore.conversationId)
      }
    } else {
      if (attachmentIds.length > 0) {
        stream = chatApi.streamAskPublicWithAttachments(text, attachmentIds)
      } else {
        stream = chatApi.streamAskPublic(text)
      }
    }
    await handleStream(stream.reader, stream.cancel, thinkingMsgId)
  } catch (e: any) {
    chatStore.removeMessage(thinkingMsgId)
    if (e?.response?.status === 401) {
      toast.warning('登录已过期，请重新登录')
      authStore.logout()
      authStore.showLoginModal = true
    } else if (e?.response?.status === 400) {
      const detail = e.response?.data?.detail || '问题不合适'
      chatStore.addMessage('assistant', `${detail}`)
    } else if (e?.response?.status === 429) {
      const detail = e.response?.data?.detail || '今日免费体验次数已用完'
      chatStore.addMessage('assistant', `${detail}`)
      guestRemaining.value = 0
    } else {
      chatStore.addMessage('assistant', '抱歉，请求出错了，请稍后再试。')
      toast.error('网络连接失败，请检查网络')
    }
  } finally {
    chatStore.isLoading = false
    scrollToBottom()
  }
}

async function handleStream(
  reader: SSEStreamReader,
  cancel: () => void,
  thinkingMsgId: string
) {
  activeStream.value = { cancel }

  reader.onThinking = (stage: string, message: string) => {
    chatStore.updateThinkingMessage(thinkingMsgId, stage, message)
    scrollToBottom()
  }

  reader.onToken = (token: string) => {
    chatStore.streamTokenToMessage(thinkingMsgId, token)
    scrollToBottom()
  }

  reader.onActionCard = (card: any) => {
    chatStore.addActionCard(thinkingMsgId, card)
    scrollToBottom()
  }

  reader.onDone = (data: { sources?: Source[]; remaining_quota?: number; is_guest?: boolean }) => {
    chatStore.finalizeMessage(thinkingMsgId, data.sources)
    currentSources.value = data.sources || []
    if (data.remaining_quota !== undefined) {
      guestRemaining.value = data.remaining_quota
    }
    activeStream.value = null
  }

  reader.onError = (error: string) => {
    chatStore.removeMessage(thinkingMsgId)
    if (error.includes('已用完') || error.includes('429')) {
    chatStore.addMessage('assistant', '今日免费体验次数已用完，请登录后继续使用AI助手，解锁更多功能。')
      guestRemaining.value = 0
    } else if (error.includes('白癜风') || error.includes('皮肤健康') || error.includes('话题')) {
      chatStore.addMessage('assistant', `${error}`)
    } else {
      chatStore.addMessage('assistant', `抱歉，请求出错了，请稍后再试。（${error}）`)
    }
    activeStream.value = null
  }

  await reader.start()
}

function handleSuggestion(text: string) {
  handleSend(text, false)
}

function startNewChat() {
  if (activeStream.value) {
    activeStream.value.cancel()
    activeStream.value = null
  }
  chatStore.clearChat()
  currentSources.value = []
}

async function handleSaveCard(messageId: string, cardIndex: number, privacy?: string) {
  const msg = chatStore.messages.find(m => m.id === messageId)
  if (!msg || !msg.actionCards || !msg.actionCards[cardIndex]) return

  const card = msg.actionCards[cardIndex]
  const action = card.type === 'diary' ? (privacy === 'public' ? 'share' : 'save') : 'save'

  try {
    const result = await chatApi.confirmAction(
      chatStore.conversationId,
      card.type,
      { ...card },
      action
    )
    chatStore.updateActionCard(messageId, cardIndex, {
      saved: true,
      privacy: privacy || 'private',
    })
    toast.success(result.message || '保存成功')
  } catch (e: any) {
    toast.error('保存失败，请稍后再试')
  }
}

function handleDismissCard(messageId: string, cardIndex: number) {
  chatStore.updateActionCard(messageId, cardIndex, { saved: true }) // mark as dismissed
}

async function selectConversation(id: string) {
  if (authStore.isLoggedIn) {
    await chatStore.loadConversation(id)
    scrollToBottom()
    showHistoryPanel.value = false
  }
}

onMounted(() => {
  fetchGuestQuota()
  if (authStore.isLoggedIn) {
    chatStore.loadConversations()
  }
  if (route.query.q) {
    const q = route.query.q as string
    nextTick(() => handleSend(q))
  }
})

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

watch(() => authStore.isLoggedIn, (loggedIn) => {
  if (loggedIn) {
    chatStore.loadConversations()
  }
})
</script>

<template>
  <div class="flex h-[calc(100dvh-3.5rem)] md:h-[calc(100dvh-3.5rem)] pb-14 md:pb-0 bg-white transition-colors duration-200">
    <!-- Desktop sidebar -->
    <aside 
      v-if="!sidebarCollapsed" 
      class="hidden md:flex w-52 flex-shrink-0 flex-col border-r border-gray-100 dark:border-gray-800 bg-white relative"
    >
      <div class="p-4 border-b border-gray-200 dark:border-gray-700">
        <button
          class="w-full flex items-center justify-center gap-2 bg-primary-600 dark:bg-primary-500 hover:bg-primary-700 dark:hover:bg-primary-600 text-white rounded-lg py-2.5 px-4 text-sm font-medium transition-colors"
          @click="startNewChat()"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
          </svg>
          新建问答
        </button>
      </div>
      <div class="flex-1 overflow-y-auto p-3">
        <div v-if="chatStore.conversations.length === 0" class="text-center py-8 text-gray-400  text-sm">
          暂无对话历史
        </div>
        <div v-else class="space-y-1">
          <button
            v-for="conv in chatStore.conversations.slice(0, 20)"
            :key="conv.id"
            class="w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors truncate"
            :class="chatStore.conversationId === conv.id
              ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
              : 'text-gray-600  hover:bg-gray-50'"
            @click="selectConversation(conv.id)"
          >
            {{ conv.title }}
          </button>
        </div>
      </div>
      <!-- Collapse button (desktop only) -->
      <button 
        class="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-12 flex items-center justify-center bg-white border border-gray-100 dark:border-gray-800 rounded-r-lg shadow-sm text-gray-400 hover:text-primary-500 transition-colors z-10"
        @click="sidebarCollapsed = true"
        title="收起侧边栏"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
      </button>
    </aside>

    <!-- Toggle button when collapsed -->
    <div v-else class="hidden md:flex flex-col h-full border-r border-gray-100 dark:border-gray-800 bg-white relative">
      <button 
        @click="sidebarCollapsed = false" 
        class="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-12 flex items-center justify-center bg-white border border-gray-100 dark:border-gray-800 rounded-r-lg shadow-sm text-gray-400 hover:text-primary-500 transition-colors z-10"
        title="展开侧边栏"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <!-- Main content -->
    <main class="flex-1 flex flex-col min-w-0">
      <!-- Messages area -->
    <div ref="messagesContainer" class="chat-scroll flex-1 overflow-y-auto">
      <div class="max-w-6xl mx-auto px-4 md:px-6 py-6">
        <div v-if="isWelcome" class="flex flex-col items-center pt-2 md:pt-4 pb-4 px-4">
          <div class="text-center max-w-lg">
            <h1 class="text-2xl md:text-3xl font-bold text-gray-900 tracking-tight">
              SubSkin更懂你
            </h1>
            <p class="mt-2 text-sm text-red-500 dark:text-red-400">
              声明：AI回复仅供参考，不构成诊疗建议。
            </p>
          </div>
          <div class="mt-8 w-full max-w-2xl">
            <SuggestionChips :suggestions="suggestions" @select="handleSuggestion" />
          </div>
        </div>

        <ChatMessage
          v-for="msg in chatStore.messages"
          :key="msg.id"
          :message="msg"
          @save-card="handleSaveCard"
          @dismiss-card="handleDismissCard"
        />
      </div>
    </div>

    <ChatInput
      :max-length="maxQuestionLength"
      :disabled="isGuestQuotaExceeded"
      :show-actions="true"
      :guest-remaining="guestRemaining"
      @send="handleSend"
      @new-chat="startNewChat"
     @toggle-history="showHistoryPanel = !showHistoryPanel"
     />
     </main>
   </div>

  <!-- History Drawer (mobile) -->
  <Teleport to="body">
    <div v-if="showHistoryPanel" class="fixed inset-0 z-50 flex">
      <div class="fixed inset-0 bg-black/50" @click="showHistoryPanel = false"></div>
      <div class="relative w-72 md:w-80 max-w-[80vw] bg-white shadow-xl h-full overflow-y-auto">
        <div class="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-900">历史问答</h3>
          <button class="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" @click="showHistoryPanel = false">✕</button>
        </div>
        <div class="p-3">
          <button
            class="w-full flex items-center justify-center gap-2 bg-primary-600 dark:bg-primary-500 hover:bg-primary-700 dark:hover:bg-primary-600 text-white rounded-lg py-2.5 px-4 text-sm font-medium transition-colors mb-4"
            @click="startNewChat(); showHistoryPanel = false"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
            </svg>
            新建问答
          </button>

          <div v-if="chatStore.conversations.length === 0" class="text-center py-8 text-gray-400  text-sm">
            暂无对话历史
          </div>
          <div v-else class="space-y-1">
            <button
              v-for="conv in chatStore.conversations.slice(0, 20)"
              :key="conv.id"
              class="w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors truncate"
              :class="chatStore.conversationId === conv.id
                ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                : 'text-gray-600  hover:bg-gray-50'"
              @click="selectConversation(conv.id)"
            >
              {{ conv.title }}
            </button>
          </div>
         </div>
       </div>
     </div>
   </Teleport>

   </template>

<style scoped>
.chat-scroll::-webkit-scrollbar {
  width: 4px;
}
.chat-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.chat-scroll::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}
.chat-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}
.dark .chat-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
}
.dark .chat-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}
</style>
