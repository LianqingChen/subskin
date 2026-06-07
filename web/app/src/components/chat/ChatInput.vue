<script setup lang="ts">
import { ref, nextTick, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSpeechRecognition } from '@/composables/useSpeechRecognition'
import { useToast } from '@/composables/useToast'

const props = withDefaults(defineProps<{
  maxLength?: number
  disabled?: boolean
  showActions?: boolean
  guestRemaining?: number | null
}>(), {
  maxLength: 200,
  disabled: false,
  showActions: false,
  guestRemaining: null,
})

const emit = defineEmits<{
  send: [text: string, isVoice: boolean, files?: Array<{ file: File; preview?: string; id: string }>]
  newChat: []
  toggleHistory: []
}>()

const authStore = useAuthStore()
const toast = useToast()
const inputText = ref('')
const textarea = ref<HTMLTextAreaElement | null>(null)
const isVoiceInput = ref(false)

// File attachment state
const cameraInput = ref<HTMLInputElement | null>(null)
const galleryInput = ref<HTMLInputElement | null>(null)
const docInput = ref<HTMLInputElement | null>(null)
const pendingFiles = ref<Array<{ file: File; preview?: string; id: string }>>([])

const { isListening, transcript, error, stop } = useSpeechRecognition()

watch(transcript, (newVal) => {
  if (newVal) {
    inputText.value = newVal
    isVoiceInput.value = true
    adjustHeight()
  }
})

watch(error, (newVal) => {
  if (newVal) {
    toast.error(newVal)
  }
})

const charCount = computed(() => inputText.value.length)
const isOverLimit = computed(() => charCount.value > props.maxLength)
const canSend = computed(() =>
  (inputText.value.trim().length > 0 || pendingFiles.value.length > 0) && !isOverLimit.value && !props.disabled
)

function handleSend() {
  const text = inputText.value.trim()
  if ((!text && pendingFiles.value.length === 0) || isOverLimit.value || props.disabled) return

  if (isListening.value) {
    stop()
  }

  const filesToSend = pendingFiles.value.length > 0 ? [...pendingFiles.value] : undefined
  pendingFiles.value = []

  emit('send', text || '(上传了附件)', isVoiceInput.value, filesToSend)
  inputText.value = ''
  isVoiceInput.value = false
  nextTick(() => adjustHeight())
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  } else {
    isVoiceInput.value = false
  }
}

function adjustHeight() {
  if (!textarea.value) return
  textarea.value.style.height = 'auto'
  textarea.value.style.height = Math.min(textarea.value.scrollHeight, 160) + 'px'
}

