import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { butlerApi } from '@/api/butler'
import { useAuthStore } from '@/stores/auth'
import type { ButlerPreference, NavSuggestion } from '@/types'

export const BUTLER_DEFAULT_PREFERENCE: ButlerPreference = {
  mascot: 'real',
  style: 'circle',
  size: 'medium',
  position: 'right',
  greeting: '我是小白管家，有什么可以帮你？',
  enabled: true,
}

const LS_KEY = 'subskin_butler_pref'

function readLocalPreference(): ButlerPreference {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return { ...BUTLER_DEFAULT_PREFERENCE }
    const parsed = JSON.parse(raw) as Partial<ButlerPreference>
    return { ...BUTLER_DEFAULT_PREFERENCE, ...parsed }
  } catch {
    return { ...BUTLER_DEFAULT_PREFERENCE }
  }
}

/**
 * 小白管家全局状态：面板开合、快捷模式、结构化导航建议、外观偏好。
 * 偏好来源优先级：登录用户后端（跨设备）> localStorage > 默认值。
 */
export const useButlerStore = defineStore('butler', () => {
  const authStore = useAuthStore()

  const isOpen = ref(false)
  const mode = ref<'chat' | 'counseling'>('chat')
  const navSuggestions = ref<NavSuggestion[]>([])
  const preference = ref<ButlerPreference>(readLocalPreference())
  // 隐藏模式（本机记忆）：隐藏后管家在屏幕边缘"偷看"，点击恢复
  const hidden = ref(localStorage.getItem('subskin_butler_hidden') === '1')

  const isFabVisible = computed(() => preference.value.enabled)

  function hide() {
    hidden.value = true
    localStorage.setItem('subskin_butler_hidden', '1')
    close()
  }

  function unhide(openPanel = false) {
    hidden.value = false
    localStorage.removeItem('subskin_butler_hidden')
    if (openPanel) open()
  }

  function open() {
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
  }

  function toggle() {
    isOpen.value = !isOpen.value
  }

  function clearNavSuggestions() {
    navSuggestions.value = []
  }

  function setNavSuggestions(items: NavSuggestion[]) {
    navSuggestions.value = items
  }

  /** 登录后从后端拉取偏好；登出/访客使用本机 localStorage。 */
  async function loadPreference() {
    if (!authStore.isLoggedIn) {
      preference.value = readLocalPreference()
      return
    }
    try {
      preference.value = await butlerApi.getPreference()
    } catch {
      // 后端不可用时回退本机偏好，不阻塞管家可用性
      preference.value = readLocalPreference()
    }
  }

  /** 保存偏好：登录用户写后端并同步本机；访客仅写本机。 */
  async function savePreference(patch: Partial<ButlerPreference>) {
    const next = { ...preference.value, ...patch }
    preference.value = next
    localStorage.setItem(LS_KEY, JSON.stringify(next))
    if (!authStore.isLoggedIn) return
    try {
      preference.value = await butlerApi.updatePreference(patch)
    } catch {
      // 保留本地已生效的值；下次进入页面会重试后端
    }
  }

  // 登录状态变化时切换偏好来源（登录→云端同步；登出→本机）
  watch(() => authStore.isLoggedIn, () => { loadPreference() })

  return {
    isOpen,
    hidden,
    mode,
    navSuggestions,
    preference,
    isFabVisible,
    open,
    close,
    toggle,
    hide,
    unhide,
    clearNavSuggestions,
    setNavSuggestions,
    loadPreference,
    savePreference,
  }
})
