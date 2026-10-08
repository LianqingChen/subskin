import { computed, ref } from 'vue'
import { chatApi } from '@/api/chat'
import { useAuthStore } from '@/stores/auth'
import { useButlerStore } from '@/stores/butler'
import { useChatStore } from '@/stores/chat'
import type { ActionCard } from '@/types'

export interface PendingAttachment {
  tempId: string
  name: string
  mimeType: string
}

/**
 * 小白管家聊天逻辑：与全屏问答页共享 useChatStore 会话（记录连续），
 * 问答走 butler 模式（统一人格），陪伴切换走 counseling 模式。
 * 附件先上传临时文件（确认保存前不入库），行动卡片由用户确认后才落库。
 */
export function useButlerChat() {
  const chatStore = useChatStore()
  const authStore = useAuthStore()
  const butlerStore = useButlerStore()

  const attachments = ref<PendingAttachment[]>([])
  const isUploading = ref(false)

  const isStreaming = computed(() => chatStore.messages.some(m => m.isSkeleton))
  const hasMessages = computed(() => chatStore.messages.length > 0)

  async function sendMessage(text: string) {
    const t = text.trim()
    if (!t || isStreaming.value) return

    butlerStore.clearNavSuggestions()
    chatStore.addMessage('user', t)
    const skeletonId = chatStore.addThinkingMessage()

    const attachmentIds = attachments.value.map(a => a.tempId)
    attachments.value = []

    const mode = butlerStore.mode === 'counseling' ? 'counseling' : 'butler'
    try {
      const stream =
        authStore.isLoggedIn && attachmentIds.length > 0
          ? chatApi.streamAskWithAttachments(t, chatStore.conversationId, attachmentIds, mode)
          : authStore.isLoggedIn
            ? chatApi.streamAsk(t, chatStore.conversationId, mode)
            : chatApi.streamAskPublic(t, mode)

      stream.reader.onThinking = (stage: string, message: string) => {
        chatStore.updateThinkingMessage(skeletonId, stage, message)
      }
      stream.reader.onToken = (token: string) => {
        chatStore.streamTokenToMessage(skeletonId, token)
      }
      stream.reader.onActionCard = (card: ActionCard) => {
        chatStore.addActionCard(skeletonId, card)
      }
      stream.reader.onNavigation = items => {
        butlerStore.setNavSuggestions(items)
      }
      stream.reader.onDone = data => {
        chatStore.finalizeMessage(skeletonId, data.sources)
      }
      stream.reader.onError = (error: string) => {
        chatStore.removeMessage(skeletonId)
        if (error.includes('已用完') || error.includes('429')) {
          chatStore.addMessage('assistant', '今日免费体验次数已用完，请登录后继续使用AI助手')
        } else {
          chatStore.addMessage('assistant', `抱歉，${error}`)
        }
      }
      await stream.reader.start()
    } catch {
      chatStore.removeMessage(skeletonId)
      chatStore.addMessage('assistant', '出了点问题，请稍后再试～')
    }
  }

  /** 上传附件为临时文件（不写入业务表；用户确认保存前只是临时的） */
  async function addAttachment(file: File) {
    if (!authStore.isLoggedIn) {
      throw new Error('访客暂不支持附件分析，请登录后使用')
    }
    if (attachments.value.length >= 3) {
      throw new Error('一次最多上传 3 个附件')
    }
    isUploading.value = true
    try {
      const res = await chatApi.uploadTemp(file)
      attachments.value.push({
        tempId: res.temp_id,
        name: file.name || res.temp_url,
        mimeType: res.mime_type,
      })
    } finally {
      isUploading.value = false
    }
  }

  function removeAttachment(tempId: string) {
    attachments.value = attachments.value.filter(a => a.tempId !== tempId)
  }

  /** 用户点击行动卡片按钮：save / share / discard，由后端 confirm-action 落库 */
  async function confirmAction(
    messageId: string,
    cardIndex: number,
    card: ActionCard,
    action: 'save' | 'share' | 'discard',
  ) {
    try {
      const res = await chatApi.confirmAction(
        chatStore.conversationId,
        card.type,
        card as unknown as Record<string, unknown>,
        action,
      )
      chatStore.updateActionCard(messageId, cardIndex, { saved: res.success } as Partial<ActionCard>)
      return res.message
    } catch {
      return '操作失败，请稍后再试'
    }
  }

  return {
    attachments,
    isUploading,
    isStreaming,
    hasMessages,
    sendMessage,
    addAttachment,
    removeAttachment,
    confirmAction,
  }
}
