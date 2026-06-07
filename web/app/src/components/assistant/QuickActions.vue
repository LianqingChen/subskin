<script setup lang="ts">
const emit = defineEmits<{
  'open-counseling': []
  'open-encyclopedia': []
}>()

function handleActionClick(id: string) {
  if (id === 'counseling') {
    emit('open-counseling')
  } else if (id === 'encyclopedia') {
    emit('open-encyclopedia')
  }
}

const actions = [
  { id: 'voice', label: '语音通话', icon: '🎙️', desc: '打电话给小金' },
  { id: 'counseling', label: '心理陪伴', icon: '💚', desc: '情绪疏导' },
  { id: 'encyclopedia', label: '小白百科', icon: '📖', desc: '知识库' },
]
</script>

<template>
  <div class="flex gap-2 justify-center py-3">
    <button
      v-for="action in actions"
      :key="action.id"
      class="flex flex-col items-center gap-0.5 px-4 py-2 rounded-2xl transition-all duration-200
        bg-white/80  backdrop-blur-sm
        border border-amber-200/50 dark:border-amber-700/30
        hover:bg-amber-50 dark:hover:bg-amber-900/20
        active:scale-95 shadow-sm hover:shadow-md"
      @click="handleActionClick(action.id)"
    >
      <span class="text-xl">{{ action.icon }}</span>
      <span class="text-[10px] font-medium text-amber-800 dark:text-amber-200">{{ action.label }}</span>
    </button>
  </div>
</template>
