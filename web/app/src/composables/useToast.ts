import { ref } from 'vue'

interface ToastItem {
  id: number
  message: string
  type: 'success' | 'warning' | 'error' | 'info'
}

const toasts = ref<ToastItem[]>([])
let nextId = 0

export function useToast() {
  function show(message: string, type: ToastItem['type'] = 'info', duration = 3000) {
    const id = nextId++
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter(t => t.id !== id)
    }, duration)
    return id
  }

  function success(message: string) { return show(message, 'success') }
  function warning(message: string) { return show(message, 'warning') }
  function error(message: string) { return show(message, 'error') }

  function remove(id: number) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  return { toasts, show, success, warning, error, remove }
}