import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi, sanitizeAssistantText, type ConversationListItem } from '@/api/chat'
import type { ActionCard, ChatAttachment, NavSuggestion } from '@/types'
import { timeAgo } from '@/utils/date'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: { title: string; url?: string }[]
  timestamp: number
  isLoading?: boolean
  isSkeleton?: boolean
  thinkingStage?: string
  thinkingMessage?: string
  isVoice?: boolean
  attachments?: ChatAttachment[]
  actionCards?: ActionCard[]
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const conversationId = ref<string>(`conv_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`)
  const isLoading = ref(false)
  const conversations = ref<ConversationListItem[]>([])

  // 结构化导航建议（后端确定性解析下发，非 LLM 生成链接）
  const navSuggestions = ref<NavSuggestion[]>([])

  function setNavSuggestions(items: NavSuggestion[]) {
    navSuggestions.value = items
  }

  function clearNavSuggestions() {
    navSuggestions.value = []
  }

  function addMessage(
    role: 'user' | 'assistant',
    content: string,
    sources?: { title: string; url?: string }[],
    isVoice?: boolean,
    attachments?: ChatAttachment[],
  ) {
    messages.value.push({
      id: `msg_${Date.now()}`,
      role,
      content,
      sources,
      timestamp: Date.now(),
      isVoice,
      attachments,
    })
  }

  function addActionCard(messageId: string, card: ActionCard) {
    const msg = messages.value.find(m => m.id === messageId)
    if (msg) {
      if (!msg.actionCards) msg.actionCards = []
      msg.actionCards.push(card)
    }
  }

  function updateActionCard(messageId: string, cardIndex: number, updates: Record<string, unknown>) {
    const msg = messages.value.find(m => m.id === messageId)
    if (msg && msg.actionCards && msg.actionCards[cardIndex]) {
      Object.assign(msg.actionCards[cardIndex], updates)
    }
  }

  function addThinkingMessage(isVoice?: boolean): string {
    const id = `loading_${Date.now()}`
    messages.value.push({
      id,
      role: 'assistant',
      content: '',
      isSkeleton: true,
      thinkingStage: 'searching',
      thinkingMessage: '正在搜索知识库...',
      timestamp: Date.now(),
      isVoice,
    })
    return id
  }

  function updateThinkingMessage(id: string, stage: string, message: string) {
    const msg = messages.value.find(m => m.id === id)
    if (msg) {
      msg.thinkingStage = stage
      msg.thinkingMessage = message
    }
  }

  function streamTokenToMessage(id: string, token: string) {
    const msg = messages.value.find(m => m.id === id)
    if (msg) {
      msg.isSkeleton = false
      msg.isLoading = false
      // 后端在 LLM 调用失败时会把带原始异常类名的提示作为 token 下发，
      // 展示前需清洗，避免暴露 AuthenticationError 等内部信息
      msg.content = sanitizeAssistantText(msg.content + token)
    }
  }

  function finalizeMessage(id: string, sources?: { title: string; url?: string }[]) {
    const msg = messages.value.find(m => m.id === id)
    if (msg) {
      msg.isSkeleton = false
      msg.isLoading = false
      msg.thinkingStage = undefined
      msg.thinkingMessage = undefined
      if (sources) {
        msg.sources = sources
      }
    }
  }

  function removeMessage(id: string) {
    const idx = messages.value.findIndex(m => m.id === id)
    if (idx >= 0) messages.value.splice(idx, 1)
  }

  function clearChat() {
    messages.value = []
    conversationId.value = `conv_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
  }

  async function loadConversations() {
    try {
      const items = await chatApi.listConversations()
      conversations.value = items.map(item => ({
        ...item,
        date: timeAgo(item.date || item.created_at) || item.date,
      }))
    } catch {
      conversations.value = []
    }
  }

  async function loadConversation(convId: string) {
    try {
      const msgs = await chatApi.getConversationMessages(convId)
      messages.value = msgs.map(m => ({
        id: `msg_${m.id}`,
        role: m.role as 'user' | 'assistant',
        content: m.role === 'assistant' ? sanitizeAssistantText(m.content) : m.content,
        timestamp: new Date(m.created_at).getTime(),
      }))
      conversationId.value = convId
    } catch { /* network error, skip */ }
  }

  async function deleteConversation(convId: string) {
    try {
      await chatApi.deleteConversation(convId)
      conversations.value = conversations.value.filter(c => c.id !== convId)
    } catch { /* network error, skip */ }
  }

  return {
    messages,
    conversationId,
    isLoading,
    conversations,
    navSuggestions,
    setNavSuggestions,
    clearNavSuggestions,
    addMessage,
    addActionCard,
    addThinkingMessage,
    updateThinkingMessage,
    updateActionCard,
    streamTokenToMessage,
    finalizeMessage,
    removeMessage,
    clearChat,
    loadConversations,
    loadConversation,
    deleteConversation,
  }
})
