<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useSpeechSynthesis } from '@/composables/useSpeechSynthesis'
import ChatPanel from '@/components/assistant/ChatPanel.vue'
import CounselingPanel from '@/components/assistant/CounselingPanel.vue'

const chatStore = useChatStore()
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)
const counselingPanelRef = ref<InstanceType<typeof CounselingPanel> | null>(null)

const { speak: _ttsSpeak } = useSpeechSynthesis()


type Mode = 'chat' | 'counseling'
const mode = ref<Mode>('chat')
const inputText = ref('')
const inputEl = ref<HTMLTextAreaElement | null>(null)
const isInputFocused = ref(false)
const chatScrollEl = ref<HTMLElement | null>(null)

const chatPresetCategories = [
  { label: '病情咨询', questions: ['白癜风会传染吗？', '白斑扩散了怎么办？', '308激光效果怎么样？', '白癜风会遗传吗？'] },
  { label: '治疗用药', questions: ['他克莫司怎么用？', 'JAK抑制剂是什么？', '光疗多久做一次？'] },
  { label: '心理生活', questions: ['我刚确诊该怎么办？', '孕期白斑会加重吗？', '遮盖液怎么选？', '日常饮食需要注意什么？'] },
]

const counselingPresetCategories = [
  { label: '情绪支持', questions: ['确诊白癜风后很焦虑，怎么办？', '白斑让我不敢社交，如何克服？', '如何面对他人的眼光？'] },
  { label: '自我接纳', questions: ['治疗没效果，很沮丧...', '家人不理解我的痛苦', '我该如何接受自己的皮肤？'] },
]

const allChatPresets = computed(() => chatPresetCategories.flatMap(c => c.questions))
const allCounselingPresets = computed(() => counselingPresetCategories.flatMap(c => c.questions))

const currentPresetCategories = computed(() =>
  mode.value === 'chat' ? chatPresetCategories : counselingPresetCategories
)

const currentPresets = computed(() =>
  mode.value === 'chat' ? allChatPresets.value : allCounselingPresets.value
)

const canSend = computed(() => !isStreaming.value && (!!inputText.value.trim() || showInlinePreset.value))

const showInputBar = computed(() => {
  if (mode.value !== 'counseling') return true
  return !(counselingPanelRef.value as any)?.showOverlay
})

// Input-inline preset rotation
const presetIndex = ref(0)
let presetTimer: ReturnType<typeof setInterval> | null = null
const presetPaused = ref(false)

const currentPreset = computed(() => currentPresets.value[presetIndex.value] || '')

const showInlinePreset = computed(() => {
  if (isInputFocused.value) return false
  if (isStreaming.value) return false
  if (inputText.value.trim()) return false
  return currentPresets.value.length > 0
})

function startPresetRotation() {
  if (presetTimer || currentPresets.value.length === 0) return
  presetIndex.value = 0
  presetTimer = setInterval(() => {
    if (presetPaused.value) return
    presetIndex.value = (presetIndex.value + 1) % currentPresets.value.length
  }, 3000)
}

function stopPresetRotation() {
  if (presetTimer) { clearInterval(presetTimer); presetTimer = null }
}

function autoResize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

const isStreaming = computed(() => chatStore.messages.some(m => m.isSkeleton))
const hasMessages = computed(() => chatStore.messages.length > 0)

// Preset question cards removed — presets now only scroll inside the input box (inline rotation)
const showPresetPanel = computed(() => false)

const matchedQuestions = computed(() => {
  const text = inputText.value.trim()
  if (!text) return [] as string[]
  const candidates = currentPresets.value
  const scored = candidates.map(q => ({ q, score: matchScore(text, q) }))
  scored.sort((a, b) => b.score - a.score)
  return scored.filter(s => s.score > 0).slice(0, 5).map(s => s.q)
})

function matchScore(input: string, question: string): number {
  const q = question.toLowerCase()
  const inp = input.toLowerCase()
  if (q === inp) return 100
  if (q.includes(inp)) return 90
  if (inp.includes(q)) return 85
  let score = 0
  for (const ch of inp) { if (q.includes(ch)) score += 2 }
  for (let i = 0; i < inp.length - 1; i++) {
    if (q.includes(inp.slice(i, i + 2))) score += 5
  }
  const words = inp.split(/[，。？\s]+/).filter(Boolean)
  for (const w of words) { if (w.length >= 2 && q.includes(w)) score += 10 }
  return score
}

