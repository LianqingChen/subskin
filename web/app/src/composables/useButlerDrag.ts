import { computed, ref, type ComputedRef, type Ref } from 'vue'
import type { ButlerPosition } from '@/types'

export interface FabPoint {
  x: number
  y: number
}

const LS_POS_KEY = 'subskin_butler_pos'

/**
 * 小白管家 FAB 长按拖动：按住 350ms 进入拖动，可拖到页面任意位置。
 * 松手规则：左右屏幕边缘 → 隐藏（边缘偷看）；底部角落 → 恢复默认锚点；其余 → 自由位置（本机持久化）。
 */
export function useButlerDrag(options: {
  fabSize: Ref<number> | ComputedRef<number>
  position: Ref<ButlerPosition> | ComputedRef<ButlerPosition>
  onHide: () => void
  onSavePosition: (side: 'right' | 'left') => void
}) {
  const fabEl = ref<HTMLButtonElement>()
  const customPos = ref<FabPoint | null>(readCustomPos())
  const isPressing = ref(false)
  const isDragging = ref(false)
  const dragPos = ref<FabPoint | null>(null)
  const suppressClick = ref(false)

  let pressTimer: ReturnType<typeof setTimeout> | null = null
  let activePointerId: number | null = null
  let pressOrigin = { x: 0, y: 0 }

  const hasCustomPos = computed(() => customPos.value !== null)

  function readCustomPos(): FabPoint | null {
    try {
      const raw = localStorage.getItem(LS_POS_KEY)
      if (!raw) return null
      const p = JSON.parse(raw) as Partial<FabPoint>
      if (typeof p?.x !== 'number' || typeof p?.y !== 'number') return null
      return { x: Math.min(Math.max(p.x, 0), 1), y: Math.min(Math.max(p.y, 0), 1) }
    } catch {
      return null
    }
  }

  function saveCustomPos(p: FabPoint) {
    customPos.value = p
    try {
      localStorage.setItem(LS_POS_KEY, JSON.stringify(p))
    } catch {
      /* 存储不可用（隐私模式等）时仅本次会话生效 */
    }
  }

  function clearCustomPos() {
    customPos.value = null
    localStorage.removeItem(LS_POS_KEY)
  }

  function clampToViewport(x: number, y: number): FabPoint {
    const m = options.fabSize.value / 2 + 6
    return {
      x: Math.min(Math.max(x, m), window.innerWidth - m),
      y: Math.min(Math.max(y, m), window.innerHeight - m),
    }
  }

  function onFabPointerDown(e: PointerEvent) {
    if (e.button !== 0) return
    suppressClick.value = false
    activePointerId = e.pointerId
    pressOrigin = { x: e.clientX, y: e.clientY }
    isPressing.value = true
    pressTimer = setTimeout(() => startDrag(e.pointerId), 350)
  }

  function cancelPress() {
    isPressing.value = false
    if (pressTimer) clearTimeout(pressTimer)
    pressTimer = null
  }

  function startDrag(pointerId: number) {
    isPressing.value = false
    isDragging.value = true
    dragPos.value = clampToViewport(pressOrigin.x, pressOrigin.y)
    try {
      fabEl.value?.setPointerCapture(pointerId)
    } catch {
      /* 指针已不在线时忽略 */
    }
    if (typeof navigator.vibrate === 'function') navigator.vibrate(12)
  }

  function onFabPointerMove(e: PointerEvent) {
    if (e.pointerId !== activePointerId) return
    if (!isDragging.value) {
      if (Math.hypot(e.clientX - pressOrigin.x, e.clientY - pressOrigin.y) > 14) cancelPress()
      return
    }
    dragPos.value = clampToViewport(e.clientX, e.clientY)
  }

  function onFabPointerUp() {
    if (isDragging.value) finishDrag()
    else cancelPress()
  }

  function onFabPointerCancel() {
    if (isDragging.value) {
      isDragging.value = false
      dragPos.value = null
    }
    cancelPress()
  }

  function finishDrag() {
    isDragging.value = false
    suppressClick.value = true
    setTimeout(() => {
      suppressClick.value = false
    }, 350)
    const pos = dragPos.value
    dragPos.value = null
    if (!pos) return
    const vw = window.innerWidth
    const vh = window.innerHeight
    if (pos.x <= 44 || pos.x >= vw - 44) {
      clearCustomPos()
      options.onHide()
      return
    }
    const cornerBand = vh * 0.22
    if (pos.y >= vh - cornerBand && (pos.x <= vw * 0.3 || pos.x >= vw * 0.7)) {
      clearCustomPos()
      const side = pos.x <= vw * 0.3 ? 'left' : 'right'
      if (options.position.value !== side) options.onSavePosition(side)
      return
    }
    saveCustomPos({ x: pos.x / vw, y: pos.y / vh })
  }

  return {
    fabEl,
    customPos,
    hasCustomPos,
    isPressing,
    isDragging,
    dragPos,
    suppressClick,
    onFabPointerDown,
    onFabPointerMove,
    onFabPointerUp,
    onFabPointerCancel,
  }
}
