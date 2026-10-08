<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { PART_LABELS } from '@/constants/bodySites'
import { toProtectedFileUrl } from '@/utils/file-url'
const props = defineProps<{ modelValue: boolean; bodyPart: string; baselineUrl?: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; captured: [File, { hasReferenceCard: boolean }]; cancel: [] }>()
const video = ref<HTMLVideoElement | null>(null)
const dialog = ref<HTMLElement | null>(null)
const facing = ref<'user' | 'environment'>('user')
const loading = ref(false)
const capturing = ref(false)
const error = ref('')
const showBaseline = ref(true)
let stream: MediaStream | null = null
let generation = 0
let returnFocus: HTMLElement | null = null
let previousOverflow: string | null = null

function releaseStream() {
  stream?.getTracks().forEach(track => track.stop())
  stream = null
  if (video.value) { video.value.pause(); video.value.srcObject = null }
}
function stop() {
  generation++
  loading.value = false
  capturing.value = false
  releaseStream()
}
function close() { stop(); emit('update:modelValue', false); emit('cancel') }
async function start() {
  stop()
  if (!props.modelValue || document.hidden) return
  const current = generation
  loading.value = true
  error.value = ''
  try {
    const requestedFacing = facing.value
    const resolution = { width: { ideal: 1920 }, height: { ideal: 1080 } }
    let next: MediaStream
    try {
      // Require the selected side first so a higher-resolution rear lens cannot win.
      next = await navigator.mediaDevices.getUserMedia({ video: { ...resolution, facingMode: { exact: requestedFacing } }, audio: false })
    } catch (cause) {
      if (!(cause instanceof DOMException) || !['OverconstrainedError', 'NotFoundError'].includes(cause.name)) throw cause
      if (current !== generation || !props.modelValue || document.hidden) return
      // Devices with a single lens (or no facing metadata) still get a usable camera.
      next = await navigator.mediaDevices.getUserMedia({ video: { ...resolution, facingMode: { ideal: requestedFacing } }, audio: false })
    }
    if (current !== generation || !props.modelValue || document.hidden) {
      next.getTracks().forEach(track => track.stop())
      return
    }
    stream = next
    await nextTick()
    if (current !== generation || !props.modelValue) return
    if (!video.value) throw new Error('preview-unavailable')
    video.value.srcObject = next
    await video.value.play()
  } catch {
    if (current !== generation || !props.modelValue) return
    releaseStream()
    error.value = '相机暂不可用。请允许相机权限后重试，或关闭后从相册选择照片。'
  } finally { if (current === generation) loading.value = false }
}
function capture() {
  const source = video.value
  if (!props.modelValue || loading.value || capturing.value || error.value || !stream || !source?.videoWidth || !source.videoHeight || source.readyState < 2) return
  const current = generation
  capturing.value = true
  try {
    const canvas = document.createElement('canvas')
    canvas.width = source.videoWidth
    canvas.height = source.videoHeight
    const context = canvas.getContext('2d')
    if (!context) throw new Error('canvas-unavailable')
    // Save the complete, unmirrored frame. Guides never enter the photograph.
    context.drawImage(source, 0, 0)
    canvas.toBlob(blob => {
      if (current !== generation || !props.modelValue) return
      capturing.value = false
      if (!blob) { releaseStream(); error.value = '照片生成失败，请重新打开相机后重试。'; return }
      const file = new File([blob], `observation-${Date.now()}.jpg`, { type: 'image/jpeg' })
      stop()
      emit('update:modelValue', false)
      emit('captured', file, { hasReferenceCard: false })
    }, 'image/jpeg', 0.95)
  } catch {
    capturing.value = false
    releaseStream()
    error.value = '照片生成失败，请重新打开相机后重试。'
  }
}
function onHidden() { if (document.hidden && props.modelValue) close() }
function onPageHide() { if (props.modelValue) close() }
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); close(); return }
  if (event.key !== 'Tab' || !dialog.value) return
  const nodes = [...dialog.value.querySelectorAll<HTMLElement>('button:not(:disabled), [tabindex="0"]')]
  const first = nodes[0], last = nodes[nodes.length - 1]
  if (!first || !last) { event.preventDefault(); dialog.value.focus(); return }
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
function releaseDialog() {
  document.removeEventListener('visibilitychange', onHidden)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('pagehide', onPageHide)
  if (previousOverflow !== null) { document.body.style.overflow = previousOverflow; previousOverflow = null }
  returnFocus?.focus()
  returnFocus = null
}
watch(() => props.modelValue, async open => {
  if (!open) { stop(); releaseDialog(); return }
  returnFocus = document.activeElement as HTMLElement | null
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  document.addEventListener('visibilitychange', onHidden)
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('pagehide', onPageHide)
  showBaseline.value = true
  facing.value = 'user'
  await nextTick()
  if (!props.modelValue) return
  dialog.value?.focus()
  await start()
})
onUnmounted(() => { stop(); releaseDialog() })
</script>
<template>
  <Teleport to="body">
    <section v-if="modelValue" ref="dialog" tabindex="-1" role="dialog" aria-modal="true" aria-label="拍摄白斑照片" class="fixed inset-0 z-[100] flex h-dvh flex-col bg-gray-950 text-white">
      <header class="shrink-0 flex items-center justify-between px-4 pt-[env(safe-area-inset-top)]">
        <h2 class="text-lg font-semibold">{{ PART_LABELS[bodyPart] || bodyPart || '拍摄照片' }}</h2>
        <button class="min-h-[44px] min-w-[44px]" aria-label="关闭相机" @click="close"><i class="ri-close-line text-2xl"></i></button>
      </header>
      <p class="shrink-0 px-4 py-3 text-sm text-gray-200">{{ baselineUrl ? '对照上次照片，保持相同角度与距离。' : '均匀光照下拍摄，把白斑边缘和周围正常皮肤拍完整。' }}</p>
      <div class="relative min-h-0 flex-1">
        <video ref="video" autoplay playsinline muted class="h-full w-full object-contain"></video>
        <img v-if="baselineUrl && showBaseline" :src="toProtectedFileUrl(baselineUrl)" alt="上次拍摄的位置参考" class="pointer-events-none absolute inset-0 h-full w-full object-contain opacity-30" />
        <p v-if="loading || error" role="status" class="absolute inset-x-4 top-1/2 rounded-xl bg-gray-900/90 p-4 text-center">{{ error || '正在打开相机…' }}</p>
      </div>
      <div class="shrink-0 space-y-3 px-4 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <button v-if="baselineUrl" class="min-h-[44px] w-full rounded-xl border border-gray-500 text-sm" :aria-pressed="showBaseline" @click="showBaseline = !showBaseline">{{ showBaseline ? '隐藏上次照片' : '显示上次照片' }}</button>
        <button v-if="error" class="min-h-[44px] w-full rounded-xl border border-gray-500" @click="start">重新打开相机</button>
        <div class="flex gap-3">
          <button class="min-h-[48px] flex-1 rounded-xl border border-gray-500" :disabled="loading || capturing" @click="facing = facing === 'user' ? 'environment' : 'user'; start()">切换镜头</button>
          <button class="min-h-[48px] flex-1 rounded-xl bg-primary-500 font-semibold disabled:opacity-40" :disabled="loading || capturing || !!error" @click="capture">{{ capturing ? '正在生成照片…' : '拍照' }}</button>
        </div>
      </div>
    </section>
  </Teleport>
</template>
