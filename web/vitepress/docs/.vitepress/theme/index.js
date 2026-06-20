import DefaultTheme from 'vitepress/theme'
import './custom.css'

const SPA_ROUTES = ['/chat', '/tracker', '/community', '/profile', '/knowledge']

function applyEmbeddedMode() {
  const params = new URLSearchParams(window.location.search)
  const isEmbedded = params.has('embedded') || sessionStorage.getItem('subskin-embedded') === '1'
  if (isEmbedded) {
    document.documentElement.classList.add('embedded-mode')
    sessionStorage.setItem('subskin-embedded', '1')
  } else {
    document.documentElement.classList.remove('embedded-mode')
    sessionStorage.removeItem('subskin-embedded')
  }
}

function isSpaRoute(href) {
  if (!href) return false
  if (SPA_ROUTES.some(route => href === route || href === route + '/')) return true
  try {
    const url = new URL(href, window.location.origin)
    return SPA_ROUTES.some(route => url.pathname === route || url.pathname === route + '/')
  } catch {
    return false
  }
}

export default {
  ...DefaultTheme,
  enhanceApp({ app }) {
    if (typeof window !== 'undefined') {
      applyEmbeddedMode()

      window.addEventListener('click', (e) => {
        const link = e.target.closest('a')
        if (!link) return
        const href = link.getAttribute('href')
        if (!href) return
        const isEmbedded = sessionStorage.getItem('subskin-embedded') === '1'

        if (isSpaRoute(href)) {
          e.preventDefault()
          if (isEmbedded) {
            let spaPath = href
            try { spaPath = new URL(href, window.location.origin).pathname } catch {}
            window.parent.postMessage({ type: 'spa-navigate', path: spaPath }, '*')
          } else {
            window.location.href = href
          }
          return
        }

        if (isEmbedded && href && (href.startsWith('/encyclopedia/') || href.startsWith('./') || href.startsWith('../') || !href.startsWith('/'))) {
          const isInternal = href.startsWith('/encyclopedia/') || href.startsWith('./') || href.startsWith('../') || (!href.startsWith('http') && !href.startsWith('#'))
          if (isInternal) {
            e.preventDefault()
            const separator = href.includes('?') ? '&' : '?'
            const absUrl = new URL(href, window.location.href)
            window.location.href = absUrl.pathname + absUrl.search + separator + 'embedded=1' + absUrl.hash
            return
          }
        }
      })

      window.addEventListener('popstate', () => {
        applyEmbeddedMode()
      })

      const observer = new MutationObserver(() => {
        applyEmbeddedMode()
      })
      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class']
      })
    }
  },
  layout() {
    return {}
  },
}