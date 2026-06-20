<template>
  <div class="user-management-page">
    <n-page-header title="用户管理" />
    <p class="page-desc">管理平台用户账号、状态与违规记录</p>

    <n-card style="margin-top: 24px" :bordered="false" class="filter-card">
      <n-space align="center" wrap>
        <n-input
          v-model:value="filter.search"
          placeholder="搜索用户名 / 邮箱 / 手机号"
          style="width: 280px; max-width: 100%"
          clearable
          @keydown.enter="handleSearch"
        />
        <n-select
          v-model:value="filter.status"
          :options="statusOptions"
          placeholder="状态筛选"
          style="width: 140px"
          clearable
        />
        <n-button type="primary" :loading="loading" @click="handleSearch">
          搜索
        </n-button>
        <n-button @click="handleReset">重置</n-button>
      </n-space>
    </n-card>

    <n-card style="margin-top: 16px" :bordered="false" class="table-card">
      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="users"
          :pagination="false"
          :bordered="false"
          :single-line="false"
          :row-key="(row: User) => row.id"
          scroll-x="700"
        />
      </n-spin>
      <n-space justify="end" style="margin-top: 16px">
        <n-pagination
          v-model:page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :item-count="pagination.itemCount"
          :page-sizes="[10, 20, 50]"
          show-size-picker
          show-quick-jumper
          @update:page="fetchUsers"
          @update:page-size="handlePageSizeChange"
        />
      </n-space>
    </n-card>

    <!-- User Detail Modal -->
    <n-modal
      v-model:show="detailModal.visible"
      preset="card"
      :title="`用户详情 — ${detailModal.user?.username || ''}`"
      style="width: 640px; max-width: 94vw;"
      :bordered="false"
      class="detail-modal"
    >
      <n-descriptions v-if="detailModal.user" :column="2" label-placement="left" bordered size="small">
        <n-descriptions-item label="ID">{{ detailModal.user.id }}</n-descriptions-item>
        <n-descriptions-item label="UID">{{ detailModal.user.uid }}</n-descriptions-item>
        <n-descriptions-item label="用户名">{{ detailModal.user.username }}</n-descriptions-item>
        <n-descriptions-item label="邮箱">{{ detailModal.user.email || '-' }}</n-descriptions-item>
        <n-descriptions-item label="手机号">{{ detailModal.user.phone || '-' }}</n-descriptions-item>
        <n-descriptions-item label="管理员">
          <n-tag :type="detailModal.user.is_admin ? 'warning' : 'default'" size="small">
            {{ detailModal.user.is_admin ? '是' : '否' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="测试账号">
          <n-tag :type="detailModal.user.is_test ? 'info' : 'default'" size="small">
            {{ detailModal.user.is_test ? '是' : '否' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="状态">
          <n-tag :type="getStatusType(detailModal.user.user_status)" size="small">
            {{ getStatusLabel(detailModal.user.user_status) }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="违规次数">{{ detailModal.user.violation_count || 0 }}</n-descriptions-item>
        <n-descriptions-item label="注册时间">{{ formatDate(detailModal.user.created_at) }}</n-descriptions-item>
        <n-descriptions-item v-if="detailModal.user.muted_until" label="禁言截止">
          {{ formatDate(detailModal.user.muted_until) }}
        </n-descriptions-item>
        <n-descriptions-item v-if="detailModal.user.banned_at" label="封号时间">
          {{ formatDate(detailModal.user.banned_at) }}
        </n-descriptions-item>
        <n-descriptions-item v-if="detailModal.user.ban_reason" label="封号原因" :span="2">
          {{ detailModal.user.ban_reason }}
        </n-descriptions-item>
      </n-descriptions>

      <n-space style="margin-top: 24px" justify="end">
        <n-button v-if="canMute(detailModal.user)" type="warning" @click="openMuteModal(detailModal.user!)">
          禁言
        </n-button>
        <n-button v-if="canUnmute(detailModal.user)" @click="handleUnmute(detailModal.user!)">
          解除禁言
        </n-button>
        <n-button v-if="canBan(detailModal.user)" type="error" @click="openBanModal(detailModal.user!)">
          封号
        </n-button>
        <n-button v-if="canUnban(detailModal.user)" @click="handleUnban(detailModal.user!)">
          解除封号
        </n-button>
      </n-space>
    </n-modal>

    <!-- Ban Modal -->
    <n-modal
      v-model:show="banModal.visible"
      preset="card"
      title="封号处理"
      style="width: 480px; max-width: 94vw;"
      :bordered="false"
    >
      <n-form label-placement="top">
        <n-form-item label="封号原因">
          <n-input
            v-model:value="banModal.reason"
            type="textarea"
            placeholder="请输入封号原因"
            :rows="3"
          />
        </n-form-item>
      </n-form>
      <n-space justify="end">
        <n-button @click="banModal.visible = false">取消</n-button>
        <n-button type="error" :loading="banModal.loading" @click="confirmBan">确认封号</n-button>
      </n-space>
    </n-modal>

    <!-- Mute Modal -->
    <n-modal
      v-model:show="muteModal.visible"
      preset="card"
      title="禁言处理"
      style="width: 480px; max-width: 94vw;"
      :bordered="false"
    >
      <n-form label-placement="top">
        <n-form-item label="禁言时长">
          <n-select
            v-model:value="muteModal.hours"
            :options="muteHourOptions"
            placeholder="请选择禁言时长"
          />
        </n-form-item>
        <n-form-item label="禁言原因（可选）">
          <n-input
            v-model:value="muteModal.reason"
            type="textarea"
            placeholder="请输入禁言原因"
            :rows="2"
          />
        </n-form-item>
      </n-form>
      <n-space justify="end">
        <n-button @click="muteModal.visible = false">取消</n-button>
        <n-button type="warning" :loading="muteModal.loading" @click="confirmMute">确认禁言</n-button>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { useMessage, NTag, NButton, NSpace } from 'naive-ui'
import request from '@/api/request'

const message = useMessage()

// Types
interface User {
  id: number
  uid: string
  username: string
  email?: string
  phone?: string
  avatar_url?: string
  is_admin: boolean
  is_active: boolean
  is_test: boolean
  user_status: string
  muted_until?: string
  banned_at?: string
  ban_reason?: string
  violation_count?: number
  created_at?: string
}

interface UsersResponse {
  items: User[]
  total: number
  page: number
  page_size: number
}

// Filter state
const filter = ref({
  search: '',
  status: null as string | null,
})

const statusOptions = [
  { label: '全部', value: '' },
  { label: '正常', value: 'active' },
  { label: '禁言', value: 'muted' },
  { label: '封号', value: 'banned' },
]

// Pagination
const pagination = ref({
  page: 1,
  pageSize: 10,
  itemCount: 0,
})

// Data
const users = ref<User[]>([])
const loading = ref(false)

// Detail modal
const detailModal = ref({
  visible: false,
  user: null as User | null,
})

// Ban modal
const banModal = ref({
  visible: false,
  userId: 0,
  reason: '',
  loading: false,
})

// Mute modal
const muteModal = ref({
  visible: false,
  userId: 0,
  hours: 24,
  reason: '',
  loading: false,
})

const muteHourOptions = [
  { label: '1 小时', value: 1 },
  { label: '6 小时', value: 6 },
  { label: '12 小时', value: 12 },
  { label: '24 小时', value: 24 },
  { label: '3 天', value: 72 },
  { label: '7 天', value: 168 },
  { label: '30 天', value: 720 },
]

// Helpers
function getStatusType(status: string) {
  switch (status) {
    case 'active':
    case 'normal':
      return 'success'
    case 'muted':
      return 'warning'
    case 'banned':
      return 'error'
    default:
      return 'default'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'active':
    case 'normal':
      return '正常'
    case 'muted':
      return '禁言'
    case 'banned':
      return '封号'
    default:
      return status || '未知'
  }
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function canMute(user: User | null) {
  if (!user) return false
  return user.user_status !== 'muted' && user.user_status !== 'banned'
}

function canUnmute(user: User | null) {
  if (!user) return false
  return user.user_status === 'muted'
}

function canBan(user: User | null) {
  if (!user) return false
  return user.user_status !== 'banned'
}

function canUnban(user: User | null) {
  if (!user) return false
  return user.user_status === 'banned'
}

// Table columns
const columns = computed(() => [
  {
    title: 'ID',
    key: 'id',
    width: 80,
    ellipsis: { tooltip: true },
  },
  {
    title: '用户名',
    key: 'username',
    ellipsis: { tooltip: true },
  },
  {
    title: '邮箱',
    key: 'email',
    ellipsis: { tooltip: true },
    render(row: User) {
      return row.email || '-'
    },
  },
  {
    title: '手机号',
    key: 'phone',
    width: 140,
    render(row: User) {
      return row.phone || '-'
    },
  },
  {
    title: '状态',
    key: 'user_status',
    width: 100,
    render(row: User) {
      return h(NTag, { type: getStatusType(row.user_status) as any, size: 'small' }, {
        default: () => getStatusLabel(row.user_status),
      })
    },
  },
  {
    title: '注册时间',
    key: 'created_at',
    width: 170,
    render(row: User) {
      return formatDate(row.created_at)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 280,
    fixed: 'right',
    render(row: User) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => showDetail(row) }, { default: () => '查看详情' }),
          canMute(row)
            ? h(NButton, { size: 'small', type: 'warning', onClick: () => openMuteModal(row) }, { default: () => '禁言' })
            : null,
          canUnmute(row)
            ? h(NButton, { size: 'small', onClick: () => handleUnmute(row) }, { default: () => '解禁' })
            : null,
          canBan(row)
            ? h(NButton, { size: 'small', type: 'error', onClick: () => openBanModal(row) }, { default: () => '封号' })
            : null,
          canUnban(row)
            ? h(NButton, { size: 'small', onClick: () => handleUnban(row) }, { default: () => '解封' })
            : null,
        ].filter(Boolean),
      })
    },
  },
])

// API calls
async function fetchUsers() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    }
    if (filter.value.search) {
      params.search = filter.value.search
    }
    if (filter.value.status) {
      params.status = filter.value.status
    }
    const res = await request.get<UsersResponse>('/users', { params })
    const data = res.data
    users.value = data.items || []
    pagination.value.itemCount = data.total || 0
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取用户列表失败')
    users.value = []
    pagination.value.itemCount = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.value.page = 1
  fetchUsers()
}

