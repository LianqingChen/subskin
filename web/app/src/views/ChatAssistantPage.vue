<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useSpeechSynthesis } from '@/composables/useSpeechSynthesis'
import { useToast } from '@/composables/useToast'
import { chatApi } from '@/api/chat'
import ChatPanel from '@/components/assistant/ChatPanel.vue'
import CompanionTools from '@/components/assistant/CompanionTools.vue'

const chatStore = useChatStore()
const authStore = useAuthStore()
const toast = useToast()
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)

const { speak: _ttsSpeak } = useSpeechSynthesis()

// 附件：临时文件（确认保存前不入库）。接受图片与常见文档。
const ATTACH_ACCEPT_TYPES = '.jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.txt,.md'
interface PendingAttachment { tempId: string; name: string; mimeType: string }
const attachments = ref<PendingAttachment[]>([])
const isUploading = ref(false)
const fileEl = ref<HTMLInputElement | null>(null)



const inputText = ref('')
const inputEl = ref<HTMLTextAreaElement | null>(null)
const isInputFocused = ref(false)
const chatScrollEl = ref<HTMLElement | null>(null)
const pageEl = ref<HTMLElement | null>(null)
const inputWrapEl = ref<HTMLElement | null>(null)
const composerInset = ref(112)
let composerObserver: ResizeObserver | null = null

const chatPresetCategories = [
  { label: '病情咨询', questions: ['白癜风会传染吗？', '白斑扩散了怎么办？', '308激光效果怎么样？', '白癜风会遗传吗？'] },
  { label: '治疗用药', questions: ['他克莫司怎么用？', 'JAK抑制剂是什么？', '光疗多久做一次？'] },
  { label: '心理生活', questions: ['我刚确诊该怎么办？', '孕期白斑会加重吗？', '遮盖液怎么选？', '日常饮食需要注意什么？'] },
]

const allChatPresets = computed(() => chatPresetCategories.flatMap(c => c.questions))

// 桌面端空闲态的示例问题卡片（取自上面的预设问题，点击只填入输入框）
const suggestionCards = [
  { icon: 'ri-question-answer-line', label: chatPresetCategories[2].label, q: chatPresetCategories[2].questions[0] },
  { icon: 'ri-stethoscope-line', label: chatPresetCategories[0].label, q: chatPresetCategories[0].questions[0] },
  { icon: 'ri-capsule-line', label: chatPresetCategories[1].label, q: chatPresetCategories[1].questions[0] },
  { icon: 'ri-leaf-line', label: chatPresetCategories[2].label, q: chatPresetCategories[2].questions[3] },
]
function fillSuggestion(q: string) {
  inputText.value = q
  nextTick(() => { inputEl.value?.focus(); autoResize() })
}

const inputPlaceholder = '请输入你的问题...'

const canSend = computed(() => !isStreaming.value && (!!inputText.value.trim() || showInlinePreset.value))

// Input-inline preset rotation
const presetIndex = ref(0)
let presetTimer: ReturnType<typeof setInterval> | null = null
const presetPaused = ref(false)

const currentPreset = computed(() => allChatPresets.value[presetIndex.value] || '')

const showInlinePreset = computed(() => {
  if (isInputFocused.value) return false
  if (isStreaming.value) return false
  if (inputText.value.trim()) return false
  return allChatPresets.value.length > 0
})

