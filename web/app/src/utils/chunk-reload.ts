import type { Router } from 'vue-router'
import { hasUnsavedInput } from '@/composables/useUnsavedGuard'

const RELOAD_KEY = 'subskin:chunk-reload-at'
// One forced reload per window; a second failure inside it is a real outage, not a stale build.
const RELOAD_WINDOW_MS = 5 * 60 * 1000

const CHUNK_ERROR_PATTERN =
  /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Loading chunk [\w-]+ failed|Unable to preload CSS/i

export function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? `${error.name} ${error.message}` : String(error ?? '')
  return CHUNK_ERROR_PATTERN.test(message)
}

function reloadOnce(targetPath?: string): boolean {
  if (hasUnsavedInput()) return false
  const last = Number(sessionStorage.getItem(RELOAD_KEY) || 0)
  if (Date.now() - last < RELOAD_WINDOW_MS) return false
  sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
  if (targetPath) {
    window.location.assign(targetPath)
  } else {
    window.location.reload()
  }
  return true
}

export function installChunkReload(router: Router): void {
  router.onError((error, to) => {
    if (isChunkLoadError(error)) reloadOnce(to.fullPath)
  })

  window.addEventListener('vite:preloadError', (event) => {
    if (reloadOnce()) event.preventDefault()
  })
}
