<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
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

// Avatar URL for the author
const authorAvatarUrl = computed(() => toProtectedFileUrl(props.post.author.avatar))

// Image carousel
const currentImageIndex = ref(0)
let carouselTimer: ReturnType<typeof setInterval> | null = null
let touchStartX = 0
let touchEndX = 0

const hasMultipleImages = computed(() =>
  props.post.images && props.post.images.length > 1
)

const carouselImages = computed(() => {
  if (!props.post.images || props.post.images.length === 0) return []
  return props.post.images
})

// Carousel: first image stays 8s, others 5s
const FIRST_IMAGE_DELAY = 8000
const OTHER_IMAGE_DELAY = 5000

function advanceCarousel() {
  currentImageIndex.value = (currentImageIndex.value + 1) % carouselImages.value.length
  // After advancing, schedule next advance with appropriate delay
  const delay = currentImageIndex.value === 0 ? FIRST_IMAGE_DELAY : OTHER_IMAGE_DELAY
  carouselTimer = setTimeout(advanceCarousel, delay)
}

function startCarousel() {
  if (!hasMultipleImages.value) return
  // If currently on first image (index 0), use longer delay
  const initialDelay = currentImageIndex.value === 0 ? FIRST_IMAGE_DELAY : OTHER_IMAGE_DELAY
  carouselTimer = setTimeout(advanceCarousel, initialDelay)
}

function stopCarousel() {
  if (carouselTimer) {
    clearTimeout(carouselTimer)
    carouselTimer = null
  }
}

// Press-and-hold text scroll
const isHolding = ref(false)
let holdTimer: ReturnType<typeof setTimeout> | null = null

const holdText = computed(() => {
  const text = props.post.content_preview || props.post.content.replace(/<[^>]+>/g, '')
  return text.slice(0, 500)
})

function onPointerDown() {
  stopCarousel()
  holdTimer = setTimeout(() => {
    isHolding.value = true
  }, 350)
}

function onPointerUp() {
  if (holdTimer) {
    clearTimeout(holdTimer)
    holdTimer = null
  }
  isHolding.value = false
  if (hasMultipleImages.value) {
    startCarousel()
  }
}

function onCarouselTouchStart(e: TouchEvent) {
  touchStartX = e.touches[0].clientX
  stopCarousel()
}

function onCarouselTouchEnd(e: TouchEvent) {
  touchEndX = e.changedTouches[0].clientX
  const diff = touchStartX - touchEndX
  const images = carouselImages.value
  if (Math.abs(diff) < 50) {
    if (hasMultipleImages.value) startCarousel()
    return
  }
  if (diff > 0 && currentImageIndex.value < images.length - 1) {
    currentImageIndex.value++
  } else if (diff < 0 && currentImageIndex.value > 0) {
    currentImageIndex.value--
  }
  if (hasMultipleImages.value) startCarousel()
}

function isVideo(post: Post): boolean {
  return post.post_type === 'video' || !!post.video_url
}

function formatCount(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

onMounted(() => {
  if (hasMultipleImages.value) startCarousel()
})

onUnmounted(() => {
  stopCarousel()
})
</script>

<template>
  <router-link
    :to="`/community/${post.id}`"
    class="block no-underline mb-3 rounded-xl overflow-hidden bg-white  shadow-sm hover:shadow-md transition-all duration-200 group"
  >
    <!-- Cover area: carousel or press-and-hold overlay -->
    <div
      class="relative aspect-[3/4] bg-gray-100  overflow-hidden select-none"
      style="touch-action: pan-y"
      data-scroll-x
      @mousedown.prevent="onPointerDown"
      @mouseup="onPointerUp"
      @mouseleave="onPointerUp"
      @touchstart="onCarouselTouchStart"
      @touchend="onCarouselTouchEnd"
      @touchcancel="onPointerUp"
    >
      <!-- Default: image carousel -->
      <template v-if="!isHolding">
        <!-- Image carousel track -->
        <div class="w-full h-full flex" v-if="carouselImages.length > 0">
          <img
            v-for="(img, idx) in carouselImages"
            :key="img.id"
            :src="toProtectedFileUrl(img.image_url)"
            :alt="post.title"
            class="w-full h-full object-cover flex-shrink-0 transition-transform duration-700"
            :class="idx === currentImageIndex ? 'opacity-100' : 'opacity-0 absolute inset-0'"
            :style="{
              transform: idx === currentImageIndex ? 'translateX(0)' : (idx === (currentImageIndex + 1) % carouselImages.length ? 'translateX(100%)' : 'translateX(-100%)'),
            }"
            loading="lazy"
          />
        </div>
        <!-- Fallback when no images -->
        <div v-else class="w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-primary-50 to-primary-100 dark:from-primary-900/30 dark:to-primary-800/30">
          <span class="text-3xl">{{ post.category?.icon || '📷' }}</span>
          <span class="text-xs text-gray-500  font-medium px-2 text-center">{{ post.category?.name }}</span>
        </div>

        <!-- Carousel dot indicators -->
        <div
          v-if="hasMultipleImages && !isHolding"
          class="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5"
          @click.stop
        >
          <span
            v-for="(_, idx) in carouselImages"
            :key="idx"
            class="w-1.5 h-1.5 rounded-full transition-all duration-300"
            :class="idx === currentImageIndex ? 'bg-white w-3' : 'bg-white/50'"
          />
        </div>

        <span v-if="isVideo(post)" class="absolute inset-0 flex items-center justify-center">
          <div class="w-12 h-12 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center">
            <svg class="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
          </div>
        </span>

        <span v-if="post.images && post.images.length > 1" class="absolute top-2 right-2 text-[10px] font-medium px-1.5 py-0.5 rounded bg-black/50 text-white backdrop-blur-sm">
          📷 {{ post.images.length }}
        </span>

        <span v-if="post.is_private" class="absolute top-2 left-2 text-[10px] font-medium px-2 py-0.5 rounded-full bg-black/50 text-white backdrop-blur-sm">🔒 私密</span>
      </template>

      <!-- Press-and-hold: text content scroll overlay -->
      <div
        v-else
        class="absolute inset-0 bg-white  z-10 overflow-hidden"
        @click.stop
      >
        <div class="p-3 animate-text-scroll">
          <h3 class="text-sm font-semibold text-gray-900  mb-2 leading-snug">
            {{ post.title }}
          </h3>
          <p class="text-xs text-gray-600  leading-relaxed whitespace-pre-line">
            {{ holdText }}
          </p>
        </div>
      </div>
    </div>

    <!-- Card footer: avatar + nickname + follow+ ... heart -->
    <div class="px-2.5 pt-1.5 pb-2 flex items-center justify-between">
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
  </router-link>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@keyframes text-scroll {
  0% {
    transform: translateY(100%);
  }
  15% {
    transform: translateY(0);
  }
  85% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(calc(-100% + 100px));
  }
}

.animate-text-scroll {
  animation: text-scroll 8s ease-in-out forwards;
}
</style>
