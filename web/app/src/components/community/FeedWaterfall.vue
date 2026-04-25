<script setup lang="ts">
import type { Post } from '@/types'
import ImagePostCard from '@/components/community/PostCard/ImagePostCard.vue'
import TextPostCard from '@/components/community/PostCard/TextPostCard.vue'
import LongPostCard from '@/components/community/PostCard/LongPostCard.vue'

defineProps<{
  posts: Post[]
}>()

const emit = defineEmits<{
  (e: 'tag-click', tagName: string): void
  (e: 'like-click', postId: number): void
  (e: 'bookmark-click', postId: number): void
}>()

function getPostType(post: Post): string {
  if (post.post_type) return post.post_type
  if (post.video_url) return 'video'
  if (post.images && post.images.length > 0) return 'image'
  const textLen = (post.content_preview || post.content.replace(/<[^>]+>/g, '')).length
  if (textLen > 200) return 'long'
  return 'text'
}

function onTagClick(tagName: string) {
  emit('tag-click', tagName)
}

function onLikeClick(postId: number) {
  emit('like-click', postId)
}

function onBookmarkClick(postId: number) {
  emit('bookmark-click', postId)
}
</script>

<template>
  <div class="columns-2 sm:columns-3 lg:columns-4 gap-2.5">
    <template v-for="post in posts" :key="post.id">
      <ImagePostCard v-if="getPostType(post) === 'image' || getPostType(post) === 'video'" :post="post" @tag-click="onTagClick" @like-click="onLikeClick" @bookmark-click="onBookmarkClick" />
      <TextPostCard v-else-if="getPostType(post) === 'text'" :post="post" @tag-click="onTagClick" @like-click="onLikeClick" @bookmark-click="onBookmarkClick" />
      <LongPostCard v-else :post="post" @tag-click="onTagClick" @like-click="onLikeClick" @bookmark-click="onBookmarkClick" />
    </template>
  </div>
</template>
