<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import type { Post, PostComment as PostCommentType, Category } from '@/types'
import PageShareSheet from '@/components/common/PageShareSheet.vue'
import PageSharePoster from '@/components/common/PageSharePoster.vue'
import AudioPlayer from '@/components/community/AudioPlayer.vue'
import FileAttachment from '@/components/community/FileAttachment.vue'
import PostCard from '@/components/community/PostCard.vue'
import TreatmentShareCard from '@/components/community/TreatmentShareCard.vue'
import RichEditor from '@/components/community/RichEditor.vue'
import FollowButton from '@/components/community/FollowButton.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import { getCategoryColor } from '@/utils/colors'
import { rewriteProtectedHtml, toProtectedFileUrl } from '@/utils/file-url'
import { timeAgo } from '@/utils/date'
import { avatarInitial } from '@/utils/avatar'
import { getMoodMeta } from '@/utils/mood'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const postId = computed(() => Number(route.params.id))
const loading = ref(true)
const post = ref<Post | null>(null)
const comments = ref<PostCommentType[]>([])
const categories = ref<Category[]>([])
const newComment = ref('')
const showShare = ref(false)
const showPoster = ref(false)
const relatedPosts = ref<Post[]>([])

// Image carousel state
const currentImageIndex = ref(0)
let touchStartX = 0
let touchEndX = 0

// Edit modal
const showEditModal = ref(false)
const editTitle = ref('')
const editContent = ref('')
const editContentJson = ref<string | null>(null)
const editCategoryId = ref<number | null>(null)

// Helper: check if rich content is empty (ignores empty HTML tags)
function isRichContentEmpty(html: string): boolean {
  if (!html?.trim()) return true
  const text = html.replace(/<[^>]*>/g, '').trim()
  return text.length === 0
}

// Delete confirmation
const showDeleteConfirm = ref(false)
const toast = useToast()

const protectedContent = computed(() => rewriteProtectedHtml(post.value?.content || ''))

// 点赞/收藏无障碍反馈文案 (aria-live)
const actionFeedback = ref('')

function formatTimeAgo(dateStr: string): string {
  return timeAgo(dateStr) || dateStr
}

function protectedFileUrl(url?: string | null): string {
  return toProtectedFileUrl(url)
}

// Image carousel swipe
function onCarouselTouchStart(e: TouchEvent) {
  touchStartX = e.touches[0].clientX
}

function onCarouselTouchEnd(e: TouchEvent) {
  touchEndX = e.changedTouches[0].clientX
  const diff = touchStartX - touchEndX
  const images = post.value?.images || []
  if (Math.abs(diff) < 50) return
  if (diff > 0 && currentImageIndex.value < images.length - 1) {
    currentImageIndex.value++
  } else if (diff < 0 && currentImageIndex.value > 0) {
    currentImageIndex.value--
  }
}

const moodMeta = computed(() => getMoodMeta(post.value?.mood))

async function loadPost() {
  loading.value = true
  try {
    const [postRes, commentsRes, catRes] = await Promise.all([
      communityApi.getPost(postId.value),
      communityApi.getComments(postId.value),
      communityApi.getCategories(),
    ])
    post.value = postRes
    comments.value = commentsRes.items
    categories.value = catRes
    currentImageIndex.value = 0
    document.title = postRes.title ? `${postRes.title} - SubSkin` : '帖子详情 - SubSkin'

    // Load related posts (same category, different post)
    if (postRes.category_id) {
      try {
        const related = await communityApi.getPosts({ category_id: postRes.category_id, limit: 6 })
        relatedPosts.value = related.items.filter(p => p.id !== postRes.id).slice(0, 4)
      } catch {
        relatedPosts.value = []
      }
    }
  } catch {
    router.push('/community')
  } finally {
    loading.value = false
  }
}

watch(postId, () => { loadPost() })

onMounted(loadPost)

watch(showEditModal, (val) => {
  if (val && post.value) {
    editTitle.value = post.value.title
    editContent.value = post.value.content
    editContentJson.value = post.value.content_json
    editCategoryId.value = post.value.category_id
  }
})

async function handleUpdatePost() {
  if (!post.value || !editTitle.value.trim() || isRichContentEmpty(editContent.value)) return
  try {
    const updated = await communityApi.updatePost(post.value.id, {
      title: editTitle.value.trim(),
      content: editContent.value,
      content_json: editContentJson.value || undefined,
      category_id: editCategoryId.value || undefined,
    })
    post.value = updated
    showEditModal.value = false
  } catch (err) {
    console.error('Failed to update post:', err)
  }
}

