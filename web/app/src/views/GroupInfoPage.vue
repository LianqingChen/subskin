<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const groupId = computed(() => Number(route.params.id))
const groupName = ref('')
const announcement = ref('')
const members = ref<any[]>([])
const isOwner = ref(false)
const showEditName = ref(false)
const editNameValue = ref('')
const showEditAnnouncement = ref(false)
const editAnnouncementValue = ref('')

onMounted(async () => {
  await loadGroupInfo()
  await loadMembers()
})

async function loadGroupInfo() {
  try {
    const res = await apiClient.get(`/im/conversations`)
    const conv = res.data.items.find((c: any) => c.id === groupId.value)
    if (conv) {
      groupName.value = conv.name || ''
    }
  } catch (e) {
    console.error('load group info failed', e)
  }
}

async function loadMembers() {
  try {
    const res = await apiClient.get(`/im/groups/${groupId.value}/members`)
    members.value = res.data.items
    isOwner.value = members.value.some(
      (m: any) => m.user_id === authStore.user?.id && m.role === 'owner',
    )
  } catch (e) {
    console.error('load members failed', e)
  }
}

async function updateName() {
  try {
    await apiClient.put(`/im/groups/${groupId.value}/info`, null, {
      params: { name: editNameValue.value },
    })
    groupName.value = editNameValue.value
    showEditName.value = false
  } catch (e) {
    console.error('update name failed', e)
  }
}

async function updateAnnouncement() {
  try {
    await apiClient.put(`/im/groups/${groupId.value}/info`, null, {
      params: { announcement: editAnnouncementValue.value },
    })
    announcement.value = editAnnouncementValue.value
    showEditAnnouncement.value = false
  } catch (e) {
    console.error('update announcement failed', e)
  }
}

async function removeMember(userId: number) {
  try {
    await apiClient.delete(`/im/groups/${groupId.value}/members/${userId}`)
    await loadMembers()
  } catch (e) {
    console.error('remove member failed', e)
  }
}

async function leaveGroup() {
  if (!confirm('确定退出群聊？')) return
  try {
    await apiClient.delete(
      `/im/groups/${groupId.value}/members/${authStore.user?.id}`,
    )
    router.push('/messages')
  } catch (e) {
    console.error('leave group failed', e)
  }
}

const roleLabel = (role: string) => {
  if (role === 'owner') return '群主'
  if (role === 'admin') return '管理员'
  return '成员'
}
</script>

<template>
  <div class="min-h-screen bg-[#F5F7FA] safe-bottom">
    <header
      class="sticky top-0 bg-[#F5F7FA] border-b dark:border-gray-700 z-10 px-4 py-3 flex items-center gap-3"
    >
      <button
        @click="router.back()"
        class="p-2 -ml-2 rounded-lg hover:bg-gray-100 text-gray-600"
      >
        <i class="ri-arrow-left-line text-xl"></i>
      </button>
      <h1 class="text-lg font-bold text-gray-900 dark:text-white flex-1 truncate">
        群聊信息
      </h1>
    </header>

    <div class="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <!-- Group name -->
      <div class="bg-[#F5F7FA] rounded-2xl p-5">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-gray-400  mb-1">群名称</div>
            <div class="text-lg font-bold text-gray-900 dark:text-white">
              {{ groupName || '未命名群聊' }}
            </div>
          </div>
          <button
            v-if="isOwner"
            @click="editNameValue = groupName; showEditName = true"
            class="p-2 rounded-lg hover:bg-gray-100 text-primary-600 dark:text-primary-400"
          >
            <i class="ri-edit-line"></i>
          </button>
        </div>
      </div>

      <!-- Announcement -->
      <div class="bg-[#F5F7FA] rounded-2xl p-5">
        <div class="flex items-center justify-between mb-2">
          <div class="text-xs text-gray-400 ">群公告</div>
          <button
            v-if="isOwner"
            @click="editAnnouncementValue = announcement; showEditAnnouncement = true"
            class="p-2 rounded-lg hover:bg-gray-100 text-primary-600 dark:text-primary-400"
          >
            <i class="ri-edit-line"></i>
          </button>
        </div>
        <div
          class="text-sm text-gray-700"
          :class="{ 'text-gray-400  italic': !announcement }"
        >
          {{ announcement || '暂无公告' }}
        </div>
      </div>

      <!-- Members -->
      <div class="bg-[#F5F7FA] rounded-2xl p-5">
        <div class="text-xs text-gray-400  mb-3">
          成员 ({{ members.length }})
        </div>
        <div class="space-y-3">
          <div
            v-for="member in members"
            :key="member.user_id"
            class="flex items-center justify-between"
          >
            <div class="flex items-center gap-3">
              <div
                class="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-300 font-bold"
              >
                {{ member.username?.[0] || '?' }}
              </div>
              <div>
                <div class="text-sm font-medium text-gray-900 dark:text-white">
                  {{ member.username }}
                </div>
                <div class="text-xs text-gray-400 ">
                  {{ roleLabel(member.role) }}
                </div>
              </div>
            </div>
            <button
              v-if="isOwner && member.user_id !== authStore.user?.id"
              @click="removeMember(member.user_id)"
              class="text-xs px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30"
            >
              移除
            </button>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="space-y-3">
        <button
          @click="leaveGroup"
          class="w-full py-3 rounded-2xl bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-medium text-sm hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
        >
          退出群聊
        </button>
      </div>
    </div>

    <!-- Edit name modal -->
    <div
      v-if="showEditName"
      class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      @click.self="showEditName = false"
    >
      <div class="bg-[#F5F7FA] rounded-2xl p-6 w-full max-w-sm">
        <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4">修改群名称</h3>
        <input
          v-model="editNameValue"
          class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <div class="flex gap-3 mt-4">
          <button
            @click="showEditName = false"
            class="flex-1 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm"
          >
            取消
          </button>
          <button
            @click="updateName"
            class="flex-1 py-2 rounded-lg bg-primary-500 text-white text-sm"
          >
            保存
          </button>
        </div>
      </div>
    </div>

    <!-- Edit announcement modal -->
    <div
      v-if="showEditAnnouncement"
      class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      @click.self="showEditAnnouncement = false"
    >
      <div class="bg-[#F5F7FA] rounded-2xl p-6 w-full max-w-sm">
        <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4">
          修改群公告
        </h3>
        <textarea
          v-model="editAnnouncementValue"
          rows="4"
          class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
        />
        <div class="flex gap-3 mt-4">
          <button
            @click="showEditAnnouncement = false"
            class="flex-1 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm"
          >
            取消
          </button>
          <button
            @click="updateAnnouncement"
            class="flex-1 py-2 rounded-lg bg-primary-500 text-white text-sm"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
