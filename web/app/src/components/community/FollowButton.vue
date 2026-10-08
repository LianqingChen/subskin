<script setup lang="ts">
import { ref, watch } from 'vue'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  targetUserId: number
  initialFollowed?: boolean
}>()

const emit = defineEmits<{
  (e: 'follow-change', followed: boolean): void
}>()

const authStore = useAuthStore()
const followed = ref(props.initialFollowed ?? false)
const loading = ref(false)

watch(() => props.initialFollowed, (val) => {
  if (val !== undefined) followed.value = val
})

async function toggleFollow() {
  if (!authStore.isLoggedIn) return
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
    emit('follow-change', followed.value)
  } catch (err) {
    console.error('Failed to toggle follow:', err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <button
    v-if="authStore.isLoggedIn"
    class="text-xs px-2.5 py-0.5 min-h-[28px] rounded-full font-medium transition-colors flex-shrink-0"
    :class="followed
      ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 border border-primary-200/70 dark:border-primary-700/40 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-500 hover:border-red-200'
      : 'bg-primary-500 text-white hover:bg-primary-600 dark:hover:bg-primary-400'"
    @click.stop="toggleFollow"
    :disabled="loading"
  >
    {{ loading ? '...' : followed ? '已关注' : '关注' }}
  </button>
</template>
