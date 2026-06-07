<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { chatApi } from '@/api/chat'
import type { ActionCard } from '@/types'

const chatStore = useChatStore()
const authStore = useAuthStore()

const showHistory = ref(false)
const guestRemaining = ref<number | null>(null)

const isStreaming = computed(() => chatStore.messages.some(m => m.isSkeleton))
const hasMessages = computed(() => chatStore.messages.length > 0)

async function sendMessage(text?: string) {
  const t = (text || '').trim()
  if (!t || isStreaming.value) return

  chatStore.addMessage('user', t)
  const skeletonId = chatStore.addThinkingMessage()
  try {
    const stream = authStore.isLoggedIn
      ? chatApi.streamAsk(t, chatStore.conversationId, 'knowledge')
      : chatApi.streamAskPublic(t, 'knowledge')
    stream.reader.onThinking = (stage: string, message: string) => {
      chatStore.updateThinkingMessage(skeletonId, stage, message)
    }
    stream.reader.onToken = (token: string) => {
      chatStore.streamTokenToMessage(skeletonId, token)
    }
    stream.reader.onActionCard = (card: ActionCard) => {
      chatStore.addActionCard(skeletonId, card)
    }
    stream.reader.onDone = (data: { sources?: { title: string; url?: string }[]; remaining_quota?: number }) => {
      chatStore.finalizeMessage(skeletonId, data.sources)
      if (data.remaining_quota !== undefined) guestRemaining.value = data.remaining_quota
    }
    stream.reader.onError = (error: string) => {
      chatStore.removeMessage(skeletonId)
if (error.includes('已用完') || error.includes('429')) {
    chatStore.addMessage('assistant', '今日免费体验次数已用完，请登录后继续使用AI助手')
        guestRemaining.value = 0
      } else {
        chatStore.addMessage('assistant', `抱歉，${error}`)
      }
    }
    await stream.reader.start()
  } catch (e: any) {
    chatStore.removeMessage(skeletonId)
    chatStore.addMessage('assistant', '出了点问题，请稍后再试～')
  }
}

function newConversation() { chatStore.clearChat(); showHistory.value = false }

async function loadConversation(convId: string) {
  await chatStore.loadConversation(convId)
  showHistory.value = false
}

function toggleHistory() { showHistory.value = !showHistory.value }

onMounted(async () => {
  if (authStore.isLoggedIn) await chatStore.loadConversations()
  if (!authStore.isLoggedIn) {
    try { const q = await chatApi.getGuestQuota(); guestRemaining.value = q.remaining } catch { guestRemaining.value = 3 }
  }
})

defineExpose({ sendMessage, toggleHistory })
</script>

<template>
  <div>
    <!-- History sidebar overlay -->
    <Transition name="slide">
      <div v-if="showHistory" class="fixed inset-0 z-30 flex">
        <div class="w-72 bg-white border-r border-gray-100 shadow-xl flex flex-col">
          <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span class="text-sm font-medium text-gray-800">历史对话</span>
            <button @click="showHistory = false" class="text-gray-400 hover:text-gray-600">&times;</button>
          </div>
          <div class="flex-1 overflow-y-auto p-2 space-y-1">
            <button @click="newConversation()" class="w-full text-left px-3 py-2 rounded-lg text-sm text-primary-600 hover:bg-primary-50 transition-colors">+ 新建对话</button>
            <div v-if="chatStore.conversations.length === 0" class="text-xs text-gray-400 px-3 py-2">暂无历史对话</div>
            <button v-for="conv in chatStore.conversations" :key="conv.id" @click="loadConversation(conv.id)" class="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-gray-50 transition-colors group">
              <div class="truncate text-gray-700">{{ conv.title || '新对话' }}</div>
              <div class="text-[10px] text-gray-400 mt-0.5">{{ conv.date }}</div>
            </button>
          </div>
        </div>
        <div class="flex-1 bg-black/10" @click="showHistory = false" />
      </div>
    </Transition>

    <!-- Guest quota -->
    <div v-if="!authStore.isLoggedIn && guestRemaining !== null && !hasMessages" class="text-center pb-2 space-y-1">
      <span class="text-[10px] text-gray-400">今日剩余 {{ guestRemaining }} 次免费提问</span>
      <button v-if="guestRemaining !== null && guestRemaining <= 1" type="button" class="block mx-auto text-[10px] text-primary-500 hover:text-primary-600" @click="authStore.showLoginModal = true">登录获取更多提问次数 →</button>
    </div>

    <!-- Messages -->
    <div v-if="hasMessages" class="space-y-3 pb-2">
      <div v-for="msg in chatStore.messages" :key="msg.id" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
        <div class="max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed"
          :class="msg.role === 'user' ? 'bg-primary-500 text-white rounded-br-md' : 'bg-gray-50 text-gray-800 rounded-bl-md'">
          <div v-if="msg.isSkeleton && !msg.content" class="flex items-center gap-2 text-primary-500">
            <span class="inline-flex gap-1">
              <span class="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style="animation-delay:0s" />
              <span class="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style="animation-delay:0.15s" />
              <span class="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style="animation-delay:0.3s" />
            </span>
            <span class="text-xs text-gray-400">{{ msg.thinkingMessage || '正在检索相关知识...' }}</span>
          </div>
          <div v-else class="answer-content">
            <span class="whitespace-pre-wrap">{{ msg.content }}</span>
            <span v-if="msg.isSkeleton && msg.content" class="inline-block w-1 h-4 bg-primary-400 ml-0.5 animate-pulse align-text-bottom rounded-sm" />
          </div>
          <div v-if="msg.sources && msg.sources.length > 0 && !msg.isSkeleton" class="mt-3 pt-3 border-t border-gray-100">
            <p class="text-[11px] font-medium text-gray-500 mb-1.5">参考来源</p>
            <a v-for="(src, si) in msg.sources" :key="si" :href="src.url || '#'" target="_blank" rel="noopener" class="block text-[11px] text-primary-600 hover:text-primary-800 truncate mb-1 last:mb-0 transition-colors">{{ si + 1 }}. {{ src.title }}</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.answer-content {
  max-height: 50vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  /* Allow scroll to chain up to chat-scroll when at boundary */
  overscroll-behavior-y: auto;
}
.answer-content::-webkit-scrollbar {
  width: 3px;
}
.answer-content::-webkit-scrollbar-track {
  background: transparent;
}
.answer-content::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.18);
  border-radius: 3px;
}
.dark .answer-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.18);
}

.slide-enter-active, .slide-leave-active { transition: all 0.25s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateX(-20px); }
</style>
