<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useSpeechRecognition } from '@/composables/useSpeechRecognition'
import { useSpeechSynthesis } from '@/composables/useSpeechSynthesis'
import { chatApi } from '@/api/chat'
import ButterflyMascot from '@/components/assistant/ButterflyMascot.vue'

const router = useRouter()
const chatStore = useChatStore()
const authStore = useAuthStore()
const { isListening, isSupported: sttSupported, transcript, start: sttStart, stop: sttStop, reset: sttReset } = useSpeechRecognition()
const { isSpeaking, isSupported: ttsSupported, speak: ttsSpeak, stop: ttsStop } = useSpeechSynthesis()

type CallState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error'
const callState = ref<CallState>('idle')
const displayText = ref('')
const aiResponse = ref('')
const callStatus = ref('')
const autoRestart = ref(true)
const textMode = computed(() => !sttSupported.value && ttsSupported.value)

// Text input mode
const inputText = ref('')
const isSending = ref(false)
const inputEl = ref<HTMLInputElement>()

watch(transcript, (val) => {
  displayText.value = val
})

// Detect final transcript and submit (voice mode)
watch(isListening, (val, oldVal) => {
  if (oldVal === true && val === false && transcript.value.trim() && callState.value === 'listening') {
    submitVoiceQuery(transcript.value.trim())
  }
})

async function submitVoiceQuery(text: string) {
  if (!text) return
  callState.value = 'thinking'
  callStatus.value = '思考中...'
  displayText.value = text
  aiResponse.value = ''
  isSending.value = true

  chatStore.addMessage('user', text, undefined, true)
  const skeletonId = chatStore.addThinkingMessage(true)

  try {
    const stream = authStore.isLoggedIn
      ? chatApi.streamAsk(text, chatStore.conversationId)
      : chatApi.streamAskPublic(text)

    stream.reader.onToken = (token: string) => {
      chatStore.streamTokenToMessage(skeletonId, token)
      aiResponse.value += token
    }

    stream.reader.onDone = (data: any) => {
      chatStore.finalizeMessage(skeletonId, data.sources)
      callState.value = 'speaking'
      callStatus.value = '小金正在说话...'
      isSending.value = false
      speakResponse(aiResponse.value)
    }

    stream.reader.onError = (error: string) => {
      chatStore.removeMessage(skeletonId)
      aiResponse.value = `抱歉，${error}`
      callState.value = 'speaking'
      isSending.value = false
      speakResponse(aiResponse.value)
    }

    await stream.reader.start()
  } catch {
    chatStore.removeMessage(skeletonId)
    aiResponse.value = '出了点问题，请再说一次吧～'
    callState.value = 'speaking'
    isSending.value = false
    speakResponse(aiResponse.value)
  }
}

function sendTextMessage() {
  const text = inputText.value.trim()
  if (!text || isSending.value) return
  inputText.value = ''
  submitVoiceQuery(text)
}

