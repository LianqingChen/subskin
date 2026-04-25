<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { communityApi } from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import type { Post, PostComment as PostCommentType, Category } from '@/types'
import LoginModal from '@/components/common/LoginModal.vue'
import ShareSheet from '@/components/community/ShareSheet.vue'
import SharePoster from '@/components/community/SharePoster.vue'
import AudioPlayer from '@/components/community/AudioPlayer.vue'
import FileAttachment from '@/components/community/FileAttachment.vue'
import PostCard from '@/components/community/PostCard.vue'
import RichEditor from '@/components/community/RichEditor.vue'
import FollowButton from '@/components/community/FollowButton.vue'
import { rewriteProtectedHtml, toProtectedFileUrl } from '@/utils/file-url'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const postId = computed(() => Number(route.params.id))
const loading = ref(true)
const post = ref<Post | null>(null)
const comments = ref<PostCommentType[]>([])
const categories = ref<Category[]>([])
const newComment = ref('')
const showLoginModal = ref(false)
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

const categoryColor: Record<string, string> = {
  '治疗分享': 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  '心理支持': 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
  '护肤经验': 'bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300',
  '日常饮食': 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  '诊断咨询': 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300',
  '白白日记': 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  '最新资讯': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
  '其他': 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
}

function formatTimeAgo(dateStr: string): string {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 60) return `${diffMins}分钟前`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}小时前`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}天前`
  return `${Math.floor(diffDays / 30)}月前`
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
  if (!authStore.isLoggedIn) { showLoginModal.value = true; return }
  if (!post.value) return
  try {
    const res = await communityApi.toggleLike(post.value.id)
    post.value.is_liked = res.liked
    post.value.like_count = res.like_count
  } catch (err) {
    console.error('Failed to toggle like:', err)
  }
}

async function toggleBookmark() {
  if (!authStore.isLoggedIn) { showLoginModal.value = true; return }
  if (!post.value) return
  try {
    const res = await communityApi.toggleBookmark(post.value.id)
    post.value.is_bookmarked = res.bookmarked
  } catch (err) {
    console.error('Failed to toggle bookmark:', err)
  }
}