function handleReset() {
  filter.value.search = ''
  filter.value.status = null
  pagination.value.page = 1
  fetchUsers()
}

function handlePageSizeChange(size: number) {
  pagination.value.pageSize = size
  pagination.value.page = 1
  fetchUsers()
}

function showDetail(user: User) {
  detailModal.value.user = user
  detailModal.value.visible = true
}

function openBanModal(user: User) {
  banModal.value.userId = user.id
  banModal.value.reason = ''
  banModal.value.visible = true
}

async function confirmBan() {
  if (!banModal.value.reason.trim()) {
    message.warning('请输入封号原因')
    return
  }
  banModal.value.loading = true
  try {
    await request.put(`/users/${banModal.value.userId}/status`, {
      action: 'ban',
      reason: banModal.value.reason,
    })
    message.success('封号成功')
    banModal.value.visible = false
    await fetchUsers()
    if (detailModal.value.user?.id === banModal.value.userId) {
      detailModal.value.visible = false
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '封号失败')
  } finally {
    banModal.value.loading = false
  }
}

function openMuteModal(user: User) {
  muteModal.value.userId = user.id
  muteModal.value.hours = 24
  muteModal.value.reason = ''
  muteModal.value.visible = true
}

async function confirmMute() {
  muteModal.value.loading = true
  try {
    await request.put(`/users/${muteModal.value.userId}/status`, {
      action: 'mute',
      hours: muteModal.value.hours,
      reason: muteModal.value.reason,
    })
    message.success('禁言成功')
    muteModal.value.visible = false
    await fetchUsers()
    if (detailModal.value.user?.id === muteModal.value.userId) {
      detailModal.value.visible = false
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '禁言失败')
  } finally {
    muteModal.value.loading = false
  }
}

async function handleUnmute(user: User) {
  try {
    await request.put(`/users/${user.id}/status`, {
      action: 'unmute',
    })
    message.success('解除禁言成功')
    await fetchUsers()
    if (detailModal.value.user?.id === user.id) {
      detailModal.value.visible = false
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '解除禁言失败')
  }
}

async function handleUnban(user: User) {
  try {
    await request.put(`/users/${user.id}/status`, {
      action: 'unban',
    })
    message.success('解除封号成功')
    await fetchUsers()
    if (detailModal.value.user?.id === user.id) {
      detailModal.value.visible = false
    }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '解除封号失败')
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.user-management-page {
  padding: 0;
}

.page-desc {
  color: #94a3b8;
  margin-top: 8px;
  font-size: 14px;
}

.filter-card {
  background-color: #1e293b;
}

.table-card {
  background-color: #1e293b;
}

:deep(.n-data-table .n-data-table-td) {
  background-color: #0f172a;
}

:deep(.n-data-table .n-data-table-th) {
  background-color: #1e293b;
}

:deep(.n-descriptions .n-descriptions-table-content) {
  background-color: #0f172a;
}

:deep(.n-descriptions .n-descriptions-table-header) {
  background-color: #1e293b;
}
</style>
