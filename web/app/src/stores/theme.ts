import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const DEFAULT_THEME_HUE = 174

const THEME_MODE_KEY = 'subskin_theme_mode'
const THEME_HUE_KEY = 'subskin_theme_hue'

function parseStoredHue(rawHue: string | null): number | null {
  if (rawHue === null) return null
  const parsedHue = Number.parseInt(rawHue, 10)
  if (!Number.isFinite(parsedHue)) return null
  return Math.min(360, Math.max(0, parsedHue))
}

export const useThemeStore = defineStore('theme', () => {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  const mode = ref<'light' | 'dark'>(mediaQuery.matches ? 'dark' : 'light')
  const customHue = ref<number | null>(parseStoredHue(localStorage.getItem(THEME_HUE_KEY)))

  const savedMode = localStorage.getItem(THEME_MODE_KEY)
  if (savedMode === 'light' || savedMode === 'dark') {
    mode.value = savedMode
  }

  function applyMode(nextMode: 'light' | 'dark') {
    if (nextMode === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  function applyHue(hue: number | null) {
    const root = document.documentElement
    root.style.setProperty('--color-primary-h', String(hue ?? DEFAULT_THEME_HUE))
  }

  applyMode(mode.value)
  applyHue(customHue.value)

  watch(mode, (nextMode) => {
    applyMode(nextMode)
    localStorage.setItem(THEME_MODE_KEY, nextMode)
  })

  watch(customHue, (hue) => {
    applyHue(hue)
    if (hue === null) {
      localStorage.removeItem(THEME_HUE_KEY)
      return
    }

    localStorage.setItem(THEME_HUE_KEY, String(hue))
  })

  function setMode(nextMode: 'light' | 'dark') {
    mode.value = nextMode
  }

  function setCustomHue(hue: number | null) {
    customHue.value = hue === null ? null : Math.min(360, Math.max(0, Math.round(hue)))
  }

  function toggleMode() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  return { mode, customHue, setMode, setCustomHue, toggleMode }
})
