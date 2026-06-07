import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { imApi } from '@/api/im'
import { useWebSocket } from '@/composables/useWebSocket'

interface Conversation {
  id: number
  type: string
  name?: string
  avatar?: string
  peer_user?: { id: number; username: string; avatar_url?: string }
  last_message?: any
  unread_count: number
  is_pinned: boolean
  is_muted: boolean
  last_message_at?: string
}

interface Message {
  id: number
  conversation_id: number
  sender_id: number
  sender_name: string
  msg_type: string
  content?: string
  metadata?: any
  status: string
  is_recalled: boolean
  created_at: string
}

export const useImStore = defineStore('im', () => {
  const conversations = ref<Conversation[]>([])
  const currentMessages = ref<Message[]>([])
  const activeConversationId = ref<number | null>(null)
  const totalUnread = computed(() =>
    conversations.value.reduce((sum, c) => sum + c.unread_count, 0),
  )
  const { connect, on, connected } = useWebSocket()

  async function loadConversations() {
    try {
      const res = await imApi.getConversations()
      conversations.value = res.data.items
    } catch (e) {
      console.error('load conversations failed', e)
    }
  }

  async function openConversation(convId: number) {
    activeConversationId.value = convId
    try {
      const res = await imApi.getMessages(convId)
      currentMessages.value = res.data.items
      await imApi.markRead(convId)
      await loadConversations()
    } catch (e) {
      console.error('load messages failed', e)
    }
  }

  async function sendMessage(
    content: string,
    msgType = 'text',
    metadata?: any,
  ) {
    if (!activeConversationId.value) return
    try {
      const res = await imApi.sendMessage({
        conversation_id: activeConversationId.value,
        msg_type: msgType,
        content,
        metadata,
      })
      currentMessages.value.push(res.data)
      await loadConversations()
    } catch (e) {
      console.error('send message failed', e)
    }
  }

  function initWS() {
    connect()
    on('message.new', (data: any) => {
      if (data.data.conversation_id === activeConversationId.value) {
        currentMessages.value.push(data.data)
      }
      loadConversations()
    })
    on('message.recall', (data: any) => {
      const msg = currentMessages.value.find(
        (m) => m.id === data.message_id,
      )
      if (msg) {
        msg.is_recalled = true
        msg.content = '[消息已撤回]'
      }
    })
    on('unread_update', () => {
      loadConversations()
    })
  }

  return {
    conversations,
    currentMessages,
    activeConversationId,
    totalUnread,
    connected,
    loadConversations,
    openConversation,
    sendMessage,
    initWS,
  }
})
