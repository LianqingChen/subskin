<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { moderationApi } from '@/api/moderation'
import type { ModerationItem, UserProfileModeration } from '@/api/moderation'

const loading = ref(false)
const items = ref<ModerationItem[]>([])
const total = ref(0)
const riskFilter = ref('')
const offset = ref(0)
const limit = 20

const selectedUser = ref<UserProfileModeration | null>(null)
const userModalOpen = ref(false)

const reviewLoading = ref<number | null>(null)
const reviewAction = ref('')
const reviewNote = ref('')
const reviewMuteHours = ref(72)
const reviewBan = ref(false)
const reviewModalItem = ref<ModerationItem | null>(null)

async function fetchPending() {
  loading.value = true
  try {
    const res = await moderationApi.getPending({
      risk_level: riskFilter.value || undefined,
      limit,
      offset: offset.value,
    })
    items.value = res.items
    total.value = res.total
  } catch (e) {
    console.error('Failed to fetch pending moderations', e)
  } finally {
    loading.value = false
  }
}

async function openUserProfile(userId: number) {
  try {
    selectedUser.value = await moderationApi.getUserProfile(userId)
    userModalOpen.value = true
  } catch (e) {
    console.error('Failed to fetch user profile', e)
  }
}

async function submitReview() {
  if (!reviewModalItem.value || !reviewAction.value) return
  reviewLoading.value = reviewModalItem.value.id
  try {
    await moderationApi.review(reviewModalItem.value.id, {
      action: reviewAction.value,
      note: reviewNote.value || undefined,
      mute_hours: reviewAction.value === 'rejected' && !reviewBan.value ? reviewMuteHours.value : undefined,
      ban: reviewAction.value === 'rejected' ? reviewBan.value : undefined,
    })
    reviewModalItem.value = null
    reviewAction.value = ''
    reviewNote.value = ''
    reviewBan.value = false
    reviewMuteHours.value = 72
    await fetchPending()
  } catch (e) {
    console.error('Failed to submit review', e)
  } finally {
    reviewLoading.value = null
  }
}

async function userAction(userId: number, action: string, hours?: number) {
  try {
    await moderationApi.userAction(userId, { action, hours, reason: '管理员操作' })
    if (selectedUser.value && selectedUser.value.user_id === userId) {
      selectedUser.value = await moderationApi.getUserProfile(userId)
    }
    await fetchPending()
  } catch (e) {
    console.error('Failed to perform user action', e)
  }
}

function riskBadgeClass(level: string) {
  switch (level) {
    case 'critical': return 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
    case 'high': return 'bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300'
    case 'medium': return 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300'
    default: return 'bg-gray-100 text-gray-600 '
  }
}

function riskLabel(level: string) {
  const map: Record<string, string> = { critical: '严重', high: '高危', medium: '中危', low: '低危' }
  return map[level] || level
}

function statusBadgeClass(status: string) {
  switch (status) {
    case 'pending': return 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300'
    case 'approved': return 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300'
    case 'rejected': return 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
    default: return 'bg-gray-100 text-gray-600 '
  }
}

function statusLabel(status: string) {
  const map: Record<string, string> = { pending: '待审核', approved: '已通过', rejected: '已拒绝', escalated: '已升级' }
  return map[status] || status
}

function userStatusLabel(status: string) {
  const map: Record<string, string> = { normal: '正常', muted: '禁言中', banned: '已封号' }
  return map[status] || status
}

function userStatusClass(status: string) {
  switch (status) {
    case 'muted': return 'text-orange-600 dark:text-orange-400'
    case 'banned': return 'text-red-600 dark:text-red-400'
    default: return 'text-green-600 dark:text-green-400'
  }
}

