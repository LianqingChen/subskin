import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

export interface ArchiveHeading { id: string; text: string; level: number }

export function resolveDocumentLink(href: string, currentPath: string): string | null {
  let path: string
  try { path = decodeURIComponent(href.split('#')[0] ?? '') } catch { return null }
  if (!path || /[\u0000-\u001f\\]/.test(path) || path.startsWith('//') || /^[a-z][a-z\d+.-]*:/i.test(path)) return null
  const marker = '/root/subskin/'
  if (path.includes(marker)) path = path.slice(path.indexOf(marker) + marker.length)
  else if (path.startsWith('/')) path = path.slice(1)
  else path = currentPath.split('/').slice(0, -1).join('/') + '/' + path
  const parts: string[] = []
  for (const part of path.split('/')) {
    if (part === '..') { if (!parts.length) return null; parts.pop() }
    else if (part && part !== '.') parts.push(part)
  }
  const normalized = parts.join('/')
  return /\.md$/i.test(normalized) ? normalized : null
}

export function renderArchiveMarkdown(content: string, currentPath: string) {
  const headings: ArchiveHeading[] = []
  const md = new MarkdownIt({ html: false, linkify: false, breaks: false })
  md.renderer.rules.image = (tokens, index) => `<span class="archive-image-note">[图片：${md.utils.escapeHtml(tokens[index]?.content || '附件')}，未加载]</span>`
  md.renderer.rules.link_open = (tokens, index, options, _env, renderer) => {
    const token = tokens[index]
    if (!token) return ''
    const href = token.attrGet('href') ?? ''
    if (/^https?:\/\//i.test(href)) {
      token.attrSet('target', '_blank'); token.attrSet('rel', 'noopener noreferrer')
    } else if (href.startsWith('#')) {
      token.attrSet('data-section', href.slice(1)); token.attrSet('href', '#')
    } else {
      const path = resolveDocumentLink(href, currentPath)
      token.attrSet('href', '#')
      if (path) token.attrSet('data-document', path)
      else { token.attrSet('aria-disabled', 'true'); token.attrSet('title', '此链接不属于可阅读的规划文档') }
    }
    return renderer.renderToken(tokens, index, options)
  }
  const tokens = md.parse(content, {})
  tokens.forEach((token, index) => {
    if (token.type === 'heading_open') {
      const id = `archive-section-${headings.length}`
      token.attrSet('id', id)
      headings.push({ id, text: tokens[index + 1]?.content ?? '', level: Number(token.tag.slice(1)) })
    }
    // Task lists remain read-only and do not create interactive form controls.
    if (token.type === 'inline' && token.children?.[0]?.type === 'text') {
      const child = token.children[0]
      child.content = child.content.replace(/^\[ \]\s/, '☐ ').replace(/^\[[xX]\]\s/, '☑ ')
    }
  })
  const html = DOMPurify.sanitize(md.renderer.render(tokens, md.options, {}), {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 's', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li',
      'blockquote', 'code', 'pre', 'span', 'a', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'title', 'id', 'class', 'start', 'aria-disabled', 'data-document', 'data-section'],
    ALLOW_DATA_ATTR: false,
  })
  return { html, headings }
}
