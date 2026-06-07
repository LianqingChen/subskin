import { ref } from 'vue'

const STORAGE_KEY = 'subskin_phone_history'
const MAX_HISTORY = 5

const phoneHistory = ref<string[]>([])

export function usePhoneHistory() {
  function load() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
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
    localStorage.setItem(STORAGE_KEY, JSON.stringify(phoneHistory.value))
  }

  function remove(phone: string) {
    phoneHistory.value = phoneHistory.value.filter((p) => p !== phone)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(phoneHistory.value))
  }

  load()

  return { phoneHistory, add, remove }
}
