<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDrafts } from '@/composables/useDrafts'
import type { DraftItem } from '@/composables/useDrafts'
import { useToast } from '@/composables/useToast'
import { toProtectedFileUrl } from '@/utils/file-url'

const router = useRouter()
const toast = useToast()
const { drafts, draftCount, hasDrafts, loadDraftsWithSync, deleteDraft, clearAllDrafts } = useDrafts()

onMounted(loadDraftsWithSync)

function formatTime(ts: number) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}天前`
  return d.toLocaleDateString('zh-CN')
}

function openDraft(draft: DraftItem) {
  if (draft.serverId) {
    router.push({ path: `/community/${draft.serverId}/edit` })
  } else {
    router.push({ path: '/community/new', query: { type: draft.type, draftKey: draft.key } })
  }
}

function handleDelete(key: string) {
  deleteDraft(key)
  toast.success('草稿已删除')
}

const showClearConfirm = ref(false)

function handleClearAll() {
  if (!hasDrafts.value) return
  showClearConfirm.value = true
}

function confirmClearAll() {
  clearAllDrafts()
  showClearConfirm.value = false
  toast.success('已清空所有草稿')
}

function excerpt(text: string, max = 60) {
  if (!text) return '（无内容）'
  return text.length > max ? text.slice(0, max) + '...' : text
}

function formatExpiry(expiresAt: number) {
  const diff = expiresAt - Date.now()
  if (diff <= 0) return '已过期'
  const days = Math.floor(diff / (24 * 60 * 60 * 1000))
  if (days > 0) return `${days}天`
  const hours = Math.floor(diff / (60 * 60 * 1000))
  if (hours > 0) return `${hours}小时`
  return '即将'
}

const protectedUrl = (url: string) => toProtectedFileUrl(url)
</script>

<template>
  <div class="min-h-[calc(100dvh-3.5rem)] bg-[#F5F7FA] pb-20 md:pb-6">
    <div class="sticky top-0 z-10 bg-[#F5F7FA]/80  backdrop-blur-md border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button class="p-2 -ml-2 rounded-lg hover:bg-gray-100 text-gray-600" @click="router.back()">
            <i class="ri-arrow-left-s-line text-xl"></i>
          </button>
          <h1 class="text-lg font-semibold text-gray-900">我的草稿</h1>
          <span v-if="draftCount > 0" class="text-xs text-gray-400">{{ draftCount }}篇</span>
        </div>
        <button v-if="hasDrafts" class="text-sm text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300" @click="handleClearAll">清空</button>
      </div>
    </div>

    <div class="max-w-4xl mx-auto px-4 pt-4">
      <div v-if="!hasDrafts" class="card p-8 text-center">
        <div class="text-4xl mb-3"><i class="ri-draft-line"></i></div>
        <div class="text-sm text-gray-400 ">暂无草稿</div>
        <div class="text-xs text-gray-300  mt-1">编辑帖子时，内容会自动保存为草稿</div>
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="draft in drafts"
          :key="draft.key"
          class="card p-4 flex items-start gap-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
          @click="openDraft(draft)"
        >
          <div class="w-10 h-10 rounded-full flex items-center justify-center text-lg shrink-0"
            :class="{
              'bg-primary-50 dark:bg-primary-900/30': draft.type === 'image',
              'bg-rose-50 dark:bg-rose-900/30': draft.type === 'video',
              'bg-sky-50 dark:bg-sky-900/30': draft.type === 'text',
              'bg-amber-50 dark:bg-amber-900/30': draft.type === 'long',
            }"
          >
            <i :class="draft.icon"></i>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-900">{{ draft.title || '（无标题）' }}</span>
              <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 ">{{ draft.typeName }}</span>
            </div>
            <p class="text-xs text-gray-500  mt-1 line-clamp-2">{{ excerpt(draft.content.replace(/<[^>]+>/g, '')) }}</p>
            <div v-if="draft.images.length" class="flex gap-1 mt-2">
              <img v-for="(img, i) in draft.images.slice(0, 3)" :key="i" :src="protectedUrl(img)" class="w-10 h-10 rounded object-cover" />
              <span v-if="draft.images.length > 3" class="w-10 h-10 rounded bg-gray-100 flex items-center justify-center text-[10px] text-gray-400">+{{ draft.images.length - 3 }}</span>
            </div>
            <div class="flex items-center gap-2 mt-1">
              <p class="text-[10px] text-gray-300 ">{{ formatTime(draft.timestamp) }}</p>
              <span v-if="draft.expiringSoon" class="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 font-medium"><i class="ri-time-line mr-0.5"></i>即将过期</span>
              <span v-else-if="draft.expiresAt" class="text-[10px] text-gray-300 ">{{ formatExpiry(draft.expiresAt) }}后过期</span>
            </div>
          </div>
          <button
            class="p-2 -mr-2 rounded-lg text-gray-300  hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors shrink-0"
            @click.stop="handleDelete(draft.key)"
          >
            <i class="ri-delete-bin-line text-base"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Clear All Confirmation -->
    <Teleport to="body">
      <Transition name="backdrop">
        <div v-if="showClearConfirm" class="fixed inset-0 z-[70] bg-black/50 backdrop-blur-sm" @click="showClearConfirm = false" />
      </Transition>
      <Transition name="dialog">
        <div v-if="showClearConfirm" class="fixed inset-x-0 top-1/3 z-[71] max-w-sm mx-auto px-6">
          <div class="bg-[#F5F7FA] rounded-2xl shadow-2xl p-6">
            <h3 class="text-base font-semibold text-gray-900 mb-2">清空所有草稿？</h3>
            <p class="text-sm text-gray-500  mb-5">此操作将删除全部 {{ draftCount }} 篇草稿，且无法恢复。</p>
            <div class="flex gap-3">
              <button class="flex-1 py-2.5 text-sm font-medium rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" @click="showClearConfirm = false">取消</button>
              <button class="flex-1 py-2.5 text-sm font-medium rounded-xl bg-red-500 text-white hover:bg-red-600 transition-colors" @click="confirmClearAll">确认清空</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.backdrop-enter-active { transition: opacity 0.2s ease-out; }
.backdrop-leave-active { transition: opacity 0.15s ease-in; }
.backdrop-enter-from, .backdrop-leave-to { opacity: 0; }

.dialog-enter-active { transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1); }
.dialog-leave-active { transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
.dialog-enter-from, .dialog-leave-to { opacity: 0; transform: scale(0.95) translateY(-10px); }
</style>
