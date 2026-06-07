<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ChatMessage } from '@/types'
import { useSpeechSynthesis } from '@/composables/useSpeechSynthesis'
import { toProtectedFileUrl } from '@/utils/file-url'

const props = defineProps<{
  message: ChatMessage
}>()

const emit = defineEmits<{
  'save-card': [messageId: string, cardIndex: number, privacy?: string]
  'dismiss-card': [messageId: string, cardIndex: number]
}>()
// eslint-disable-next-line @typescript-eslint/no-unused-vars
void emit

const isUser = computed(() => props.message.role === 'user')

const { isSpeaking, isSupported, currentMessageId, speak, stop } = useSpeechSynthesis()

// Local privacy state for diary cards (avoid mutating props directly)
const diaryPrivacy = ref<Record<string, string>>({})

function getDiaryPrivacy(messageId: string, index: number, defaultPrivacy: string): string {
  const key = `${messageId}-${index}`
  if (!diaryPrivacy.value[key]) {
    diaryPrivacy.value[key] = defaultPrivacy || 'private'
  }
  return diaryPrivacy.value[key]
}

function setDiaryPrivacy(messageId: string, index: number, privacy: string) {
  diaryPrivacy.value[`${messageId}-${index}`] = privacy
}

const isThisMessageSpeaking = computed(() => isSpeaking.value && currentMessageId.value === props.message.id)

function formatContent(content: string): string {
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" class="text-primary-600 dark:text-primary-400 hover:underline">$1</a>')
}

