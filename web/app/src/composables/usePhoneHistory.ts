import { ref } from 'vue'

const STORAGE_KEY = 'subskin_phone_history'
// 2026-08-30 隐私加固：手机号属 L3 数据，改存 sessionStorage（关闭浏览器即清除）
const MAX_HISTORY = 5

const phoneHistory = ref<string[]>([])

export function usePhoneHistory() {
  function load() {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY)
      if (stored) phoneHistory.value = JSON.parse(stored)
    } catch {
      phoneHistory.value = []
    }
  }

  function add(phone: string) {
    load()
    phoneHistory.value = [
      phone,
      ...phoneHistory.value.filter((p) => p !== phone),
    ].slice(0, MAX_HISTORY)
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(phoneHistory.value))
  }

  function remove(phone: string) {
    phoneHistory.value = phoneHistory.value.filter((p) => p !== phone)
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(phoneHistory.value))
  }

  load()

  return { phoneHistory, add, remove }
}
