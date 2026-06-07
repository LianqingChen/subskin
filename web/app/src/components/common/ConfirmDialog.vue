<script setup lang="ts">
/**
 * Unified confirm dialog component.
 * Replaces 3 different confirmation implementations:
 * - PostDetailPage custom modal
 * - TrackerPage swipe-to-delete
 * - ProfilePage browser confirm()
 */
defineProps<{
  visible: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  confirmClass?: string
  loading?: boolean
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 bg-black/50 z-[110] flex items-center justify-center"
      @click.self="emit('cancel')"
    >
      <div class="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-xl">
        <h3 v-if="title" class="text-lg font-semibold text-gray-900 mb-2">
          {{ title }}
        </h3>
        <p v-if="message" class="text-sm text-gray-500  mb-4">
          {{ message }}
        </p>

        <div class="flex gap-3 justify-end">
          <button
            class="btn-ghost px-4 py-2"
            :disabled="loading"
            @click="emit('cancel')"
          >
            {{ cancelText || '取消' }}
          </button>
          <button
            :class="confirmClass || 'bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition-colors'"
            :disabled="loading"
            @click="emit('confirm')"
          >
            {{ loading ? '处理中...' : (confirmText || '确认') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
