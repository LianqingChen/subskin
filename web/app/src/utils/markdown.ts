import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

/**
 * 智能问答等 AI 文本的 markdown 渲染。
 *
 * - html:false：不渲染输入中的原始 HTML（防 XSS），markdown-it 会转义。
 * - linkify/breaks：自动识别链接、单个换行转 <br>（聊天场景更友好）。
 * - 输出再经 DOMPurify 二次兜底，并把 http(s) 链接设为新窗口打开。
 */

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

const defaultLinkOpen =
  md.renderer.rules.link_open ||
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const href = token.attrGet('href') || ''
  if (/^https?:\/\//i.test(href)) {
    token.attrSet('target', '_blank')
    token.attrSet('rel', 'noopener noreferrer')
  }
  return defaultLinkOpen(tokens, idx, options, env, self)
}

export function renderMarkdown(text: string): string {
  if (!text) return ''
  const rawHtml = md.render(text)
  try {
    return DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS: [
        'p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'h1', 'h2', 'h3', 'h4',
        'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'span',
        'div', 'img', 'a', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      ],
      ALLOWED_ATTR: ['src', 'href', 'alt', 'title', 'target', 'rel'],
      ALLOW_DATA_ATTR: false,
    })
  } catch {
    return rawHtml.replace(/<[^>]*>/g, '')
  }
}
