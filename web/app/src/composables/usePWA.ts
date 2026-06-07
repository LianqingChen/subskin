import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRegisterSW } from 'virtual:pwa-register/vue'
import { useAuthStore } from '@/stores/auth'

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

type PWAInstallStatus = 'installed' | 'installable' | 'dismissed_today' | 'dismissed_forever' | 'unsupported'

const STORAGE_KEY_INSTALLED = 'subskin_pwa_installed'
const STORAGE_KEY_DISMISSED_AT = 'subskin_pwa_dismissed_at'
const STORAGE_KEY_DISMISS_COUNT = 'subskin_pwa_dismiss_count'
const STORAGE_KEY_VISIT_DATES = 'subskin_visit_dates'
const DISMISS_COOLDOWN_MS = 3 * 24 * 60 * 60 * 1000  // "稍后" → 3 days
const DISMISS_COOLDOWN_LONG_MS = 7 * 24 * 60 * 60 * 1000  // "✕" → 7 days
const DISMISS_EXPIRE_MS = 30 * 24 * 60 * 60 * 1000
const MAX_SHOW_COUNT = 5
const REQUIRED_CONSECUTIVE_DAYS = 1

// beforeinstallprompt fires during page load before Vue onMounted — capture at module level
let capturedBeforeInstallPrompt: BeforeInstallPromptEvent | null = null
let capturedBeforeInstallPromptFired = false

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e: Event) => {
    e.preventDefault()
    capturedBeforeInstallPrompt = e as BeforeInstallPromptEvent
    capturedBeforeInstallPromptFired = true
  })
}

const SW_UPDATE_INTERVAL_MS = 5 * 60 * 1000

