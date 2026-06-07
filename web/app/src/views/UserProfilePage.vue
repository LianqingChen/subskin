<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '@/api/community'
import { imApi } from '@/api/im'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { toProtectedFileUrl } from '@/utils/file-url'
import FollowButton from '@/components/community/FollowButton.vue'
import FeedWaterfall from '@/components/community/FeedWaterfall.vue'
import type { PublicUserProfile, Post } from '@/types'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()

const userId = computed(() => Number(route.params.userId))
const profile = ref<PublicUserProfile | null>(null)
const posts = ref<Post[]>([])
const totalPosts = ref(0)
const loading = ref(false)
const postsLoading = ref(false)
const avatarError = ref(false)

const avatarUrl = computed(() => {
  if (!profile.value?.avatar_url || avatarError.value) return ''
  return toProtectedFileUrl(profile.value.avatar_url)
})

const isSelf = computed(() => authStore.user?.id === userId.value)

async function handleSendMessage() {
  if (!authStore.isLoggedIn) {
    authStore.showLoginModal = true
    return
  }
  try {
    const res = await imApi.createPrivateChat(userId.value)
    router.push(`/chat/${res.data.conversation_id}`)
  } catch (err) {
    toast.error('发起聊天失败')
    console.error('Failed to create private chat:', err)
  }
}

async function fetchProfile() {
  loading.value = true
  try {
    profile.value = await communityApi.getPublicProfile(userId.value)
  } catch {
    toast.error('用户不存在')
    router.replace('/community')
  } finally {
    loading.value = false
  }
}

async function fetchPosts() {
  postsLoading.value = true
  try {
    const res = await communityApi.getUserPosts(userId.value, 20)
    posts.value = res.items
    totalPosts.value = res.total
  } catch {
    // silently fail
  } finally {
    postsLoading.value = false
  }
}

function handleLikeClick(postId: number) {
  const post = posts.value.find(p => p.id === postId)
  if (!post) return
  communityApi.toggleLike(postId).then(() => {
    if (post.is_liked) {
      post.is_liked = false
      post.like_count--
    } else {
      post.is_liked = true
      post.like_count++
    }
  })
}

function handleBookmarkClick(postId: number) {
  const post = posts.value.find(p => p.id === postId)
  if (!post) return
  communityApi.toggleBookmark(postId).then(() => {
    post.is_bookmarked = !post.is_bookmarked
  })
}

function handleTagClick(tagName: string) {
  router.push(`/community?tag=${encodeURIComponent(tagName)}`)
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' })
}

onMounted(() => {
  fetchProfile()
  fetchPosts()
})
</script>

<template>
  <div class="min-h-[calc(100dvh-3.5rem)] bg-[#F5F7FA] pb-20 md:pb-6">
    <div class="sticky top-0 z-10 bg-[#F5F7FA]/80  backdrop-blur-md border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
        <button class="p-2 -ml-2 rounded-lg hover:bg-gray-100 text-gray-600" @click="router.back()">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 class="text-lg font-semibold text-gray-900">用户主页</h1>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <svg class="animate-spin h-8 w-8 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    </div>

    <div v-else-if="profile" class="max-w-4xl mx-auto px-4 pt-4">
      <div class="card p-5">
        <!-- Top: avatar + user info -->
        <div class="flex items-start gap-4">
          <div class="w-16 h-16 rounded-full overflow-hidden bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-xl font-bold shrink-0">
            <img v-if="avatarUrl" :src="avatarUrl" :alt="profile.username" class="w-full h-full object-cover" @error="avatarError = true" />
            <span v-else>{{ profile.username.charAt(0) }}</span>
          </div>
          <div class="flex-1 min-w-0 pt-1">
            <div class="flex items-center gap-2">
              <span class="text-lg font-bold text-gray-900 dark:text-white truncate">{{ profile.username }}</span>
              <svg v-if="profile.is_doctor" class="w-4 h-4 text-primary-500 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/>
              </svg>
            </div>
            <div v-if="profile.patient_relation" class="text-xs text-gray-500  mt-0.5">{{ profile.patient_relation }}</div>
            <div v-if="profile.created_at" class="text-xs text-gray-400  mt-0.5">{{ formatDate(profile.created_at) }}加入</div>
          </div>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-3 gap-3 mt-4">
          <div class="text-center py-2 rounded-lg bg-gray-50 ">
            <div class="text-lg font-bold text-gray-900 dark:text-white">{{ profile.post_count }}</div>
            <div class="text-xs text-gray-500 ">帖子</div>
          </div>
          <div class="text-center py-2 rounded-lg bg-gray-50 ">
            <div class="text-lg font-bold text-gray-900 dark:text-white">{{ profile.following_count }}</div>
            <div class="text-xs text-gray-500 ">关注</div>
          </div>
          <div class="text-center py-2 rounded-lg bg-gray-50 ">
            <div class="text-lg font-bold text-gray-900 dark:text-white">{{ profile.follower_count }}</div>
            <div class="text-xs text-gray-500 ">粉丝</div>
          </div>
        </div>

        <!-- Action buttons -->
        <div v-if="!isSelf" class="flex gap-3 mt-4">
          <FollowButton :targetUserId="profile.id" :initialFollowed="profile.is_followed" />
          <button
            class="flex-1 text-sm py-1.5 rounded-lg font-medium transition-colors bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 hover:bg-primary-100 dark:hover:bg-primary-900/50 border border-primary-200 dark:border-primary-700"
            @click="handleSendMessage"
          >
            <i class="ri-chat-3-line mr-1.5"></i>私信
          </button>
        </div>
      </div>

      <div class="mt-4">
        <h2 class="text-sm font-semibold text-gray-700 mb-3">TA的帖子</h2>
        <div v-if="postsLoading" class="text-center py-8 text-sm text-gray-400">加载中...</div>
        <div v-else-if="!posts.length" class="card p-8 text-center text-sm text-gray-400">暂无公开帖子</div>
        <FeedWaterfall v-else :posts="posts" @tag-click="handleTagClick" @like-click="handleLikeClick" @bookmark-click="handleBookmarkClick" />
      </div>
    </div>
  </div>
</template>