async function submitComment() {
  if (!authStore.isLoggedIn) { showLoginModal.value = true; return }
  if (!newComment.value.trim() || !post.value) return
  try {
    const comment = await communityApi.addComment(post.value.id, { content: newComment.value.trim() })
    comments.value.push(comment)
    post.value.comment_count += 1
    newComment.value = ''
  } catch (err) {
    console.error('Failed to add comment:', err)
  }
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
  <div class="max-w-2xl mx-auto px-3 pb-24">
    <!-- Top bar -->
    <div class="flex items-center gap-3 py-3 sticky top-0 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md z-20">
      <button @click="goBack" class="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
        </svg>
      </button>
      <span class="text-sm font-medium text-gray-700 dark:text-gray-300">帖子详情</span>
      <!-- Author actions -->
      <div v-if="authStore.user && post && post.author.id === authStore.user.id" class="ml-auto flex items-center gap-3">
        <button class="text-xs text-gray-400 dark:text-gray-500 hover:text-primary-600" @click="showEditModal = true">编辑</button>
        <button class="text-xs text-gray-400 dark:text-gray-500 hover:text-red-500" @click="showDeleteConfirm = true">删除</button>
      </div>
    </div>

    <div v-if="loading" class="text-center py-12 text-gray-400 dark:text-gray-500">加载中...</div>

    <template v-else-if="post">
      <!-- Image Carousel -->
      <div
        v-if="post.images.length > 0"
        class="relative rounded-xl overflow-hidden bg-black mb-4"
        @touchstart="onCarouselTouchStart"
        @touchend="onCarouselTouchEnd"
      >
        <div class="aspect-[4/3] relative">
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
      </div>

      <!-- Post Content -->
      <article class="space-y-4">
        <!-- Author + category -->
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-sm font-medium">
            {{ post.author.username.charAt(0) }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-sm text-gray-900 dark:text-gray-100">
            {{ post.author.username }}
            <svg v-if="post.author.is_doctor" class="w-3.5 h-3.5 text-primary-500 inline -mt-0.5" viewBox="0 0 20 20" fill="currentColor" title="认证医生">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/>
            </svg>
          </div>
            <div class="text-[11px] text-gray-400 dark:text-gray-500">{{ formatTimeAgo(post.created_at) }}</div>
          </div>
          <FollowButton
            v-if="authStore.isLoggedIn && post.author.id !== authStore.user?.id"
            :targetUserId="post.author.id"
            class="ml-2"
          />
          <span :class="categoryColor[post.category.name] || 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'" class="px-2 py-0.5 rounded-full text-[11px] font-medium flex-shrink-0">
            {{ post.category.icon }} {{ post.category.name }}
          </span>
        </div>

        <!-- Title -->
        <h1 class="text-lg font-bold text-gray-900 dark:text-gray-100 leading-snug">{{ post.title }}</h1>

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
        <div v-if="post.mood" class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-sm text-gray-700 dark:text-gray-300">
          {{ post.mood }}
        </div>

        <!-- Audio -->
        <div v-if="post.audios && post.audios.length > 0" class="space-y-2">
          <AudioPlayer v-for="audio in post.audios" :key="audio.id" :src="protectedFileUrl(audio.audio_url)" :duration="audio.duration" />
        </div>

        <!-- Attachments -->
        <FileAttachment v-if="post.attachments && post.attachments.length > 0" :attachments="post.attachments" />

        <!-- Content -->
        <div class="prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 text-[15px] leading-relaxed" v-html="protectedContent"></div>

        <!-- Medical disclaimer -->
        <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-lg p-3 flex items-start gap-2">
          <span class="text-amber-500 text-sm mt-0.5">⚠️</span>
          <p class="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">本文不构成医疗建议，内容仅供参考。请勿轻信偏方，治疗请遵医嘱。</p>
        </div>

        <!-- Engagement stats -->
        <div class="flex items-center gap-4 text-xs text-gray-400 dark:text-gray-500 py-2">
          <span>{{ post.like_count }} 人觉得有帮助</span>
          <span>{{ post.comment_count }} 条评论</span>
        </div>
      </article>

      <!-- Comments Section -->
      <section class="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800">
        <h3 class="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-4">评论 ({{ comments.length }})</h3>
        <div class="space-y-4">
          <div v-for="comment in comments" :key="comment.id" class="flex gap-3 pb-4 border-b border-gray-50 dark:border-gray-800 last:border-0">
            <div class="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center text-gray-600 dark:text-gray-400 text-xs font-medium flex-shrink-0">
              {{ comment.author.username.charAt(0) }}
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ comment.author.username }}</span>
                <span v-if="post && comment.author.id === post.author.id" class="text-[10px] bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 px-1.5 py-0.5 rounded font-medium">楼主</span>
                <span class="text-[11px] text-gray-400 dark:text-gray-500">{{ formatTimeAgo(comment.created_at) }}</span>
              </div>
              <p class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{{ comment.content }}</p>
            </div>
          </div>
          <div v-if="comments.length === 0" class="text-center py-8 text-sm text-gray-400 dark:text-gray-500">
            暂无评论，来说两句吧 💬
          </div>
        </div>
      </section>

      <!-- Related Posts -->
      <section v-if="relatedPosts.length > 0" class="mt-8 pt-4 border-t border-gray-100 dark:border-gray-800">
        <h3 class="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-3">相关分享</h3>
        <div class="columns-2 gap-2">
          <PostCard v-for="rp in relatedPosts" :key="rp.id" :post="rp" />
        </div>
      </section>
    </template>

    <!-- Fixed bottom action bar -->
    <div v-if="post" class="fixed bottom-0 left-0 right-0 bg-white/90 dark:bg-gray-900/90 backdrop-blur-md border-t border-gray-100 dark:border-gray-800 z-30 safe-bottom">
      <div class="max-w-2xl mx-auto px-3 py-2 flex items-center gap-2">
        <!-- Comment input -->
        <div class="flex-1 relative">
          <input
            v-model="newComment"
            type="text"
            placeholder="写下你的评论..."
            class="w-full bg-gray-100 dark:bg-gray-800 rounded-full px-4 py-2 text-sm text-gray-700 dark:text-gray-300 placeholder-gray-400 dark:placeholder-gray-500 outline-none"
            @keydown.enter="submitComment"
          />
        </div>
        <!-- Action buttons -->
        <button class="flex flex-col items-center gap-0.5 px-2 py-1 transition-colors"
          :class="post.is_liked ? 'text-red-500' : 'text-gray-400 dark:text-gray-500 hover:text-red-500'"
          @click="toggleLike"
        >
          <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path v-if="post.is_liked" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/>
            <path v-else fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656zm5.656 1.414L10 7.757l1.172-1.171a2.5 2.5 0 113.535 3.535L10 15.828 5.293 10.12a2.5 2.5 0 013.535-3.535z" clip-rule="evenodd"/>
          </svg>
          <span class="text-[10px]">{{ post.like_count }}</span>
        </button>
        <button class="flex flex-col items-center gap-0.5 px-2 py-1 transition-colors"
          :class="post.is_bookmarked ? 'text-yellow-500' : 'text-gray-400 dark:text-gray-500 hover:text-yellow-500'"
          @click="toggleBookmark"
        >
          <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path v-if="post.is_bookmarked" d="M5 2a2 2 0 00-2 2v14l3.5-2 3.5 2 3.5-2 3.5 2V4a2 2 0 00-2-2H5z"/>
            <path v-else fill-rule="evenodd" d="M3 4a2 2 0 012-2h10a2 2 0 012 2v14l-3.5-2L10 18l-3.5-2L3 18V4z" clip-rule="evenodd"/>
          </svg>
          <span class="text-[10px]">收藏</span>
        </button>
        <button class="flex flex-col items-center gap-0.5 px-2 py-1 text-gray-400 dark:text-gray-500 hover:text-primary-600 transition-colors" @click="showShare = true">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z"/>
          </svg>
          <span class="text-[10px]">分享</span>
        </button>
      </div>
    </div>
  </div>

  <LoginModal v-if="showLoginModal" @close="showLoginModal = false" />
  <ShareSheet v-if="post" :visible="showShare" :post="post" @close="showShare = false" @generate-poster="showShare = false; showPoster = true" />
  <SharePoster v-if="post" :visible="showPoster" :post="post" @close="showPoster = false" />

  <!-- Delete Confirmation Modal -->
  <Teleport to="body">
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/50 z-[110] flex items-center justify-center" @click.self="showDeleteConfirm = false">
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-sm w-full mx-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">确认删除</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">删除后无法恢复，确定要删除这篇分享吗？</p>
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
      <div class="bg-white dark:bg-gray-800 w-full md:max-w-2xl md:rounded-xl flex flex-col h-full md:h-auto md:max-h-[90vh]">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 sticky top-0 bg-white dark:bg-gray-800 z-10 flex-shrink-0">
          <h2 class="text-lg font-semibold dark:text-gray-100">编辑分享</h2>
          <button class="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="showEditModal = false">&times;</button>
        </div>
        <div class="p-6 space-y-4 overflow-y-auto flex-1">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">分类</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="cat in categories"
                :key="cat.id"
                class="px-3 py-1.5 rounded-lg text-sm border transition-colors"
                :class="editCategoryId === cat.id
                  ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-primary-300'"
                @click="editCategoryId = cat.id"
              >
                {{ cat.icon }} {{ cat.name }}
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">标题</label>
            <input v-model="editTitle" type="text" class="input-field" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">内容</label>
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
.safe-bottom {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
</style>
