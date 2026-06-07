import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'

interface SwipeOptions {
  minDistance?: number
  maxDuration?: number
  directionRatio?: number
}

// Global swipe lock — set to true to disable page-level swipe detection
let _swipeLocked = false
export function lockSwipe() { _swipeLocked = true }
export function unlockSwipe() { _swipeLocked = false }

export function useSwipe(options: SwipeOptions = {}) {
  const {
    minDistance = 50,
    maxDuration = 500,
    directionRatio = 1.5,
  } = options

  const direction = ref<'left' | 'right' | null>(null)
  const isSwiping = ref(false)

  let startX = 0
  let startY = 0
  let startTime = 0

  function onTouchStart(e: TouchEvent) {
    if (e.touches.length !== 1) return
    if (_swipeLocked) return
    // Skip swipe detection when touch originates inside an iframe
    // (e.g. encyclopedia iframe handles its own scroll/touch)
    const target = e.target as HTMLElement
    if (target?.closest('iframe')) return
    // Skip swipe inside 3D model / canvas areas (e.g. DigitalHuman)
    if (target?.closest('canvas') || target?.closest('[data-swipe-ignore]')) return
    // Skip swipe detection when touch originates inside a horizontally scrollable container
    // (e.g. category tabs, horizontal carousels) — their own scroll should not trigger page navigation
    const scrollableParent = target?.closest('[data-scroll-x], .overflow-x-auto, .overflow-x-scroll')
    if (scrollableParent) return
    const touch = e.touches[0]
    startX = touch.clientX
    startY = touch.clientY
    startTime = Date.now()
    isSwiping.value = true
    direction.value = null
  }

  function onTouchEnd(e: TouchEvent) {
    if (!isSwiping.value) return
    isSwiping.value = false

    if (e.changedTouches.length !== 1) return
    const touch = e.changedTouches[0]
    const deltaX = touch.clientX - startX
    const deltaY = touch.clientY - startY
    const duration = Date.now() - startTime

    if (duration > maxDuration) return

    const absX = Math.abs(deltaX)
    const absY = Math.abs(deltaY)
    if (absX < absY * directionRatio) return
    if (absX < minDistance) return

    direction.value = deltaX < 0 ? 'left' : 'right'
  }

  function init() {
    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchend', onTouchEnd, { passive: true })
  }

  function cleanup() {
    document.removeEventListener('touchstart', onTouchStart)
    document.removeEventListener('touchend', onTouchEnd)
  }

  onMounted(init)
  onUnmounted(cleanup)

  return { direction, isSwiping, cleanup }
}

export function useSwipeNavigation() {
  const router = useRouter()
  const { direction } = useSwipe()

  const tabOrder = [
    '/',
    '/community',
    '/messages',
    '/profile',
  ]

  function getCurrentTabIndex(): number {
    const path = router.currentRoute.value.path
    for (let i = 0; i < tabOrder.length; i++) {
      const tab = tabOrder[i]
      if (tab === '/' && (path === '/' || path === '/chat' || path === '/tracker')) return i
      if (tab !== '/' && path.startsWith(tab)) return i
    }
    return -1
  }

  watch(direction, (dir) => {
    if (!dir) return
    const currentIndex = getCurrentTabIndex()
    if (currentIndex === -1) return

    const nextIndex = dir === 'left' ? currentIndex + 1 : currentIndex - 1
    if (nextIndex < 0 || nextIndex >= tabOrder.length) return

    router.push(tabOrder[nextIndex])
  })
}