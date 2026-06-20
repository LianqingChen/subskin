/**
 * useLabelHistory — undo/redo for canvas layer state.
 *
 * Extracted from MaskEditorAdmin.vue. Manages a ring buffer of
 * { skin: ImageData, lesion: ImageData } snapshots.
 */

import { ref, computed } from 'vue'

interface HistorySnapshot {
  skin: ImageData
  lesion: ImageData
}

const HISTORY_MAX = 50

export function useLabelHistory() {
  const history = ref<HistorySnapshot[]>([])
  const historyIndex = ref(-1)

  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)

  function snapshot(skinCanvas: HTMLCanvasElement, lesionCanvas: HTMLCanvasElement) {
    const w = skinCanvas.width
    const h = skinCanvas.height
    if (w === 0 || h === 0) return

    const skinCtx = skinCanvas.getContext('2d')
    const lesionCtx = lesionCanvas.getContext('2d')
    if (!skinCtx || !lesionCtx) return

    const skin = skinCtx.getImageData(0, 0, w, h)
    const lesion = lesionCtx.getImageData(0, 0, w, h)

    // Truncate any redo history
    history.value = history.value.slice(0, historyIndex.value + 1)
    history.value.push({ skin, lesion })

    if (history.value.length > HISTORY_MAX) {
      history.value.shift()
    } else {
      historyIndex.value++
    }
  }

  function undo(skinCanvas: HTMLCanvasElement, lesionCanvas: HTMLCanvasElement, drawOverlay: () => void) {
    if (!canUndo.value) return
    historyIndex.value--
    applySnapshot(history.value[historyIndex.value], skinCanvas, lesionCanvas, drawOverlay)
  }

  function redo(skinCanvas: HTMLCanvasElement, lesionCanvas: HTMLCanvasElement, drawOverlay: () => void) {
    if (!canRedo.value) return
    historyIndex.value++
    applySnapshot(history.value[historyIndex.value], skinCanvas, lesionCanvas, drawOverlay)
  }

  function applySnapshot(
    snap: HistorySnapshot,
    skinCanvas: HTMLCanvasElement,
    lesionCanvas: HTMLCanvasElement,
    drawOverlay: () => void,
  ) {
    const skinCtx = skinCanvas.getContext('2d')
    const lesionCtx = lesionCanvas.getContext('2d')
    if (!skinCtx || !lesionCtx) return
    skinCtx.putImageData(snap.skin, 0, 0)
    lesionCtx.putImageData(snap.lesion, 0, 0)
    drawOverlay()
  }

  function reset() {
    history.value = []
    historyIndex.value = -1
  }

  return {
    canUndo,
    canRedo,
    snapshot,
    undo,
    redo,
    reset,
  }
}
