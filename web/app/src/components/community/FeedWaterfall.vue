<script setup lang="ts">
import type { Post } from '@/types'
import ImagePostCard from '@/components/community/PostCard/ImagePostCard.vue'
import TextPostCard from '@/components/community/PostCard/TextPostCard.vue'
import LongPostCard from '@/components/community/PostCard/LongPostCard.vue'

defineProps<{
  posts: Post[]
}>()

const emit = defineEmits<{
  (e: 'like-click', postId: number): void
  (e: 'follow-change', followed: boolean, userId: number): void
}>()

function getPostType(post: Post): string {
  if (post.post_type) return post.post_type
  if (post.video_url) return 'video'
  if (post.images && post.images.length > 0) return 'image'
  const textLen = (post.content_preview || post.content.replace(/<[^>]+>/g, '')).length
  if (textLen > 200) return 'long'
  return 'text'
}

function onLikeClick(postId: number) {
  emit('like-click', postId)
}

function onFollowChange(followed: boolean, userId: number) {
  emit('follow-change', followed, userId)
}
</script>

<template>
  <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
    <template v-for="post in posts" :key="post.id">
      <ImagePostCard v-if="getPostType(post) === 'image' || getPostType(post) === 'video'" :post="post" @like-click="onLikeClick" @follow-change="onFollowChange" />
      <TextPostCard v-else-if="getPostType(post) === 'text'" :post="post" @like-click="onLikeClick" @follow-change="onFollowChange" />
      <LongPostCard v-else :post="post" @like-click="onLikeClick" @follow-change="onFollowChange" />
    </template>
  </div>
</template>