export function usePWA() {
  let swRegistration: ServiceWorkerRegistration | null = null
  let updateInterval: ReturnType<typeof setInterval> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const updateDismissedUntil = ref(0)  // timestamp — don't re-show banner until after this

  const { needRefresh, updateServiceWorker } = useRegisterSW({
    onRegisteredSW(_swUrl, registration) {
      if (registration) {
        swRegistration = registration
        registration.update().catch(() => {})
      }
    },
    onRegisterError(error) {
      console.error('SW registration error:', error)
    },
  })

  const showUpdateBanner = computed(() =>
    needRefresh.value && Date.now() >= updateDismissedUntil.value
  )

  const isInstallable = ref(false)
  const isInstalled = ref(false)
  const isOffline = ref(!navigator.onLine)
  const installStatus = ref<PWAInstallStatus>('unsupported')
  const hasDeferredPrompt = ref(false)

  let deferredPrompt: BeforeInstallPromptEvent | null = null
  let showCount = 0

  function detectStandaloneMode(): boolean {
    return window.matchMedia('(display-mode: standalone)').matches
      || !!(window.navigator as any).standalone
      || document.referrer.includes('android-app://')
  }

  // wasPreviouslyInstalled must cross-check runtime: stale localStorage after PWA uninstall would permanently block prompts
  function wasPreviouslyInstalled(): boolean {
    return localStorage.getItem(STORAGE_KEY_INSTALLED) === 'true' && detectStandaloneMode()
  }

  function isDismissedInCooldown(): boolean {
    const dismissedAt = localStorage.getItem(STORAGE_KEY_DISMISSED_AT)
    if (!dismissedAt) return false
    const cooldown = parseInt(localStorage.getItem('subskin_pwa_dismiss_cooldown') || String(DISMISS_COOLDOWN_MS))
    return Date.now() - parseInt(dismissedAt) < cooldown
  }

  // Dismiss count auto-resets after DISMISS_EXPIRE_MS so users aren't permanently locked out
  function getDismissCount(): number {
    const dismissedAt = localStorage.getItem(STORAGE_KEY_DISMISSED_AT)
    if (dismissedAt) {
      const age = Date.now() - parseInt(dismissedAt)
      if (age > DISMISS_EXPIRE_MS) {
        localStorage.removeItem(STORAGE_KEY_DISMISSED_AT)
        localStorage.removeItem(STORAGE_KEY_DISMISS_COUNT)
        return 0
      }
    }
    return parseInt(localStorage.getItem(STORAGE_KEY_DISMISS_COUNT) || '0')
  }

  function _todayStr(): string {
    const now = new Date()
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    const d = String(now.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
  }

  function _loadVisitDates(): string[] {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY_VISIT_DATES) || '[]')
    } catch {
      return []
    }
  }

  function _saveVisitDates(dates: string[]) {
    localStorage.setItem(STORAGE_KEY_VISIT_DATES, JSON.stringify(dates))
  }

  function recordVisitDay() {
    const today = _todayStr()
    const dates = _loadVisitDates()
    if (dates[dates.length - 1] === today) return
    dates.push(today)
    if (dates.length > 60) dates.splice(0, dates.length - 60)
    _saveVisitDates(dates)
  }

  function getConsecutiveDays(): number {
    const dates = _loadVisitDates()
    if (dates.length === 0) return 0

    const today = _todayStr()
    const datesSet = new Set(dates)

    if (!datesSet.has(today)) return 0

    let count = 0
    const d = new Date()
    while (true) {
      const y = d.getFullYear()
      const m = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      const key = `${y}-${m}-${day}`
      if (!datesSet.has(key)) break
      count++
      d.setDate(d.getDate() - 1)
    }
    return count
  }

  function isHighFrequencyUser(): boolean {
    return getConsecutiveDays() >= REQUIRED_CONSECUTIVE_DAYS
  }

  function shouldShowPrompt(): boolean {
    if (detectStandaloneMode()) {
      markInstalled()
      return false
    }
    if (wasPreviouslyInstalled()) return false
    if (!isHighFrequencyUser()) return false
    if (isDismissedInCooldown()) return false
    if (getDismissCount() >= MAX_SHOW_COUNT) return false
    return true
  }

  function reportInstallStatusToBackend(installed: boolean) {
    const authStore = useAuthStore()
    if (!authStore.isLoggedIn) return

    const uid = authStore.user?.uid
    if (!uid) return

    try {
      fetch('/api/user/pwa-status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}),
        },
        body: JSON.stringify({ installed, uid, timestamp: new Date().toISOString() }),
        keepalive: true,
      }).catch(() => {})
    } catch {}
  }

  function markInstalled() {
    isInstalled.value = true
    isInstallable.value = false
    installStatus.value = 'installed'
    localStorage.setItem(STORAGE_KEY_INSTALLED, 'true')
  }

  function markDismissed(cooldownMs: number = DISMISS_COOLDOWN_MS) {
    isInstallable.value = false
    localStorage.setItem(STORAGE_KEY_DISMISSED_AT, Date.now().toString())
    localStorage.setItem('subskin_pwa_dismiss_cooldown', cooldownMs.toString())
    const count = getDismissCount() + 1
    localStorage.setItem(STORAGE_KEY_DISMISS_COUNT, count.toString())

    if (count >= MAX_SHOW_COUNT) {
      installStatus.value = 'dismissed_forever'
    } else {
      installStatus.value = 'dismissed_today'
      deferredPrompt = null
      hasDeferredPrompt.value = false
    }

    reportInstallStatusToBackend(false)
  }

  function handleBeforeInstallPrompt(e: Event) {
    e.preventDefault()
    deferredPrompt = e as BeforeInstallPromptEvent
    hasDeferredPrompt.value = true

    if (detectStandaloneMode() || wasPreviouslyInstalled()) {
      installStatus.value = 'installed'
      return
    }

    if (shouldShowPrompt()) {
      isInstallable.value = true
      installStatus.value = 'installable'
      showCount++
    }
  }

  function handleAppInstalled() {
    markInstalled()
    reportInstallStatusToBackend(true)
    // Let the app layer show feedback
    window.dispatchEvent(new CustomEvent('pwa-installed'))
  }

  function handleOnline() {
    isOffline.value = false
    if (swRegistration) {
      swRegistration.update().catch(() => {})
    }
  }

  function handleOffline() {
    isOffline.value = true
  }

  async function installApp(): Promise<boolean> {
    if (!deferredPrompt) return false
    await deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    deferredPrompt = null
    hasDeferredPrompt.value = false

    if (outcome === 'accepted') {
      markInstalled()
      reportInstallStatusToBackend(true)
      return true
    } else {
      markDismissed()
      return false
    }
  }

  function dismissInstall() {
    markDismissed(DISMISS_COOLDOWN_MS)
  }

  function dismissInstallLong() {
    markDismissed(DISMISS_COOLDOWN_LONG_MS)
  }

  function resetDismissState() {
    localStorage.removeItem(STORAGE_KEY_DISMISSED_AT)
    localStorage.removeItem(STORAGE_KEY_DISMISS_COUNT)
  }

  function forceResetAndReload() {
    localStorage.removeItem(STORAGE_KEY_INSTALLED)
    localStorage.removeItem(STORAGE_KEY_DISMISSED_AT)
    localStorage.removeItem(STORAGE_KEY_DISMISS_COUNT)
    location.reload()
  }

  // If localStorage says installed but runtime says otherwise, the PWA was uninstalled —
  // clear stale flag AND reset dismiss state so the prompt can appear again
  function clearStaleInstalledFlag() {
    if (localStorage.getItem(STORAGE_KEY_INSTALLED) === 'true' && !detectStandaloneMode()) {
      localStorage.removeItem(STORAGE_KEY_INSTALLED)
      // PWA was uninstalled — reset dismiss state to give a fresh chance
      localStorage.removeItem(STORAGE_KEY_DISMISSED_AT)
      localStorage.removeItem(STORAGE_KEY_DISMISS_COUNT)
    }
  }

  async function updateApp() {
    const reloadFallback = setTimeout(() => window.location.reload(), 3000)
    try {
      await updateServiceWorker(true)
    } catch {
      clearTimeout(reloadFallback)
      window.location.reload()
    }
  }

  function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && swRegistration) {
      swRegistration.update().catch(() => {})
    }
  }

  onMounted(() => {
    recordVisitDay()

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        window.location.reload()
      })
    }

    setTimeout(() => {
      if (swRegistration) {
        swRegistration.update().catch(() => {})
      }
    }, 1000)

    clearStaleInstalledFlag()

    updateInterval = setInterval(() => {
      if (swRegistration) {
        swRegistration.update().catch(() => {})
      }
    }, SW_UPDATE_INTERVAL_MS)

    const loadedBuildTime = typeof __BUILD_TIME__ !== 'undefined' ? __BUILD_TIME__ : 0
    pollTimer = setInterval(async () => {
      if (needRefresh.value) {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
        return
      }
      try {
        const resp = await fetch(`/version.json?t=${Date.now()}`, { cache: 'no-store' })
        if (!resp.ok) return
        const data = await resp.json()
        if (data.buildTime && data.buildTime > loadedBuildTime) {
          needRefresh.value = true
          if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
        }
      } catch { /* ignore network errors */ }
    }, 30000)

    if (detectStandaloneMode()) {
      markInstalled()
      return
    }

    if (wasPreviouslyInstalled()) {
      isInstalled.value = true
      installStatus.value = 'installed'
      return
    }

    if (capturedBeforeInstallPromptFired && capturedBeforeInstallPrompt) {
      deferredPrompt = capturedBeforeInstallPrompt
      hasDeferredPrompt.value = true
      capturedBeforeInstallPrompt = null
      capturedBeforeInstallPromptFired = false

      if (shouldShowPrompt()) {
        isInstallable.value = true
        installStatus.value = 'installable'
        showCount++
      }
    } else if (!shouldShowPrompt()) {
      if (isDismissedInCooldown()) {
        installStatus.value = 'dismissed_today'
      } else if (getDismissCount() >= MAX_SHOW_COUNT) {
        installStatus.value = 'dismissed_forever'
      }
    }
  })

  onUnmounted(() => {
    if (updateInterval) {
      clearInterval(updateInterval)
      updateInterval = null
    }
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.removeEventListener('appinstalled', handleAppInstalled)
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  function dismissUpdate() {
    updateDismissedUntil.value = Date.now() + 60 * 60 * 1000
    setTimeout(() => {
      if (swRegistration) {
        swRegistration.update().catch(() => {})
      }
    }, 60 * 60 * 1000)
  }

  return {
    isInstallable,
    isInstalled,
    isOffline,
    needsUpdate: needRefresh,
    showUpdateBanner,
    updateDismissedUntil,
    installApp,
    dismissInstall,
    dismissInstallLong,
    installStatus,
    hasDeferredPrompt,
    resetDismissState,
    forceResetAndReload,
    updateApp,
    dismissUpdate,
    getConsecutiveDays,
    isHighFrequencyUser,
    recordVisitDay,
  }
}
