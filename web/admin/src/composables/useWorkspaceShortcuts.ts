import { onBeforeUnmount, onMounted } from 'vue'
import type { ClassMapEditor, EditorTool } from './useClassMapEditor'
import { CLASSES } from '@/utils/classMap'

interface Handlers {
  submitNext: () => void
  next: () => void
  prev: () => void
  toggleOverlay: () => void
  peek: (on: boolean) => void
  zoom: (factor: number) => void
  fit: () => void
}

const TOOL_KEYS: Record<string, EditorTool> = { b: 'brush', f: 'fill', w: 'wand', r: 'remove' }

/** 工作台快捷键；输入框内不触发，系统组合键（Ctrl+L 等）不拦截。 */
export function useWorkspaceShortcuts(editor: ClassMapEditor, h: Handlers) {
  function typing(e: KeyboardEvent) {
    return !!(e.target as HTMLElement | null)?.closest('input, textarea, select, [contenteditable], .n-base-selection')
  }
  function onDown(e: KeyboardEvent) {
    if (typing(e)) return
    const key = e.key.toLowerCase()
    const mod = e.ctrlKey || e.metaKey
    if (mod && key === 'z') { e.preventDefault(); if (e.shiftKey) editor.redo(); else editor.undo(); return }
    if (mod && key === 'y') { e.preventDefault(); editor.redo(); return }
    if (mod && key === 'enter') { e.preventDefault(); h.submitNext(); return }
    if (e.altKey && key === 'arrowright') { e.preventDefault(); h.next(); return }
    if (e.altKey && key === 'arrowleft') { e.preventDefault(); h.prev(); return }
    if (mod || e.altKey) return
    const cls = CLASSES.find((c) => c.key === e.key)
    if (cls) { editor.activeClass.value = cls.value; if (editor.tool.value === 'remove') editor.tool.value = 'brush'; return }
    if (TOOL_KEYS[key]) { editor.tool.value = TOOL_KEYS[key]; return }
    if (key === '[') editor.brushSize.value = Math.max(2, Math.round(editor.brushSize.value / 1.25))
    else if (key === ']') editor.brushSize.value = Math.min(120, Math.round(editor.brushSize.value * 1.25))
    else if (key === 'h') h.toggleOverlay()
    else if (key === 'c' && !e.repeat) h.peek(true)
    else if (key === '=' || key === '+') h.zoom(1.25)
    else if (key === '-') h.zoom(0.8)
    else if (key === '`' || key === 'home') h.fit()
  }
  function onUp(e: KeyboardEvent) { if (e.key.toLowerCase() === 'c') h.peek(false) }
  onMounted(() => { window.addEventListener('keydown', onDown); window.addEventListener('keyup', onUp) })
  onBeforeUnmount(() => { window.removeEventListener('keydown', onDown); window.removeEventListener('keyup', onUp) })
}
