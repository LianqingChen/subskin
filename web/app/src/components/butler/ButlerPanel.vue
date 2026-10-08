<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useButlerStore } from '@/stores/butler'
import { useToast } from '@/composables/useToast'
import { useButlerChat } from '@/composables/useButlerChat'
import { BUTLER_ACCEPT_TYPES } from '@/utils/butler'
import ButlerChat from '@/components/butler/ButlerChat.vue'
import ButlerCreature3D from '@/components/butler/ButlerCreature3D.vue'
// 站点模块唯一事实来源：与后端提示词/导航解析共用同一份清单
import siteModulesJson from '../../../../shared/site-modules.json'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'

interface SiteModule {
  label: string
  path: string
  icon: string
  desc: string
  keywords: string[]
  quick: boolean
}

const QUICK_NAV = (siteModulesJson.modules as SiteModule[]).filter(m => m.quick)

const butlerStore = useButlerStore()
const authStore = useAuthStore()
const router = useRouter()
const toast = useToast()
const { attachments, isUploading, isStreaming, hasMessages, sendMessage, addAttachment, removeAttachment } = useButlerChat()

const inputText = ref('')
const inputEl = ref<HTMLTextAreaElement | null>(null)
const fileEl = ref<HTMLInputElement | null>(null)

// 3D 形象（金斑蝶/梅花鹿）：空状态大图与头部小头像均实时渲染
const creature3D = computed<'butterfly' | 'deer'>(() =>
  butlerStore.preference.mascot === 'deer' ? 'deer' : 'butterfly',
)

const isCounseling = computed(() => butlerStore.mode === 'counseling')
const canSend = computed(() => !isStreaming.value && (!!inputText.value.trim() || attachments.value.length > 0))

function setMode(mode: 'chat' | 'counseling') {
  butlerStore.mode = mode
}

function goFullAssistant() {
  butlerStore.close()
  router.push('/')
}

function goNav(path: string) {
  butlerStore.close()
  router.push(path)
}

function autoResize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 100) + 'px'
}

