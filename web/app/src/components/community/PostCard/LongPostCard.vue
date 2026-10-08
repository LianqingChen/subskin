<script setup lang="ts">
import { computed } from 'vue'
import type { Post } from '@/types'
import { toProtectedFileUrl } from '@/utils/file-url'
import { avatarInitial } from '@/utils/avatar'
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
    class="feed-card block no-underline rounded-xl overflow-hidden bg-white dark:bg-gray-800 group"
  >
    <div class="p-3">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 leading-snug line-clamp-2 mb-1.5">
        {{ post.title }}
      </h3>

      <!-- 治疗分享结构化摘要 -->
      <div v-if="post.treatment_share" class="flex flex-wrap items-center gap-1.5 mb-2">
        <span class="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300">
          <i class="ri-capsule-line"></i> 治疗经验
        </span>
        <span v-if="post.treatment_share.duration" class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-300">
          <i class="ri-time-line"></i> {{ post.treatment_share.duration }}
        </span>
        <span v-if="post.treatment_share.effect_rating" class="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-900/40 text-amber-500">
          <i v-for="n in post.treatment_share.effect_rating" :key="n" class="ri-star-fill"></i>
        </span>
        <span v-if="post.treatment_share.cost_range" class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-300">
          <i class="ri-money-cny-circle-line"></i> {{ post.treatment_share.cost_range }}
        </span>
      </div>

      <p class="text-[12px] md:text-[13px] text-gray-600 dark:text-gray-300 leading-relaxed line-clamp-3 mb-1.5">
        {{ post.content_preview || post.content.replace(/<[^>]+>/g, '').slice(0, 150) }}
      </p>

      <div class="text-[11px] text-gray-400 dark:text-gray-500 mb-1">
        阅读 {{ readTime(post) }}
      </div>

      <!-- Avatar + nickname + follow+ ... heart -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5 min-w-0">
          <router-link :to="`/user/${post.author.id}`" @click.stop class="flex-shrink-0 no-underline">
            <img v-if="authorAvatarUrl" :src="authorAvatarUrl" :alt="post.author.username" class="w-5 h-5 rounded-full object-cover bg-gray-100" @error="($event.target as HTMLImageElement).style.display = 'none'" />
            <div v-else class="w-5 h-5 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-[10px] font-bold">
              {{ avatarInitial(post.author.username) }}
            </div>
          </router-link>
          <router-link :to="`/user/${post.author.id}`" @click.stop class="min-w-0 text-[12px] text-gray-600 dark:text-gray-400 truncate max-w-[96px] no-underline">
            {{ post.author.username }}
          </router-link>
          <FollowPlus class="hidden sm:inline-flex" :targetUserId="post.author.id" :initialFollowed="post.author.is_followed" @follow-change="(f, uid) => emit('follow-change', f, uid)" />
        </div>
        <button class="flex flex-shrink-0 items-center gap-1 p-1.5 -mr-1" :class="post.is_liked ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'" :aria-pressed="post.is_liked" :aria-label="post.is_liked ? `已点赞，共${post.like_count}人` : '点赞'" @click.stop="emit('like-click', post.id)">
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
/* 卡片无阴影；仅桌面鼠标悬停时轻微浮起 */
.feed-card {
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}
@media (hover: hover) and (min-width: 768px) {
  .feed-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px -8px rgba(15, 23, 42, 0.18);
  }
}
</style>