// File handling
function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (!target.files) return
  for (const file of Array.from(target.files)) {
    if (pendingFiles.value.length >= 3) {
      toast.error('最多上传3个文件')
      break
    }
    const id = `att_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    const entry: { file: File; preview?: string; id: string } = { file, id }
    if (file.type.startsWith('image/')) {
      entry.preview = URL.createObjectURL(file)
    }
    pendingFiles.value.push(entry)
  }
  target.value = ''
}

function removePendingFile(id: string) {
  const idx = pendingFiles.value.findIndex(f => f.id === id)
  if (idx >= 0) {
    const entry = pendingFiles.value[idx]
    if (entry.preview) URL.revokeObjectURL(entry.preview)
    pendingFiles.value.splice(idx, 1)
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
}
// eslint-disable-next-line @typescript-eslint/no-unused-vars
void formatFileSize
</script>

<template>
  <div class="sticky bottom-0 z-20 bg-gradient-to-t from-white via-white/95 to-transparent dark:from-gray-950 dark:via-gray-950/95 dark:to-transparent pt-2 pb-2 md:pb-3 safe-bottom">
    <div class="max-w-3xl mx-auto px-3">

      <!-- Action buttons row (only shown when showActions is true) -->
      <div v-if="showActions" class="flex items-center justify-end gap-1 mb-1.5 px-1">
          <button
            class="p-1.5 rounded-lg text-primary-500 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors"
            title="新建问答"
            @click="emit('newChat')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
            </svg>
          </button>
          <button
            class="p-1.5 rounded-lg text-primary-500 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors"
            title="历史问答"
            @click="emit('toggleHistory')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
              <path d="M3 3v5h5"/>
              <path d="M12 12V7"/>
              <path d="M12 12l4 2"/>
            </svg>
          </button>
      </div>

      <!-- Pending file previews -->
      <div v-if="pendingFiles.length > 0" class="flex gap-2 mb-1.5 px-1 overflow-x-auto scrollbar-hide">
        <div
          v-for="pf in pendingFiles"
          :key="pf.id"
          class="relative flex-shrink-0 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm bg-white group"
        >
          <!-- Image preview -->
          <div v-if="pf.preview" class="relative w-16 h-16">
            <img :src="pf.preview" class="w-full h-full object-cover" :alt="pf.file.name" />
            <div class="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors"></div>
            <button
              class="absolute top-1 right-1 w-5 h-5 bg-black/50 backdrop-blur-sm text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500"
              @click="removePendingFile(pf.id)"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
            </button>
          </div>
          <!-- Document preview -->
          <div v-else class="flex items-center gap-2 px-2.5 py-2 min-w-[100px] max-w-[160px]">
            <span class="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center flex-shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-amber-500 dark:text-amber-400" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" /></svg>
            </span>
            <span class="text-[11px] text-gray-600  truncate leading-tight">{{ pf.file.name }}</span>
            <button
              class="flex-shrink-0 w-5 h-5 text-gray-400  hover:text-red-500 dark:hover:text-red-400 rounded-full hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center justify-center transition-colors"
              @click="removePendingFile(pf.id)"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Hidden file inputs -->
      <input ref="cameraInput" type="file" accept="image/*" capture="environment" class="hidden" @change="handleFileSelect" />
      <input ref="galleryInput" type="file" accept="image/*,.pdf,.doc,.docx,.txt,.md" multiple class="hidden" @change="handleFileSelect" />
      <input ref="docInput" type="file" accept=".pdf,.doc,.docx,.txt,.md,image/*" multiple class="hidden" @change="handleFileSelect" />

      <!-- Input box -->
      <div
        class="rounded-2xl border transition-all duration-200 shadow-sm"
        :class="isOverLimit
          ? 'border-red-300 dark:border-red-500 bg-white'
          : 'border-gray-200 dark:border-gray-700 bg-white focus-within:border-primary-400 dark:focus-within:border-primary-500 focus-within:shadow-md focus-within:shadow-primary-500/5'"
      >
        <div class="flex items-center gap-2 px-4 py-2.5">
          <textarea
            ref="textarea"
            v-model="inputText"
            :placeholder="pendingFiles.length > 0 ? '添加描述（可选）...' : '请输入问题，按 Enter 发送'"
            class="flex-1 bg-transparent border-none outline-none resize-none text-[15px] leading-relaxed min-h-[24px] max-h-[160px] py-0.5 text-gray-900 placeholder-gray-400"
            :class="{ 'text-gray-400 ': disabled }"
            rows="1"
            :disabled="disabled"
            :maxlength="maxLength + 50"
            @input="adjustHeight"
            @keydown="handleKeydown"
          />
           <button
            class="flex-shrink-0 w-8 h-8 flex items-center justify-center transition-all duration-200"
            :class="canSend
              ? 'text-primary-500 hover:text-primary-600 active:scale-90'
              : 'text-gray-300  cursor-default'"
            :disabled="!canSend"
            title="提交问题"
            @click="handleSend"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4">
              <path d="M22 2L11 13" />
              <path d="M22 2L15 22L11 13L2 9L22 2Z" />
            </svg>
          </button>
        </div>
      </div>
      <div class="flex items-center justify-between mt-1.5 px-1 text-xs text-gray-400 ">
        <span v-if="charCount > 0" :class="isOverLimit ? 'text-red-500 dark:text-red-400 font-medium' : ''">
          {{ charCount }}/{{ maxLength }}
        </span>
        <span v-if="!authStore.isLoggedIn && !disabled" class="text-amber-600 dark:text-amber-500">
          访客模式 · 剩余{{ guestRemaining }}次
        </span>
      </div>
    </div>
  </div>
</template>
