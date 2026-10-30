import { onBeforeUnmount } from 'vue'

type DirtyCheck = () => boolean

const checks = new Set<DirtyCheck>()

function focusedFieldHasText(): boolean {
  const el = document.activeElement
  if (el instanceof HTMLTextAreaElement) return el.value.trim().length > 0
  if (el instanceof HTMLInputElement) {
    return ['text', 'search', 'email', 'tel', 'url', 'number'].includes(el.type) && el.value.trim().length > 0
  }
  return el instanceof HTMLElement && el.isContentEditable && (el.textContent ?? '').trim().length > 0
}

/** True when a page reported unsaved work, or the user is mid-typing in a field. */
export function hasUnsavedInput(): boolean {
  for (const check of checks) {
    if (check()) return true
  }
  return focusedFieldHasText()
}

/** Register a dirty check for the lifetime of the calling component; app-initiated reloads defer while it returns true. */
export function useUnsavedGuard(check: DirtyCheck): void {
  checks.add(check)
  onBeforeUnmount(() => checks.delete(check))
}
