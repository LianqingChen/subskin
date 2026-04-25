<script setup lang="ts">
import type { Post } from '@/types'

defineProps<{
  post: Post
}>()

const emit = defineEmits<{
  (e: 'tag-click', tagName: string): void
  (e: 'like-click', postId: number): void
  (e: 'bookmark-click', postId: number): void
}>()

function formatCount(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

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

function readTime(post: Post): string {
  const text = post.content_preview || post.content.replace(/<[^>]+>/g, '')
  const minutes = Math.max(1, Math.ceil(text.length / 400))
  return `${minutes}分钟`
}
</script>

<template>
  <router-link
    :to="`/community/${post.id}`"
    class="block no-underline break-inside-avoid mb-2.5 rounded-xl overflow-hidden bg-white dark:bg-gray-800 shadow-sm hover:shadow-md transition-all duration-200 group"
  >
    <div class="p-3.5">
      <h3 class="text-[14px] font-semibold text-gray-900 dark:text-gray-100 leading-snug line-clamp-2 mb-2">
        {{ post.title }}
      </h3>

      <p class="text-[12px] text-gray-600 dark:text-gray-400 leading-relaxed line-clamp-3 mb-2">
        {{ post.content_preview || post.content.replace(/<[^>]+>/g, '').slice(0, 150) }}
      </p>

      <div class="text-[10px] text-primary-500 dark:text-primary-400 mb-2">
        阅读 {{ readTime(post) }}
      </div>

      <div class="flex items-center gap-1.5 mb-1.5">
        <div class="w-4 h-4 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-[9px] font-bold flex-shrink-0">
          {{ post.author.username.charAt(0) }}
        </div>
        <span class="text-[11px] text-gray-500 dark:text-gray-400 truncate max-w-[70px]">{{ post.author.username }}</span>
        <span class="text-[10px] text-gray-300 dark:text-gray-600">·</span>
        <span class="text-[10px] text-gray-400 dark:text-gray-500">{{ timeAgo(post.created_at) }}</span>
      </div>

      <div class="flex items-center gap-1 text-[11px] text-gray-400 dark:text-gray-500">
        <!-- Like (heart) -->
        <span class="flex items-center gap-0.5 cursor-pointer p-1 -m-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700" :class="post.is_liked ? 'text-red-500' : 'hover:text-red-500'" @click.stop="emit('like-click', post.id)">
          <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path v-if="post.is_liked" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/>
            <path v-else fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656zm5.656 1.414L10 7.757l1.172-1.171a2.5 2.5 0 113.535 3.535L10 15.828 5.293 10.12a2.5 2.5 0 013.535-3.535z" clip-rule="evenodd"/>
          </svg>
          <span>{{ formatCount(post.like_count) }}</span>
        </span>
        <!-- Bookmark (star) -->
        <span class="flex items-center gap-0.5 cursor-pointer p-1 -m-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700" :class="post.is_bookmarked ? 'text-yellow-500' : 'hover:text-yellow-500'" @click.stop="emit('bookmark-click', post.id)">
          <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path v-if="post.is_bookmarked" d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
            <path v-else d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
          </svg>
        </span>
        <!-- Comment -->
        <span class="flex items-center gap-0.5 p-1 -m-1">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
          <span>{{ formatCount(post.comment_count) }}</span>
        </span>
      </div>

      <div v-if="post.tags && post.tags.length > 0" class="flex flex-wrap gap-1 mt-1.5">
        <button v-for="tag in post.tags.slice(0, 3)" :key="tag.id"
          class="text-[10px] text-primary-600 dark:text-primary-400 bg-primary-50 dark:bg-primary-900/30 px-1.5 py-0.5 rounded hover:bg-primary-100 dark:hover:bg-primary-900/50 transition-colors"
          @click.stop="emit('tag-click', tag.name)">
          #{{ tag.name }}
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
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
