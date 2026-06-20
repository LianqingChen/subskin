<script setup lang="ts">
import { computed } from 'vue'
import type { Post } from '@/types'
import { toProtectedFileUrl } from '@/utils/file-url'
import FollowPlus from '@/components/community/FollowPlus.vue'

const props = defineProps<{
  post: Post
}>()

const emit = defineEmits<{
  (e: 'like-click', postId: number): void
  (e: 'follow-change', followed: boolean, userId: number): void
}>()

function formatCount(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function readTime(post: Post): string {
  const text = post.content_preview || post.content.replace(/<[^>]+>/g, '')
  const minutes = Math.max(1, Math.ceil(text.length / 400))
  return `${minutes}分钟`
}

const authorAvatarUrl = computed(() => toProtectedFileUrl(props.post.author.avatar))
</script>

<template>
  <router-link
    :to="`/community/${post.id}`"
    class="block no-underline mb-3 rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-all duration-200 group"
  >
    <div class="p-3.5">
      <h3 class="text-[14px] font-semibold text-gray-900 leading-snug line-clamp-2 mb-2">
        {{ post.title }}
      </h3>

      <p class="text-[12px] text-gray-600 leading-relaxed line-clamp-3 mb-2">
        {{ post.content_preview || post.content.replace(/<[^>]+>/g, '').slice(0, 150) }}
      </p>

      <div class="text-[10px] text-primary-500 dark:text-primary-400 mb-2">
        阅读 {{ readTime(post) }}
      </div>

      <!-- Avatar + nickname + follow+ ... heart -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5 min-w-0">
          <router-link :to="`/user/${post.author.id}`" @click.stop class="flex-shrink-0 no-underline">
            <img v-if="authorAvatarUrl" :src="authorAvatarUrl" :alt="post.author.username" class="w-5 h-5 rounded-full object-cover bg-gray-100" @error="($event.target as HTMLImageElement).style.display = 'none'" />
            <div v-else class="w-5 h-5 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-[10px] font-bold">
              {{ post.author.username.charAt(0) }}
            </div>
          </router-link>
          <router-link :to="`/user/${post.author.id}`" @click.stop class="text-[12px] text-gray-600 dark:text-gray-400 truncate max-w-[80px] no-underline">
            {{ post.author.username }}
          </router-link>
          <FollowPlus :targetUserId="post.author.id" :initialFollowed="post.author.is_followed" @follow-change="(f, uid) => emit('follow-change', f, uid)" />
        </div>
        <button class="flex items-center gap-1" :class="post.is_liked ? 'text-red-500' : 'text-gray-400'" @click.stop="emit('like-click', post.id)">
          <svg class="w-4 h-4" viewBox="0 0 20 20" :fill="post.is_liked ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.5">
            <path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/>
          </svg>
          <span class="text-[12px]">{{ formatCount(post.like_count) }}</span>
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