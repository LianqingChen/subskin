<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getRevisions, voteRevision } from '@/api/encyclopedia'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  articleSlug: string
}>()

const toast = useToast()
const authStore = useAuthStore()
const revisions = ref<any[]>([])
const loading = ref(true)
const filter = ref<string>('all')

const statusMap: Record<string, { label: string, color: string }> = {
  pending: { label: '待审核', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' },
  approved: { label: '已采纳', color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' },
  rejected: { label: '已拒绝', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' },
}

const changeTypeMap: Record<string, string> = {
  suggest: '建议',
  approved: '已采纳',
  rejected: '已拒绝',
  rollback: '回滚',
}

async function loadRevisions() {
  loading.value = true
  try {
    const params = filter.value !== 'all' ? { status: filter.value } : {}
    revisions.value = await getRevisions(props.articleSlug, params)
  } catch (e) {
    toast.error('加载修订历史失败')
  } finally {
    loading.value = false
  }
}

async function handleVote(revisionId: number, voteType: 'up' | 'down') {
  if (!authStore.isLoggedIn) {
    toast.error('请先登录')
    return
  }
  try {
    const result = await voteRevision(revisionId, { vote_type: voteType })
    const revision = revisions.value.find(r => r.id === revisionId)
    if (revision) {
      revision.upvotes = result.upvotes
      revision.downvotes = result.downvotes
    }
  } catch (e) {
    toast.error('投票失败')
  }
}

onMounted(() => {
  loadRevisions()
})
</script>

<template>
  <div>
    <!-- Filter Tabs -->
    <div class="flex gap-2 mb-6">
      <button
        v-for="option in [
          { key: 'all', label: '全部' },
          { key: 'pending', label: '待审核' },
          { key: 'approved', label: '已采纳' },
          { key: 'rejected', label: '已拒绝' },
        ]"
        :key="option.key"
        class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
        :class="filter === option.key
          ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
          : 'text-gray-600  hover:bg-gray-100 dark:hover:bg-gray-300'"
        @click="filter = option.key; loadRevisions()"
      >
        {{ option.label }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-8">
      <div class="w-8 h-8 border-2 border-primary-200 border-t-primary-500 rounded-full animate-spin"></div>
    </div>

    <!-- Revision List -->
    <div v-else-if="revisions.length === 0" class="text-center py-8 text-gray-500 ">
      暂无修订记录
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="revision in revisions"
        :key="revision.id"
        class="bg-white rounded-xl border border-gray-200 dark:border-gray-700 p-4"
      >
        <!-- Revision Header -->
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-900">
                修订 #{{ revision.id }}
              </span>
              <span
                class="px-2 py-0.5 rounded-full text-xs font-medium"
                :class="statusMap[revision.status]?.color"
              >
                {{ statusMap[revision.status]?.label }}
              </span>
              <span class="text-xs text-gray-500 ">
                {{ changeTypeMap[revision.change_type] }}
              </span>
            </div>
            <p class="text-xs text-gray-500  mt-1">
              {{ new Date(revision.created_at).toLocaleString('zh-CN') }}
            </p>
          </div>

          <!-- Vote Buttons -->
          <div class="flex items-center gap-1">
            <button
              class="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors"
              :class="authStore.isLoggedIn
                ? 'text-gray-600  hover:text-green-600 dark:hover:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20'
                : 'text-gray-400 cursor-not-allowed'"
              @click="handleVote(revision.id, 'up')"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
              </svg>
              {{ revision.upvotes }}
            </button>
            <button
              class="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors"
              :class="authStore.isLoggedIn
                ? 'text-gray-600  hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                : 'text-gray-400 cursor-not-allowed'"
              @click="handleVote(revision.id, 'down')"
            >
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.057 2H5.642a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
              </svg>
              {{ revision.downvotes }}
            </button>
          </div>
        </div>

        <!-- Change Summary -->
        <p class="text-sm text-gray-700 mb-3">
          <i class="ri-file-edit-line mr-1"></i>{{ revision.change_summary || '无修订说明' }}
        </p>

        <!-- Diff Preview -->
        <details class="text-sm">
          <summary class="cursor-pointer text-primary-600 dark:text-primary-400 hover:underline">
            查看变更内容
          </summary>
          <pre class="mt-2 p-3 bg-gray-50 rounded-lg text-xs overflow-x-auto font-mono whitespace-pre-wrap">
{{ revision.diff_preview || '无内容变更' }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>
