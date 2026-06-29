const UPLOAD_PREFIX = '/uploads/'
const FILES_PREFIX = '/api/files/serve/'
const ABSOLUTE_URL_RE = /^(?:[a-z]+:)?\/\//i

import DOMPurify from 'dompurify'

// Short-lived, file-serving-only token cache. Preferred over the long-lived
// access token for file URLs so that leaked URLs/referrer/logs only expose a
// token that grants file reads and expires within minutes. Falls back to the
// access token if no file token has been issued yet (e.g. before login
// completes the preflight fetch).
const FILE_TOKEN_KEY = 'subskin_file_token'
const FILE_TOKEN_EXPIRES_KEY = 'subskin_file_token_expires'

let fileTokenPromise: Promise<string | null> | null = null

function getCachedFileToken(): string | null {
  if (typeof window === 'undefined') return null
  const token = window.localStorage.getItem(FILE_TOKEN_KEY)
  if (!token) return null
  const expiresAt = Number(window.localStorage.getItem(FILE_TOKEN_EXPIRES_KEY) || 0)
  // Refresh slightly before the real expiry to avoid race conditions.
  if (!expiresAt || Date.now() >= expiresAt - 30_000) return null
  return token
}

function setCachedFileToken(token: string, expiresInSeconds: number): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(FILE_TOKEN_KEY, token)
  window.localStorage.setItem(
    FILE_TOKEN_EXPIRES_KEY,
    String(Date.now() + expiresInSeconds * 1000),
  )
}

/**
 * Lazily fetch (and cache) a short-lived file token. Called from the auth
 * store after login and from a background refresher. Renders do NOT await
 * this — `appendAccessToken` falls back to the access token if the file token
 * is not yet available, so images always load.
 */
export async function ensureFileToken(): Promise<void> {
  if (getCachedFileToken()) return
  if (fileTokenPromise) {
    await fileTokenPromise
    return
  }
  const access = window.localStorage.getItem('subskin_token')
  if (!access) return
  fileTokenPromise = (async () => {
    try {
      // Lazy import to avoid a circular dependency with the api client.
      const { authApi } = await import('../api/auth')
      const { token, expires_in } = await authApi.getFileAccessToken()
      setCachedFileToken(token, expires_in)
      return token
    } catch {
      return null
    } finally {
      fileTokenPromise = null
    }
  })()
  await fileTokenPromise
}

export function clearFileToken(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(FILE_TOKEN_KEY)
  window.localStorage.removeItem(FILE_TOKEN_EXPIRES_KEY)
}

function appendAccessToken(url: string): string {
  if (typeof window === 'undefined') return url
  // Prefer the scoped, short-lived file token; fall back to the access token.
  const token = getCachedFileToken() || window.localStorage.getItem('subskin_token')
  if (!token) return url

  const parsed = new URL(url, window.location.origin)
  if (!parsed.searchParams.has('access_token')) {
    parsed.searchParams.set('access_token', token)
  }
  return `${parsed.pathname}${parsed.search}${parsed.hash}`
}

export function toProtectedFileUrl(url?: string | null): string {
  if (!url) return ''
  if (url.startsWith('data:') || url.startsWith('blob:') || ABSOLUTE_URL_RE.test(url)) {
    return url
  }

  if (url.startsWith(FILES_PREFIX)) {
    return appendAccessToken(url)
  }

  if (!url.startsWith(UPLOAD_PREFIX)) {
    return url
  }

  const relativePath = url.slice(UPLOAD_PREFIX.length)
  return appendAccessToken(`${FILES_PREFIX}${relativePath}`)
}

export function rewriteProtectedHtml(html?: string | null): string {
  if (!html) return ''
  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') {
    return html
  }

  // Sanitize first to strip <script>, event handlers, <iframe>, etc.
  // User post content is rendered via v-html, so without sanitization any
  // stored XSS payload (e.g. <img onerror=...> or <script>) would execute.
  // DOMPurify is configured to keep the rich-text tags we support while
  // dropping anything executable. The ALLOWED_ATTR list is deliberately
  // permissive for presentation but excludes on* handlers.
  let safeHtml: string
  try {
    safeHtml = DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [
        'p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'h1', 'h2', 'h3', 'h4',
        'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'span',
        'div', 'img', 'a', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'figure', 'figcaption', 'video', 'audio', 'source',
      ],
      ALLOWED_ATTR: ['src', 'href', 'alt', 'title', 'class', 'style', 'target', 'rel', 'controls', 'width', 'height'],
      ALLOW_DATA_ATTR: false,
    })
  } catch {
    // If DOMPurify fails to load, fall back to a strict strip of scripts/event
    // handlers rather than rendering raw HTML.
    safeHtml = html
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/\son\w+\s*=\s*"[^"]*"/gi, '')
      .replace(/\son\w+\s*=\s*'[^']*'/gi, '')
      .replace(/\son\w+\s*=\s*[^\s>]+/gi, '')
      .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
  }

  const parser = new DOMParser()
  const document = parser.parseFromString(safeHtml, 'text/html')

  document.querySelectorAll<HTMLElement>('[src], [href]').forEach((element) => {
    const src = element.getAttribute('src')
    if (src) {
      element.setAttribute('src', toProtectedFileUrl(src))
    }

    const href = element.getAttribute('href')
    if (href) {
      element.setAttribute('href', toProtectedFileUrl(href))
    }
  })

  return document.body.innerHTML
}