async function onSend() {
  if (!canSend.value) return
  const text = inputText.value.trim()
  inputText.value = ''
  // 附件必须伴随文字问题一起发送（后端 question 必填）
  if (text) await sendMessage(text)
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
</script>

<template>
  <Teleport to="body">
    <Transition name="butler-panel">
      <section
        v-if="butlerStore.isOpen"
        aria-label="小白管家"
        class="fixed z-[80] flex flex-col bg-white dark:bg-gray-900 safe-top safe-bottom
               inset-0
               md:inset-auto md:bottom-24 md:h-[min(640px,80dvh)] md:w-[400px] md:rounded-2xl
               md:shadow-2xl md:border md:border-gray-200 dark:md:border-gray-700 overflow-hidden"
        :class="butlerStore.preference.position === 'left' ? 'md:left-6' : 'md:right-6'"
      >
        <!-- 头部 -->
        <header class="flex items-center gap-2 px-3 py-2.5 border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
          <div class="w-8 h-8 rounded-full overflow-hidden bg-primary-50 dark:bg-primary-900/40 flex items-center justify-center shrink-0">
            <ButlerCreature3D :creature="creature3D" :size="32" mood="happy" />
          </div>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-gray-900 dark:text-gray-100 leading-tight">小白管家</p>
            <p class="text-[10px] text-gray-400 truncate">{{ isCounseling ? '温暖倾听，安静陪伴' : '问答 · 导航 · 陪伴，随时都在' }}</p>
          </div>
          <div class="flex items-center gap-1">
            <div class="flex bg-gray-100 dark:bg-gray-800 rounded-full p-0.5" role="tablist" aria-label="管家模式">
              <button type="button" role="tab" :aria-selected="!isCounseling" @click="setMode('chat')"
                class="px-2.5 py-1 rounded-full text-[11px] transition-colors"
                :class="!isCounseling ? 'bg-white dark:bg-gray-700 text-primary-600 dark:text-primary-400 shadow-sm font-medium' : 'text-gray-500'">
                问答
              </button>
              <button type="button" role="tab" :aria-selected="isCounseling" @click="setMode('counseling')"
                class="px-2.5 py-1 rounded-full text-[11px] transition-colors"
                :class="isCounseling ? 'bg-white dark:bg-gray-700 text-primary-600 dark:text-primary-400 shadow-sm font-medium' : 'text-gray-500'">
                陪伴
              </button>
            </div>
            <button type="button" class="w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              aria-label="全屏问答" title="全屏问答" @click="goFullAssistant">
              <i class="ri-fullscreen-line"></i>
            </button>
            <button type="button" class="w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              aria-label="收起小白管家" @click="butlerStore.close()">
              <i class="ri-close-line"></i>
            </button>
          </div>
        </header>

        <!-- 空状态：问候 + 常用入口 -->
        <div v-if="!hasMessages" class="flex-1 min-h-0 overflow-y-auto px-4 pt-8 pb-4">
          <div class="flex flex-col items-center text-center mb-6">
            <div class="w-16 h-16 rounded-full overflow-hidden bg-primary-50 dark:bg-primary-900/40 flex items-center justify-center mb-3 shadow-md shadow-primary-500/10">
              <ButlerCreature3D :creature="creature3D" :size="64" mood="greeting" />
            </div>
            <p class="text-sm text-gray-700 dark:text-gray-300">{{ butlerStore.preference.greeting }}</p>
            <p class="text-[11px] text-gray-400 mt-1">可以问我白癜风知识、怎么用网站，也可以聊聊心情</p>
          </div>
          <nav aria-label="常用入口" class="grid grid-cols-2 gap-2 max-w-xs mx-auto">
            <button v-for="nav in QUICK_NAV" :key="nav.path" type="button"
              class="flex items-center gap-2 px-3 py-3 min-h-[52px] rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/60 hover:bg-primary-50 dark:hover:bg-primary-900/30 hover:border-primary-200 dark:hover:border-primary-800 transition-colors text-left"
              @click="goNav(nav.path)">
              <i :class="nav.icon" class="text-primary-500 dark:text-primary-400 text-lg shrink-0"></i>
              <span class="text-xs text-gray-700 dark:text-gray-300">{{ nav.label }}</span>
            </button>
          </nav>
          <p v-if="!authStore.isLoggedIn" class="text-center text-[10px] text-gray-400 mt-5">
            游客每日可免费提问几次，<button type="button" class="text-primary-500 hover:underline" @click="authStore.showLoginModal = true">登录</button>后不限次并支持保存记录
          </p>
        </div>

        <!-- 消息区（与全屏助手共享会话） -->
        <ButlerChat v-else />

        <!-- 输入栏 -->
        <footer class="flex-none border-t border-gray-100 dark:border-gray-800 px-3 py-2 bg-white dark:bg-gray-900">
          <MedicalDisclaimer variant="inline" class="mb-1.5" />
          <div v-if="attachments.length" class="flex flex-wrap gap-1.5 mb-1.5">
            <span v-for="att in attachments" :key="att.tempId"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 max-w-[160px]">
              <i :class="att.mimeType.startsWith('image/') ? 'ri-image-line' : 'ri-file-text-line'"></i>
              <span class="truncate">{{ att.name }}</span>
              <button type="button" aria-label="移除附件" class="text-gray-400 hover:text-red-500" @click="removeAttachment(att.tempId)">
                <i class="ri-close-line"></i>
              </button>
            </span>
          </div>
          <div class="flex items-end gap-1.5">
            <button type="button" class="w-9 h-9 flex-none flex items-center justify-center rounded-full text-gray-400 hover:text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/40 transition-colors"
              :aria-label="isUploading ? '上传中' : '添加附件'"
              :disabled="isUploading || !authStore.isLoggedIn"
              @click="fileEl?.click()">
              <i :class="isUploading ? 'ri-loader-4-line animate-spin' : 'ri-attachment-2'"></i>
            </button>
            <input ref="fileEl" type="file" class="sr-only" :accept="BUTLER_ACCEPT_TYPES" multiple aria-label="选择附件" @change="onFileChange" />
            <label for="butler-input" class="sr-only">提问</label>
            <textarea id="butler-input" ref="inputEl" v-model="inputText" rows="1"
              :disabled="isStreaming"
              :placeholder="isCounseling ? '说说此刻的心情，我在这里陪你...' : '想问什么，随时告诉我...'"
              class="flex-1 min-w-0 resize-none bg-gray-50 dark:bg-gray-800 rounded-xl px-3 py-2 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 outline-none focus:ring-1 focus:ring-primary-300 dark:focus:ring-primary-700 max-h-[100px]"
              @input="autoResize"
              @keydown.enter.exact.prevent="onSend" />
            <button type="button" class="w-9 h-9 flex-none flex items-center justify-center rounded-full transition-all"
              :class="canSend ? 'bg-primary-500 text-white hover:bg-primary-600 active:scale-90' : 'text-gray-300 dark:text-gray-600'"
              :disabled="!canSend"
              aria-label="发送"
              @click="onSend">
              <i class="ri-send-plane-fill"></i>
            </button>
          </div>
        </footer>
      </section>
    </Transition>
  </Teleport>
</template>

<style scoped>
.butler-panel-enter-active,
.butler-panel-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.butler-panel-enter-from,
.butler-panel-leave-to {
  opacity: 0;
  transform: translateY(16px);
}
</style>