function stripMarkdownAndHtml(content: string): string {
  let text = content.replace(/\[(.*?)\]\(.*?\)/g, '$1')
  text = text.replace(/[*_~`]/g, '')
  text = text.replace(/<[^>]*>?/gm, '')
  return text
}

function playVoice() {
  if (isThisMessageSpeaking.value) {
    stop()
    return
  }
  
  const cleanText = stripMarkdownAndHtml(props.message.content)
  const textToSpeak = `${cleanText}。以上答复仅供参考，不构成医疗诊断建议。`
  speak(textToSpeak, props.message.id)
}

function protectedFileUrl(url?: string) {
  return toProtectedFileUrl(url)
}

watch(() => props.message.isLoading, (isLoading, oldIsLoading) => {
  if (oldIsLoading === true && isLoading === false && props.message.isVoice && !isUser.value) {
    playVoice()
  }
})
</script>

<template>
  <!-- User message -->
  <div v-if="isUser" class="flex justify-end mb-5 px-4 md:px-0">
    <div class="max-w-[80%] md:max-w-[70%]">
      <!-- User attachments -->
      <div v-if="message.attachments?.length" class="flex flex-wrap gap-1.5 mb-1.5 justify-end">
        <template v-for="att in message.attachments" :key="att.id">
          <img v-if="att.type === 'image'" :src="att.thumbnailUrl || att.url" class="w-16 h-16 rounded-lg object-cover border border-white/20" :alt="att.name" />
          <div v-else class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-primary-500/80 text-white text-xs">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" /></svg>
            {{ att.name }}
          </div>
        </template>
      </div>
      <div class="bg-primary-600 dark:bg-primary-500 text-white rounded-2xl rounded-tr-md px-4 py-3 text-[15px] leading-relaxed">
        {{ message.content }}
      </div>
    </div>
  </div>

  <!-- AI message -->
  <div v-else class="mb-5">
    <!-- Thinking skeleton with stage -->
    <div
      v-if="message.isSkeleton && message.thinkingMessage"
      class="mx-auto max-w-3xl px-4 md:px-6"
    >
      <div class="flex items-center gap-2 py-3 px-4 rounded-xl bg-gray-50  border border-gray-100 dark:border-gray-700/50">
        <div class="flex gap-1">
          <span class="w-1.5 h-1.5 bg-primary-500 rounded-full animate-pulse" style="animation-delay: 0ms" />
          <span class="w-1.5 h-1.5 bg-primary-500 rounded-full animate-pulse" style="animation-delay: 200ms" />
          <span class="w-1.5 h-1.5 bg-primary-500 rounded-full animate-pulse" style="animation-delay: 400ms" />
        </div>
        <span class="text-sm text-gray-500 ">{{ message.thinkingMessage }}</span>
      </div>
      <div v-if="message.thinkingStage === 'generating'" class="mt-3 space-y-2 px-1">
        <div class="h-2 bg-gray-100 rounded-full animate-pulse w-4/5" />
        <div class="h-2 bg-gray-100 rounded-full animate-pulse w-3/5" />
      </div>
    </div>

    <!-- Streaming AI content -->
    <div
      v-else-if="message.content && (message.isLoading || message.isSkeleton)"
      class="mx-auto max-w-3xl px-4 md:px-6"
    >
      <div class="py-1">
        <div v-html="formatContent(message.content)" class="text-[15px] leading-7 text-gray-800 prose-sm" />
        <span class="inline-block w-0.5 h-4 bg-primary-500 animate-pulse ml-0.5 align-text-bottom rounded-sm" />
      </div>
    </div>

    <!-- Simple loading skeleton -->
    <div
      v-else-if="message.isSkeleton && !message.thinkingMessage"
      class="mx-auto max-w-3xl px-4 md:px-6"
    >
      <div class="flex items-center gap-2 py-3 px-4 rounded-xl bg-gray-50 ">
        <div class="flex gap-1">
          <span class="w-2 h-2 bg-gray-300  rounded-full animate-bounce" style="animation-delay: 0ms" />
          <span class="w-2 h-2 bg-gray-300  rounded-full animate-bounce" style="animation-delay: 150ms" />
          <span class="w-2 h-2 bg-gray-300  rounded-full animate-bounce" style="animation-delay: 300ms" />
        </div>
      </div>
    </div>

    <!-- Final AI message -->
    <div
      v-else
      class="mx-auto max-w-3xl px-4 md:px-6 relative group"
    >
      <div 
        class="text-[15px] leading-7 text-gray-800 transition-colors duration-300" 
        :class="{ 'bg-primary-50/50 dark:bg-primary-900/10 rounded-lg p-2 -mx-2': isThisMessageSpeaking }"
        v-html="formatContent(message.content)" 
      />

      <!-- Action Cards -->
      <div v-if="message.actionCards?.length" class="mt-4 space-y-3">
        <template v-for="(card, index) in message.actionCards" :key="index">
          <!-- VASI Card -->
          <div v-if="card.type === 'vasi'" class="bg-white border border-gray-100 dark:border-gray-700/50 rounded-xl p-4 mt-3">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-medium text-gray-700 flex items-center gap-2">
                <span><i class="ri-bar-chart-2-line"></i> VASI 白斑评估</span>
                <span class="text-xs px-2 py-0.5 rounded-full" :class="card.stage === '进展期' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'">{{ card.stage }}</span>
                <span v-if="card.riskLevel" class="text-xs px-2 py-0.5 rounded-full" :class="{
                  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': card.riskLevel === 'green',
                  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400': card.riskLevel === 'amber',
                  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': card.riskLevel === 'red',
                }">{{ card.riskLevel === 'green' ? '稳定' : card.riskLevel === 'amber' ? '关注' : '风险' }}</span>
              </div>
            </div>
            <div class="flex gap-4 mb-4">
              <div v-if="card.imageUrl" class="flex-shrink-0">
                <img :src="protectedFileUrl(card.imageUrl)" alt="VASI Image" class="w-16 h-16 rounded-lg object-cover border border-gray-100 dark:border-gray-700" />
              </div>
              <div class="flex-1 grid grid-cols-2 gap-y-2 text-sm">
                <div>
                  <span class="text-gray-500 ">VASI评分：</span>
                  <span class="text-gray-800 font-medium">{{ card.vasiScore }}</span>
                </div>
                <div>
                  <span class="text-gray-500 ">评估部位：</span>
                  <span class="text-gray-800 font-medium">{{ card.bodySite }}</span>
                </div>
                <div>
                  <span class="text-gray-500 ">受累面积：</span>
                  <span class="text-gray-800 font-medium">{{ card.areaPercentage }}%</span>
                </div>
                <div>
                  <span class="text-gray-500 ">白斑类型：</span>
                  <span class="text-gray-800 font-medium">{{ card.classification }}</span>
                </div>
              </div>
            </div>
            <div class="flex items-center justify-end gap-3">
              <template v-if="card.saved">
                <span class="text-green-600 dark:text-green-400 text-sm font-medium flex items-center gap-1">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
                  已保存
                </span>
              </template>
              <template v-else>
                <button @click="emit('dismiss-card', message.id, index)" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm transition-colors">忽略</button>
                <button @click="emit('save-card', message.id, index)" class="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-1.5 rounded-lg transition-colors">保存到测评</button>
              </template>
            </div>
          </div>

          <!-- Report Card -->
          <div v-else-if="card.type === 'report'" class="bg-white border border-gray-100 dark:border-gray-700/50 rounded-xl p-4 mt-3">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-medium text-gray-700"><i class="ri-file-text-line"></i> 体检解读：{{ card.title }}</div>
              <span v-if="card.riskLevel" class="text-xs px-2 py-0.5 rounded-full" :class="{
                'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': card.riskLevel === 'green',
                'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400': card.riskLevel === 'amber',
                'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': card.riskLevel === 'red',
              }">{{ card.riskLevel === 'green' ? '正常' : card.riskLevel === 'amber' ? '关注' : '风险' }}</span>
            </div>
            <div class="mb-4">
              <p class="text-sm text-gray-600  mb-3">{{ card.summary }}</p>
              <!-- Structured findings with risk indicators -->
              <div v-if="card.keyFindings?.length" class="space-y-2 mb-3">
                <div v-for="(finding, fIndex) in card.keyFindings" :key="fIndex" class="flex items-start gap-2 text-sm">
                  <span class="mt-0.5 w-2 h-2 rounded-full flex-shrink-0" :class="{
                    'bg-green-500': finding.risk === 'green',
                    'bg-amber-500': finding.risk === 'amber',
                    'bg-red-500': finding.risk === 'red',
                  }"></span>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-medium text-gray-800">{{ finding.name }}</span>
                      <span class="text-gray-600 ">{{ finding.value }}</span>
                      <span v-if="finding.status === 'high'" class="text-xs px-1.5 py-0.5 rounded bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400">↑偏高</span>
                      <span v-else-if="finding.status === 'low'" class="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400">↓偏低</span>
                      <span v-else class="text-xs px-1.5 py-0.5 rounded bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400">正常</span>
                    </div>
                    <div v-if="finding.reference" class="text-xs text-gray-400  mt-0.5">参考范围：{{ finding.reference }}</div>
                    <div v-if="finding.explanation" class="text-xs text-gray-500  mt-1">{{ finding.explanation }}</div>
                  </div>
                </div>
              </div>
              <div v-if="card.fileName" class="mt-3 text-xs text-gray-400  flex items-center gap-1">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3.5 h-3.5"><path fill-rule="evenodd" d="M4.466 3.162A2 2 0 016.286 2h7.428a2 2 0 011.82 1.162l2.667 6.162A2 2 0 0118 10.146V16a2 2 0 01-2 2H4a2 2 0 01-2-2v-5.854a2 2 0 01-.201-.822l2.667-6.162zM6.75 8a.75.75 0 000 1.5h6.5a.75.75 0 000-1.5h-6.5z" clip-rule="evenodd" /></svg>
                {{ card.fileName }}
              </div>
            </div>
            <!-- Disclaimer -->
            <div v-if="card.disclaimer" class="mb-3 text-xs text-gray-400  flex items-start gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3 h-3 mt-0.5 flex-shrink-0">
                <path fill-rule="evenodd" d="M8 15A7 7 0 108 1a7 7 0 000 14zm0 1A8 8 0 108 0a8 8 0 000 16z" clip-rule="evenodd" />
                <path d="M7.25 4.75a.75.75 0 011.5 0v4a.75.75 0 01-1.5 0v-4zm.75 7.5a.75.75 0 100-1.5.75.75 0 000 1.5z" />
              </svg>
              <span>{{ card.disclaimer }}</span>
            </div>
            <div class="flex items-center justify-end gap-3">
              <template v-if="card.saved">
                <span class="text-green-600 dark:text-green-400 text-sm font-medium flex items-center gap-1">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
                  已保存
                </span>
              </template>
              <template v-else>
                <button @click="emit('dismiss-card', message.id, index)" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm transition-colors">忽略</button>
                <button @click="emit('save-card', message.id, index)" class="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-1.5 rounded-lg transition-colors">保存到测评</button>
              </template>
            </div>
          </div>

          <!-- Diary Card -->
          <div v-else-if="card.type === 'diary'" class="bg-white border border-gray-100 dark:border-gray-700/50 rounded-xl p-4 mt-3">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-medium text-gray-700"><i class="ri-book-3-line mr-1"></i>白白日记草稿：{{ card.title }}</div>
              <div class="text-xs text-gray-400 ">{{ card.date }}</div>
            </div>
            <div class="mb-4 text-sm text-gray-800 prose-sm max-w-none" v-html="formatContent(card.content)"></div>
            <div class="flex items-center justify-between">
              <div v-if="!card.saved" class="flex items-center gap-4 text-sm">
                <label class="flex items-center gap-1.5 cursor-pointer text-gray-600  hover:text-gray-800 dark:hover:text-gray-200">
                  <input type="radio" :name="'privacy-' + message.id + '-' + index" value="private" :checked="getDiaryPrivacy(message.id, index, card.privacy) === 'private'" @change="setDiaryPrivacy(message.id, index, 'private')" class="text-primary-600 focus:ring-primary-500" />
                  <span><i class="ri-lock-line"></i> 仅自己可见</span>
                </label>
                <label class="flex items-center gap-1.5 cursor-pointer text-gray-600  hover:text-gray-800 dark:hover:text-gray-200">
                  <input type="radio" :name="'privacy-' + message.id + '-' + index" value="public" :checked="getDiaryPrivacy(message.id, index, card.privacy) === 'public'" @change="setDiaryPrivacy(message.id, index, 'public')" class="text-primary-600 focus:ring-primary-500" />
                  <span><i class="ri-global-line"></i> 公开分享</span>
                </label>
              </div>
              <div v-else class="text-sm text-gray-500 ">
                {{ getDiaryPrivacy(message.id, index, card.privacy) === 'private' ? '仅自己可见' : '公开分享' }}
              </div>
              <div class="flex items-center gap-3">
                <template v-if="card.saved">
                  <span class="text-green-600 dark:text-green-400 text-sm font-medium flex items-center gap-1">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
                    已保存
                  </span>
                </template>
                <template v-else>
                  <button @click="emit('dismiss-card', message.id, index)" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm transition-colors">忽略</button>
                  <button @click="emit('save-card', message.id, index, getDiaryPrivacy(message.id, index, card.privacy))" class="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-1.5 rounded-lg transition-colors">保存日记</button>
                </template>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- TTS Button -->
      <button
        v-if="isSupported && !isUser"
        class="absolute -left-2 md:-left-6 top-1 p-1.5 rounded-full text-gray-400 hover:text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
        :class="{ 'opacity-100 text-primary-500 bg-primary-50 dark:bg-primary-900/30': isThisMessageSpeaking }"
        :title="isThisMessageSpeaking ? '停止播报' : '语音播报'"
        @click="playVoice"
      >
        <svg v-if="isThisMessageSpeaking" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4 animate-pulse">
          <rect x="6" y="4" width="4" height="16"></rect>
          <rect x="14" y="4" width="4" height="16"></rect>
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
        </svg>
      </button>

      <!-- Source references -->
      <div v-if="message.sources?.length" class="mt-4 space-y-2">
        <div class="text-xs text-gray-400  flex items-center gap-1.5 font-medium">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path fill-rule="evenodd" d="M4.22 6.22a.75.75 0 011.06 0L8 8.94l2.72-2.72a.75.75 0 111.06 1.06l-3.25 3.25a.75.75 0 01-1.06 0L4.22 7.28a.75.75 0 010-1.06z" clip-rule="evenodd" />
          </svg>
          参考知识
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <a
            v-for="source in message.sources"
            :key="source.title"
            :href="source.url || '#'"
            target="_blank"
            rel="noopener"
            class="flex items-start gap-2 px-3 py-2.5 rounded-xl bg-gray-50  border border-gray-100 dark:border-gray-700/50 hover:border-primary-200 dark:hover:border-primary-800 hover:bg-white dark:hover:bg-gray-300/80 transition-colors group no-underline"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-gray-300  group-hover:text-primary-500 dark:group-hover:text-primary-400">
              <path d="M12.232 4.232a2.5 2.5 0 013.536 3.536l-1.225 1.224a.75.75 0 001.061 1.06l1.224-1.224a4 4 0 00-5.656-5.656l-3 3a4 4 0 00.225 5.764.75.75 0 00.977-1.138 2.5 2.5 0 01-.142-3.667l3-3z" />
              <path d="M11.603 7.963a.75.75 0 00-.977 1.138 2.5 2.5 0 01.142 3.667l-3 3a2.5 2.5 0 01-3.536-3.536l1.225-1.224a.75.75 0 00-1.061-1.06l-1.224 1.224a4 4 0 105.656 5.656l3-3a4 4 0 00-.225-5.764z" />
            </svg>
            <div class="min-w-0">
              <div class="text-sm font-medium text-gray-700 group-hover:text-primary-600 dark:group-hover:text-primary-400 truncate">{{ source.title }}</div>
              <div v-if="source.snippet" class="text-xs text-gray-400  line-clamp-2 mt-0.5">{{ source.snippet }}</div>
            </div>
          </a>
        </div>
      </div>

      <!-- Disclaimer -->
      <div class="mt-3 text-xs text-gray-400  flex items-center gap-1">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3 h-3">
          <path fill-rule="evenodd" d="M8 15A7 7 0 108 1a7 7 0 000 14zm0 1A8 8 0 108 0a8 8 0 000 16z" clip-rule="evenodd" />
          <path d="M7.25 4.75a.75.75 0 011.5 0v4a.75.75 0 01-1.5 0v-4zm.75 7.5a.75.75 0 100-1.5.75.75 0 000 1.5z" />
        </svg>
        AI助手答复仅供参考，不构成医疗诊断建议
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
