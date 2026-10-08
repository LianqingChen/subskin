import { ref } from 'vue'

const GREETINGS = [
  '嗨～我是小白管家！',
  '今天的白斑记录了吗？',
  '有问题随时点我哦',
  '要不要看看最新的白斑变化报告？',
  '出门记得防晒呀',
  '心情不好也可以找我聊聊',
  '白友圈有新分享，去看看？',
  '需要我帮你找功能入口吗？',
]
const GREETING_MAX_PER_SESSION = 3

/**
 * 小白管家随机跳跃 + 定时招呼气泡。
 * 跳跃与招呼互斥；面板打开/隐藏/拖动中不打扰；每次会话最多招呼 3 次。
 */
export function useButlerRoam(options: {
  isOpen: () => boolean
  isHidden: () => boolean
  isLively: () => boolean
  hasCustomPos: () => boolean
  isDragging: () => boolean
  onOpenPanel: () => void
}) {
  const roam = ref({ x: 0, y: 0 })
  const isMoving = ref(false)
  const greetingVisible = ref(false)
  const greetingText = ref('')

  let roamTimer: ReturnType<typeof setTimeout> | null = null
  let greetingTimer: ReturnType<typeof setTimeout> | null = null
  let greetingHideTimer: ReturnType<typeof setTimeout> | null = null
  let greetingCount = Number(sessionStorage.getItem('butler_greeted') || 0)
  let greetingIndex = 0

  function scheduleRoam() {
    roamTimer = setTimeout(doRoam, 14000 + Math.random() * 16000)
  }

  function stopRoam() {
    if (roamTimer) clearTimeout(roamTimer)
  }

  function doRoam() {
    if (options.hasCustomPos() || options.isDragging()) {
      scheduleRoam()
      return
    }
    if (!options.isOpen() && !options.isHidden() && !isMoving.value && options.isLively() && !greetingVisible.value) {
      isMoving.value = true
      if (roam.value.x === 0 && roam.value.y === 0) {
        roam.value = { x: -(10 + Math.random() * 64), y: -(12 + Math.random() * 72) }
      } else {
        roam.value = { x: 0, y: 0 }
      }
      setTimeout(() => { isMoving.value = false }, 950)
    }
    scheduleRoam()
  }

  function showGreeting() {
    if (options.isOpen() || options.isHidden() || options.isDragging() || greetingCount >= GREETING_MAX_PER_SESSION) {
      scheduleNextGreeting()
      return
    }
    greetingText.value = GREETINGS[greetingIndex % GREETINGS.length]
    greetingIndex++
    greetingCount++
    sessionStorage.setItem('butler_greeted', String(greetingCount))
    greetingVisible.value = true
    greetingHideTimer = setTimeout(() => {
      greetingVisible.value = false
      scheduleNextGreeting()
    }, 6000)
  }

  function scheduleNextGreeting() {
    const delay = 90000 + Math.random() * 60000
    greetingTimer = setTimeout(showGreeting, delay)
  }

  function startGreetingLoop() {
    if (greetingCount >= GREETING_MAX_PER_SESSION) return
    greetingTimer = setTimeout(showGreeting, greetingCount === 0 ? 8000 : 45000)
  }

  function stopGreetingLoop() {
    if (greetingTimer) clearTimeout(greetingTimer)
    if (greetingHideTimer) clearTimeout(greetingHideTimer)
  }

  function onGreetingClick() {
    greetingVisible.value = false
    options.onOpenPanel()
  }

  return {
    roam,
    isMoving,
    greetingVisible,
    greetingText,
    scheduleRoam,
    stopRoam,
    startGreetingLoop,
    stopGreetingLoop,
    onGreetingClick,
  }
}
