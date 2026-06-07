import { ref, computed, onUnmounted } from 'vue'

interface SpeechRecognitionEvent {
  resultIndex: number
  results: SpeechRecognitionResultList
}

interface SpeechRecognitionResultList {
  length: number
  [index: number]: SpeechRecognitionResult
}

interface SpeechRecognitionResult {
  isFinal: boolean
  [index: number]: SpeechRecognitionAlternative
}

interface SpeechRecognitionAlternative {
  transcript: string
}

interface SpeechRecognitionInstance {
  continuous: boolean
  interimResults: boolean
  lang: string
  onstart: (() => void) | null
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance
  }
}

export function useSpeechRecognition() {
  const isListening = ref(false)
  const transcript = ref('')
  const error = ref<string | null>(null)
  
  const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition
  const isSupported = computed(() => !!SpeechRecognitionCtor)
  
  let recognition: any = null
  // Track whether we should auto-restart when recognition unexpectedly ends
  let shouldAutoRestart = false
  // Debounce restarts to avoid rapid-fire restart loops
  let restartTimer: ReturnType<typeof setTimeout> | null = null

  if (isSupported.value) {
    recognition = new SpeechRecognitionCtor!()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'zh-CN'

    recognition.onstart = () => {
      isListening.value = true
      error.value = null
    }

    recognition.onresult = (event: any) => {
      let currentTranscript = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        currentTranscript += result[0].transcript
      }
      transcript.value = currentTranscript
    }

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error', event.error)
      // 'no-speech' and 'aborted' are benign — don't show to user
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        error.value = event.error === 'not-allowed'
          ? '请授权麦克风权限后重试'
          : `语音识别错误: ${event.error}`
      }
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        shouldAutoRestart = false
      }
      isListening.value = false
    }

    recognition.onend = () => {
      isListening.value = false
      // Auto-restart if user hasn't explicitly stopped and no error occurred
      if (shouldAutoRestart) {
        if (restartTimer) clearTimeout(restartTimer)
        restartTimer = setTimeout(() => {
          if (shouldAutoRestart) {
            try {
              recognition.start()
            } catch (_err) {
              shouldAutoRestart = false
            }
          }
        }, 150)
      }
    }
  }

  function start() {
    if (!isSupported.value) {
      error.value = '您的浏览器不支持语音输入'
      return
    }
    
    if (isListening.value) return
    
    transcript.value = ''
    error.value = null
    shouldAutoRestart = true
    
    try {
      recognition.start()
    } catch (err) {
      console.error('Failed to start recognition:', err)
      shouldAutoRestart = false
      error.value = '无法启动语音识别，请刷新页面后重试'
    }
  }

  function stop() {
    shouldAutoRestart = false
    if (restartTimer) { clearTimeout(restartTimer); restartTimer = null }
    
    if (!isSupported.value || !isListening.value) return
    
    try {
      recognition.stop()
    } catch (err) {
      console.error('Failed to stop recognition:', err)
    }
  }

  function reset() {
    transcript.value = ''
    error.value = null
  }

  onUnmounted(() => {
    if (isListening.value) {
      stop()
    }
  })

  return {
    isListening,
    isSupported,
    transcript,
    error,
    start,
    stop,
    reset
  }
}
