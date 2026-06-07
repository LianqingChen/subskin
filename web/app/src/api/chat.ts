import apiClient from './client'
import type { ActionCard } from '@/types'

export interface Source {
  title: string
  url: string
  snippet: string
}

export interface QuestionResponse {
  answer: string
  sources: Source[]
  remaining_quota?: number
  is_guest?: boolean
}

export interface ConversationListItem {
  id: string
  title: string
  date: string
  created_at: string
}

export interface ConversationMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export const chatApi = {
  async ask(question: string, conversationId: string, mode?: string) {
    const { data } = await apiClient.post('/rag/ask', {
      question,
      conversation_id: conversationId,
      mode,
    })
    return data as QuestionResponse
  },

  async askPublic(question: string, mode?: string) {
    const { data } = await apiClient.post('/rag/ask-public', {
      question,
      mode,
    })
    return data as QuestionResponse
  },

  async getGuestQuota() {
    const { data } = await apiClient.get('/rag/guest-quota')
    return data as { used: number; limit: number; remaining: number }
  },

  async listConversations() {
    const { data } = await apiClient.get('/rag/conversations')
    return data as ConversationListItem[]
  },

  async getConversationMessages(conversationId: string) {
    const { data } = await apiClient.get(`/rag/conversations/${conversationId}/messages`)
    return data as ConversationMessage[]
  },

  async deleteConversation(conversationId: string) {
    await apiClient.delete(`/rag/conversations/${conversationId}`)
  },

  async uploadTemp(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post('/rag/upload-temp', formData)
    return data as { temp_url: string; temp_id: string; mime_type: string; size: number }
  },

  streamAsk(question: string, conversationId: string, mode?: string) {
    return createSSEConnection('/rag/ask-stream', { question, conversation_id: conversationId, mode })
  },

  streamAskWithAttachments(question: string, conversationId: string, attachmentIds: string[], mode?: string) {
    return createSSEConnection('/rag/ask-stream', {
      question,
      conversation_id: conversationId,
      attachment_ids: attachmentIds,
      mode,
    })
  },

  streamAskPublic(question: string, mode?: string) {
    return createSSEConnection('/rag/ask-public-stream', { question, mode })
  },

  streamAskPublicWithAttachments(question: string, attachmentIds: string[], mode?: string) {
    return createSSEConnection('/rag/ask-public-stream', {
      question,
      attachment_ids: attachmentIds,
      mode,
    })
  },

  async confirmAction(
    conversationId: string,
    cardType: string,
    cardData: Record<string, unknown>,
    action: string,
  ) {
    const { data } = await apiClient.post('/rag/confirm-action', {
      conversation_id: conversationId,
      card_type: cardType,
      card_data: cardData,
      action,
    })
    return data
  },
}

function createSSEConnection(endpoint: string, body: Record<string, unknown>) {
  const controller = new AbortController()
  const reader = new SSEStreamReader(endpoint, body, controller)
  return {
    reader,
    cancel() {
      controller.abort()
    },
  }
}

export class SSEStreamReader {
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  private controller: AbortController
  private endpoint: string
  private body: Record<string, unknown>

  onThinking: ((stage: string, message: string) => void) | null = null
  onToken: ((token: string) => void) | null = null
  onActionCard: ((card: ActionCard) => void) | null = null
  onDone: ((data: { sources?: Source[]; remaining_quota?: number; is_guest?: boolean }) => void) | null = null
  onError: ((error: string) => void) | null = null

  constructor(endpoint: string, body: Record<string, unknown>, controller: AbortController) {
    this.endpoint = endpoint
    this.body = body
    this.controller = controller
  }

  async start() {
    const baseURL = '/api'
    const url = `${baseURL}${this.endpoint}`

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    const token = localStorage.getItem('subskin_token')
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    let response: Response
    try {
      response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(this.body),
        signal: this.controller.signal,
      })
    } catch (e: any) {
      this.onError?.(e.message || '网络连接失败')
      return
    }

    if (!response.ok) {
      let detail = response.statusText
      try {
        const errBody = await response.json()
        detail = errBody.detail || detail
      } catch { /* skip */ }
      this.onError?.(detail)
      return
    }

    this.reader = response.body?.getReader() ?? null
    if (!this.reader) {
      this.onError?.('浏览器不支持流式读取')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await this.reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const jsonStr = trimmed.slice(6)
          try {
            const event = JSON.parse(jsonStr)
            if (event.type === 'thinking') {
              this.onThinking?.(event.stage, event.message)
            } else if (event.type === 'token') {
              this.onToken?.(event.content)
            } else if (event.type === 'action_card') {
              this.onActionCard?.(event.card)
            } else if (event.type === 'done') {
              this.onDone?.(event)
            }
          } catch { /* partial SSE data, skip */ }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        this.onError?.(e.message || '流式读取失败')
      }
    }
  }

  cancel() {
    this.controller.abort()
    if (this.reader) {
      this.reader.cancel().catch(() => {})
      this.reader = null
    }
  }
}
