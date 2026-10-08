import { ref, watch, onMounted, onBeforeUnmount, type Ref } from 'vue'
import { alphaMask, paintPhotoMasks, type PhotoMaskTool } from '@/utils/photo-mask'
import { loadPhotoMasks, renderPhotoMasks, exportPhotoMasks, type LoadedPhotoMasks, type PhotoMaskSources } from '@/utils/photo-mask-canvas'
import { RGBTaskError, type RGBSelector } from '@/api/rgb-segmentation'
import { assessmentError } from '@/utils/assessment-errors'
export interface PhotoCanvasOptions extends PhotoMaskSources { editable?: boolean; busy?: boolean; tool?: PhotoMaskTool; brushSize?: number; refine?: RGBSelector | null; outline?: ((signal: AbortSignal) => Promise<{ lesion: string; uncertain: string }>) | null }
export function usePhotoMaskCanvas(options: PhotoCanvasOptions, target: Ref<HTMLCanvasElement | null>) {
  const ready = ref(false), error = ref(''), painting = ref(false)
  let loaded: LoadedPhotoMasks | null = null, generation = 0, frame = 0
  let activePointer: number | null = null, previous: [number, number] | null = null
  let dirty: { x: number; y: number; width: number; height: number } | undefined
  let strokeLayer: 'skin' | 'lesion' = 'lesion', strokeErase = false
  let beforeStroke: { skin: Uint8Array; lesion: Uint8Array } | null = null
  const refining = ref(false)
  const outlining = ref(false)
  // 撤销/重做：每次笔画或 AI 结果落层前保存一份快照（1024 规范图上每份约 2MB），最多保留 20 步。
  type Snap = { skin: Uint8Array; lesion: Uint8Array }
  const HISTORY_LIMIT = 20
  const undoStack: Snap[] = [], redoStack: Snap[] = []
  const canUndo = ref(false), canRedo = ref(false)
  function syncHistory() { canUndo.value = undoStack.length > 0; canRedo.value = redoStack.length > 0 }
  function sameMasks(a: Snap, b: Snap) {
    for (let i = 0; i < a.skin.length; i++) if (a.skin[i] !== b.skin[i] || a.lesion[i] !== b.lesion[i]) return false
    return true
  }
  function recordChange(before: Snap) {
    if (!loaded || sameMasks(before, loaded.masks)) return
    undoStack.push(before); if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
    redoStack.length = 0; syncHistory()
  }
  function restore(from: Snap[], to: Snap[]) {
    const snap = from.pop()
    if (!snap || !loaded || painting.value || refining.value || outlining.value || options.busy) { if (snap) from.push(snap); return }
    to.push({ skin: loaded.masks.skin, lesion: loaded.masks.lesion })
    loaded.masks.skin = snap.skin; loaded.masks.lesion = snap.lesion
    dirty = undefined; render(); syncHistory()
  }
  const undo = () => restore(undoStack, redoStack)
  const redo = () => restore(redoStack, undoStack)
  const busyNote = ref('')
  let refineController: AbortController | null = null
  function render() { if (loaded && target.value) renderPhotoMasks(target.value, loaded) }
  function schedule() { if (!frame) frame = requestAnimationFrame(() => {
    frame = 0
    if (loaded && target.value) renderPhotoMasks(target.value, loaded, dirty)
    dirty = undefined
  }) }
  async function load() {
    const current = ++generation; ready.value = false; error.value = ''; loaded = null; endStroke()
    undoStack.length = 0; redoStack.length = 0; syncHistory()
    try {
      const state = await loadPhotoMasks(options)
      if (current !== generation) return
      loaded = state; render(); ready.value = true
    } catch (e) { if (current === generation) error.value = e instanceof Error ? e.message : '照片加载失败，请重试' }
  }
  function point(e: PointerEvent): [number, number] | null {
    const rect = target.value?.getBoundingClientRect()
    if (!rect || !loaded || !rect.width || !rect.height || e.clientX < rect.left || e.clientY < rect.top || e.clientX >= rect.left + rect.width || e.clientY >= rect.top + rect.height) return null
    return [(e.clientX - rect.left) * loaded.masks.width / rect.width, (e.clientY - rect.top) * loaded.masks.height / rect.height]
  }
  function stroke(e: PointerEvent) {
    if (!loaded || !target.value) return
    const next = point(e)
    if (!next) { previous = null; return }
    const ratio = loaded.masks.width / target.value.getBoundingClientRect().width
    const radius = (options.brushSize || 12) * ratio / 2, from = previous || next
    paintPhotoMasks(loaded.masks, strokeLayer, strokeErase, from, next, radius)
    const x = Math.max(0, Math.floor(Math.min(from[0], next[0]) - radius - 1)), y = Math.max(0, Math.floor(Math.min(from[1], next[1]) - radius - 1))
    const right = Math.min(loaded.masks.width, Math.ceil(Math.max(from[0], next[0]) + radius + 2)), bottom = Math.min(loaded.masks.height, Math.ceil(Math.max(from[1], next[1]) + radius + 2))
    if (dirty) { const left = Math.min(x, dirty.x), top = Math.min(y, dirty.y); dirty = { x: left, y: top, width: Math.max(right, dirty.x + dirty.width) - left, height: Math.max(bottom, dirty.y + dirty.height) - top } }
    else dirty = { x, y, width: right - x, height: bottom - y }
    previous = next; schedule()
  }
  function endStroke() {
    const pointer = activePointer
    activePointer = null; beforeStroke = null; previous = null; painting.value = false
    if (pointer !== null && target.value?.hasPointerCapture(pointer)) target.value.releasePointerCapture(pointer)
  }
  function cancelStroke(event?: PointerEvent) {
    if (event && event.pointerId !== activePointer) return
    if (loaded && beforeStroke) { loaded.masks.skin = beforeStroke.skin; loaded.masks.lesion = beforeStroke.lesion; dirty = undefined; render() }
    endStroke()
  }
  function readMaskAlpha(image: HTMLImageElement, width: number, height: number): Uint8Array {
    const el = document.createElement('canvas'); el.width = width; el.height = height
    const ctx = el.getContext('2d', { willReadFrequently: true })
    if (!ctx) throw new Error('画布暂不可用，请重试')
    ctx.drawImage(image, 0, 0, width, height)
    return alphaMask(ctx.getImageData(0, 0, width, height).data)
  }
  function loadMaskImage(url: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve(image)
      image.onerror = () => reject(new Error('精修结果加载失败，请重试'))
      image.src = url
    })
  }
  async function applyRemoteLesionMask(state: LoadedPhotoMasks, dataUrl: string): Promise<number> {
    const { width, height, skin, lesion } = state.masks
    const image = await loadMaskImage(dataUrl)
    if (loaded !== state) return 0
    if (image.naturalWidth !== width || image.naturalHeight !== height) throw new RGBTaskError('REVISION_CONFLICT')
    const incoming = readMaskAlpha(image, width, height)
    // 远程结果只写入白斑层，并被当前皮肤范围约束，不扩大测量分母。
    let added = 0
    for (let i = 0; i < lesion.length; i++) if (incoming[i] && skin[i] && !lesion[i]) { lesion[i] = 1; added++ }
    render()
    return added
  }
  async function runOutline() {
    const outline = options.outline
    const state = loaded
    if (!outline || !state || refining.value || outlining.value) return
    refineController?.abort()
    const controller = new AbortController()
    refineController = controller
    const signal = controller.signal
    const { skin, lesion } = state.masks
    const skinBefore = skin.slice(), lesionBefore = lesion.slice()
    outlining.value = true
    error.value = ''
    busyNote.value = '正在自动圈出候选范围…'
    try {
      const result = await outline(signal)
      if (signal.aborted || loaded !== state) return
      for (let i = 0; i < skin.length; i++) if (skin[i] !== skinBefore[i] || lesion[i] !== lesionBefore[i]) { error.value = '标注已变化，请重新点按粗定位'; return }
      const added = await applyRemoteLesionMask(state, result.lesion)
      if (added === 0) {
        // 门禁未放行的提案以“候选草稿”落到白斑层，由用户核对或擦除；测量仍以用户确认为准。
        const fallback = result.uncertain ? await applyRemoteLesionMask(state, result.uncertain) : 0
        error.value = fallback > 0
          ? 'AI 未找到可直接确认的区域，候选已放入白斑层供你核对'
          : 'AI 没找到白斑范围。可先用「白斑」画笔粗略涂一下，再用「AI吸附」点白斑内部来贴合边界'
      }
      recordChange({ skin: skinBefore, lesion: lesionBefore })
    } catch (e) {
      if (!signal.aborted) error.value = e instanceof RGBTaskError ? e.message : assessmentError(e, '视觉粗定位暂未完成，可使用画笔调整')
    } finally { outlining.value = false; busyNote.value = '' }
  }
  async function refineAt(x: number, y: number) {
    const selector = options.refine
    const state = loaded
    if (!selector || !state || refining.value) return
    refineController?.abort()
    const controller = new AbortController()
    refineController = controller
    const signal = controller.signal
    const { width, height, skin, lesion } = state.masks
    const skinBefore = skin.slice(), lesionBefore = lesion.slice()
    const { skinMaskDataUrl } = exportPhotoMasks(state)
    refining.value = true
    error.value = ''
    busyNote.value = '正在吸附边界…'
    try {
      const dataUrl = await selector({
        x: (Math.min(width - 1, Math.max(0, Math.round(x))) + 0.5) / width,
        y: (Math.min(height - 1, Math.max(0, Math.round(y))) + 0.5) / height,
        skinMask: skinMaskDataUrl,
        signal,
      })
      if (signal.aborted || loaded !== state) return
      for (let i = 0; i < skin.length; i++) if (skin[i] !== skinBefore[i] || lesion[i] !== lesionBefore[i]) { error.value = '标注已变化，请重新点选'; return }
      await applyRemoteLesionMask(state, dataUrl)
      recordChange({ skin: skinBefore, lesion: lesionBefore })
    } catch (e) {
      if (!signal.aborted) error.value = e instanceof RGBTaskError ? e.message : assessmentError(e, '交互分割暂未完成，可使用画笔调整')
    } finally { refining.value = false; busyNote.value = '' }
  }
  function down(e: PointerEvent) {
    if (!options.editable || options.busy || refining.value || outlining.value || !ready.value || !loaded) return
    if (activePointer !== null) { cancelStroke(); return }
    if (!e.isPrimary || e.button !== 0) return
    if (options.tool === 'refine') { e.preventDefault(); const at = point(e); if (at) void refineAt(at[0], at[1]); return }
    e.preventDefault()
    error.value = ''; activePointer = e.pointerId; painting.value = true
    beforeStroke = { skin: loaded.masks.skin.slice(), lesion: loaded.masks.lesion.slice() }
    strokeErase = options.tool === 'eraser'; strokeLayer = options.tool === 'skin' || strokeErase ? 'skin' : 'lesion'; previous = point(e)
    target.value?.setPointerCapture(e.pointerId); stroke(e)
  }
  function move(e: PointerEvent) { if (e.pointerId === activePointer && !options.busy) { e.preventDefault(); stroke(e) } }
  function up(e: PointerEvent) {
    if (e.pointerId !== activePointer) return
    e.preventDefault(); if (!options.busy) stroke(e)
    const before = beforeStroke
    endStroke()
    if (before) recordChange(before)
  }
  function snapshot() {
    if (!ready.value || !loaded || painting.value || options.busy) return null
    if (!loaded.masks.skin.some(Boolean)) { error.value = '请用皮肤画笔标出可见皮肤'; return null }
    render()
    return { ...exportPhotoMasks(loaded), annotatedImageDataUrl: target.value?.toDataURL('image/png') }
  }
  watch(() => [options.image, options.skin, options.lesion, options.candidate], load)
  onMounted(load)
  onBeforeUnmount(() => { generation++; endStroke(); refineController?.abort(); if (frame) cancelAnimationFrame(frame); loaded = null })
  return { ready, error, painting, refining, outlining, busyNote, canUndo, canRedo, undo, redo, load, down, move, up, cancelStroke, snapshot, runOutline }
}
