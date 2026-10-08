import apiClient from './client'
import type { ActionCard, NavSuggestion } from '@/types'

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

/**
 * 将后端/网络异常转为用户友好文案，
 * 避免向用户暴露 AuthenticationError 等原始异常类型。
 */
function toFriendlyError(raw: string): string {
  const text = String(raw || '')
  // 额度/限流类保留原文（包含业务语义，供页面进一步判断）
  if (text.includes('已用完') || text.includes('429') || text.includes('quota')) return text
  if (/AuthenticationError|Unauthorized|Forbidden|凭证|token/i.test(text)) {
    return 'AI 服务授权异常，请稍后再试'
  }
  if (/RateLimit|限流|TooManyRequests/i.test(text)) {
    return 'AI 服务暂时繁忙，请稍后再试'
  }
  if (/Timeout|超时/i.test(text)) {
    return 'AI 服务响应超时，请稍后再试'
  }
  // 其他包含异常类型名/英文错误的兜底为友好文案
  if (/[A-Z]\w*(Error|Exception)|failed|error/i.test(text)) {
    return 'AI 服务暂时不可用，请稍后再试'
  }
  return text || 'AI 服务暂时繁忙，请稍后再试'
}

/**
 * 清洗 AI 回答正文：后端在 LLM 调用失败时会把
 * "AI 问答服务暂时不可用，请稍后再试。（错误: AuthenticationError）" 这样的
 * 文本直接作为流式 token 下发（非 HTTP 错误路径，toFriendlyError 拦不到），
 * 需在展示前剥离“（错误: ...）”后缀及任何原始异常类名。
 */
export function sanitizeAssistantText(text: string): string {
  if (!text) return text
  // 剥离"（错误: XxxError）" / "(错误: ...)" 整段后缀
  let cleaned = text.replace(/[（(]\s*错误\s*[:：][^（）()]*?[）)]/g, '').trimEnd()
  // 若仍暴露原始异常类名（如 AuthenticationError / TimeoutException），整体替换
  if (/[A-Z][A-Za-z0-9_]*(Error|Exception)/.test(cleaned)) {
    return 'AI 服务暂时繁忙，请稍后再试'
  }
  return cleaned
}

export class SSEStreamReader {
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  private controller: AbortController
  private endpoint: string
  private body: Record<string, unknown>

  onThinking: ((stage: string, message: string) => void) | null = null
  onToken: ((token: string) => void) | null = null
  onActionCard: ((card: ActionCard) => void) | null = null
  onNavigation: ((items: NavSuggestion[]) => void) | null = null
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
      this.onError?.(toFriendlyError(e.message || '网络连接失败'))
      return
    }

    if (!response.ok) {
      let detail = response.statusText
      try {
        const errBody = await response.json()
        detail = errBody.detail || detail
      } catch { /* skip */ }
      this.onError?.(toFriendlyError(detail))
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
            } else if (event.type === 'navigation') {
              this.onNavigation?.(event.items)
            } else if (event.type === 'done') {
              this.onDone?.(event)
            }
          } catch { /* partial SSE data, skip */ }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        this.onError?.(toFriendlyError(e.message || '流式读取失败'))
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
