<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  bodyPart: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'captured': [file: File]
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const stream = ref<MediaStream | null>(null)
const facingMode = ref<'environment' | 'user'>('user')
const error = ref('')
const loading = ref(true)

const bodyPartLabel = computed(() => {
  const map: Record<string, string> = {
    face: '面部', neck: '颈部', hands: '手部',
    trunk: '躯干', arms: '上肢', legs: '下肢', feet: '足部',
  }
  return map[props.bodyPart] || '患处'
})

type MaskShape = { type: 'ellipse' | 'rect'; attrs: Record<string, string> }[]

function getMaskShapes(part: string): MaskShape {
  switch (part) {
    case 'face':
      return [{ type: 'ellipse', attrs: { cx: '50', cy: '38', rx: '26', ry: '34' } }]
    case 'neck':
      return [{ type: 'rect', attrs: { x: '28', y: '22', width: '44', height: '36', rx: '10' } }]
    case 'hands':
      return [
        { type: 'ellipse', attrs: { cx: '25', cy: '50', rx: '20', ry: '26' } },
        { type: 'ellipse', attrs: { cx: '75', cy: '50', rx: '20', ry: '26' } },
      ]
    case 'feet':
      return [
        { type: 'ellipse', attrs: { cx: '28', cy: '72', rx: '19', ry: '16' } },
        { type: 'ellipse', attrs: { cx: '72', cy: '72', rx: '19', ry: '16' } },
      ]
    case 'trunk':
      return [{ type: 'rect', attrs: { x: '20', y: '16', width: '60', height: '58', rx: '12' } }]
    case 'arms':
      return [
        { type: 'rect', attrs: { x: '6', y: '14', width: '18', height: '62', rx: '9' } },
        { type: 'rect', attrs: { x: '76', y: '14', width: '18', height: '62', rx: '9' } },
      ]
    case 'legs':
      return [
        { type: 'rect', attrs: { x: '22', y: '38', width: '22', height: '52', rx: '9' } },
        { type: 'rect', attrs: { x: '56', y: '38', width: '22', height: '52', rx: '9' } },
      ]
    default:
      return [{ type: 'rect', attrs: { x: '12', y: '12', width: '76', height: '76', rx: '14' } }]
  }
}

const shapes = computed(() => getMaskShapes(props.bodyPart))

function renderShape(shape: { type: string; attrs: Record<string, string> }) {
  const keys = Object.entries(shape.attrs)
    .map(([k, v]) => `${k}="${v}"`)
    .join(' ')
  if (shape.type === 'ellipse') return `<ellipse ${keys} />`
  return `<rect ${keys} />`
}

function renderMaskHoles() {
  return shapes.value.map(s => renderShape({ ...s, attrs: { ...s.attrs, fill: 'black' } })).join('\n')
}

function renderOutlines() {
  return shapes.value
    .map(s => renderShape({ ...s, attrs: { ...s.attrs, fill: 'none', stroke: 'white', 'stroke-width': '0.35', 'stroke-dasharray': '2.5,2' } }))
    .join('\n')
}

