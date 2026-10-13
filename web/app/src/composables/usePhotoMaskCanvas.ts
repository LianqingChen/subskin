import { ref, watch, onMounted, onBeforeUnmount, type Ref } from 'vue'
import { adoptUncertain, alphaMask, discardUncertain, paintPhotoMasks, replaceLayer, type PhotoMaskTool, type PhotoMasks } from '@/utils/photo-mask'
import { loadPhotoMasks, renderPhotoMasks, exportPhotoMasks, maskDataUrl, type LoadedPhotoMasks, type PhotoMaskSources } from '@/utils/photo-mask-canvas'
import { RGBTaskError, type RGBSelector } from '@/api/rgb-segmentation'
import { assessmentError } from '@/utils/assessment-errors'
export interface PhotoCanvasOptions extends PhotoMaskSources { editable?: boolean; busy?: boolean; tool?: PhotoMaskTool; brushSize?: number; refine?: RGBSelector | null; outline?: ((signal: AbortSignal) => Promise<{ lesion: string; uncertain: string }>) | null; snap?: ((skin: string, target: string, signal: AbortSignal) => Promise<string>) | null }
export function usePhotoMaskCanvas(options: PhotoCanvasOptions, target: Ref<HTMLCanvasElement | null>) {
  const ready = ref(false), error = ref(''), painting = ref(false)
  let loaded: LoadedPhotoMasks | null = null, generation = 0, frame = 0
  let activePointer: number | null = null, previous: [number, number] | null = null
  let dirty: { x: number; y: number; width: number; height: number } | undefined
  let strokeLayer: 'skin' | 'lesion' = 'lesion', strokeErase = false
  type Snap = { skin: Uint8Array; lesion: Uint8Array; uncertain: Uint8Array }
  let beforeStroke: Snap | null = null
  const refining = ref(false)
  const outlining = ref(false)
  const snapping = ref(false)
  const hasCandidate = ref(false)
  // 撤销/重做：每次笔画或 AI 结果落层前保存一份快照（1024 规范图上每份约 3MB），最多保留 20 步。
  const HISTORY_LIMIT = 20
  const undoStack: Snap[] = [], redoStack: Snap[] = []
  const canUndo = ref(false), canRedo = ref(false)
  function uncertainOf(masks: PhotoMasks): Uint8Array {
    return masks.uncertain && masks.uncertain.length === masks.skin.length ? masks.uncertain : new Uint8Array(masks.skin.length)
  }
  function cloneSnap(masks: PhotoMasks): Snap {
    return { skin: masks.skin.slice(), lesion: masks.lesion.slice(), uncertain: uncertainOf(masks).slice() }
  }
  function syncCandidate() { hasCandidate.value = !!loaded?.masks.uncertain?.some(Boolean) }
  function syncHistory() { canUndo.value = undoStack.length > 0; canRedo.value = redoStack.length > 0 }
  function sameMasks(a: Snap, masks: PhotoMasks) {
    const uncertain = uncertainOf(masks)
    if (a.uncertain.length !== uncertain.length) return false
    for (let i = 0; i < a.skin.length; i++) if (a.skin[i] !== masks.skin[i] || a.lesion[i] !== masks.lesion[i] || a.uncertain[i] !== uncertain[i]) return false
    return true
  }
  function recordChange(before: Snap) {
    if (!loaded || sameMasks(before, loaded.masks)) return
    undoStack.push(before); if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
    redoStack.length = 0; syncHistory(); syncCandidate()
  }
  function restore(from: Snap[], to: Snap[]) {
    const snap = from.pop()
    if (!snap || !loaded || painting.value || refining.value || outlining.value || snapping.value || options.busy) { if (snap) from.push(snap); return }
    to.push(cloneSnap(loaded.masks))
    loaded.masks.skin = snap.skin; loaded.masks.lesion = snap.lesion; loaded.masks.uncertain = snap.uncertain
    dirty = undefined; render(); syncHistory(); syncCandidate()
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
      loaded = state; render(); syncCandidate(); ready.value = true
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
    if (loaded && beforeStroke) { loaded.masks.skin = beforeStroke.skin; loaded.masks.lesion = beforeStroke.lesion; loaded.masks.uncertain = beforeStroke.uncertain; dirty = undefined; render() }
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
    const uncertain = state.masks.uncertain
    for (let i = 0; i < lesion.length; i++) {
      if (incoming[i] && skin[i] && !lesion[i]) { lesion[i] = 1; added++ }
      if (uncertain && incoming[i]) uncertain[i] = 0
    }
    render()
    return added
  }
  async function addRemoteUncertain(state: LoadedPhotoMasks, dataUrl: string): Promise<number> {
    const { width, height, skin, lesion } = state.masks
    const image = await loadMaskImage(dataUrl)
    if (loaded !== state) return 0
    if (image.naturalWidth !== width || image.naturalHeight !== height) throw new RGBTaskError('REVISION_CONFLICT')
    const incoming = readMaskAlpha(image, width, height)
    if (!state.masks.uncertain) state.masks.uncertain = new Uint8Array(lesion.length)
    const uncertain = state.masks.uncertain
    let added = 0
    for (let i = 0; i < uncertain.length; i++) if (incoming[i] && skin[i] && !lesion[i] && !uncertain[i]) { uncertain[i] = 1; added++ }
    render()
    return added
  }
  async function runOutline() {
    const outline = options.outline
    const state = loaded
    if (!outline || !state || refining.value || outlining.value || snapping.value) return
    refineController?.abort()
    const controller = new AbortController()
    refineController = controller
    const signal = controller.signal
    const before = cloneSnap(state.masks)
    outlining.value = true
    error.value = ''
    busyNote.value = '正在自动圈出候选范围…'
    try {
      const result = await outline(signal)
      if (signal.aborted || loaded !== state) return
      if (!sameMasks(before, state.masks)) { error.value = '标注已变化，请重新点按粗定位'; return }
      const addedLesion = result.lesion ? await addRemoteUncertain(state, result.lesion) : 0
      const addedUncertain = result.uncertain ? await addRemoteUncertain(state, result.uncertain) : 0
      if (addedLesion + addedUncertain === 0) error.value = 'AI 没找到白斑范围。可先用「白斑」画笔粗略涂一下，再用「贴合边界」'
      else error.value = '候选已标成浅橙，可一键当作白斑或丢弃'
      recordChange(before)
    } catch (e) {
      if (!signal.aborted) error.value = e instanceof RGBTaskError ? e.message : assessmentError(e, '视觉粗定位暂未完成，可使用画笔调整')
    } finally { outlining.value = false; busyNote.value = ''; syncCandidate() }
  }
  async function refineAt(x: number, y: number) {
    const selector = options.refine
    const state = loaded
    if (!selector || !state || refining.value || snapping.value) return
    refineController?.abort()
    const controller = new AbortController()
    refineController = controller
    const signal = controller.signal
    const { width, height } = state.masks
    const before = cloneSnap(state.masks)
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
      if (!sameMasks(before, state.masks)) { error.value = '标注已变化，请重新点选'; return }
      await applyRemoteLesionMask(state, dataUrl)
      recordChange(before)
    } catch (e) {
      if (!signal.aborted) error.value = e instanceof RGBTaskError ? e.message : assessmentError(e, '交互分割暂未完成，可使用画笔调整')
    } finally { refining.value = false; busyNote.value = ''; syncCandidate() }
  }
  function mutateCandidates(kind: 'adopt' | 'discard') {
    if (!loaded || painting.value || refining.value || outlining.value || snapping.value || options.busy) return
    const before = cloneSnap(loaded.masks)
    if (kind === 'adopt') adoptUncertain(loaded.masks)
    else discardUncertain(loaded.masks)
    dirty = undefined; render(); recordChange(before)
  }
  const adoptCandidates = () => mutateCandidates('adopt')
  const discardCandidates = () => mutateCandidates('discard')
  async function snapEdges() {
    const snap = options.snap
    const state = loaded
    if (!snap || !state || refining.value || outlining.value || snapping.value) return
    const useUncertain = !!state.masks.uncertain?.some(Boolean)
    if (!useUncertain && !state.masks.lesion.some(Boolean)) { error.value = '没有可贴合的范围'; return }
    refineController?.abort()
    const controller = new AbortController()
    refineController = controller
    const before = cloneSnap(state.masks)
    snapping.value = true
    error.value = ''
    busyNote.value = '正在贴合边界…'
    try {
      const { width, height } = state.masks
      const target = useUncertain ? uncertainOf(state.masks) : state.masks.lesion
      const dataUrl = await snap(exportPhotoMasks(state).skinMaskDataUrl, maskDataUrl(target, width, height), controller.signal)
      if (controller.signal.aborted || loaded !== state) return
      if (!sameMasks(before, state.masks)) { error.value = '标注已变化，请重新点按贴合边界'; return }
      const image = await loadMaskImage(dataUrl)
      if (image.naturalWidth !== width || image.naturalHeight !== height) throw new RGBTaskError('REVISION_CONFLICT')
      replaceLayer(state.masks, useUncertain ? 'uncertain' : 'lesion', readMaskAlpha(image, width, height))
      dirty = undefined; render(); recordChange(before)
    } catch (e) {
      if (!controller.signal.aborted) error.value = e instanceof RGBTaskError ? e.message : assessmentError(e, '边界贴合暂未完成，可使用画笔调整')
    } finally { snapping.value = false; busyNote.value = ''; syncCandidate() }
  }
  function down(e: PointerEvent) {
    if (!options.editable || options.busy || refining.value || outlining.value || snapping.value || !ready.value || !loaded) return
    if (activePointer !== null) { cancelStroke(); return }
    if (!e.isPrimary || e.button !== 0) return
    if (options.tool === 'refine') { e.preventDefault(); const at = point(e); if (at) void refineAt(at[0], at[1]); return }
    e.preventDefault()
    error.value = ''; activePointer = e.pointerId; painting.value = true
    beforeStroke = cloneSnap(loaded.masks)
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
  return { ready, error, painting, refining, outlining, snapping, hasCandidate, busyNote, canUndo, canRedo, undo, redo, load, down, move, up, cancelStroke, snapshot, runOutline, adoptCandidates, discardCandidates, snapEdges }
}
