<script setup lang="ts">
import { ref, watch, computed } from 'vue'
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
// 查看自己的帖子时不显示关注按钮
const isSelf = computed(() => authStore.user?.id != null && authStore.user.id === props.targetUserId)

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
  <!-- 卡片内的关注：克制的文字按钮，不抢内容的视觉焦点 -->
  <button
    v-if="!isSelf"
    class="flex-shrink-0 !min-h-0 text-[11px] leading-none px-1 py-1 rounded-md font-medium transition-colors whitespace-nowrap"
    :class="followed
      ? 'text-gray-400 dark:text-gray-500 hover:text-red-500'
      : 'text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-gray-700'"
    @click.stop.prevent="toggleFollow"
    :disabled="loading"
  >
    {{ loading ? '...' : followed ? '已关注' : '+ 关注' }}
  </button>
</template>