function speakResponse(text: string) {
  const cleanText = text.replace(/[*_~`]/g, '').trim()
  if (!cleanText) {
    startListening()
    return
  }
  ttsSpeak(cleanText, 'voice_' + Date.now())

  const checkSpeaking = setInterval(() => {
    if (!isSpeaking.value && callState.value === 'speaking') {
      clearInterval(checkSpeaking)
      if (autoRestart.value) {
        if (textMode.value) {
          callState.value = 'idle'
          callStatus.value = '请继续输入文字...'
        } else {
          startListening()
        }
      }
    }
  }, 300)
}

function startListening() {
  callState.value = 'listening'
  callStatus.value = '我在听...'
  displayText.value = ''
  aiResponse.value = ''
  sttReset()
  sttStart()
}

function toggleCall() {
  if (callState.value === 'idle' || callState.value === 'error') {
    if (textMode.value) {
      callState.value = 'idle'
      callStatus.value = '请输入你想说的话...'
    } else {
      startListening()
    }
  } else {
    endCall()
  }
}

function endCall() {
  autoRestart.value = false
  ttsStop()
  sttStop()
  callState.value = 'idle'
  callStatus.value = ''
  displayText.value = ''
  aiResponse.value = ''
  inputText.value = ''
  isSending.value = false
  router.back()
}

function interrupt() {
  if (callState.value === 'speaking') {
    ttsStop()
    if (textMode.value) {
      callState.value = 'idle'
      callStatus.value = '请继续输入文字...'
    } else {
      startListening()
    }
  }
}

const pulseScale = computed(() => {
  if (callState.value === 'listening') return 'scale-100'
  if (callState.value === 'thinking') return 'scale-90'
  if (callState.value === 'speaking') return 'scale-95'
  return 'scale-90'
})

onMounted(() => {
  if (!ttsSupported.value) {
    callState.value = 'error'
    callStatus.value = '您的浏览器不支持语音功能'
  } else if (textMode.value) {
    callState.value = 'idle'
    callStatus.value = '文字输入模式 · 我可以用语音回复你'
  }
})

onUnmounted(() => {
  ttsStop()
  sttStop()
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex flex-col items-center justify-between safe-area-inset"
    style="background: linear-gradient(180deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%)">
    <!-- Top bar -->
    <div class="w-full px-4 py-3 flex justify-between items-center">
      <button @click="endCall" class="text-white/60 hover:text-white/90 transition-colors p-2">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 12H5m7-7l-7 7 7 7" />
        </svg>
      </button>
      <span class="text-white/80 text-sm font-medium">{{ textMode ? '文字通话' : '语音通话' }}</span>
      <div class="w-10" />
    </div>

    <!-- Butterfly + status -->
    <div class="flex flex-col items-center mt-4">
      <div class="relative">
        <div v-if="callState === 'listening'" class="absolute inset-0 rounded-full animate-ping bg-amber-400/20" style="width:160px;height:160px;top:-30px;left:-30px" />
        <div v-if="callState === 'listening'" class="absolute inset-0 rounded-full animate-ping bg-amber-400/10" style="width:200px;height:200px;top:-50px;left:-50px;animation-delay:0.3s" />
        <div v-if="callState === 'speaking'" class="absolute inset-0 rounded-full bg-green-400/20" style="width:160px;height:160px;top:-30px;left:-30px;animation: pulse-glow 2s ease-in-out infinite" />

        <div :class="['transition-transform duration-500', pulseScale]">
          <ButterflyMascot size="lg" :animated="callState !== 'idle'" />
        </div>
      </div>

      <p class="text-white/70 text-sm mt-3 mb-1">{{ callStatus || '按下开始通话' }}</p>

      <!-- Mode indicator -->
      <p v-if="textMode && callState === 'idle'" class="text-white/30 text-xs">
        <span class="inline-flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/></svg>
          当前浏览器不支持语音输入，请打字对话
        </span>
      </p>

      <p v-if="callState === 'error'" class="text-red-400/80 text-xs mt-1">{{ callStatus }}</p>
    </div>

    <!-- Transcript area -->
    <div class="flex-1 w-full px-6 py-4 overflow-y-auto max-w-md mx-auto">
      <div v-if="displayText" class="mb-4 text-right">
        <div class="inline-block bg-amber-500/20 text-amber-200 px-4 py-2 rounded-2xl rounded-br-md text-sm max-w-[80%]">
          {{ displayText }}
        </div>
      </div>

      <div v-if="aiResponse" class="text-left">
        <div class="inline-block bg-white/10 text-white/90 px-4 py-2 rounded-2xl rounded-bl-md text-sm max-w-[80%] leading-relaxed">
          {{ aiResponse }}
          <span v-if="callState === 'thinking'" class="inline-block w-1.5 h-4 bg-amber-400 ml-0.5 animate-pulse align-text-bottom rounded-sm" />
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="!displayText && !aiResponse && callState !== 'listening' && callState !== 'thinking'" class="flex flex-col items-center justify-center h-full text-white/20 text-center">
        <div class="text-4xl mb-3">💬</div>
        <p class="text-xs">{{ textMode ? '在下方输入你想说的话' : '点击麦克风开始对话' }}</p>
      </div>
    </div>

    <!-- Controls -->
    <div class="w-full pb-4 px-4 max-w-md mx-auto">
      <!-- Mic visualizer (voice mode only) -->
      <div v-if="callState === 'listening' && !textMode" class="flex justify-center gap-1 mb-4">
        <div v-for="i in 5" :key="i" class="w-1 bg-amber-400/60 rounded-full animate-pulse"
          :style="{ height: `${12 + Math.random() * 20}px`, animationDelay: `${i * 0.1}s` }" />
      </div>

      <!-- Text input (text mode) -->
      <div v-if="textMode && callState !== 'speaking'" class="flex items-center gap-2 mb-2">
        <input
          ref="inputEl"
          v-model="inputText"
          type="text"
          placeholder="输入你想说的话..."
          :disabled="isSending"
          class="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-sm text-white placeholder-white/30 outline-none focus:border-amber-400/50 focus:ring-1 focus:ring-amber-400/30 transition-all"
          @keydown.enter="sendTextMessage"
        />
        <button
          @click="sendTextMessage"
          :disabled="!inputText.trim() || isSending"
          class="shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all"
          :class="inputText.trim() && !isSending ? 'bg-amber-500 text-white hover:bg-amber-400 active:scale-90' : 'bg-white/10 text-white/30'"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <!-- Typing indicator during AI thinking -->
      <div v-if="textMode && isSending" class="flex justify-center py-3">
        <div class="flex gap-1">
          <span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay:0s" />
          <span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay:0.15s" />
          <span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay:0.3s" />
        </div>
      </div>

      <!-- Action buttons -->
      <div class="flex justify-center items-center gap-6 mt-2">
        <!-- End call -->
        <button @click="endCall"
          class="w-14 h-14 rounded-full bg-red-500/90 hover:bg-red-600 flex items-center justify-center shadow-lg shadow-red-500/30 transition-all active:scale-90">
          <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
          </svg>
        </button>

        <!-- Main action button -->
        <button @click="callState === 'speaking' ? interrupt() : toggleCall()"
          :class="[
            'w-20 h-20 rounded-full flex items-center justify-center shadow-xl transition-all duration-300 active:scale-90',
            callState === 'idle' || callState === 'error' ? 'bg-amber-500 hover:bg-amber-400 shadow-amber-500/40' : '',
            callState === 'listening' ? 'bg-gradient-to-br from-amber-400 to-orange-500 shadow-amber-500/50 animate-pulse' : '',
            callState === 'thinking' ? 'bg-amber-600/80 shadow-amber-500/20' : '',
            callState === 'speaking' ? 'bg-green-500 hover:bg-green-400 shadow-green-500/40' : '',
          ]">
          <!-- Idle: microphone icon -->
          <svg v-if="callState === 'idle' || callState === 'error'" class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
          <!-- Listening: active mic -->
          <svg v-else-if="callState === 'listening'" class="w-8 h-8 text-white" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
          </svg>
          <!-- Speaking: interrupt bars -->
          <div v-else-if="callState === 'speaking'" class="flex gap-1">
            <span v-for="i in 3" :key="i" class="w-1.5 bg-white rounded-full animate-pulse"
              :style="{ height: `${10 + i * 4}px`, animationDelay: `${i * 0.2}s`, animationDuration: '0.8s' }" />
          </div>
          <!-- Thinking: loading dots -->
          <div v-else class="flex gap-0.5">
            <span class="w-1.5 h-4 bg-white/80 rounded-full animate-bounce" style="animation-delay:0s" />
            <span class="w-1.5 h-4 bg-white/80 rounded-full animate-bounce" style="animation-delay:0.15s" />
            <span class="w-1.5 h-4 bg-white/80 rounded-full animate-bounce" style="animation-delay:0.3s" />
          </div>
        </button>

        <!-- Mute placeholder -->
        <button @click="endCall"
          class="w-14 h-14 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center shadow-lg transition-all active:scale-90">
          <svg class="w-6 h-6 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
          </svg>
        </button>
      </div>

      <!-- Hints -->
      <p v-if="!ttsSupported && callState === 'error'" class="text-center text-white/40 text-xs mt-4">
        请使用 Chrome 浏览器打开
      </p>
      <p v-else-if="textMode && callState === 'idle'" class="text-center text-white/40 text-xs mt-3">
        输入文字后点发送，我用语音回复你
      </p>
      <p v-else-if="callState === 'listening'" class="text-center text-white/40 text-xs mt-3">
        直接说话即可，我听到后会回答你
      </p>
      <p v-else-if="callState === 'speaking'" class="text-center text-white/40 text-xs mt-3">
        点中间按钮可以打断我
      </p>
    </div>
  </div>
</template>

<style scoped>
@keyframes pulse-glow {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.05); }
}
</style>