function startPresetRotation() {
  if (presetTimer || allChatPresets.value.length === 0) return
  presetIndex.value = 0
  presetTimer = setInterval(() => {
    if (presetPaused.value) return
    presetIndex.value = (presetIndex.value + 1) % allChatPresets.value.length
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

function onInputFocus() {
  isInputFocused.value = true
  stopPresetRotation()
  // 键盘弹出过程有延迟，稍后重算一次高度，确保输入框不被底部导航/键盘遮挡
  setTimeout(syncViewportHeight, 150)
  setTimeout(syncViewportHeight, 350)
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

async function sendMessage() {
  if (isStreaming.value) return
  const text = inputText.value.trim()
  const message = text || (showInlinePreset.value ? currentPreset.value : '')
  if (!message) return
  inputText.value = ''
  const attachmentIds = attachments.value.map(a => a.tempId)
  attachments.value = []
  chatPanelRef.value?.sendMessage(message, attachmentIds)
  inputEl.value?.blur()
}

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  for (const file of files) {
    try {
      await addAttachment(file)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '上传失败，请稍后再试')
    }
  }
}

async function addAttachment(file: File) {
  if (!authStore.isLoggedIn) {
    throw new Error('访客暂不支持附件分析，请登录后使用')
  }
  if (attachments.value.length >= 3) {
    throw new Error('一次最多上传 3 个附件')
  }
  isUploading.value = true
  try {
    const res = await chatApi.uploadTemp(file)
    attachments.value.push({
      tempId: res.temp_id,
      name: file.name || res.temp_url,
      mimeType: res.mime_type,
    })
  } finally {
    isUploading.value = false
  }
}

function removeAttachment(tempId: string) {
  attachments.value = attachments.value.filter(a => a.tempId !== tempId)
}

function newConversation() {
  chatStore.clearChat()
  stopPresetRotation()
  if (!isInputFocused.value) startPresetRotation()
}

function toggleHistory() { chatPanelRef.value?.toggleHistory() }

// 移动端键盘弹出时 100dvh 不可靠，会导致输入框被底部导航/键盘遮挡；
// 用 visualViewport 动态同步页面高度（键盘弹出/收起都会触发 resize）。
function syncViewportHeight() {
  const el = pageEl.value
  if (!el || typeof window === 'undefined') return
  const vv = window.visualViewport
  const vh = vv && vv.height ? vv.height : window.innerHeight
  const headerH = 57
  let bottomH = 0
  if (window.innerWidth < 768) {
    const nav = document.querySelector('.bottom-nav') as HTMLElement | null
    bottomH = nav ? Math.round(nav.getBoundingClientRect().height) : 54
  }
  el.style.height = `${Math.max(vh - headerH - bottomH, 200)}px`
}

onMounted(() => {
  if (!hasMessages.value) startPresetRotation()
  setupScrollChain()
  syncViewportHeight()
  if (inputWrapEl.value && typeof ResizeObserver !== 'undefined') {
    composerObserver = new ResizeObserver(() => {
      const scroll = chatScrollEl.value
      const nearBottom = !scroll || scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 64
      composerInset.value = Math.ceil(inputWrapEl.value?.getBoundingClientRect().height || 96) + 12
      if (nearBottom) scrollToBottom()
    })
    composerObserver.observe(inputWrapEl.value)
  }
  window.visualViewport?.addEventListener('resize', syncViewportHeight)
  window.visualViewport?.addEventListener('scroll', syncViewportHeight)
  window.addEventListener('resize', syncViewportHeight)
})
onUnmounted(() => {
  stopPresetRotation()
  composerObserver?.disconnect()
  teardownScrollChain()
  window.visualViewport?.removeEventListener('resize', syncViewportHeight)
  window.visualViewport?.removeEventListener('scroll', syncViewportHeight)
  window.removeEventListener('resize', syncViewportHeight)
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
    ref="pageEl"
    class="chat-page flex flex-col bg-white dark:bg-gray-950 w-full min-w-full"
    :class="{ 'chat-page--idle': !hasMessages }"
  >
    <!-- Nav bar -->
    <div class="flex-shrink-0 max-w-3xl mx-auto w-full px-4">
      <div class="flex items-center justify-end h-11">
        <div class="flex items-center gap-0.5">
          <button type="button" @click="newConversation" class="w-7 h-7 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors" aria-label="新建对话">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <button type="button" @click="toggleHistory" class="w-7 h-7 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors" aria-label="历史对话">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Logo (idle only) -->
    <div v-if="!hasMessages" class="chat-welcome flex-shrink-0 max-w-3xl mx-auto w-full px-4">
      <div class="flex flex-col items-center pt-12 pb-6 md:pt-0 md:pb-8">
        <div class="relative mb-8 md:mb-5 w-20 h-20 md:w-16 md:h-16 rounded-full bg-primary-50 dark:bg-primary-900 flex items-center justify-center">
          <div class="absolute inset-0 rounded-full bg-primary-400/20 blur-2xl scale-150 pointer-events-none"></div>
          <i class="ri-robot-3-line text-5xl md:text-4xl text-primary-500 dark:text-primary-400 relative" aria-hidden="true"></i>
        </div>
        <h1 class="text-lg md:text-2xl font-semibold text-gray-800 dark:text-gray-100 tracking-tight mb-1">SubSkin AI 助手</h1>
        <p class="hidden md:block text-sm text-gray-500 dark:text-gray-400 mt-1">白癜风相关的病情、用药、生活问题，都可以问我</p>
        <!-- 全站统一页脚声明（首页置于小助手下方，不在对话框上方） -->
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-2">
          本平台不构成医疗建议，所有内容仅供参考。
        </p>
      </div>
    </div>

    <!-- Chat area: flex-1 fills remaining space, spacer pushes short content to bottom -->
    <div ref="chatScrollEl" :style="{ paddingBottom: composerInset + 'px' }" class="chat-scroll flex-1 flex flex-col min-h-0 overflow-y-auto max-w-3xl mx-auto w-full px-4">
      <!-- Spacer: pushes messages to bottom when content is short; collapses to 0 when content overflows -->
      <div class="flex-grow shrink-0 pointer-events-none"></div>
      <ChatPanel ref="chatPanelRef" />
    </div>

    <!-- Companion tools + Input bar（固定在底部导航上方，键盘弹出也不被遮挡） -->
    <div ref="inputWrapEl" class="chat-input-wrap">
      <div class="max-w-3xl mx-auto w-full px-4 pb-1.5">
      <!-- 知心陪伴快捷工具：正念呼吸 / 用药提醒
           点击输入框或开始输入时自动隐藏，聚焦输入体验；失焦且无内容时恢复 -->
      <div v-if="!isInputFocused && !inputText.trim()" class="flex items-center justify-between pb-1.5">
        <CompanionTools />
      </div>

      <!-- 附件预览 -->
      <div v-if="attachments.length" class="flex flex-wrap gap-1.5 mb-1.5">
        <span v-for="att in attachments" :key="att.tempId"
          class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] bg-primary-50 dark:bg-primary-900 text-primary-700 dark:text-primary-300 max-w-[160px]">
          <i :class="att.mimeType.startsWith('image/') ? 'ri-image-line' : 'ri-file-text-line'"></i>
          <span class="truncate">{{ att.name }}</span>
          <button type="button" aria-label="移除附件" class="text-gray-400 hover:text-red-500" @click="removeAttachment(att.tempId)">
            <i class="ri-close-line"></i>
          </button>
        </span>
      </div>

      <div
        class="chat-input-bar rounded-2xl px-3.5 py-2 border transition-all duration-200 flex items-center gap-2"
        :class="isInputFocused ? 'border-primary-200 dark:border-primary-700 shadow-md shadow-primary-500/5' : 'border-primary-100 dark:border-primary-900'">

        <button type="button" class="shrink-0 w-9 h-9 flex items-center justify-center rounded-full text-gray-400 hover:text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors"
          :aria-label="isUploading ? '上传中' : '添加附件'"
          :disabled="isUploading || isStreaming"
          @click="fileEl?.click()">
          <i :class="isUploading ? 'ri-loader-4-line animate-spin' : 'ri-attachment-2'"></i>
        </button>
        <input ref="fileEl" type="file" class="hidden" :accept="ATTACH_ACCEPT_TYPES" multiple aria-label="选择附件" @change="onFileChange" />

        <div class="flex-1 relative min-w-0">
          <label for="chat-input" class="sr-only">{{ inputPlaceholder }}</label>
          <textarea id="chat-input" ref="inputEl" v-model="inputText" rows="1"
            :disabled="isStreaming"
            :placeholder="inputPlaceholder"
            class="w-full bg-transparent text-sm text-gray-800 dark:text-gray-100 placeholder-transparent outline-none min-w-0 resize-none relative z-10"
            :class="showInlinePreset ? 'text-transparent' : ''"
            :aria-label="inputPlaceholder"
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
          :class="['shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200',
            canSend ? 'active:scale-90 text-white' : 'text-gray-300 dark:text-gray-600']"
          :disabled="!canSend"
          :aria-label="'发送'"
          :style="canSend ? 'background: linear-gradient(135deg, #1C857C, #26A69A)' : ''">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor" style="transform:rotate(-45deg)">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
      </div>
    </div>

    <!-- 桌面端空闲态：示例问题卡片（手机端保留输入框内的轮播提示） -->
    <div v-if="!hasMessages" class="chat-suggestions hidden md:block flex-shrink-0 max-w-3xl mx-auto w-full px-4 pt-3">
      <div class="grid grid-cols-2 gap-2.5">
        <button
          v-for="card in suggestionCards"
          :key="card.q"
          type="button"
          class="group flex items-start gap-3 rounded-xl border border-gray-200/80 bg-white px-4 py-3 text-left transition-colors hover:border-primary-200 hover:bg-primary-50 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-primary-700 dark:hover:bg-gray-800"
          data-track-id="chat_suggestion_card"
          @click="fillSuggestion(card.q)"
        >
          <i :class="card.icon" class="mt-0.5 text-lg text-primary-600 dark:text-primary-400" aria-hidden="true"></i>
          <span class="min-w-0">
            <span class="block text-sm font-medium text-gray-800 dark:text-gray-100">{{ card.q }}</span>
            <span class="mt-0.5 block text-xs text-gray-400 dark:text-gray-500">{{ card.label }}</span>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Chat page fills viewport minus AppHeader (h-14 + border-b = 57px) and BottomNav */
.chat-page {
  height: calc(100vh - 57px);
  height: calc(100dvh - 57px);
}
@media (max-width: 767px) {
  .chat-page {
    /* Mobile: also subtract BottomNav (54px) + iOS safe area */
    height: calc(100vh - 57px - 54px - env(safe-area-inset-bottom, 0px));
    height: calc(100dvh - 57px - 54px - env(safe-area-inset-bottom, 0px));
  }
}

/* Input bar: light gradient in light mode, flat dark surface in dark mode */
.chat-input-bar {
  background: linear-gradient(135deg, #eef6f5 0%, #f5faf9 100%);
}
.dark .chat-input-bar {
  background: #111827;
}

/* 输入区固定在底部导航上方：键盘弹出时浏览器会把 fixed 元素顶到键盘之上，避免被遮挡 */
.chat-input-wrap {
  position: fixed;
  left: var(--app-sidebar-w);
  right: 0;
  bottom: calc(54px + env(safe-area-inset-bottom, 0px));
  z-index: 30;
  padding-top: 10px;
  background: linear-gradient(to top, rgba(255, 255, 255, 0.96) 0%, rgba(255, 255, 255, 0) 100%);
  pointer-events: none;
}
.chat-input-wrap > div {
  pointer-events: auto;
}
.dark .chat-input-wrap {
  background: linear-gradient(to top, rgba(3, 7, 18, 0.96) 0%, rgba(3, 7, 18, 0) 100%);
}
@media (min-width: 768px) {
  .chat-input-wrap {
    bottom: 0;
  }
  /* 桌面/平板空闲态：欢迎区 + 输入框 + 示例问题成组，整体垂直居中偏上；
     有消息后恢复为消息流 + 底部固定输入框 */
  .chat-page--idle {
    padding-bottom: 8vh;
  }
  .chat-page--idle .chat-welcome {
    order: 1;
    margin-top: auto;
  }
  .chat-page--idle .chat-input-wrap {
    order: 2;
    position: static;
    padding-top: 0;
    background: none;
    pointer-events: auto;
  }
  .chat-page--idle .chat-suggestions {
    order: 3;
  }
  .chat-page--idle .chat-scroll {
    order: 4;
    flex: 0 0 auto;
    overflow: visible;
    margin-bottom: auto;
    padding-bottom: 0 !important;
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
  /* 给固定在底部的输入栏留出空间，避免最后一条消息被遮挡 */
  padding-bottom: 112px;
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
</style>
