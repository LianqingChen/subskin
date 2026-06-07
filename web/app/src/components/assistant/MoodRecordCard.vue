<script setup lang="ts">
import { ref, computed } from 'vue'
import { communityApi } from '@/api/community'
import { useToast } from '@/composables/useToast'

const emit = defineEmits<{ close: [] }>()
const toast = useToast()

type State = 'editing' | 'completed'
const state = ref<State>('editing')
const sharing = ref(false)

const record = ref({
  situation: '',
  thought: '',
  emotion: '',
  evidence: '',
  alternative: '',
})

const hasContent = computed(() =>
  Object.values(record.value).some((v) => v.trim())
)

function complete() {
  if (!hasContent.value) return
  state.value = 'completed'
}

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

const formattedContent = computed(() => {
  const r = record.value
  const lines: string[] = []
  if (r.situation.trim()) lines.push(`<p><strong>📝 情境</strong>：${r.situation.trim()}</p>`)
  if (r.thought.trim()) lines.push(`<p><strong>💭 想法</strong>：${r.thought.trim()}</p>`)
  if (r.emotion.trim()) lines.push(`<p><strong>💗 感受</strong>：${r.emotion.trim()}</p>`)
  if (r.evidence.trim()) lines.push(`<p><strong>🔍 反思</strong>：${r.evidence.trim()}</p>`)
  if (r.alternative.trim()) lines.push(`<p><strong>🌈 新视角</strong>：${r.alternative.trim()}</p>`)
  return lines.join('')
})

const summary = computed(() => {
  const parts: { icon: string; label: string; value: string }[] = []
  if (record.value.situation.trim()) parts.push({ icon: '📝', label: '情境', value: record.value.situation.trim() })
  if (record.value.thought.trim()) parts.push({ icon: '💭', label: '想法', value: record.value.thought.trim() })
  if (record.value.emotion.trim()) parts.push({ icon: '💗', label: '感受', value: record.value.emotion.trim() })
  if (record.value.evidence.trim()) parts.push({ icon: '🔍', label: '反思', value: record.value.evidence.trim() })
  if (record.value.alternative.trim()) parts.push({ icon: '🌈', label: '新视角', value: record.value.alternative.trim() })
  return parts
})

async function share() {
  if (sharing.value) return
  sharing.value = true
  try {
    await communityApi.createPost({
      title: '💗 心情记录',
      content: formattedContent.value,
      category_id: 3,
      post_type: 'long',
      mood: '😊日常',
    })
    toast.success('已分享到社区')
    emit('close')
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || '分享失败，请重试')
  } finally {
    sharing.value = false
  }
}

function closeWithoutSharing() {
  emit('close')
}
</script>

<template>
  <div class="bg-blue-50/80 rounded-2xl p-4 mt-3 border border-blue-100 space-y-3">
    <div class="flex items-center justify-between">
      <p class="text-xs text-blue-700 font-medium">💗 心情记录</p>
      <button
        class="w-5 h-5 rounded-full flex items-center justify-center text-blue-400 hover:bg-blue-100 hover:text-blue-600 transition-colors"
        aria-label="关闭"
        @click="emit('close')"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>

    <template v-if="state === 'editing'">
      <textarea v-model="record.situation" placeholder="发生了什么事？" rows="1" @input="autoResize"
        class="w-full text-xs bg-white rounded-lg px-3 py-2 border border-blue-200 outline-none focus:border-blue-400 text-gray-700 resize-none overflow-hidden" />
      <textarea v-model="record.thought" placeholder="当时在想什么？" rows="1" @input="autoResize"
        class="w-full text-xs bg-white rounded-lg px-3 py-2 border border-blue-200 outline-none focus:border-blue-400 text-gray-700 resize-none overflow-hidden" />
      <textarea v-model="record.emotion" placeholder="什么感受？" rows="1" @input="autoResize"
        class="w-full text-xs bg-white rounded-lg px-3 py-2 border border-blue-200 outline-none focus:border-blue-400 text-gray-700 resize-none overflow-hidden" />
      <textarea v-model="record.evidence" placeholder="换个角度怎么看？" rows="1" @input="autoResize"
        class="w-full text-xs bg-white rounded-lg px-3 py-2 border border-blue-200 outline-none focus:border-blue-400 text-gray-700 resize-none overflow-hidden" />
      <textarea v-model="record.alternative" placeholder="对自己说句鼓励的话？" rows="1" @input="autoResize"
        class="w-full text-xs bg-white rounded-lg px-3 py-2 border border-blue-200 outline-none focus:border-blue-400 text-gray-700 resize-none overflow-hidden" />
      <button
        class="w-full py-2 bg-blue-500 text-white text-xs rounded-xl hover:bg-blue-600 transition-colors active:scale-[0.98] disabled:opacity-50"
        :disabled="!hasContent"
        @click="complete"
      >完成记录</button>
    </template>

    <template v-else>
      <div class="text-center space-y-2">
        <div v-for="(item, i) in summary" :key="i" class="text-xs leading-relaxed">
          <span class="text-blue-500">{{ item.icon }}</span>
          <span class="text-blue-600 font-medium ml-0.5">{{ item.label }}</span>
          <span class="text-gray-600 ml-1">{{ item.value }}</span>
        </div>
      </div>
      <button
        class="w-full py-2.5 bg-blue-500 text-white text-sm rounded-xl hover:bg-blue-600 transition-colors active:scale-[0.98] disabled:opacity-50"
        :disabled="sharing"
        @click="share"
      >{{ sharing ? '分享中...' : '分享到社区' }}</button>
      <button
        class="w-full py-2 bg-white/60 text-blue-500 text-xs rounded-xl hover:bg-white transition-colors"
        @click="closeWithoutSharing"
      >仅保存，不分享</button>
    </template>
  </div>
</template>
