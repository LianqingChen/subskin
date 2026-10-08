<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useButlerStore } from '@/stores/butler'
import { useChatStore } from '@/stores/chat'
import { useButlerChat } from '@/composables/useButlerChat'
import ActionCardView from '@/components/common/ActionCardView.vue'

const chatStore = useChatStore()
const butlerStore = useButlerStore()
const router = useRouter()
const { isStreaming, hasMessages, confirmAction } = useButlerChat()

const scrollEl = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    const el = scrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(() => chatStore.messages.length, scrollToBottom)
watch(() => chatStore.messages.map(m => m.content).join(''), scrollToBottom)
onMounted(scrollToBottom)

/** 点击导航芯片：站内跳转并收起面板 */
function goNav(path: string) {
  butlerStore.close()
  router.push(path)
}
</script>

<template>
  <div ref="scrollEl" class="flex-1 min-h-0 overflow-y-auto overscroll-contain px-3 py-3">
    <div v-if="hasMessages" class="space-y-3">
      <div v-for="msg in chatStore.messages" :key="msg.id" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
        <div class="max-w-[88%] px-3 py-2 rounded-2xl text-sm leading-relaxed"
          :class="msg.role === 'user'
            ? 'bg-primary-500 text-white rounded-br-md'
            : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-bl-md'">
          <div v-if="msg.isSkeleton && !msg.content" class="flex items-center gap-2 py-0.5">
            <span class="inline-flex gap-1">
              <span class="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style="animation-delay:0s" />
              <span class="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style="animation-delay:0.15s" />
              <span class="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style="animation-delay:0.3s" />
            </span>
            <span class="text-xs text-gray-400">{{ msg.thinkingMessage || '正在思考...' }}</span>
          </div>
          <template v-else>
            <span class="whitespace-pre-wrap break-words">{{ msg.content }}</span>
            <span v-if="msg.isSkeleton && msg.content" class="inline-block w-1 h-4 bg-primary-400 ml-0.5 animate-pulse align-text-bottom rounded-sm" />
            <!-- 行动卡片：用户逐次确认后才保存/发布 -->
            <template v-if="msg.actionCards && msg.actionCards.length && !msg.isSkeleton">
              <ActionCardView
                v-for="(card, ci) in msg.actionCards"
                :key="ci"
                :card="card"
                :saved="card.saved"
                @confirm="action => confirmAction(msg.id, ci, card, action)"
              />
            </template>
            <div v-if="msg.sources && msg.sources.length > 0 && !msg.isSkeleton" class="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
              <p class="text-[10px] font-medium text-gray-500 dark:text-gray-400 mb-1">参考来源</p>
              <a v-for="(src, si) in msg.sources" :key="si" :href="src.url" target="_blank" rel="noopener"
                class="block text-[10px] text-primary-600 dark:text-primary-400 hover:underline truncate mb-0.5 last:mb-0">{{ si + 1 }}. {{ src.title }}</a>
            </div>
          </template>
        </div>
      </div>

      <!-- 结构化导航芯片（由后端确定性解析下发，非 LLM 生成链接） -->
      <div v-if="butlerStore.navSuggestions.length && !isStreaming" class="flex flex-wrap gap-1.5 pt-1">
        <button v-for="nav in butlerStore.navSuggestions" :key="nav.path + nav.label" type="button"
          class="inline-flex items-center gap-1.5 px-3 py-2 min-h-[40px] rounded-full text-xs border border-primary-200 dark:border-primary-800 text-primary-700 dark:text-primary-300 bg-primary-50 dark:bg-primary-900/30 hover:bg-primary-100 dark:hover:bg-primary-900/50 transition-colors"
          @click="goNav(nav.path)">
          <i :class="nav.icon || 'ri-links'"></i>
          <span>{{ nav.label }}</span>
          <span class="text-gray-400 dark:text-gray-500">{{ nav.desc }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
