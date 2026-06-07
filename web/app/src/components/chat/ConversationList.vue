<script setup lang="ts">
defineProps<{
  conversations: { id: string; title: string; date: string }[]
  activeId?: string
}>()

const emit = defineEmits<{
  select: [id: string]
  newChat: []
}>()

function formatDate(date: string): string {
  const d = new Date(date)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const oneDay = 86400000
  if (diff < oneDay) return '今天'
  if (diff < 2 * oneDay) return '昨天'
  if (diff < 7 * oneDay) return `${Math.floor(diff / oneDay)}天前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <aside class="hidden lg:flex flex-col w-64 border-r border-gray-200 bg-white">
    <div class="p-4 border-b border-gray-100">
      <button
        class="w-full btn-primary text-sm py-2 flex items-center justify-center gap-2"
        @click="emit('newChat')"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
          <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
        </svg>
        新对话
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-2 space-y-1">
      <button
        v-for="conv in conversations"
        :key="conv.id"
        class="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors"
        :class="activeId === conv.id
          ? 'bg-primary-50 text-primary-700 font-medium'
          : 'text-gray-600 hover:bg-gray-50'"
        @click="emit('select', conv.id)"
      >
        <div class="truncate">{{ conv.title }}</div>
        <div class="text-xs text-gray-400 mt-0.5">{{ formatDate(conv.date) }}</div>
      </button>

      <div v-if="!conversations.length" class="text-center py-8 text-gray-400 text-xs">
        暂无对话历史
      </div>
    </div>
  </aside>
</template>