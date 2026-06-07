<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { chatApi, SSEStreamReader } from '@/api/chat'
import { useToast } from '@/composables/useToast'
import { trackEvent } from '@/composables/useTracking'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import SuggestionChips from '@/components/chat/SuggestionChips.vue'
import type { Source } from '@/types'

const props = defineProps<{
  show: boolean
  contextHint?: string
}>()

const emit = defineEmits<{
  close: []
}>()

const authStore = useAuthStore()
const chatStore = useChatStore()
const toast = useToast()

const messagesContainer = ref<HTMLElement | null>(null)
const guestRemaining = ref<number | null>(null)
const guestLimit = 3
const currentSources = ref<Source[]>([])
const activeStream = ref<{ cancel: () => void } | null>(null)
const showHistoryPanel = ref(false)

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
  } catch { guestRemaining.value = guestLimit }
}

function scrollToBottom() {
  nextTick(() => { messagesContainer.value?.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' }) })
}

async function handleSend(text: string, isVoice: boolean = false, files?: Array<{ file: File; preview?: string; id: string }>) {
  if (!text.trim() && (!files || files.length === 0)) return
  if (isGuestQuotaExceeded.value) {
    chatStore.addMessage('assistant', '今日免费体验次数已用完，请登录后继续使用AI助手，解锁更多功能。')
    authStore.showLoginModal = true
    return
  }

  const attachments: Array<{ id: string; type: 'image' | 'document'; url: string; name: string; size: number; mimeType: string; thumbnailUrl?: string }> = []
  const attachmentIds: string[] = []
  if (files && files.length > 0 && authStore.isLoggedIn) {
    for (const f of files) {
      try {
        const result = await chatApi.uploadTemp(f.file)
        attachmentIds.push(result.temp_id)
        attachments.push({ id: result.temp_id, type: f.file.type.startsWith('image/') ? 'image' : 'document', url: result.temp_url, name: f.file.name, size: result.size, mimeType: f.file.type, thumbnailUrl: f.preview })
      } catch { toast.error(`文件 ${f.file.name} 上传失败`) }
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
      stream = attachmentIds.length > 0 ? chatApi.streamAskWithAttachments(text, chatStore.conversationId, attachmentIds) : chatApi.streamAsk(text, chatStore.conversationId)
    } else {
      stream = attachmentIds.length > 0 ? chatApi.streamAskPublicWithAttachments(text, attachmentIds) : chatApi.streamAskPublic(text)
    }
    await handleStream(stream.reader, stream.cancel, thinkingMsgId)
  } catch (e: any) {
    chatStore.removeMessage(thinkingMsgId)
    if (e?.response?.status === 401) { toast.warning('登录已过期，请重新登录'); authStore.logout(); authStore.showLoginModal = true }
    else if (e?.response?.status === 429) { chatStore.addMessage('assistant', '今日免费体验次数已用完'); guestRemaining.value = 0 }
    else { chatStore.addMessage('assistant', '抱歉，请求出错了，请稍后再试。') }
  } finally { chatStore.isLoading = false; scrollToBottom() }
}

async function handleStream(reader: SSEStreamReader, cancel: () => void, thinkingMsgId: string) {
  activeStream.value = { cancel }
  reader.onThinking = (stage: string, message: string) => { chatStore.updateThinkingMessage(thinkingMsgId, stage, message); scrollToBottom() }
  reader.onToken = (token: string) => { chatStore.streamTokenToMessage(thinkingMsgId, token); scrollToBottom() }
  reader.onActionCard = (card: any) => { chatStore.addActionCard(thinkingMsgId, card); scrollToBottom() }
  reader.onDone = (data: { sources?: Source[]; remaining_quota?: number; is_guest?: boolean }) => {
    chatStore.finalizeMessage(thinkingMsgId, data.sources)
    currentSources.value = data.sources || []
    if (data.remaining_quota !== undefined) guestRemaining.value = data.remaining_quota
    activeStream.value = null
  }
  reader.onError = (error: string) => {
    chatStore.removeMessage(thinkingMsgId)
    if (error.includes('已用完') || error.includes('429')) { chatStore.addMessage('assistant', '今日免费体验次数已用完，请登录后继续使用。'); guestRemaining.value = 0 }
    else if (error.includes('白癜风') || error.includes('皮肤健康') || error.includes('话题')) { chatStore.addMessage('assistant', error) }
    else { chatStore.addMessage('assistant', `抱歉，请求出错了，请稍后再试。（${error}）`) }
    activeStream.value = null
  }
  await reader.start()
}

function handleSuggestion(text: string) { handleSend(text, false) }

function startNewChat() {
  if (activeStream.value) { activeStream.value.cancel(); activeStream.value = null }
  chatStore.clearChat()
  currentSources.value = []
}

async function handleSaveCard(messageId: string, cardIndex: number, privacy?: string) {
  const msg = chatStore.messages.find(m => m.id === messageId)
  if (!msg?.actionCards?.[cardIndex]) return
  const card = msg.actionCards[cardIndex]
  const action = card.type === 'diary' ? (privacy === 'public' ? 'share' : 'save') : 'save'
  try {
    await chatApi.confirmAction(chatStore.conversationId, card.type, { ...card }, action)
    chatStore.updateActionCard(messageId, cardIndex, { saved: true, privacy: privacy || 'private' })
    toast.success('保存成功')
  } catch { toast.error('保存失败') }
}

function handleDismissCard(messageId: string, cardIndex: number) {
  chatStore.updateActionCard(messageId, cardIndex, { saved: true })
}

async function selectConversation(id: string) {
  if (authStore.isLoggedIn) { await chatStore.loadConversation(id); scrollToBottom(); showHistoryPanel.value = false }
}

watch(() => props.show, (visible) => {
  if (visible) { fetchGuestQuota(); scrollToBottom() }
})

watch(() => chatStore.messages.length, () => scrollToBottom())

onMounted(() => {
  fetchGuestQuota()
  if (authStore.isLoggedIn) chatStore.loadConversations()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="chat-slide">
      <div v-if="show" class="fixed inset-0 z-40 flex flex-col bg-white">
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800 bg-white sticky top-0 z-10">
          <button class="flex items-center gap-1.5 px-2 py-1.5 -ml-2 rounded-lg text-gray-700 bg-gray-100 hover:bg-gray-200 dark:hover:bg-gray-300 active:scale-95 transition-all" @click="emit('close')">
            <i class="ri-arrow-left-s-line text-xl"></i>
            <span class="text-sm font-medium">返回</span>
          </button>
          <div class="flex items-center gap-1.5">
            <i class="ri-robot-3-line text-primary-500 text-lg"></i>
            <span class="font-semibold text-gray-900">AI助手</span>
          </div>
          <div class="flex items-center gap-1">
            <button class="p-2 rounded-lg text-gray-500  hover:bg-gray-100 dark:hover:bg-gray-300 transition-colors" title="新建问答" @click="startNewChat">
              <i class="ri-add-line text-lg"></i>
            </button>
            <button class="p-2 rounded-lg text-gray-500  hover:bg-gray-100 dark:hover:bg-gray-300 transition-colors" title="历史" @click="showHistoryPanel = !showHistoryPanel">
              <i class="ri-history-line text-lg"></i>
            </button>
          </div>
        </div>

        <!-- Context hint -->
        <div v-if="contextHint" class="px-4 py-2 bg-primary-50 dark:bg-primary-900/20 border-b border-primary-100 dark:border-primary-800">
          <p class="text-xs text-primary-700 dark:text-primary-300 flex items-center gap-1.5">
            <i class="ri-focus-3-line"></i> {{ contextHint }}
          </p>
        </div>

        <!-- Messages -->
        <div ref="messagesContainer" class="flex-1 overflow-y-auto">
          <div class="max-w-4xl mx-auto px-4 py-4">
            <div v-if="isWelcome" class="flex flex-col items-center pt-4 pb-4">
              <h1 class="text-xl md:text-2xl font-bold text-gray-900 tracking-tight">SubSkin更懂你</h1>
              <p class="mt-2 text-xs text-red-500 dark:text-red-400">声明：AI回复仅供参考，不构成诊疗建议。</p>
              <div class="mt-6 w-full max-w-2xl">
                <SuggestionChips :suggestions="suggestions" @select="handleSuggestion" />
              </div>
            </div>
            <ChatMessage v-for="msg in chatStore.messages" :key="msg.id" :message="msg" @save-card="handleSaveCard" @dismiss-card="handleDismissCard" />
          </div>
        </div>

        <!-- Input -->
        <ChatInput :max-length="maxQuestionLength" :disabled="isGuestQuotaExceeded" :show-actions="false" :guest-remaining="guestRemaining" @send="handleSend" @new-chat="startNewChat" @toggle-history="showHistoryPanel = !showHistoryPanel" />
      </div>
    </Transition>

    <!-- History Drawer -->
    <Teleport to="body">
      <div v-if="showHistoryPanel && show" class="fixed inset-0 z-50 flex">
        <div class="fixed inset-0 bg-black/50" @click="showHistoryPanel = false" />
        <div class="relative w-72 md:w-80 max-w-[80vw] bg-white shadow-xl h-full overflow-y-auto">
          <div class="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-lg font-semibold text-gray-900">历史问答</h3>
            <button class="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" @click="showHistoryPanel = false"><i class="ri-close-line text-lg"></i></button>
          </div>
          <div class="p-3">
            <button class="w-full flex items-center justify-center gap-2 bg-primary-600 dark:bg-primary-500 hover:bg-primary-700 text-white rounded-lg py-2.5 px-4 text-sm font-medium mb-4" @click="startNewChat(); showHistoryPanel = false">
              <i class="ri-add-line"></i> 新建问答
            </button>
            <div v-if="chatStore.conversations.length === 0" class="text-center py-8 text-gray-400 text-sm">暂无对话历史</div>
            <div v-else class="space-y-1">
              <button v-for="conv in chatStore.conversations.slice(0, 20)" :key="conv.id" class="w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors truncate" :class="chatStore.conversationId === conv.id ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium' : 'text-gray-600  hover:bg-gray-50 dark:hover:bg-gray-300'" @click="selectConversation(conv.id)">{{ conv.title }}</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </Teleport>
</template>

<style scoped>
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.chat-slide-enter-from,
.chat-slide-leave-to {
  transform: translateY(100%);
}
</style>
