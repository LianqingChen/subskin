import { ref, onUnmounted } from 'vue'

export type QualityLevel = 'ok' | 'warn' | 'fail'

export interface CameraQualityState {
  blur: QualityLevel
  glare: QualityLevel
  darkness: QualityLevel
  skin: QualityLevel
  overall: QualityLevel
  blurScore: number
  glareRatio: number
  brightness: number
  skinRatio: number
  message: string
  hint: string
}

const DEFAULT_STATE: CameraQualityState = {
  blur: 'ok',
  glare: 'ok',
  darkness: 'ok',
  skin: 'ok',
  overall: 'ok',
  blurScore: 0,
  glareRatio: 0,
  brightness: 128,
  skinRatio: 0,
  message: '',
  hint: '',
}

const SAMPLE_SIZE = 160
const SAMPLE_INTERVAL_MS = 800

const BLUR_FAIL_THRESHOLD = 8
const BLUR_WARN_THRESHOLD = 25
const GLARE_FAIL_RATIO = 0.25
const GLARE_WARN_RATIO = 0.15
const DARK_FAIL = 25
const DARK_WARN = 50
const BRIGHT_FAIL = 245
const BRIGHT_WARN = 230
const SKIN_FAIL_RATIO = 0.01
const SKIN_WARN_RATIO = 0.04

/**
 * Lightweight on-device camera quality monitor.
 * Samples a downscaled grayscale frame every 500ms and computes:
 *   - Variance of Laplacian (focus measure) for blur
 *   - Ratio of saturated pixels (>=250) for glare
 *   - Mean luminance for darkness
 * All math is pure JS, zero deps, ~3ms per sample on a 160×120 frame.
 */
export function useCameraQuality() {
  const state = ref<CameraQualityState>({ ...DEFAULT_STATE })
  const running = ref(false)
  let timer: number | null = null
  let canvas: HTMLCanvasElement | null = null
  let ctx: CanvasRenderingContext2D | null = null

  function ensureCanvas() {
    if (canvas) return
    canvas = document.createElement('canvas')
    canvas.width = SAMPLE_SIZE
    canvas.height = Math.round(SAMPLE_SIZE * 0.75)
    ctx = canvas.getContext('2d', { willReadFrequently: true })
  }

  function sampleFrame(video: HTMLVideoElement): CameraQualityState {
    if (!ctx || !canvas) return state.value
    if (video.videoWidth === 0 || video.videoHeight === 0) return state.value

    const w = canvas.width
    const h = canvas.height
    ctx.drawImage(video, 0, 0, w, h)
    const img = ctx.getImageData(0, 0, w, h)
    const data = img.data
    const pixels = w * h

    const gray = new Uint8ClampedArray(pixels)
    let brightSum = 0
    let glarePixels = 0
    let skinPixels = 0
    for (let i = 0; i < pixels; i++) {
      const idx = i * 4
      const r = data[idx]
      const g = data[idx + 1]
      const b = data[idx + 2]
      const lum = (r * 0.299 + g * 0.587 + b * 0.114) | 0
      gray[i] = lum
      brightSum += lum
      if (r >= 250 && g >= 250 && b >= 250) glarePixels++

      const cr = ((r * 0.5) - (g * 0.4187) - (b * 0.0813) + 128) | 0
      const cb = ((-r * 0.1687) - (g * 0.3313) + (b * 0.5) + 128) | 0
      if (cr >= 133 && cr <= 180 && cb >= 77 && cb <= 130 && lum >= 50) {
        skinPixels++
      }
    }
    const brightness = brightSum / pixels
    const glareRatio = glarePixels / pixels
    const skinRatio = skinPixels / pixels

    let laplacianSum = 0
    let laplacianSqSum = 0
    let count = 0
    for (let y = 1; y < h - 1; y++) {
      for (let x = 1; x < w - 1; x++) {
        const i = y * w + x
        const v =
          -gray[i - w - 1] - gray[i - w] - gray[i - w + 1] +
          -gray[i - 1]      + 8 * gray[i] - gray[i + 1] +
          -gray[i + w - 1] - gray[i + w] - gray[i + w + 1]
        laplacianSum += v
        laplacianSqSum += v * v
        count++
      }
    }
    const mean = laplacianSum / count
    const blurScore = laplacianSqSum / count - mean * mean

    const blur: QualityLevel =
      blurScore < BLUR_FAIL_THRESHOLD ? 'fail' :
      blurScore < BLUR_WARN_THRESHOLD ? 'warn' : 'ok'
    const glare: QualityLevel =
      glareRatio > GLARE_FAIL_RATIO ? 'fail' :
      glareRatio > GLARE_WARN_RATIO ? 'warn' : 'ok'
    const darkness: QualityLevel =
      brightness < DARK_FAIL || brightness > BRIGHT_FAIL ? 'fail' :
      brightness < DARK_WARN || brightness > BRIGHT_WARN ? 'warn' : 'ok'
    const skin: QualityLevel =
      skinRatio < SKIN_FAIL_RATIO ? 'fail' :
      skinRatio < SKIN_WARN_RATIO ? 'warn' : 'ok'

    const overall: QualityLevel =
      [blur, glare, darkness].includes('fail') ? 'warn' :
      [blur, glare, darkness, skin].includes('warn') ? 'warn' : 'ok'

    let message = ''
    let hint = ''
    if (brightness < DARK_FAIL) {
      message = '光线很暗'
      hint = '画面看不清，建议补一点光'
    } else if (brightness > BRIGHT_FAIL) {
      message = '画面过曝'
      hint = '稍微避开强光会更好'
    } else if (glare === 'fail') {
      message = '反光较强'
      hint = '可以换个角度，仍可拍摄'
    } else if (blur === 'fail' && skin === 'fail') {
      message = '画面不清晰'
      hint = '靠近一些再试，仍可拍摄'
    } else {
      message = '准备就绪'
      hint = '随时可以拍摄'
    }

    return { blur, glare, darkness, skin, overall, blurScore, glareRatio, brightness, skinRatio, message, hint }
  }

  function start(video: HTMLVideoElement) {
    stop()
    ensureCanvas()
    running.value = true
    const tick = () => {
      if (!running.value) return
      try {
        state.value = sampleFrame(video)
      } catch {
        // sampling failures are non-fatal (video not ready, tab hidden, etc.)
      }
      timer = window.setTimeout(tick, SAMPLE_INTERVAL_MS)
    }
    tick()
  }

  function stop() {
    running.value = false
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    state.value = { ...DEFAULT_STATE }
  }

  onUnmounted(stop)

  return { state, start, stop, running }
}