// Avatar URL for the author
const authorAvatarUrl = computed(() => toProtectedFileUrl(post.value?.author.avatar))
const authorAvatarError = ref(false)

// Reset avatar error when post changes
watch(postId, () => { authorAvatarError.value = false })

async function confirmDeletePost() {
  if (!post.value) return
  try {
    await communityApi.deletePost(post.value.id)
    showDeleteConfirm.value = false
    router.push('/community')
  } catch (err) {
    showDeleteConfirm.value = false
    toast.error('删除失败，请稍后重试')
    console.error('Failed to delete post:', err)
  }
}

async function toggleLike() {
  if (!authStore.isLoggedIn) { authStore.showLoginModal = true; return }
  if (!post.value) return
  try {
    const res = await communityApi.toggleLike(post.value.id)
    post.value.is_liked = res.liked
    post.value.like_count = res.like_count
    actionFeedback.value = res.liked ? '已点赞' : '已取消点赞'
  } catch (err) {
    console.error('Failed to toggle like:', err)
  }
}

async function toggleBookmark() {
  if (!authStore.isLoggedIn) { authStore.showLoginModal = true; return }
  if (!post.value) return
  try {
    const res = await communityApi.toggleBookmark(post.value.id)
    post.value.is_bookmarked = res.bookmarked
    actionFeedback.value = res.bookmarked ? '已收藏' : '已取消收藏'
  } catch (err) {
    console.error('Failed to toggle bookmark:', err)
  }
}

async function onShared() {
  // 未登录用户仍可复制链接/系统分享，但转发计数需登录（与点赞/收藏一致）
  if (!authStore.isLoggedIn || !post.value) return
  try {
    const res = await communityApi.sharePost(post.value.id)
    post.value.share_count = res.share_count
    actionFeedback.value = '已转发'
  } catch (err) {
    console.error('Failed to count share:', err)
  }
}

async function submitComment() {
  if (!authStore.isLoggedIn) { authStore.showLoginModal = true; return }
  if (!newComment.value.trim() || !post.value) return
  try {
    const comment = await communityApi.addComment(post.value.id, { content: newComment.value.trim() })
    comments.value.push(comment)
    post.value.comment_count += 1
    newComment.value = ''
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    toast.error(detail || '评论失败，请稍后重试')
  }
}

/** 桌面端有图帖子用左右两栏（小红书式） */
const hasMedia = computed(() => !!post.value && post.value.images.length > 0)
function stepImage(delta: number) {
  if (!post.value) return
  const total = post.value.images.length
  currentImageIndex.value = (currentImageIndex.value + delta + total) % total
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/community')
  }
}
</script>

