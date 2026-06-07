<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getComments, createComment } from '@/api/encyclopedia'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  articleSlug: string
}>()

const toast = useToast()
const authStore = useAuthStore()
const comments = ref<any[]>([])
const loading = ref(true)
const newComment = ref('')
const submitting = ref(false)
const replyTo = ref<number | undefined>(undefined)

async function loadComments() {
  loading.value = true
  try {
    comments.value = await getComments(props.articleSlug)
  } catch (e) {
    toast.error('加载评论失败')
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!authStore.isLoggedIn) {
    toast.error('请先登录')
    return
  }
  if (!newComment.value.trim()) {
    toast.error('请输入评论内容')
    return
  }

  submitting.value = true
  try {
    await createComment(props.articleSlug, {
      content: newComment.value,
      parent_id: replyTo.value ?? undefined,
    })
    toast.success('评论已提交，等待审核')
    newComment.value = ''
    replyTo.value = undefined
    loadComments()
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || '评论失败')
  } finally {
    submitting.value = false
  }
}

function startReply(commentId: number) {
  if (!authStore.isLoggedIn) {
    toast.error('请先登录')
    return
  }
  replyTo.value = commentId
}

function cancelReply() {
  replyTo.value = undefined
}

onMounted(() => {
  loadComments()
})
</script>

<template>
  <div>
    <!-- Comment Form -->
    <div class="bg-white rounded-xl border border-gray-200 dark:border-gray-700 p-4 mb-6">
      <div v-if="replyTo" class="flex items-center justify-between mb-2 text-sm text-primary-600 dark:text-primary-400">
        <span><i class="ri-chat-3-line mr-1"></i>回复评论</span>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" @click="cancelReply">取消</button>
      </div>
      <textarea
        v-model="newComment"
        class="input-field text-sm"
        rows="3"
        :placeholder="authStore.isLoggedIn ? '发表你的看法...' : '登录后即可评论'"
        :disabled="!authStore.isLoggedIn"
      />
      <div class="flex justify-end mt-2">
        <button class="btn-primary text-sm" :disabled="submitting || !authStore.isLoggedIn" @click="handleSubmit">
          {{ submitting ? '提交中...' : '发表评论' }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-8">
      <div class="w-8 h-8 border-2 border-primary-200 border-t-primary-500 rounded-full animate-spin"></div>
    </div>

    <!-- Comments List -->
    <div v-else-if="comments.length === 0" class="text-center py-8 text-gray-500 ">
      暂无评论，快来发表你的看法吧
    </div>

    <div v-else class="space-y-4">
      <div v-for="comment in comments" :key="comment.id" class="bg-white rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <!-- Comment Header -->
        <div class="flex items-center gap-2 mb-2">
          <div class="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-sm font-medium text-primary-600 dark:text-primary-400">
            {{ (comment.username || '匿')[0] }}
          </div>
          <span class="text-sm font-medium text-gray-900">
            {{ comment.username || '匿名用户' }}
          </span>
          <span class="text-xs text-gray-500 ">
            {{ new Date(comment.created_at).toLocaleString('zh-CN') }}
          </span>
        </div>

        <!-- Comment Content -->
        <p class="text-sm text-gray-700 mb-3">
          {{ comment.content }}
        </p>

        <!-- Reply Button -->
        <button
          class="text-xs text-primary-600 dark:text-primary-400 hover:underline"
          @click="startReply(comment.id)"
        >
          回复
        </button>

        <!-- Replies -->
        <div v-if="comment.replies?.length" class="ml-8 mt-3 space-y-3 border-l-2 border-gray-100 dark:border-gray-800 pl-4">
          <div v-for="reply in comment.replies" :key="reply.id" class="bg-gray-50  rounded-lg p-3">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-sm font-medium text-gray-900">
                {{ reply.username || '匿名用户' }}
              </span>
              <span class="text-xs text-gray-500 ">
                {{ new Date(reply.created_at).toLocaleString('zh-CN') }}
              </span>
            </div>
            <p class="text-sm text-gray-700">
              {{ reply.content }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
