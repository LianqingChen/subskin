import { useAuthStore } from '@/stores/auth'

const SESSION_KEY = 'subskin_sid'

let sessionId: string | null = null

export function getSessionId(): string {
  if (!sessionId) {
    const stored = sessionStorage.getItem(SESSION_KEY)
    if (stored) {
      sessionId = stored
    } else {
      sessionId = crypto.randomUUID()
      sessionStorage.setItem(SESSION_KEY, sessionId!)
    }
  }
  return sessionId
}

export interface TrackEvent {
  event_type: string
  element_id?: string
  page_path?: string
  element_text?: string
  extra_data?: Record<string, unknown>
  session_id?: string
}

const eventQueue: TrackEvent[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null
const FLUSH_INTERVAL = 3000
const MAX_QUEUE_SIZE = 20

function flushEvents() {
  if (eventQueue.length === 0) return
  const events = [...eventQueue]
  eventQueue.length = 0

  import('@/api/client').then(({ default: apiClient }) => {
    apiClient.post('/events/track/batch', { events }).catch(() => {
      eventQueue.unshift(...events)
    })
  })
}

function scheduleFlush() {
  if (!flushTimer) {
    flushTimer = setTimeout(() => {
      flushTimer = null
      flushEvents()
    }, FLUSH_INTERVAL)
  }
}

export function trackEvent(event: TrackEvent) {
  event.page_path = event.page_path || window.location.pathname
  event.session_id = event.session_id || getSessionId()

  try {
    const authStore = useAuthStore()
    if (authStore.user?.uid) {
      event.extra_data = { ...event.extra_data, uid: authStore.user.uid }
    }
  } catch {
    // store not initialized
  }

  eventQueue.push(event)

  if (eventQueue.length >= MAX_QUEUE_SIZE) {
    flushEvents()
  } else {
    scheduleFlush()
  }
}



export function trackPageView(path?: string) {
  trackEvent({
    event_type: 'page_view',
    page_path: path || window.location.pathname,
  })
}

export function trackClick(elementId: string, elementText?: string, extra?: Record<string, unknown>) {
  trackEvent({
    event_type: 'click',
    element_id: elementId,
    element_text: elementText,
    extra_data: extra,
  })
}

export function trackInput(elementId: string, action: string = 'input', extra?: Record<string, unknown>) {
  trackEvent({
    event_type: action,
    element_id: elementId,
    extra_data: extra,
  })
}

export function flushTracking() {
  flushEvents()
}

export function resetSessionId() {
  sessionId = null
  sessionStorage.removeItem(SESSION_KEY)
}