function setMode(m: Mode) {
  if (mode.value === m) return
  mode.value = m
}

function onInputFocus() {
  isInputFocused.value = true
  stopPresetRotation()
}

function onInputBlur() {
  isInputFocused.value = false
  if (!inputText.value.trim() && !hasMessages.value) {
    startPresetRotation()
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = chatScrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(() => chatStore.messages.length, () => scrollToBottom())
watch(() => chatStore.messages.map(m => m.content).join(''), () => scrollToBottom())

// Live transcript display while recording



async function sendMessage() {
  if (isStreaming.value) return
  const text = inputText.value.trim()
  const message = text || (showInlinePreset.value ? currentPreset.value : '')
  if (!message) return
  inputText.value = ''
  if (mode.value === 'chat') chatPanelRef.value?.sendMessage(message)
  else counselingPanelRef.value?.sendMessage(message)
  inputEl.value?.blur()
}

function sendPreset(q: string) {
  inputText.value = ''
  if (mode.value === 'chat') chatPanelRef.value?.sendMessage(q)
  else counselingPanelRef.value?.sendMessage(q)
  inputEl.value?.blur()
}

function newConversation() {
  chatStore.clearChat()
  stopPresetRotation()
  if (!isInputFocused.value) startPresetRotation()
}

function toggleHistory() { if (mode.value === 'chat') chatPanelRef.value?.toggleHistory() }


const modeHint = computed(() =>
  mode.value === 'chat'
    ? '科普资讯，智能问答 — 随时解答白癜风相关问题'
    : '温暖倾听，安静陪伴 — 这里没有评判，只有理解和关怀'
)

onMounted(() => {
  if (!hasMessages.value) startPresetRotation()
  setupScrollChain()
})
onUnmounted(() => {
  stopPresetRotation()
  teardownScrollChain()
})

// ── Scroll chain: answer-content ↔ chat-scroll ──
let wheelHandler: ((e: WheelEvent) => void) | null = null
let touchStartY = 0
let touchMoveHandler: ((e: TouchEvent) => void) | null = null
let touchStartHandler: ((e: TouchEvent) => void) | null = null

function setupScrollChain() {
  const scrollEl = chatScrollEl.value
  if (!scrollEl) return

  // Desktop: intercept wheel events on answer-content at scroll boundary
  wheelHandler = (e: WheelEvent) => {
    const answerEl = (e.target as HTMLElement).closest('.answer-content') as HTMLElement | null
    if (!answerEl) return

    const atTop = answerEl.scrollTop <= 0
    const atBottom = answerEl.scrollTop + answerEl.clientHeight >= answerEl.scrollHeight - 1

    if ((e.deltaY < 0 && atTop) || (e.deltaY > 0 && atBottom)) {
      e.preventDefault()
      scrollEl.scrollTop += e.deltaY
    }
  }
  scrollEl.addEventListener('wheel', wheelHandler, { capture: true, passive: false })

  // Mobile: touch scroll chain
  touchStartHandler = (e: TouchEvent) => {
    touchStartY = e.touches[0].clientY
  }
  touchMoveHandler = (e: TouchEvent) => {
    const answerEl = (e.target as HTMLElement).closest('.answer-content') as HTMLElement | null
    if (!answerEl) return

    const touchY = e.touches[0].clientY
    const deltaY = touchStartY - touchY // positive = finger moving up = scroll content down
    const atTop = answerEl.scrollTop <= 0
    const atBottom = answerEl.scrollTop + answerEl.clientHeight >= answerEl.scrollHeight - 1

    // At boundary & scrolling toward boundary → chain to parent
    if ((deltaY < 0 && atTop) || (deltaY > 0 && atBottom)) {
      // Temporarily disable inner scroll so parent can capture the gesture
      answerEl.style.overflowY = 'hidden'
      scrollEl.scrollTop += deltaY
      // Re-enable after gesture ends
      const reenable = () => {
        answerEl.style.overflowY = ''
        answerEl.removeEventListener('touchend', reenable)
        answerEl.removeEventListener('touchcancel', reenable)
      }
      answerEl.addEventListener('touchend', reenable, { once: true })
      answerEl.addEventListener('touchcancel', reenable, { once: true })
    }
    touchStartY = touchY
  }
  scrollEl.addEventListener('touchstart', touchStartHandler, { passive: true })
  scrollEl.addEventListener('touchmove', touchMoveHandler, { passive: true })
}

function teardownScrollChain() {
  const scrollEl = chatScrollEl.value
  if (!scrollEl) return
  if (wheelHandler) scrollEl.removeEventListener('wheel', wheelHandler, { capture: true })
  if (touchStartHandler) scrollEl.removeEventListener('touchstart', touchStartHandler)
  if (touchMoveHandler) scrollEl.removeEventListener('touchmove', touchMoveHandler)
}
</script>

<template>
  <div
    class="chat-page flex flex-col bg-white w-full min-w-full"
  >
    <!-- Nav bar -->
    <div class="flex-shrink-0 max-w-6xl mx-auto w-full px-4">
      <div class="flex items-center justify-end h-11">
        <div class="flex items-center gap-0.5">
          <button type="button" @click="newConversation" class="w-7 h-7 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <button type="button" @click="toggleHistory" class="w-7 h-7 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Logo + toggle (idle only) -->
    <div v-if="!hasMessages" class="flex-shrink-0 max-w-6xl mx-auto w-full px-4">
      <div class="flex flex-col items-center pt-8 pb-6 md:pt-16 md:pb-8">
        <div class="flex items-center gap-2.5 mb-5 md:mb-6">
          <img src="/subskin_logo.png" alt="SubSkin" class="w-10 h-10 md:w-12 md:h-12" />
          <span class="text-xl md:text-2xl font-semibold text-gray-800 tracking-tight">SubSkin 更懂你</span>
        </div>
        <div class="flex w-full bg-gray-100/80 rounded-full p-0.5">
          <button type="button" @click="setMode('chat')"
            class="flex-1 py-2.5 rounded-full text-sm font-medium transition-all duration-200 flex items-center justify-center gap-1.5"
            :class="mode === 'chat' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'">
            <i class="ri-flashlight-line text-current mr-1.5"></i> 智能问答
          </button>
          <button type="button" @click="setMode('counseling')"
            class="flex-1 py-2.5 rounded-full text-sm font-medium transition-all duration-200 flex items-center justify-center gap-1.5"
            :class="mode === 'counseling' ? 'bg-white text-green-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'">
            <i class="ri-heart-3-line text-current mr-1.5"></i> 知心陪伴
          </button>
        </div>
        <p class="text-xs text-gray-400 mt-3">{{ modeHint }}</p>
      </div>
    </div>

    <!-- Chat area: flex-1 fills remaining space, spacer pushes short content to bottom -->
    <div ref="chatScrollEl" class="chat-scroll flex-1 flex flex-col min-h-0 overflow-y-auto max-w-6xl mx-auto w-full px-4">
      <!-- Compact mode toggle: sits at top of scroll area, slides into view when user scrolls up -->
      <div v-if="hasMessages" class="flex-shrink-0 pt-3 pb-2">
        <div class="flex w-full bg-gray-100/80 rounded-full p-0.5 max-w-[240px] mx-auto">
          <button type="button" @click="setMode('chat')"
            class="flex-1 py-2 rounded-full text-sm font-medium transition-all duration-200 flex items-center justify-center gap-1"
            :class="mode === 'chat' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'">
            <i class="ri-flashlight-line text-current mr-1"></i> 智能问答
          </button>
          <button type="button" @click="setMode('counseling')"
            class="flex-1 py-2 rounded-full text-sm font-medium transition-all duration-200 flex items-center justify-center gap-1"
            :class="mode === 'counseling' ? 'bg-white text-green-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'">
            <i class="ri-heart-3-line text-current mr-1"></i> 知心陪伴
          </button>
        </div>
      </div>
      <!-- Spacer: pushes messages to bottom when content is short; collapses to 0 when content overflows -->
      <div class="flex-grow shrink-0 pointer-events-none"></div>
      <Transition name="tab-fade" mode="out-in">
        <ChatPanel v-if="mode === 'chat'" key="chat" ref="chatPanelRef" />
        <CounselingPanel v-else key="counseling" ref="counselingPanelRef" />
      </Transition>
    </div>

    <!-- Input bar -->
    <Transition name="input-slide">
      <div v-if="showInputBar" class="flex-shrink-0 max-w-6xl mx-auto w-full px-4 py-1.5">
      <div
        class="rounded-2xl px-3.5 py-2 border transition-all duration-200 flex items-center gap-2"
        :class="isInputFocused ? 'border-primary-200 shadow-md shadow-primary-500/5' : 'border-primary-100'"
        style="background: linear-gradient(135deg, #eef6f5 0%, #f5faf9 100%)">

        <div class="flex-1 relative min-w-0">
          <label for="chat-input" class="sr-only">输入你的问题</label>
          <textarea id="chat-input" ref="inputEl" v-model="inputText" rows="1"
            :disabled="isStreaming"
            :placeholder="'请输入你的问题...'"
            class="w-full bg-transparent text-sm text-gray-800 placeholder-transparent outline-none min-w-0 resize-none relative z-10"
            :class="showInlinePreset ? 'text-transparent' : ''"
            aria-label="输入你的问题"
            @input="autoResize"
            @focus="onInputFocus"
            @blur="onInputBlur"
            @keydown.enter.prevent="sendMessage" />

          <div
            v-if="showInlinePreset"
            class="absolute inset-0 flex items-center pointer-events-none overflow-hidden"
            @mouseenter="presetPaused = true"
            @mouseleave="presetPaused = false"
          >
            <Transition name="preset-roll" mode="out-in">
              <span :key="presetIndex" class="text-sm text-primary-400 whitespace-nowrap block w-full truncate">
                {{ currentPreset }}
              </span>
            </Transition>
          </div>
        </div>

        <button type="button" @click="sendMessage"
          :class="['shrink-0 w-7 h-7 rounded-full flex items-center justify-center transition-all duration-200',
            canSend ? 'active:scale-90 text-white' : 'text-gray-300']"
          :disabled="!canSend"
          :style="canSend ? 'background: linear-gradient(135deg, #1C857C, #26A69A)' : ''">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" style="transform:rotate(-45deg)">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>

      <!-- Suggestion panel -->
      <Transition name="panel-slide">
        <div v-if="showPresetPanel" class="mt-2">
          <div class="bg-white rounded-2xl border border-primary-100 shadow-sm p-4 max-h-[240px] overflow-y-auto">
            <template v-if="inputText.trim()">
              <div class="flex flex-wrap gap-1.5">
                <button type="button"
                  v-for="q in matchedQuestions" :key="q"
                  @mousedown.prevent="sendPreset(q)"
                  class="px-3 py-1.5 rounded-full text-xs bg-primary-50 text-primary-600 hover:bg-primary-100 transition-colors min-h-[44px] flex items-center">
                  {{ q }}
                </button>
              </div>
              <p v-if="matchedQuestions.length === 0" class="text-xs text-gray-400">未找到匹配的推荐问题</p>
            </template>
            <template v-else>
              <div v-for="cat in currentPresetCategories" :key="cat.label" class="mb-2.5 last:mb-0">
                <p class="text-[10px] text-gray-400 mb-1.5 ml-1">{{ cat.label }}</p>
                <div class="flex flex-wrap gap-1.5">
                  <button type="button"
                    v-for="q in cat.questions" :key="q"
                    @mousedown.prevent="sendPreset(q)"
                    class="px-3 py-1.5 rounded-full text-xs border border-gray-100 text-gray-600 hover:bg-gray-50 hover:border-gray-200 transition-colors min-h-[44px] flex items-center">
                    {{ q }}
                  </button>
                </div>
              </div>
            </template>
          </div>
        </div>
      </Transition>
    </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Chat page fills viewport minus AppHeader (h-14 + border-b = 57px) and BottomNav */
.chat-page {
  height: calc(100dvh - 57px);
}
@media (max-width: 767px) {
  .chat-page {
    /* Mobile: also subtract BottomNav (54px) + iOS safe area */
    height: calc(100dvh - 57px - 54px - env(safe-area-inset-bottom, 0px));
  }
}

/* Scrollable chat history area */
.chat-scroll {
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: contain;
  /* Firefox */
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.3) transparent;
  /* Always reserve scrollbar space so it's visible */
  scrollbar-gutter: stable;
}
.dark .chat-scroll {
  scrollbar-color: rgba(255, 255, 255, 0.3) transparent;
}
/* WebKit scrollbar */
.chat-scroll::-webkit-scrollbar {
  width: 6px;
}
.chat-scroll::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
}
.chat-scroll::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.28);
  border-radius: 6px;
}
.chat-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.45);
}
.dark .chat-scroll::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.06);
}
.dark .chat-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.28);
}
.dark .chat-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.4);
}

/* Input bar slide-down / slide-up */
.input-slide-enter-active,
.input-slide-leave-active {
  transition: all 0.3s ease;
}
.input-slide-enter-from,
.input-slide-leave-to {
  opacity: 0;
  transform: translateY(100%);
}
</style>