const svgOverlay = computed(() => {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" style="width:100%;height:100%;position:absolute;top:0;left:0;pointer-events:none">
    <defs>
      <mask id="camera-mask">
        <rect width="100" height="100" fill="white" />
        ${renderMaskHoles()}
      </mask>
    </defs>
    <rect width="100" height="100" fill="rgba(0,0,0,0.55)" mask="url(#camera-mask)" />
    ${renderOutlines()}
  </svg>`
})

// ── Crop helpers: map SVG viewBox shapes → video pixel coordinates ──

interface CropRect { x: number; y: number; w: number; h: number }

function getShapeBoundingBox(part: string): CropRect {
  const shapeList = getMaskShapes(part)
  let minX = 100, minY = 100, maxX = 0, maxY = 0

  for (const shape of shapeList) {
    if (shape.type === 'ellipse') {
      const cx = parseFloat(shape.attrs.cx)
      const cy = parseFloat(shape.attrs.cy)
      const rx = parseFloat(shape.attrs.rx)
      const ry = parseFloat(shape.attrs.ry)
      minX = Math.min(minX, cx - rx)
      minY = Math.min(minY, cy - ry)
      maxX = Math.max(maxX, cx + rx)
      maxY = Math.max(maxY, cy + ry)
    } else {
      const x = parseFloat(shape.attrs.x)
      const y = parseFloat(shape.attrs.y)
      const w = parseFloat(shape.attrs.width)
      const h = parseFloat(shape.attrs.height)
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x + w)
      maxY = Math.max(maxY, y + h)
    }
  }

  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY }
}

function computeCropRect(
  videoW: number, videoH: number,
  containerW: number, containerH: number,
  part: string, isFront: boolean,
): CropRect {
  // SVG viewBox (0–100 square) → container mapping (xMidYMid slice)
  const svgScale = Math.max(containerW / 100, containerH / 100)

  const vboxToContainer = (vx: number, vy: number): [number, number] => [
    (vx - 50) * svgScale + containerW / 2,
    (vy - 50) * svgScale + containerH / 2,
  ]

  // Video → container mapping (object-cover)
  const videoScale = Math.max(containerW / videoW, containerH / videoH)
  const visibleVideoW = videoW * videoScale
  const visibleVideoH = videoH * videoScale
  const videoOffX = (containerW - visibleVideoW) / 2
  const videoOffY = (containerH - visibleVideoH) / 2

  const containerToVideo = (cx: number, cy: number): [number, number] => {
    // Front camera flips the display → flip container x before mapping
    const ex = isFront ? containerW - cx : cx
    return [(ex - videoOffX) / videoScale, (cy - videoOffY) / videoScale]
  }

  const bb = getShapeBoundingBox(part)
  const corners: [number, number][] = [
    vboxToContainer(bb.x, bb.y),
    vboxToContainer(bb.x + bb.w, bb.y),
    vboxToContainer(bb.x, bb.y + bb.h),
    vboxToContainer(bb.x + bb.w, bb.y + bb.h),
  ]

  let minPX = Infinity, minPY = Infinity, maxPX = -Infinity, maxPY = -Infinity
  for (const [cx, cy] of corners) {
    const [px, py] = containerToVideo(cx, cy)
    minPX = Math.min(minPX, px)
    minPY = Math.min(minPY, py)
    maxPX = Math.max(maxPX, px)
    maxPY = Math.max(maxPY, py)
  }

  // 5% padding around the shape
  const pw = (maxPX - minPX) * 0.05
  const ph = (maxPY - minPY) * 0.05

  return {
    x: Math.max(0, Math.floor(minPX - pw)),
    y: Math.max(0, Math.floor(minPY - ph)),
    w: Math.min(videoW, Math.ceil(maxPX - minPX + 2 * pw)),
    h: Math.min(videoH, Math.ceil(maxPY - minPY + 2 * ph)),
  }
}

async function startCamera() {
  loading.value = true
  error.value = ''
  try {
    if (stream.value) {
      stream.value.getTracks().forEach(t => t.stop())
    }
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: facingMode.value, width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: false,
    })
    if (videoRef.value) {
      videoRef.value.srcObject = stream.value
      await videoRef.value.play()
    }
  } catch (e: any) {
    error.value = e.name === 'NotAllowedError'
      ? '相机权限被拒绝，请在设置中允许访问相机'
      : `无法访问相机：${e.message || '未知错误'}`
  } finally {
    loading.value = false
  }
}

function flipCamera() {
  facingMode.value = facingMode.value === 'environment' ? 'user' : 'environment'
  startCamera()
}

function capture() {
  if (!videoRef.value || !canvasRef.value) return
  const video = videoRef.value
  const canvas = canvasRef.value

  // Get the container that holds both the video and SVG overlay
  const container = video.parentElement
  if (!container) return
  const rect = container.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return

  const isFront = facingMode.value === 'user'

  // Compute the crop rectangle in video-pixel coordinates
  const crop = computeCropRect(
    video.videoWidth, video.videoHeight,
    rect.width, rect.height,
    props.bodyPart, isFront,
  )

  canvas.width = crop.w
  canvas.height = crop.h

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  if (isFront) {
    // Mirror output to match what the user sees on screen
    ctx.drawImage(
      video,
      crop.x, crop.y, crop.w, crop.h,
      crop.w, 0, -crop.w, crop.h,
    )
  } else {
    ctx.drawImage(
      video,
      crop.x, crop.y, crop.w, crop.h,
      0, 0, crop.w, crop.h,
    )
  }

  canvas.toBlob((blob) => {
    if (!blob) return
    const file = new File([blob], `photo_${Date.now()}.jpg`, { type: 'image/jpeg' })
    emit('captured', file)
  }, 'image/jpeg', 0.9)
}

function close() {
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (val) => {
  if (val) startCamera()
  else {
    if (stream.value) {
      stream.value.getTracks().forEach(t => t.stop())
      stream.value = null
    }
  }
})

onUnmounted(() => {
  if (stream.value) {
    stream.value.getTracks().forEach(t => t.stop())
    stream.value = null
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="camera-fade">
      <div v-if="modelValue" class="fixed inset-0 z-[200] bg-black flex flex-col">
        <!-- Camera view -->
        <div class="relative flex-1 overflow-hidden">
          <div v-if="loading" class="absolute inset-0 flex items-center justify-center z-10">
            <div class="text-white text-center">
              <i class="ri-loader-4-line animate-spin text-3xl block mb-2"></i>
              <p class="text-sm opacity-80">启动相机...</p>
            </div>
          </div>

          <div v-if="error" class="absolute inset-0 flex items-center justify-center z-10 px-8">
            <div class="text-white text-center">
              <i class="ri-error-warning-line text-4xl block mb-3 opacity-60"></i>
              <p class="text-sm mb-4">{{ error }}</p>
              <button
                class="px-6 py-2.5 rounded-xl bg-white/20 text-white text-sm font-medium hover:bg-white/30 transition-colors"
                @click="close"
              >
                返回
              </button>
            </div>
          </div>

          <video
            v-show="!error"
            ref="videoRef"
            autoplay
            playsinline
            class="absolute inset-0 w-full h-full object-cover"
            :class="{ 'scale-x-[-1]': facingMode === 'user' }"
          />

          <!-- Overlay with body part guide -->
          <div
            v-show="!loading && !error"
            class="absolute inset-0"
            v-html="svgOverlay"
          />

          <!-- Body part label -->
          <div
            v-show="!loading && !error"
            class="absolute top-8 left-0 right-0 text-center pointer-events-none"
          >
            <span class="text-white/80 text-sm font-medium bg-black/30 px-4 py-1.5 rounded-full">
              请将{{ bodyPartLabel }}对准框内
            </span>
          </div>

          <canvas ref="canvasRef" class="hidden" />
        </div>

        <!-- Bottom bar -->
        <div
          v-show="!loading && !error"
          class="flex items-center justify-between px-8 pb-8 pt-4 bg-gradient-to-t from-black/80 to-transparent"
        >
          <!-- Close -->
          <button
            class="w-11 h-11 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center transition-colors"
            @click="close"
          >
            <i class="ri-close-line text-white text-xl"></i>
          </button>

          <!-- Capture button -->
          <button
            class="w-[68px] h-[68px] rounded-full border-[4px] border-white flex items-center justify-center hover:scale-105 active:scale-95 transition-transform"
            @click="capture"
          >
            <span class="w-[54px] h-[54px] rounded-full bg-white" />
          </button>

          <!-- Flip camera -->
          <button
            class="w-11 h-11 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center transition-colors"
            @click="flipCamera"
          >
            <i class="ri-camera-switch-line text-white text-xl"></i>
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.camera-fade-enter-active,
.camera-fade-leave-active {
  transition: opacity 0.25s ease;
}
.camera-fade-enter-from,
.camera-fade-leave-to {
  opacity: 0;
}
</style>
