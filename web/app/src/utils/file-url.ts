const UPLOAD_PREFIX = '/uploads/'
const FILES_PREFIX = '/api/files/serve/'
const ABSOLUTE_URL_RE = /^(?:[a-z]+:)?\/\//i

function appendAccessToken(url: string): string {
  if (typeof window === 'undefined') return url
  const token = window.localStorage.getItem('subskin_token')
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

  const parser = new DOMParser()
  const document = parser.parseFromString(html, 'text/html')

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
