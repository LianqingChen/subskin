<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { chatApi } from '@/api/chat'
import BreathingExercise from '@/components/assistant/BreathingExercise.vue'
import MoodRecordCard from '@/components/assistant/MoodRecordCard.vue'

const chatStore = useChatStore()
const authStore = useAuthStore()

const isStreaming = ref(false)
const showCrisisAlert = ref(false)
const showBreathing = ref(false)
const showMoodRecord = ref(false)
const showOverlay = computed(() => showBreathing.value || showMoodRecord.value)

const crisisKeywords = ['不想活了', '自杀', '死了算了', '结束生命', '活下去没意义', '想死', 'kill myself', 'suicide']
function detectCrisis(text: string): boolean { return crisisKeywords.some(kw => text.includes(kw)) }

async function sendMessage(text?: string) {
  const t = (text || '').trim()
  if (!t || isStreaming.value) return

  if (detectCrisis(t)) showCrisisAlert.value = true

  chatStore.addMessage('user', t)
  const skeletonId = chatStore.addThinkingMessage()
  isStreaming.value = true

  try {
    const stream = authStore.isLoggedIn ? chatApi.streamAsk(t, chatStore.conversationId, 'counseling') : chatApi.streamAskPublic(t, 'counseling')
    stream.reader.onToken = (token: string) => { chatStore.streamTokenToMessage(skeletonId, token) }
    stream.reader.onDone = () => { chatStore.finalizeMessage(skeletonId); isStreaming.value = false }
    stream.reader.onError = (error: string) => { chatStore.removeMessage(skeletonId); chatStore.addMessage('assistant', `抱歉，${error}`); isStreaming.value = false }
    await stream.reader.start()
  } catch {
    chatStore.removeMessage(skeletonId); chatStore.addMessage('assistant', '出了点问题，我们再试一次好吗？'); isStreaming.value = false
  }
}

function toggleBreathing() {
  if (showBreathing.value) { showBreathing.value = false; return }
  showBreathing.value = true
  showMoodRecord.value = false
}

function toggleMoodRecord() {
  if (showMoodRecord.value) { showMoodRecord.value = false; return }
  showMoodRecord.value = true
  showBreathing.value = false
}

const crisisResources = [
  { name: '全国心理援助热线', phone: '400-161-9995' },
  { name: '北京心理危机干预中心', phone: '010-82951332' },
  { name: '生命热线', phone: '400-821-1215' },
]

defineExpose({ sendMessage, showOverlay })
</script>

<template>
  <div>
    <!-- Crisis alert -->
    <div v-if="showCrisisAlert" class="fixed inset-0 z-40 bg-red-50/95 flex flex-col items-center justify-center p-6 text-center">
      <div class="text-5xl mb-4">❤️‍🩹</div>
      <p class="text-red-800 font-bold text-lg mb-2">我们很在意你</p>
      <p class="text-red-700 text-sm mb-4 max-w-xs">你的感受很重要。请考虑联系专业人士获得支持：</p>
      <div class="space-y-2 mb-6">
        <div v-for="r in crisisResources" :key="r.phone" class="text-sm text-red-600">{{ r.name }}<br/><span class="font-mono font-bold">{{ r.phone }}</span></div>
      </div>
      <button @click="showCrisisAlert = false" class="px-6 py-2 rounded-full bg-red-500 text-white text-sm hover:bg-red-600 transition-colors">我收到了，谢谢</button>
    </div>

    <!-- Quick tools -->
    <div class="flex gap-2 mt-3">
      <button @click="toggleBreathing"
        :class="['flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs transition-all duration-200', showBreathing ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/30' : 'bg-white border border-purple-100 text-purple-600 hover:bg-purple-50']">
        <span>🧘</span><span>正念呼吸</span>
      </button>
      <button @click="toggleMoodRecord"
        :class="['flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs transition-all duration-200', showMoodRecord ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30' : 'bg-white border border-blue-100 text-blue-600 hover:bg-blue-50']">
        <span>💗</span><span>心情记录</span>
      </button>
    </div>

    <!-- Full-screen overlay for breathing / mood record cards -->
    <Teleport to="body">
      <Transition name="overlay-fade">
        <div v-if="showOverlay" class="fixed inset-0 z-[70] flex flex-col bg-white safe-top safe-bottom">
          <!-- Card content (scrollable) -->
          <div class="flex-1 overflow-y-auto px-3 py-6">
            <div class="max-w-md mx-auto">
              <BreathingExercise v-if="showBreathing" @close="showBreathing = false" />
              <MoodRecordCard v-if="showMoodRecord" @close="showMoodRecord = false" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Messages -->
    <div v-if="chatStore.messages.length > 0" class="py-3 space-y-3">
      <div v-for="msg in chatStore.messages" :key="msg.id" :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']">
        <div class="max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed"
          :class="msg.role === 'user' ? 'bg-green-500 text-white rounded-br-md' : 'bg-gray-50 text-gray-800 rounded-bl-md'">
          <div v-if="msg.isSkeleton && !msg.content" class="flex items-center gap-2 text-green-500">
            <span class="inline-flex gap-1">
              <span class="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce" style="animation-delay:0s" />
              <span class="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce" style="animation-delay:0.15s" />
              <span class="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce" style="animation-delay:0.3s" />
            </span>
            <span class="text-xs text-gray-400">正在倾听...</span>
          </div>
          <div v-else class="answer-content">
            <span class="whitespace-pre-wrap">{{ msg.content }}</span>
            <span v-if="msg.isSkeleton && msg.content" class="inline-block w-1 h-4 bg-green-400 ml-0.5 animate-pulse align-text-bottom rounded-sm" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.answer-content {
  max-height: 50vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: auto;
}
.answer-content::-webkit-scrollbar {
  width: 3px;
}
.answer-content::-webkit-scrollbar-track {
  background: transparent;
}
.answer-content::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.18);
  border-radius: 3px;
}
.dark .answer-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.18);
}

/* Overlay transition */
.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: all 0.25s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