function formatTime(ts: string | null) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchPending()
  refreshTimer = setInterval(fetchPending, 3600000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="flex flex-col gap-5 p-4 md:p-6 max-w-6xl mx-auto w-full">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <span class="text-sm text-gray-500 ">待审核 {{ total }} 条</span>
      <div class="flex items-center gap-2">
        <select
          v-model="riskFilter"
          @change="offset = 0; fetchPending()"
          class="text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white px-3 py-1.5 text-gray-700"
        >
          <option value="">全部风险等级</option>
          <option value="critical">严重</option>
          <option value="high">高危</option>
          <option value="medium">中危</option>
          <option value="low">低危</option>
        </select>
      </div>
    </div>

    <div v-if="!items.length && !loading" class="card p-8 text-center">
      <div class="text-gray-400  text-sm">暂无待审核内容</div>
    </div>

    <div v-for="item in items" :key="item.id" class="card p-4 md:p-5">
      <div class="flex items-start justify-between gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap mb-2">
            <span class="px-2 py-0.5 rounded-full text-xs font-semibold" :class="riskBadgeClass(item.risk_level)">
              {{ riskLabel(item.risk_level) }}
            </span>
            <span class="px-2 py-0.5 rounded-full text-xs font-semibold" :class="statusBadgeClass(item.status)">
              {{ statusLabel(item.status) }}
            </span>
            <span v-if="item.ai_confidence" class="text-xs text-gray-400">
              AI置信度 {{ (item.ai_confidence * 100).toFixed(0) }}%
            </span>
            <span class="text-xs text-gray-400">{{ formatTime(item.created_at) }}</span>
          </div>

          <div v-if="item.post_title" class="text-sm font-medium text-gray-900 dark:text-white mb-1 truncate">
            {{ item.post_title }}
          </div>

          <div v-if="item.content_snapshot" class="text-xs text-gray-600  mb-2 line-clamp-3 bg-gray-50  rounded p-2">
            {{ item.content_snapshot }}
          </div>

          <div v-if="item.ai_reason" class="text-xs text-amber-700 dark:text-amber-300 mb-2">
            AI判断：{{ item.ai_reason }}
          </div>

          <div v-if="item.risk_categories?.length" class="flex gap-1 flex-wrap mb-2">
            <span v-for="cat in item.risk_categories" :key="cat"
              class="px-1.5 py-0.5 rounded text-[10px] bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400">
              {{ cat }}
            </span>
          </div>

          <div class="flex items-center gap-2 text-xs text-gray-500 ">
            <span>用户：</span>
            <button @click="openUserProfile(item.user_id)" class="text-primary-600 dark:text-primary-400 hover:underline">
              {{ item.author_username || `#${item.user_id}` }}
            </button>
            <span>· 类型：{{ item.content_type }}</span>
          </div>
        </div>

        <div v-if="item.status === 'pending'" class="shrink-0 flex flex-col gap-2">
          <button @click="reviewModalItem = item; reviewAction = 'approved'"
            class="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/60 transition-colors">
            通过
          </button>
          <button @click="reviewModalItem = item; reviewAction = 'rejected'"
            class="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/60 transition-colors">
            拒绝
          </button>
          <button @click="reviewModalItem = item; reviewAction = 'escalated'"
            class="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
            升级
          </button>
        </div>
      </div>

      <div v-if="item.reviewed_by" class="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700 text-xs text-gray-400">
        已审核 · 备注：{{ item.review_note || '无' }}
      </div>
    </div>

    <div v-if="total > limit" class="flex items-center justify-center gap-3">
      <button @click="offset = Math.max(0, offset - limit); fetchPending()" :disabled="offset === 0"
        class="px-3 py-1.5 rounded-lg text-sm bg-gray-100 text-gray-600  disabled:opacity-50">
        上一页
      </button>
      <span class="text-sm text-gray-500">{{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }}</span>
      <button @click="offset += limit; fetchPending()" :disabled="offset + limit >= total"
        class="px-3 py-1.5 rounded-lg text-sm bg-gray-100 text-gray-600  disabled:opacity-50">
        下一页
      </button>
    </div>

    <!-- Review Modal -->
    <Teleport to="body">
      <div v-if="reviewModalItem" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="reviewModalItem = null">
        <div class="bg-white rounded-2xl p-5 w-full max-w-md shadow-xl">
          <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-3">
            审核：{{ reviewAction === 'approved' ? '通过' : reviewAction === 'rejected' ? '拒绝' : '升级' }}
          </h3>

          <div class="mb-3 text-sm text-gray-600 ">
            <div v-if="reviewModalItem.post_title">帖子：{{ reviewModalItem.post_title }}</div>
            <div>用户：{{ reviewModalItem.author_username || `#${reviewModalItem.user_id}` }}</div>
            <div>风险：{{ riskLabel(reviewModalItem.risk_level) }}</div>
          </div>

          <div class="mb-3">
            <label class="text-sm text-gray-700 block mb-1">备注</label>
            <textarea v-model="reviewNote" rows="2"
              class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white px-3 py-2 text-sm text-gray-900 dark:text-white"
              placeholder="审核说明（可选）"></textarea>
          </div>

          <div v-if="reviewAction === 'rejected'" class="mb-3 space-y-2">
            <label class="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" v-model="reviewBan" class="rounded" />
              封号
            </label>
            <div v-if="!reviewBan">
              <label class="text-sm text-gray-700 block mb-1">禁言时长</label>
              <select v-model="reviewMuteHours"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white px-3 py-2 text-sm text-gray-900 dark:text-white">
                <option :value="24">24小时</option>
                <option :value="72">3天</option>
                <option :value="168">7天</option>
                <option :value="720">30天</option>
              </select>
            </div>
          </div>

          <div class="flex gap-2 justify-end">
            <button @click="reviewModalItem = null"
              class="px-4 py-2 rounded-lg text-sm text-gray-600  hover:bg-gray-100 dark:hover:bg-gray-300">
              取消
            </button>
            <button @click="submitReview()" :disabled="reviewLoading === reviewModalItem?.id"
              class="px-4 py-2 rounded-lg text-sm font-medium text-white"
              :class="reviewAction === 'approved' ? 'bg-green-600 hover:bg-green-700' : reviewAction === 'rejected' ? 'bg-red-600 hover:bg-red-700' : 'bg-gray-600 hover:bg-gray-700'">
              确认
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- User Profile Modal -->
    <Teleport to="body">
      <div v-if="userModalOpen && selectedUser" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="userModalOpen = false">
        <div class="bg-white rounded-2xl p-5 w-full max-w-md shadow-xl">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-gray-900 dark:text-white">
              {{ selectedUser.username }}
            </h3>
            <span class="text-sm font-medium" :class="userStatusClass(selectedUser.user_status)">
              {{ userStatusLabel(selectedUser.user_status) }}
            </span>
          </div>

          <div class="grid grid-cols-4 gap-2 mb-4">
            <div class="text-center p-2 rounded-lg bg-gray-50 ">
              <div class="text-lg font-bold text-red-600 dark:text-red-400">{{ selectedUser.critical_count }}</div>
              <div class="text-[10px] text-gray-500">严重</div>
            </div>
            <div class="text-center p-2 rounded-lg bg-gray-50 ">
              <div class="text-lg font-bold text-orange-600 dark:text-orange-400">{{ selectedUser.high_count }}</div>
              <div class="text-[10px] text-gray-500">高危</div>
            </div>
            <div class="text-center p-2 rounded-lg bg-gray-50 ">
              <div class="text-lg font-bold text-yellow-600 dark:text-yellow-400">{{ selectedUser.medium_count }}</div>
              <div class="text-[10px] text-gray-500">中危</div>
            </div>
            <div class="text-center p-2 rounded-lg bg-gray-50 ">
              <div class="text-lg font-bold text-gray-600 ">{{ selectedUser.low_count }}</div>
              <div class="text-[10px] text-gray-500">低危</div>
            </div>
          </div>

          <div class="text-xs text-gray-500  mb-1">
            违规总次数：{{ selectedUser.violation_count }}
          </div>
          <div v-if="selectedUser.muted_until" class="text-xs text-orange-600 dark:text-orange-400 mb-1">
            禁言至：{{ new Date(selectedUser.muted_until).toLocaleString('zh-CN') }}
          </div>
          <div v-if="selectedUser.banned_at" class="text-xs text-red-600 dark:text-red-400 mb-1">
            封号时间：{{ new Date(selectedUser.banned_at).toLocaleString('zh-CN') }}
            <span v-if="selectedUser.ban_reason">· 原因：{{ selectedUser.ban_reason }}</span>
          </div>

          <div v-if="selectedUser.recent_logs.length" class="mt-3 space-y-1.5 max-h-40 overflow-y-auto">
            <div class="text-xs font-semibold text-gray-600  mb-1">操作记录</div>
            <div v-for="log in selectedUser.recent_logs" :key="log.id"
              class="flex items-center gap-2 text-xs text-gray-500  py-1 border-b border-gray-100 dark:border-gray-700/50">
              <span class="font-medium" :class="log.action === 'ban' ? 'text-red-600' : log.action === 'mute' ? 'text-orange-600' : 'text-green-600'">
                {{ log.action === 'ban' ? '封号' : log.action === 'mute' ? `禁言${log.duration_hours}h` : log.action === 'unban' ? '解封' : log.action === 'unmute' ? '解禁' : log.action }}
              </span>
              <span class="truncate flex-1">{{ log.reason || '-' }}</span>
              <span class="shrink-0">{{ formatTime(log.created_at) }}</span>
            </div>
          </div>

          <div class="flex gap-2 mt-4 justify-end flex-wrap">
            <button v-if="selectedUser.user_status === 'muted'" @click="userAction(selectedUser!.user_id, 'unmute')"
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 hover:bg-green-200">
              解除禁言
            </button>
            <button v-if="selectedUser.user_status === 'banned'" @click="userAction(selectedUser!.user_id, 'unban')"
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 hover:bg-green-200">
              解封
            </button>
            <button v-if="selectedUser.user_status === 'normal'" @click="userAction(selectedUser!.user_id, 'mute', 72)"
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300 hover:bg-orange-200">
              禁言3天
            </button>
            <button v-if="selectedUser.user_status !== 'banned'" @click="userAction(selectedUser!.user_id, 'ban')"
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 hover:bg-red-200">
              封号
            </button>
            <button @click="userModalOpen = false"
              class="px-3 py-1.5 rounded-lg text-xs text-gray-600  hover:bg-gray-100 dark:hover:bg-gray-300">
              关闭
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
