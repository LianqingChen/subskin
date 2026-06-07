import { ref, computed, onUnmounted } from 'vue'

export function useSpeechSynthesis() {
  const isSpeaking = ref(false)
  const currentMessageId = ref<string | null>(null)
  const error = ref<string | null>(null)
  
  const isSupported = computed(() => 'speechSynthesis' in window)
  
  let utterance: SpeechSynthesisUtterance | null = null

  function getChineseVoice(): SpeechSynthesisVoice | null {
    if (!isSupported.value) return null
    
    const voices = window.speechSynthesis.getVoices()
    return voices.find(voice => voice.lang.includes('zh')) || 
           voices.find(voice => voice.lang.includes('cmn')) || 
           voices[0] || null
  }

  function speak(text: string, messageId: string) {
    if (!isSupported.value) {
      error.value = '您的浏览器不支持语音播报'
      return
    }

    stop()

    try {
      utterance = new SpeechSynthesisUtterance(text)
      
      const voice = getChineseVoice()
      if (voice) {
        utterance.voice = voice
      }
      
      utterance.lang = 'zh-CN'
      utterance.rate = 1.0
      utterance.pitch = 1.0

      utterance.onstart = () => {
        isSpeaking.value = true
        currentMessageId.value = messageId
        error.value = null
      }

      utterance.onend = () => {
        isSpeaking.value = false
        currentMessageId.value = null
      }

      utterance.onerror = (event) => {
        console.error('Speech synthesis error', event)
        if (event.error !== 'canceled') {
          error.value = '语音播报出错'
        }
        isSpeaking.value = false
        currentMessageId.value = null
      }

      window.speechSynthesis.speak(utterance)
    } catch (err) {
      console.error('Failed to start speech synthesis:', err)
      error.value = '无法启动语音播报'
      isSpeaking.value = false
      currentMessageId.value = null
    }
  }

  function stop() {
    if (!isSupported.value) return
    
    try {
      window.speechSynthesis.cancel()
      isSpeaking.value = false
      currentMessageId.value = null
    } catch (err) {
      console.error('Failed to stop speech synthesis:', err)
    }
  }

  if (isSupported.value) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices()
    }
  }

  onUnmounted(() => {
    stop()
  })

  return {
    isSpeaking,
    isSupported,
    currentMessageId,
    error,
    speak,
    stop
  }
}
