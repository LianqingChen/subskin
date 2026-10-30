import { computed, ref, shallowRef } from 'vue'
import { growRegion, mapStats, paintDisc, paintLine, UNKNOWN, type ClassValue } from '@/utils/classMap'

export type EditorTool = 'brush' | 'fill' | 'wand' | 'remove'
const MAX_HISTORY = 30

/** 类别图编辑状态：画笔/填充/魔棒/点除 + 撤销重做。像素坐标为规范图坐标。 */
export function useClassMapEditor() {
  const width = ref(0)
  const height = ref(0)
  const map = shallowRef<Uint8Array>(new Uint8Array(0))
  const version = ref(0)
  const activeClass = ref<ClassValue>(2)
  const tool = ref<EditorTool>('brush')
  const brushSize = ref(16)
  const tolerance = ref(18)
  const dirty = ref(false)
  const edits = ref(0)
  const undoStack: Uint8Array[] = []
  const redoStack: Uint8Array[] = []
  const canUndo = ref(false)
  const canRedo = ref(false)
  let photo: Uint8ClampedArray | null = null
  let last: [number, number] | null = null

  const stats = computed(() => { void version.value; return mapStats(map.value) })

  function bump() { version.value++; dirty.value = true }
  function syncFlags() { canUndo.value = undoStack.length > 0; canRedo.value = redoStack.length > 0 }
  function snapshot() {
    undoStack.push(map.value.slice())
    if (undoStack.length > MAX_HISTORY) undoStack.shift()
    redoStack.length = 0
    edits.value++
    syncFlags()
  }

  function reset(next: Uint8Array, w: number, h: number) {
    width.value = w; height.value = h
    map.value = next
    undoStack.length = 0; redoStack.length = 0
    dirty.value = false; edits.value = 0
    syncFlags()
    version.value++
  }
  function setPhoto(rgba: Uint8ClampedArray | null) { photo = rgba }

  function replace(next: Uint8Array) {
    if (next.length !== map.value.length) return
    snapshot()
    map.value = next
    bump()
  }

  function inside(x: number, y: number) { return x >= 0 && y >= 0 && x < width.value && y < height.value }

  function strokeStart(x: number, y: number) {
    if (!inside(x, y)) return
    snapshot()
    paintDisc(map.value, width.value, height.value, x, y, brushSize.value / 2, activeClass.value)
    last = [x, y]
    bump()
  }
  function strokeMove(x: number, y: number) {
    if (!last) return
    paintLine(map.value, width.value, height.value, last, [x, y], brushSize.value / 2, activeClass.value)
    last = [x, y]
    bump()
  }
  function strokeEnd() { last = null }

  /** 填充：同类连通区改为当前类别；魔棒：颜色相近区改为当前类别；点除：点中的白斑连通区改回正常皮肤。 */
  function clickAt(x: number, y: number): boolean {
    if (!inside(x, y)) return false
    const px = Math.floor(x); const py = Math.floor(y)
    const value = map.value[py * width.value + px]
    let target: ClassValue = activeClass.value
    let region: Int32Array
    if (tool.value === 'remove') {
      if (value !== 2) return false
      region = growRegion(map.value, width.value, height.value, px, py, null, 0)
      target = 1
    } else if (tool.value === 'wand') {
      if (!photo) return false
      region = growRegion(map.value, width.value, height.value, px, py, photo, tolerance.value, Math.floor(map.value.length * 0.6))
    } else {
      if (value === target) return false
      region = growRegion(map.value, width.value, height.value, px, py, null, 0)
    }
    snapshot()
    for (let i = 0; i < region.length; i++) map.value[region[i]] = target
    bump()
    return true
  }

  function fillUnknown(value: ClassValue) {
    snapshot()
    const next = map.value
    for (let i = 0; i < next.length; i++) if (next[i] === UNKNOWN) next[i] = value
    bump()
  }
  function clearAll() {
    snapshot()
    map.value.fill(UNKNOWN)
    bump()
  }

  function undo() {
    const prev = undoStack.pop()
    if (!prev) return
    redoStack.push(map.value)
    map.value = prev
    syncFlags(); bump()
  }
  function redo() {
    const next = redoStack.pop()
    if (!next) return
    undoStack.push(map.value)
    map.value = next
    syncFlags(); bump()
  }

  return {
    width, height, map, version, activeClass, tool, brushSize, tolerance, dirty, edits, stats, canUndo, canRedo,
    reset, setPhoto, replace, strokeStart, strokeMove, strokeEnd, clickAt, fillUnknown, clearAll, undo, redo,
    markSaved: () => { dirty.value = false },
  }
}

export type ClassMapEditor = ReturnType<typeof useClassMapEditor>
