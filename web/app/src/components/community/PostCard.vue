<script setup lang="ts">
import type { Post } from '@/types'
import { toProtectedFileUrl } from '@/utils/file-url'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { ref } from 'vue'

const props = defineProps<{
  post: Post
}>()

const authStore = useAuthStore()

const localLiked = ref(props.post.is_liked)
const localLikeCount = ref(props.post.like_count)

function timeAgo(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 60) return minutes <= 0 ? '刚刚' : `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return `${Math.floor(days / 30)}个月前`
}

function formatTimeCity(post: Post): string {
  const time = timeAgo(post.created_at)
  if (post.city) return `${post.city} · ${time}`
  return time
}

// Mood tag: prefer API mood field, fallback to category-based
const MOOD_MAP: Record<string, { icon: string; label: string; color: string }> = {
  '💪坚持中': { icon: 'ri-boxing-line', label: '坚持中', color: 'bg-orange-500/80 text-white' },
  '😔低落': { icon: 'ri-emotion-sad-line', label: '低落', color: 'bg-purple-500/80 text-white' },
  '🎉好转': { icon: 'ri-emotion-happy-line', label: '好转', color: 'bg-green-500/80 text-white' },
  '🤔疑问': { icon: 'ri-question-line', label: '疑问', color: 'bg-cyan-500/80 text-white' },
}

function getMoodTag(post: Post): { icon: string; label: string; color: string } | null {
  if (post.mood && MOOD_MAP[post.mood]) return MOOD_MAP[post.mood]
  if (post.diary_date) return { icon: 'ri-book-3-line', label: '日记', color: 'bg-amber-500/80 text-white' }
  const name = post.category?.name || ''
  if (name === '心理支持') return { icon: 'ri-heart-2-line', label: '倾诉', color: 'bg-purple-500/80 text-white' }
  if (name === '治疗分享') return { icon: 'ri-capsule-line', label: '经验', color: 'bg-blue-500/80 text-white' }
  if (name === '护肤经验') return { icon: 'ri-flask-line', label: '护肤', color: 'bg-pink-500/80 text-white' }
  if (name === '日常饮食') return { icon: 'ri-restaurant-line', label: '饮食', color: 'bg-green-500/80 text-white' }
  if (name === '诊断咨询') return { icon: 'ri-microscope-line', label: '咨询', color: 'bg-cyan-500/80 text-white' }
  return null
}

function formatCount(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function coverUrl(post: Post): string {
  if (post.images && post.images.length > 0) {
    return toProtectedFileUrl(post.images[0].image_url)
  }
  return ''
}

async function toggleLike(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  if (!authStore.isLoggedIn) {
    authStore.showLoginModal = true
    return
  }
  try {
    await communityApi.toggleLike(props.post.id)
    localLiked.value = !localLiked.value
    localLikeCount.value += localLiked.value ? 1 : -1
  } catch {
    // silently fail
  }
}
</script>

<template>
  <router-link
    :to="`/community/${post.id}`"
    class="block no-underline break-inside-avoid mb-2 rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow duration-200 group"
  >
    <!-- Cover Image -->
    <div class="relative aspect-[3/4] bg-gray-100 overflow-hidden">
      <!-- Has image -->
      <img
        v-if="coverUrl(post)"
        :src="coverUrl(post)"
        :alt="post.title"
        class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        loading="lazy"
      />
      <!-- No image: category-based gradient placeholder -->
      <div v-else class="w-full h-full flex flex-col items-center justify-center gap-2"
        :class="{
          'bg-gradient-to-br from-blue-100 to-blue-200 dark:from-blue-900/40 dark:to-blue-800/40': post.category?.name === '治疗分享',
          'bg-gradient-to-br from-purple-100 to-purple-200 dark:from-purple-900/40 dark:to-purple-800/40': post.category?.name === '心理支持',
          'bg-gradient-to-br from-pink-100 to-pink-200 dark:from-pink-900/40 dark:to-pink-800/40': post.category?.name === '护肤经验',
          'bg-gradient-to-br from-green-100 to-green-200 dark:from-green-900/40 dark:to-green-800/40': post.category?.name === '日常饮食',
          'bg-gradient-to-br from-cyan-100 to-cyan-200 dark:from-cyan-900/40 dark:to-cyan-800/40': post.category?.name === '诊断咨询',
          'bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-700/40 dark:to-gray-600/40': !['治疗分享','心理支持','护肤经验','日常饮食','诊断咨询'].includes(post.category?.name || ''),
        }"
      >
        <i :class="post.category?.icon || 'ri-file-edit-line'" class="text-3xl"></i>
        <span class="text-xs text-gray-500  font-medium px-2 text-center">{{ post.category?.name }}</span>
      </div>

      <!-- Mood tag overlay (bottom-left) -->
      <span
        v-if="getMoodTag(post)"
        class="absolute bottom-2 left-2 text-[10px] font-medium px-2 py-0.5 rounded-full backdrop-blur-sm"
        :class="getMoodTag(post)!.color"
      >
        <i :class="getMoodTag(post)!.icon" class="mr-0.5"></i> {{ getMoodTag(post)!.label }}
      </span>

      <!-- Private indicator -->
      <span
        v-if="post.is_private"
        class="absolute top-2 right-2 text-[10px] font-medium px-2 py-0.5 rounded-full bg-black/50 text-white backdrop-blur-sm"
      >
        <i class="ri-lock-line"></i> 私密
      </span>

      <!-- Multi-image indicator -->
      <span
        v-if="post.images && post.images.length > 1"
        class="absolute top-2 right-2 text-[10px] font-medium px-1.5 py-0.5 rounded bg-black/50 text-white backdrop-blur-sm"
      >
        <i class="ri-camera-line"></i> {{ post.images.length }}
      </span>

      <!-- Medical disclaimer micro badge -->
      <span class="absolute bottom-2 right-2 text-[9px] text-white/60 font-medium">
        仅供参考
      </span>
    </div>

    <!-- Text Content -->
    <div class="px-2.5 pt-2 pb-2">
      <!-- Title -->
      <h3 class="text-[13px] font-medium text-gray-900 leading-snug line-clamp-2 mb-1.5">
        {{ post.title }}
      </h3>

      <!-- Author row: avatar + nickname + verified icon -->
      <router-link :to="`/user/${post.author.id}`" @click.stop class="flex items-center gap-1.5 min-w-0 no-underline">
        <div class="w-4 h-4 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-[9px] font-bold flex-shrink-0">
          {{ post.author.username.charAt(0) }}
        </div>
        <span class="text-[11px] text-gray-500  truncate max-w-[70px]">{{ post.author.username }}</span>
        <svg v-if="post.author.is_doctor" class="w-3 h-3 text-primary-500 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor" title="认证医生">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/>
        </svg>
        <i v-if="post.author.is_verified" class="ri-shield-check-line text-primary-500 text-xs flex-shrink-0" title="实名认证"></i>
      </router-link>

      <!-- Bottom row: time+city · like heart -->
      <div class="flex items-center justify-between mt-1">
        <span class="text-[10px] text-gray-400 ">{{ formatTimeCity(post) }}</span>
        <button class="flex items-center gap-0.5" :class="localLiked ? 'text-red-500' : 'text-red-400 dark:text-red-400'" @click.prevent.stop="toggleLike">
          <svg class="w-3.5 h-3.5 transition-colors" viewBox="0 0 20 20" :fill="localLiked ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.5">
            <path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/>
          </svg>
          <span class="text-[11px] text-red-500">{{ formatCount(localLikeCount) }}</span>
        </button>
      </div>
    </div>
  </router-link>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
