<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { toProtectedFileUrl } from '@/utils/file-url'
import { avatarInitial } from '@/utils/avatar'
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

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/community')
  }
}

watch(profile, (p) => {
  if (p?.username) document.title = `${p.username} - SubSkin`
})

onMounted(() => {
  fetchProfile()
  fetchPosts()
})
</script>

<template>
  <div class="pb-8">
    <div class="page-wide">
      <div class="flex items-center gap-2 py-2 md:py-3">
        <button class="-ml-2 flex h-10 w-10 items-center justify-center rounded-full text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800" aria-label="返回" @click="goBack">
          <i class="ri-arrow-left-s-line text-xl" aria-hidden="true"></i>
        </button>
        <h1 class="truncate text-base font-semibold text-gray-900 dark:text-white">{{ profile?.username || '用户主页' }}</h1>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <svg class="animate-spin h-8 w-8 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    </div>

    <div v-else-if="profile" class="page-wide">
      <!-- 手机端上下排列；平板/桌面：头像信息在左，数据与关注在右 -->
      <div class="card p-5 md:flex md:items-center md:gap-8 md:p-6">
        <!-- Top: avatar + user info -->
        <div class="flex items-start gap-4 md:flex-1 md:items-center">
          <div class="w-16 h-16 md:w-20 md:h-20 rounded-full overflow-hidden bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-xl font-bold shrink-0">
            <img v-if="avatarUrl" :src="avatarUrl" :alt="profile.username" class="w-full h-full object-cover" @error="avatarError = true" />
            <span v-else>{{ avatarInitial(profile.username) }}</span>
          </div>
          <div class="flex-1 min-w-0 pt-1">
            <div class="flex items-center gap-2">
              <span class="text-lg font-bold text-gray-900 dark:text-white truncate">{{ profile.username }}</span>
              <i v-if="profile.is_doctor" class="ri-verified-badge-fill text-primary-500 shrink-0" title="医护人员已认证" aria-label="医护人员已认证"></i>
            </div>
            <div v-if="profile.patient_relation" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ profile.patient_relation }}</div>
            <div v-if="profile.created_at" class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{{ formatDate(profile.created_at) }}加入</div>
          </div>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-3 gap-3 mt-4 md:mt-0 md:w-80 md:shrink-0">
          <div class="text-center py-2 rounded-lg bg-gray-50 dark:bg-gray-800/60">
            <div class="text-lg font-bold text-gray-900 dark:text-white">{{ profile.post_count }}</div>
            <div class="text-xs text-gray-500 dark:text-gray-400">帖子</div>
          </div>
          <div class="text-center py-2 rounded-lg bg-gray-50 dark:bg-gray-800/60">
            <div class="text-lg font-bold text-gray-900 dark:text-white">{{ profile.following_count }}</div>
            <div class="text-xs text-gray-500 dark:text-gray-400">关注</div>
          </div>
          <div class="text-center py-2 rounded-lg bg-gray-50 dark:bg-gray-800/60">
            <div class="text-lg font-bold text-gray-900 dark:text-white">{{ profile.follower_count }}</div>
            <div class="text-xs text-gray-500 dark:text-gray-400">粉丝</div>
          </div>
        </div>

        <!-- Action buttons -->
        <div v-if="!isSelf" class="flex gap-3 mt-4 md:mt-0 md:shrink-0">
          <FollowButton :targetUserId="profile.id" :initialFollowed="profile.is_followed" />
        </div>
      </div>

      <div class="mt-5 md:mt-6">
        <h2 class="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">TA的帖子</h2>
        <div v-if="postsLoading" class="text-center py-8 text-sm text-gray-400">加载中...</div>
        <div v-else-if="!posts.length" class="card p-8 text-center text-sm text-gray-400">暂无公开帖子</div>
        <FeedWaterfall v-else :posts="posts" @tag-click="handleTagClick" @like-click="handleLikeClick" @bookmark-click="handleBookmarkClick" />
      </div>
    </div>
  </div>
</template>
