<script setup lang="ts">
import { ref, watch } from 'vue'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  targetUserId: number
  initialFollowed?: boolean
}>()

const emit = defineEmits<{
  (e: 'follow-change', followed: boolean, userId: number): void
}>()

const authStore = useAuthStore()
const followed = ref(props.initialFollowed ?? false)
const loading = ref(false)

watch(() => props.initialFollowed, (val) => {
  if (val !== undefined) followed.value = val
})

async function toggleFollow() {
  if (!authStore.isLoggedIn) {
    authStore.showLoginModal = true
    return
  }
  if (loading.value) return
  loading.value = true
  try {
    if (followed.value) {
      await communityApi.unfollowUser(props.targetUserId)
      followed.value = false
    } else {
      await communityApi.followUser(props.targetUserId)
      followed.value = true
    }
    emit('follow-change', followed.value, props.targetUserId)
  } catch (err) {
    console.error('Failed to toggle follow:', err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <button
    class="flex-shrink-0 text-[11px] px-1.5 py-0.5 rounded-sm font-medium transition-colors whitespace-nowrap"
    :class="followed
      ? 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-500'
      : 'bg-primary-50 dark:bg-primary-900/40 text-primary-600 dark:text-primary-400 hover:bg-primary-100 dark:hover:bg-primary-900/60'"
    @click.stop="toggleFollow"
    :disabled="loading"
  >
    {{ loading ? '...' : followed ? '已关注' : '关注' }}
  </button>
</template>