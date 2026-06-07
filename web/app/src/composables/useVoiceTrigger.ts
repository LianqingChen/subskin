import { ref, onUnmounted } from 'vue'

type SpeechRecognitionType = any

interface VoiceTriggerOptions {
  keywords: string[]
  onTrigger: () => void
  lang?: string
}

const TRIGGER_DEBOUNCE_MS = 1500

export function useVoiceTrigger() {
  const supported = ref(
    typeof window !== 'undefined' &&
    (('SpeechRecognition' in window) || ('webkitSpeechRecognition' in window))
  )
  const listening = ref(false)
  const lastHeard = ref('')
  const errorMessage = ref('')

  let recognition: SpeechRecognitionType | null = null
  let lastTriggerAt = 0
  let shouldRestart = false

  function start(opts: VoiceTriggerOptions) {
    if (!supported.value) {
      errorMessage.value = '当前浏览器不支持语音识别'
      return false
    }
    if (listening.value) return true

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    recognition = new SpeechRecognition()
    recognition.lang = opts.lang || 'zh-CN'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    const keywords = opts.keywords.map(k => k.toLowerCase())

    recognition.onresult = (event: any) => {
      let transcript = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript
      }
      lastHeard.value = transcript.trim()
      const lower = transcript.toLowerCase()
      const matched = keywords.some(k => lower.includes(k))
      if (matched) {
        const now = Date.now()
        if (now - lastTriggerAt < TRIGGER_DEBOUNCE_MS) return
        lastTriggerAt = now
        opts.onTrigger()
      }
    }

    recognition.onerror = (event: any) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        errorMessage.value = '麦克风权限被拒绝'
        shouldRestart = false
      } else if (event.error === 'no-speech') {
        errorMessage.value = ''
      } else {
        errorMessage.value = `语音识别错误：${event.error}`
      }
    }

    recognition.onend = () => {
      if (shouldRestart && recognition) {
        try {
          recognition.start()
        } catch {
          listening.value = false
          shouldRestart = false
        }
      } else {
        listening.value = false
      }
    }

    try {
      shouldRestart = true
      recognition.start()
      listening.value = true
      errorMessage.value = ''
      return true
    } catch (e: any) {
      errorMessage.value = e?.message || '无法启动语音识别'
      listening.value = false
      shouldRestart = false
      return false
    }
  }

  function stop() {
    shouldRestart = false
    listening.value = false
    if (recognition) {
      try { recognition.stop() } catch { void 0 }
      recognition = null
    }
  }

  onUnmounted(stop)

  return { supported, listening, lastHeard, errorMessage, start, stop }
}