<template>
  <div class="mx-auto w-full px-4 pb-48 sm:px-6 md:pb-28 lg:px-8" :class="hasMedia ? 'max-w-6xl' : 'max-w-3xl'">
    <!-- Top bar -->
    <div class="flex items-center gap-2 py-2 md:py-3">
      <button @click="goBack" class="-ml-2 flex h-10 w-10 items-center justify-center rounded-full text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-800 dark:hover:text-gray-100" aria-label="返回">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
        </svg>
      </button>
      <span class="text-sm font-medium text-gray-700 dark:text-gray-200">帖子详情</span>
      <!-- Author actions -->
      <div v-if="authStore.user && post && post.author.id === authStore.user.id" class="ml-auto flex items-center gap-3">
        <button class="text-xs text-gray-400  hover:text-primary-600" @click="showEditModal = true">编辑</button>
        <button class="text-xs text-gray-400  hover:text-red-500" @click="showDeleteConfirm = true">删除</button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />

    <template v-else-if="post">
      <!-- 桌面端有图：左图（sticky）右文；手机端单栏 -->
      <div :class="hasMedia ? 'lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-start lg:gap-8' : ''">
      <!-- Image Carousel -->
      <div
        v-if="post.images.length > 0"
        class="group relative mb-4 overflow-hidden rounded-2xl bg-gray-100 dark:bg-gray-900 lg:sticky lg:top-[4.5rem] lg:mb-0"
        @touchstart="onCarouselTouchStart"
        @touchend="onCarouselTouchEnd"
      >
        <div class="aspect-[4/3] relative lg:aspect-[4/5] lg:max-h-[calc(100vh-8rem)] lg:w-full">
          <img
            v-for="(img, idx) in post.images"
            :key="img.id"
            v-show="idx === currentImageIndex"
            :src="protectedFileUrl(img.image_url)"
            alt=""
            class="absolute inset-0 w-full h-full object-contain transition-opacity duration-200"
          />
        </div>
        <!-- Dots indicator -->
        <div v-if="post.images.length > 1" class="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5">
          <span
            v-for="(_, idx) in post.images"
            :key="idx"
            class="w-1.5 h-1.5 rounded-full transition-all duration-200"
            :class="idx === currentImageIndex ? 'bg-white w-4' : 'bg-white/50'"
          ></span>
        </div>
        <!-- Image counter -->
        <span class="absolute top-3 right-3 text-xs text-white bg-black/40 rounded-full px-2 py-0.5">
          {{ currentImageIndex + 1 }}/{{ post.images.length }}
        </span>
        <!-- 桌面端没有滑动手势，提供左右切换按钮 -->
        <template v-if="post.images.length > 1">
          <button type="button" class="absolute left-3 top-1/2 hidden h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow transition-opacity hover:bg-white md:flex md:opacity-0 md:group-hover:opacity-100" aria-label="上一张" @click="stepImage(-1)"><i class="ri-arrow-left-s-line text-xl" aria-hidden="true"></i></button>
          <button type="button" class="absolute right-3 top-1/2 hidden h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow transition-opacity hover:bg-white md:flex md:opacity-0 md:group-hover:opacity-100" aria-label="下一张" @click="stepImage(1)"><i class="ri-arrow-right-s-line text-xl" aria-hidden="true"></i></button>
        </template>
      </div>

      <div class="min-w-0">
      <!-- Post Content -->
      <article class="space-y-4">
        <!-- Author + category -->
        <div class="flex items-center gap-3">
          <router-link :to="`/user/${post.author.id}`" class="flex-shrink-0 no-underline">
            <img v-if="authorAvatarUrl && !authorAvatarError" :src="authorAvatarUrl" :alt="post.author.username" class="w-9 h-9 rounded-full object-cover bg-gray-100" @error="authorAvatarError = true" />
            <div v-else class="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-sm font-medium">
              {{ avatarInitial(post.author.username) }}
            </div>
          </router-link>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-sm text-gray-900 dark:text-gray-100">
            {{ post.author.username }}
            <i v-if="post.author.is_doctor" class="ri-verified-badge-fill text-primary-500 text-sm inline -mt-0.5" title="认证医生" aria-label="认证医生"></i>
          </div>
            <div class="text-[11px] text-gray-400 ">{{ formatTimeAgo(post.created_at) }}</div>
          </div>
          <div v-if="authStore.isLoggedIn && post.author.id !== authStore.user?.id" class="flex items-center gap-2">
            <FollowButton :targetUserId="post.author.id" />
          </div>
          <span :class="getCategoryColor(post.category.name)" class="px-2 py-0.5 rounded-full text-[11px] font-medium flex-shrink-0 inline-flex items-center gap-0.5">
            <i :class="post.category.icon" aria-hidden="true"></i> {{ post.category.name }}
          </span>
        </div>

        <!-- Title -->
        <h1 class="text-lg font-bold text-gray-900 dark:text-gray-100 leading-snug md:text-xl">{{ post.title }}</h1>

        <!-- Tags -->
        <div v-if="post.tags && post.tags.length > 0" class="flex flex-wrap gap-1.5">
          <router-link
            v-for="tag in post.tags"
            :key="tag.id"
            :to="`/community?tag=${encodeURIComponent(tag.name)}`"
            class="text-xs text-primary-600 dark:text-primary-400 bg-primary-50 dark:bg-primary-900/50 hover:bg-primary-100 dark:hover:bg-primary-900 px-2 py-0.5 rounded-full transition-colors no-underline"
          >
            #{{ tag.name }}
          </router-link>
        </div>

        <!-- Mood badge -->
        <div v-if="moodMeta" class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm text-white" :class="moodMeta.color">
          <i :class="moodMeta.icon" class="text-xs"></i>
          {{ moodMeta.label }}
        </div>

        <!-- 治疗分享结构化信息卡 -->
        <TreatmentShareCard v-if="post.treatment_share" :treatment="post.treatment_share" />

        <!-- Audio -->
        <div v-if="post.audios && post.audios.length > 0" class="space-y-2">
          <AudioPlayer v-for="audio in post.audios" :key="audio.id" :src="protectedFileUrl(audio.audio_url)" :duration="audio.duration" />
        </div>

        <!-- Attachments -->
        <FileAttachment v-if="post.attachments && post.attachments.length > 0" :attachments="post.attachments" />

        <!-- Content -->
        <div class="prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-gray-200 text-[15px] leading-relaxed" v-html="protectedContent"></div>

        <!-- Medical disclaimer -->
        <MedicalDisclaimer variant="banner" message="本文不构成医疗建议，内容仅供参考。请勿轻信偏方，治疗请遵医嘱。" />

        <!-- Engagement stats -->
        <div class="flex items-center gap-4 text-xs text-gray-400  py-2">
          <span>{{ post.like_count }} 人觉得有帮助</span>
          <span>{{ post.comment_count }} 条评论</span>
        </div>
      </article>

      <!-- Comments Section -->
      <section class="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800">
        <h3 class="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-4">评论 ({{ comments.length }})</h3>
        <div class="space-y-4">
          <div v-for="comment in comments" :key="comment.id" class="flex gap-3 pb-4 border-b border-gray-50 dark:border-gray-800 last:border-0">
            <div class="w-8 h-8 rounded-full bg-gray-100  flex items-center justify-center text-gray-600  text-xs font-medium flex-shrink-0">
              {{ avatarInitial(comment.author.username) }}
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ comment.author.username }}</span>
                <span v-if="post && comment.author.id === post.author.id" class="text-[10px] bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 px-1.5 py-0.5 rounded font-medium">楼主</span>
                <span class="text-[11px] text-gray-400 ">{{ formatTimeAgo(comment.created_at) }}</span>
              </div>
              <p class="text-sm text-gray-600 dark:text-gray-300 leading-relaxed break-words min-w-0">{{ comment.content }}</p>
            </div>
          </div>
          <div v-if="comments.length === 0" class="text-center py-8 text-sm text-gray-400 ">
            暂无评论，来说两句吧 <i class="ri-chat-3-line ml-0.5"></i>
          </div>
        </div>
      </section>

      </div>
      </div>

      <!-- Related Posts -->
      <section v-if="relatedPosts.length > 0" class="mt-8 pt-4 border-t border-gray-100 dark:border-gray-800">
        <h3 class="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-3">相关分享</h3>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <PostCard v-for="rp in relatedPosts" :key="rp.id" :post="rp" />
        </div>
      </section>
    </template>

    <!-- Fixed bottom action bar：移动端抬高到 BottomNav（54px + safe-area）之上，避免重叠/误触导航 -->
    <div v-if="post" class="comment-bar app-fixed-x fixed bg-white/95 dark:bg-gray-900/95 backdrop-blur-md border-t border-gray-100 dark:border-gray-800 z-30">
      <!-- 与正文同宽；桌面两栏时对齐右栏 -->
      <div class="mx-auto w-full px-4 sm:px-6 lg:px-8" :class="hasMedia ? 'max-w-6xl lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-8' : 'max-w-3xl'">
      <div v-if="hasMedia" class="hidden lg:block" aria-hidden="true"></div>
      <div class="flex min-w-0 items-center gap-2 py-2">
        <!-- Comment input -->
        <div class="flex-1 relative">
          <input
            v-model="newComment"
            type="text"
            placeholder="写下你的评论..."
            class="w-full bg-gray-100 dark:bg-gray-800 rounded-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 outline-none"
            @keydown.enter="submitComment"
          />
        </div>
        <button
          v-if="newComment.trim()"
          class="w-9 h-9 rounded-full bg-primary-600 hover:bg-primary-700 text-white flex items-center justify-center transition-colors shrink-0"
          aria-label="发送评论"
          @click="submitComment"
        >
          <i class="ri-send-plane-fill" aria-hidden="true"></i>
        </button>
        <!-- Action buttons -->
        <span class="sr-only" aria-live="polite">{{ actionFeedback }}</span>
        <button class="flex flex-col items-center gap-0.5 px-2 py-1 transition-colors"
          :class="post.is_liked ? 'text-red-500' : 'text-gray-400  hover:text-red-500'"
          :aria-pressed="post.is_liked"
          :aria-label="post.is_liked ? `已点赞，共${post.like_count}人` : '点赞'"
          @click="toggleLike"
        >
          <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path v-if="post.is_liked" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/>
            <path v-else fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656zm5.656 1.414L10 7.757l1.172-1.171a2.5 2.5 0 113.535 3.535L10 15.828 5.293 10.12a2.5 2.5 0 013.535-3.535z" clip-rule="evenodd"/>
          </svg>
          <span class="text-[10px]">{{ post.like_count }}</span>
        </button>
        <button class="flex flex-col items-center gap-0.5 px-2 py-1 transition-colors"
          :class="post.is_bookmarked ? 'text-yellow-500' : 'text-gray-400  hover:text-yellow-500'"
          :aria-pressed="post.is_bookmarked"
          :aria-label="post.is_bookmarked ? '已收藏' : '收藏'"
          @click="toggleBookmark"
        >
          <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path v-if="post.is_bookmarked" d="M5 2a2 2 0 00-2 2v14l3.5-2 3.5 2 3.5-2 3.5 2V4a2 2 0 00-2-2H5z"/>
            <path v-else fill-rule="evenodd" d="M3 4a2 2 0 012-2h10a2 2 0 012 2v14l-3.5-2L10 18l-3.5-2L3 18V4z" clip-rule="evenodd"/>
          </svg>
          <span class="text-[10px]">{{ post.is_bookmarked ? '已收藏' : '收藏' }}</span>
        </button>
        <button class="flex flex-col items-center gap-0.5 px-2 py-1 text-gray-400  hover:text-primary-600 transition-colors" @click="showShare = true" aria-label="转发">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z"/>
          </svg>
          <span class="text-[10px]">{{ post.share_count ? `转发 ${post.share_count}` : '转发' }}</span>
        </button>
      </div>
      </div>
    </div>
  </div>

  <PageShareSheet v-if="post" :visible="showShare" :post="post" @close="showShare = false" @shared="onShared" @generate-poster="showShare = false; showPoster = true" />
  <PageSharePoster v-if="post" :visible="showPoster" :post="post" @close="showPoster = false" />

  <!-- Delete Confirmation Modal -->
  <Teleport to="body">
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/50 z-[110] flex items-center justify-center" @click.self="showDeleteConfirm = false">
      <div class="bg-white  rounded-xl p-6 max-w-sm w-full mx-4">
        <h3 class="text-lg font-semibold text-gray-900  mb-2">确认删除</h3>
        <p class="text-sm text-gray-500  mb-4">删除后无法恢复，确定要删除这篇分享吗？</p>
        <div class="flex gap-3 justify-end">
          <button class="btn-ghost px-4 py-2" @click="showDeleteConfirm = false">取消</button>
          <button class="bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition-colors" @click="confirmDeletePost">删除</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Edit Post Modal -->
  <Teleport to="body">
    <div v-if="showEditModal" class="fixed inset-0 bg-black/50 z-[110] flex items-stretch md:items-center justify-center" @click.self="showEditModal = false">
      <div class="bg-white  w-full md:max-w-2xl md:rounded-xl flex flex-col h-full md:h-auto md:max-h-[90vh]">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 sticky top-0 bg-white  z-10 flex-shrink-0">
          <h2 class="text-lg font-semibold ">编辑分享</h2>
          <button class="text-gray-400  hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="showEditModal = false">&times;</button>
        </div>
        <div class="p-6 space-y-4 overflow-y-auto flex-1">
          <div>
            <label class="block text-sm font-medium text-gray-700  mb-1">分类</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="cat in categories"
                :key="cat.id"
                class="px-3 py-1.5 rounded-lg text-sm border transition-colors"
                :class="editCategoryId === cat.id
                  ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600  hover:border-primary-300'"
                @click="editCategoryId = cat.id"
              >
                <i :class="cat.icon" aria-hidden="true"></i> {{ cat.name }}
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700  mb-1">标题</label>
            <input v-model="editTitle" type="text" class="input-field" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700  mb-1">内容</label>
            <RichEditor v-model="editContent" placeholder="编辑你的分享内容..." />
          </div>
          <button
            class="btn-primary w-full py-2.5"
            :disabled="!editTitle.trim() || isRichContentEmpty(editContent)"
            @click="handleUpdatePost"
          >
            保存修改
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.comment-bar {
  /* 移动端 BottomNav 固定高 54px + safe-area，评论栏需整体避开 */
  bottom: calc(54px + env(safe-area-inset-bottom, 0px));
}
@media (min-width: 768px) {
  /* 桌面端无 BottomNav，贴底并兼顾 safe-area */
  .comment-bar {
    bottom: 0;
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }
}
</style>
