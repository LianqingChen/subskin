<script setup lang="ts">
import { isAxiosError } from 'axios'
import { type CredentialInfo } from '@/api/auth'
import { communityApi } from '@/api/community'
import { authApi } from '@/api/auth'
import { patientProfileApi, type PatientProfile, type ModuleDefaults } from '@/api/patient-profile'
import { vasiApi, type VasiHistoryItem } from '@/api/vasi'
import { useToast } from '@/composables/useToast'
import { useDrafts } from '@/composables/useDrafts'
import { usePWA } from '@/composables/usePWA'
import { useAuthStore } from '@/stores/auth'
import { usePrivacyStore } from '@/stores/privacy'
import { toProtectedFileUrl } from '@/utils/file-url'
import { computed, reactive, ref, watch } from 'vue'
import PrivacyModal from '@/components/profile/PrivacyModal.vue'
import PhotoModal from '@/components/profile/PhotoModal.vue'
import NotificationModal from '@/components/profile/NotificationModal.vue'
import InstallModal from '@/components/profile/InstallModal.vue'
import SecurityModal from '@/components/profile/SecurityModal.vue'
import PatientProfileSection from '@/components/profile/PatientProfileSection.vue'

const PATIENT_RELATION_OPTIONS = [
  { value: '本人', label: '我是白友' },
  { value: '父母', label: '白友父母' },
  { value: '伴侣', label: '白友伴侣' },
  { value: '朋友', label: '白友朋友' },
  { value: '医护人员', label: '医护人员' },
  { value: '其他', label: '其他' },
] as const

const authStore = useAuthStore()
const privacyStore = usePrivacyStore()
const toast = useToast()
const { draftCount: profileDraftCount, loadDraftsWithSync: loadProfileDrafts } = useDrafts()
const { isInstalled, hasDeferredPrompt, installApp, forceResetAndReload } = usePWA()

const isLoggedIn = computed(() => authStore.isLoggedIn)
const userName = computed(() => authStore.user?.username ?? '未登录')
const userUid = computed(() => authStore.user?.uid ?? '')
const userUidShort = computed(() => {
  const uid = userUid.value
  if (!uid) return ''
  if (uid.length <= 8) return uid
  return uid.slice(0, 4) + '…' + uid.slice(-4)
})
const showFullUid = ref(false)
const userAvatar = computed(() => toProtectedFileUrl(authStore.user?.avatar_url ?? ''))
const avatarLoadError = ref(false)

watch(userAvatar, () => {
  avatarLoadError.value = false
})

function onAvatarError() {
  avatarLoadError.value = true
}

const showAvatarImage = computed(() => userAvatar.value && !avatarLoadError.value)
const userInitial = computed(() => {
  const source = (showProfileModal.value ? profileForm.username : userName.value).trim()
  return source.charAt(0).toUpperCase() || 'U'
})

const showProfileModal = ref(false)
const showPrivacyModal = ref(false)
const showPhotoModal = ref(false)
const showNotificationModal = ref(false)
const showInstallModal = ref(false)
const showSecurityModal = ref(false)
const isSavingProfile = ref(false)
const isUploadingAvatar = ref(false)
const isLoadingTracking = ref(false)
const isLoadingCredentials = ref(false)
const avatarInput = ref<HTMLInputElement | null>(null)
const securityDialogMode = ref<'bind-phone' | 'bind-email' | 'set-password' | 'reset-password'>('bind-phone')

const profiles = ref<PatientProfile[]>([])
const credentials = ref<CredentialInfo[]>([])
const moduleDefaults = reactive<ModuleDefaults>({ tracker_profile_id: null, report_profile_id: null, diary_profile_id: null })

const profileForm = reactive({
  username: '',
  patientRelation: '',
})

const nicknameCheckStatus = ref<'idle' | 'checking' | 'available' | 'duplicate'>('idle')
const nicknameCheckReason = ref('')
let nicknameCheckTimer: ReturnType<typeof setTimeout> | null = null

async function checkNicknameAvailability() {
  const nickname = profileForm.username.trim()
  const currentUsername = authStore.user?.username ?? ''
  if (!nickname || nickname.length < 2) {
    nicknameCheckStatus.value = 'idle'
    nicknameCheckReason.value = ''
    return
  }
  if (nickname === currentUsername) {
    nicknameCheckStatus.value = 'available'
    nicknameCheckReason.value = ''
    return
  }
  nicknameCheckStatus.value = 'checking'
  try {
    const res = await authApi.checkNickname(nickname)
    nicknameCheckStatus.value = res.available ? 'available' : 'duplicate'
    nicknameCheckReason.value = res.reason || ''
  } catch {
    nicknameCheckStatus.value = 'idle'
  }
}

function debouncedNicknameCheck() {
  if (nicknameCheckTimer) clearTimeout(nicknameCheckTimer)
  nicknameCheckStatus.value = 'idle'
  nicknameCheckTimer = setTimeout(checkNicknameAvailability, 500)
}

const trackingSummary = reactive({
  assessmentCount: '-',
  improvementRate: '-',
  trackingDays: '-',
  vasiScore: '-',
})

const communityStats = reactive({ postCount: 0, bookmarkCount: 0, commentCount: 0 })

const menuItems = computed(() => [
  { label: '我的发布', icon: 'ri-file-edit-line', count: communityStats.postCount, route: authStore.user?.id ? `/user/${authStore.user.id}` : '/community' },
  { label: '我的收藏', icon: 'ri-star-line', count: communityStats.bookmarkCount, route: '/community' },
  { label: '我的评论', icon: 'ri-chat-3-line', count: communityStats.commentCount, route: '/community' },
])

const allSettingsItems = [
  { label: '添加桌面', icon: 'ri-smartphone-line', action: 'install', requireNotInstalled: true },
  { label: '隐私设置', icon: 'ri-lock-line', action: 'privacy', requireNotInstalled: false },
  { label: '照片权限', icon: 'ri-camera-line', action: 'photo', requireNotInstalled: false },
  { label: '通知设置', icon: 'ri-notification-3-line', action: 'notification', requireNotInstalled: false },
] as const

const settingsItems = computed(() =>
  allSettingsItems.filter(item => !item.requireNotInstalled || !isInstalled.value)
)

const joinDate = computed(() => {
  if (!authStore.user?.created_at) return ''
  return new Date(authStore.user.created_at).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
  })
})

const displayPhone = computed(() => privacyStore.maskPhone(authStore.user?.phone))
const displayEmail = computed(() => privacyStore.maskEmail(authStore.user?.email))
const patientRelationText = computed(() => authStore.user?.patient_relation || '未设置')
const phoneCredentials = computed(() => credentials.value.filter((item) => item.cred_type === 'phone'))
const emailCredentials = computed(() => credentials.value.filter((item) => item.cred_type === 'email'))
const passwordCredential = computed(() => credentials.value.find((item) => item.cred_type === 'password') ?? null)
const hasPhoneCredential = computed(() => phoneCredentials.value.length > 0)
const hasEmailCredential = computed(() => emailCredentials.value.length > 0)
const hasPasswordCredential = computed(() => Boolean(passwordCredential.value))
const bindableCredentialCount = computed(
  () => credentials.value.filter((item) => item.cred_type === 'phone' || item.cred_type === 'email').length,
)
const privacyModeEnabled = computed({
  get: () => !privacyStore.privacyMode,
  set: async (enabled: boolean) => {
    if (enabled !== !privacyStore.privacyMode) {
      await privacyStore.togglePrivacyMode()
    }
  },
})
const displayedVasiScore = computed(() => {
  if (trackingSummary.vasiScore === '-') return '-'
  return privacyModeEnabled.value ? '••••' : trackingSummary.vasiScore
})

watch(
  () => authStore.user,
  () => {
    if (!showProfileModal.value) {
      syncProfileForm()
    }
  },
  { immediate: true },
)

watch(
  () => authStore.user?.id,
  async (userId) => {
    if (!userId) {
      resetTrackingSummary()
      resetCommunityStats()
      profiles.value = []
      credentials.value = []
      return
    }
    await Promise.all([fetchTrackingSummary(), fetchCommunityStats(), loadProfiles(), loadCredentials()])
    loadProfileDrafts()
  },
  { immediate: true },
)

function getErrorDetail(error: unknown, fallback = '操作失败，请稍后重试') {
  if (isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail || fallback
  }
  return fallback
}

function openSecurityModal(mode: 'bind-phone' | 'bind-email' | 'set-password' | 'reset-password') {
  securityDialogMode.value = mode
  showSecurityModal.value = true
}

async function onSecurityUpdated() {
  await Promise.all([loadCredentials(), authStore.fetchUser()])
}

function resetTrackingSummary() {
  trackingSummary.assessmentCount = '-'
  trackingSummary.improvementRate = '-'
  trackingSummary.trackingDays = '-'
  trackingSummary.vasiScore = '-'
}

function resetCommunityStats() {
  communityStats.postCount = 0
  communityStats.bookmarkCount = 0
  communityStats.commentCount = 0
}

function formatNumber(value: number, digits = 0) {
  return Number.isInteger(value) || digits === 0
    ? String(Math.round(value))
    : value.toFixed(digits)
}

function formatPercent(value: number) {
  const rounded = Math.abs(value) >= 10 ? value.toFixed(0) : value.toFixed(1)
  const normalized = rounded.replace(/\.0$/, '')
  return `${value > 0 ? '+' : ''}${normalized}%`
}

function calculateTrackingDays(items: VasiHistoryItem[]) {
  if (!items.length) return '-'
  const timestamps = items
    .map((item) => new Date(item.assessment_date).getTime())
    .filter((value) => Number.isFinite(value))

  if (!timestamps.length) return '-'

  const min = Math.min(...timestamps)
  const max = Math.max(...timestamps)
  const days = Math.max(1, Math.floor((max - min) / (1000 * 60 * 60 * 24)) + 1)
  return `${days}`
}

function calculateImprovementRate(items: VasiHistoryItem[]) {
  if (items.length < 2) return '-'

  const sorted = [...items].sort(
    (a, b) => new Date(a.assessment_date).getTime() - new Date(b.assessment_date).getTime(),
  )
  const firstScore = sorted[0]?.final_vasi_score ?? sorted[0]?.vasi_score ?? null
  const lastScore = sorted[sorted.length - 1]?.final_vasi_score ?? sorted[sorted.length - 1]?.vasi_score ?? null

  if (!firstScore || lastScore === null) return '-'

  const improvement = ((firstScore - lastScore) / firstScore) * 100
  return Number.isFinite(improvement) ? formatPercent(improvement) : '-'
}

async function fetchTrackingSummary() {
  if (!isLoggedIn.value) {
    resetTrackingSummary()
    return
  }

  isLoadingTracking.value = true
  try {
    const history = await vasiApi.getHistory(50, 0)
    trackingSummary.assessmentCount = history.total ? String(history.total) : '-'
    trackingSummary.trackingDays = calculateTrackingDays(history.items)
    trackingSummary.improvementRate = calculateImprovementRate(history.items)
    trackingSummary.vasiScore = history.items.length
      ? formatNumber(history.items[0].final_vasi_score ?? history.items[0].vasi_score, 1)
      : '-'
  } catch (error) {
    console.error('Failed to fetch VASI history:', error)
    resetTrackingSummary()
  } finally {
    isLoadingTracking.value = false
  }
}

async function fetchCommunityStats() {
  if (!isLoggedIn.value) {
    resetCommunityStats()
    return
  }

  try {
    const data = await communityApi.getUserStats()
    communityStats.postCount = data.post_count
    communityStats.bookmarkCount = data.bookmark_count
    communityStats.commentCount = data.comment_count
  } catch {
    resetCommunityStats()
  }
}

async function loadProfiles() {
  if (!isLoggedIn.value) return
  try {
    const [profilesData, defaultsData] = await Promise.all([
      patientProfileApi.list(),
      patientProfileApi.getModuleDefaults()
    ])
    profiles.value = profilesData
    Object.assign(moduleDefaults, defaultsData)
  } catch (error) {
    console.error('Failed to load patient profiles:', error)
  }
}

async function loadCredentials() {
  if (!isLoggedIn.value) {
    credentials.value = []
    return
  }

  isLoadingCredentials.value = true
  try {
    credentials.value = await authStore.getCredentials()
  } catch (error) {
    credentials.value = []
    toast.error(getErrorDetail(error, '账号凭证加载失败，请稍后重试'))
  } finally {
    isLoadingCredentials.value = false
  }
}

function getCredentialIcon(credential: CredentialInfo) {
  if (credential.cred_type === 'phone') return 'ri-smartphone-line'
  if (credential.cred_type === 'email') return 'ri-mail-line'
  if (credential.cred_type === 'password') return 'ri-key-2-line'
  return 'ri-shield-keyhole-line'
}

function getCredentialLabel(credential: CredentialInfo) {
  if (credential.cred_type === 'phone') return '手机'
  if (credential.cred_type === 'email') return '邮箱'
  if (credential.cred_type === 'password') return '密码'
  return credential.cred_type
}

const CRED_TYPE_ORDER: Record<string, number> = { phone: 0, email: 1, password: 2 }
const sortedCredentials = computed(() =>
  [...credentials.value].sort((a, b) =>
    (CRED_TYPE_ORDER[a.cred_type] ?? 99) - (CRED_TYPE_ORDER[b.cred_type] ?? 99),
  ),
)

function getCredentialDisplay(credential: CredentialInfo) {
  if (credential.cred_type === 'phone') return maskPhone(credential.cred_id)
  if (credential.cred_type === 'email') return maskEmail(credential.cred_id)
  if (credential.cred_type === 'password') return credential.verified ? '已设置' : '未设置'
  return credential.cred_id
}

function canUnbindCredential(credential: CredentialInfo) {
  return (
    (credential.cred_type === 'phone' || credential.cred_type === 'email') &&
    bindableCredentialCount.value > 1
  )
}

async function unbindCredential(credential: CredentialInfo) {
  if (!canUnbindCredential(credential)) return
  const confirmText = `确定解绑${getCredentialLabel(credential)} ${getCredentialDisplay(credential)} 吗？`
  if (!confirm(confirmText)) return

  try {
    await authStore.unbindCredential(credential.id)
    await Promise.all([loadCredentials(), authStore.fetchUser()])
    toast.success(`${getCredentialLabel(credential)}已解绑`)
  } catch (error) {
    toast.error(getErrorDetail(error, '解绑失败，请稍后重试'))
  }
}

async function saveModuleDefaults() {
  try {
    await patientProfileApi.setModuleDefaults(moduleDefaults)
    toast.success('默认档案已更新')
  } catch (error: any) {
    toast.error(error.response?.data?.detail || '更新默认档案失败')
  }
}

function openProfileModal() {
  syncProfileForm()
  showProfileModal.value = true
}

function closeProfileModal() {
  if (isSavingProfile.value || isUploadingAvatar.value) return
  syncProfileForm()
  showProfileModal.value = false
}

function openSecurityFromProfileModal() {
  closeProfileModal()
  if (!hasPhoneCredential.value) {
    openSecurityModal('bind-phone')
    return
  }
  if (!hasEmailCredential.value) {
    openSecurityModal('bind-email')
    return
  }
  openSecurityModal('set-password')
}

function handleSettingsItemClick(item: { action: string }) {
  if (item.action === 'install') {
    if (isInstalled.value) return
    showInstallModal.value = true
    return
  }

  if (item.action === 'privacy') {
    showPrivacyModal.value = true
    return
  }

  if (item.action === 'photo') {
    showPhotoModal.value = true
    return
  }

  if (item.action === 'notification') {
    showNotificationModal.value = true
    return
  }
}

function maskPhone(phone: string | null | undefined) {
  if (!phone) return ''
  return phone.replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2')
}

function maskEmail(email: string | null | undefined) {
  if (!email) return ''
  const atIndex = email.indexOf('@')
  if (atIndex < 0) return email
  const local = email.slice(0, atIndex)
  const domain = email.slice(atIndex + 1)
  if (local.length <= 2) return `***@${domain}`
  return `${local.slice(0, 2)}***@${domain}`
}

function syncProfileForm() {
  profileForm.username = authStore.user?.username ?? ''
  profileForm.patientRelation = authStore.user?.patient_relation ?? ''
}

async function saveProfile() {
  const username = profileForm.username.trim()
  const patientRelation = profileForm.patientRelation.trim()

  if (username.length < 2) {
    toast.warning('昵称至少2个字符')
    return
  }

  if (nicknameCheckStatus.value === 'duplicate') {
    toast.warning(nicknameCheckReason.value || '该昵称已被使用')
    return
  }

  isSavingProfile.value = true
  try {
    await authStore.updateProfile({
      username,
      patient_relation: patientRelation || null,
    })
    showProfileModal.value = false
    toast.success('个人信息已保存')
  } catch (error: any) {
    toast.error(error.response?.data?.detail || '保存失败，请稍后重试')
  } finally {
    isSavingProfile.value = false
  }
}

function triggerAvatarUpload() {
  if (!showProfileModal.value || isUploadingAvatar.value) return
  avatarInput.value?.click()
}

async function handleAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  if (!file.type.startsWith('image/')) {
    toast.error('请上传图片文件')
    input.value = ''
    return
  }

  if (file.size > 5 * 1024 * 1024) {
    toast.error('图片大小不能超过5MB')
    input.value = ''
    return
  }

  isUploadingAvatar.value = true
  try {
    await authStore.uploadAvatar(file)
    toast.success('头像已更新')
  } catch (error: any) {
    toast.error(error.response?.data?.detail || '头像上传失败，请稍后重试')
  } finally {
    isUploadingAvatar.value = false
    input.value = ''
  }
}
</script>

<template>
  <div class="max-w-6xl mx-auto w-full px-4 py-6 space-y-6">
    <template v-if="isLoggedIn">
    <div class="card p-6">
      <div class="flex items-center justify-between gap-3 mb-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full overflow-hidden bg-primary-100 dark:bg-primary-900 shrink-0 relative cursor-pointer" @click="openProfileModal">
            <img
              v-if="showAvatarImage"
              :src="userAvatar"
              :alt="`${userName}头像`"
              class="absolute inset-0 w-full h-full object-cover"
              @error="onAvatarError"
            />
            <span v-else class="absolute inset-0 flex items-center justify-center text-primary-700 dark:text-primary-300 text-lg font-bold">{{ userInitial }}</span>
          </div>
          <div>
            <h3 class="font-medium text-gray-900">{{ authStore.user?.username || '用户昵称' }}<i v-if="authStore.user?.is_verified" class="ri-shield-check-line text-primary-500 ml-1" title="实名认证"></i><svg v-if="authStore.user?.is_doctor && !authStore.user?.is_verified" class="w-3.5 h-3.5 text-primary-500 inline ml-1" viewBox="0 0 20 20" fill="currentColor" title="认证医生"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg></h3>
            <p class="text-xs text-gray-400 ">管理头像、昵称和联系方式</p>
          </div>
        </div>
        <button type="button" class="btn-ghost text-sm" @click="openProfileModal">
          编辑
        </button>
      </div>

      <div class="space-y-1.5">
        <p
          v-if="userUid"
          class="text-xs text-gray-400  font-mono flex flex-wrap items-center gap-x-2 gap-y-1"
        >
          <span class="inline-flex items-center gap-1">
            UID: {{ showFullUid ? userUid : userUidShort }}
            <button
              v-if="userUid.length > 8"
              type="button"
              class="inline-flex items-center justify-center w-4 h-4 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              :title="showFullUid ? '收起' : '展开完整UID'"
              @click="showFullUid = !showFullUid"
            >
              <svg v-if="!showFullUid" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3 h-3">
                <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
                <path fill-rule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3 h-3">
                <path fill-rule="evenodd" d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.745-1.745a10.029 10.029 0 003.3-4.38 1.651 1.651 0 000-1.185A10.004 10.004 0 009.999 3a9.956 9.956 0 00-4.744 1.194L3.28 2.22zM7.752 6.69l1.092 1.092a2.5 2.5 0 013.374 3.373l1.092 1.092a4 4 0 00-5.558-5.558z" clip-rule="evenodd" />
                <path d="M10.748 13.93l2.523 2.523A9.987 9.987 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41a1.651 1.651 0 010-1.186 10.007 10.007 0 012.89-4.036l2.167 2.167a4 4 0 005.027 5.395z" />
              </svg>
            </button>
          </span>
        </p>

        <div class="space-y-1 text-sm text-gray-500 ">
          <p class="flex items-center gap-1">
            <span><i class="ri-team-line"></i> 与白友关系：{{ patientRelationText }}</span>
          </p>
          <p v-if="joinDate" class="text-xs text-gray-400 ">
            📅 加入SubSkin: {{ joinDate }}
          </p>
         </div>
        </div>
     </div>
    </template>

    <template v-else>
    <div class="card p-8 text-center">
      <div class="text-5xl mb-4"><i class="ri-user-line text-4xl"></i></div>
      <h2 class="text-xl font-semibold text-gray-900 mb-2">登录后查看个人中心</h2>
      <p class="text-gray-500  text-sm mb-4">登录后可以查看追踪数据和管理社区内容</p>
      <button type="button"
        class="inline-flex items-center gap-1.5 px-6 py-2.5 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors min-h-[44px]"
        @click="authStore.showLoginModal = true"
      >
        <i class="ri-login-box-line"></i>
        去登录
      </button>
    </div>

    <!-- Feature preview cards -->
    <div class="grid grid-cols-2 gap-3 mt-4">
      <div class="card p-4 opacity-50 blur-sm select-none pointer-events-none">
        <div class="flex items-center gap-2 mb-2">
          <div class="w-8 h-8 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
            <i class="ri-bar-chart-2-line text-primary-600 dark:text-primary-400 text-lg"></i>
          </div>
          <span class="text-sm font-medium text-gray-700">测评历史</span>
        </div>
        <p class="text-xs text-gray-400">查看你的 VASI 评分变化趋势</p>
      </div>
      <div class="card p-4 opacity-50 blur-sm select-none pointer-events-none">
        <div class="flex items-center gap-2 mb-2">
          <div class="w-8 h-8 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
            <i class="ri-file-text-line text-primary-600 dark:text-primary-400 text-lg"></i>
          </div>
          <span class="text-sm font-medium text-gray-700">体检报告</span>
        </div>
        <p class="text-xs text-gray-400">AI 解读的体检指标汇总</p>
      </div>
      <div class="card p-4 opacity-50 blur-sm select-none pointer-events-none">
        <div class="flex items-center gap-2 mb-2">
          <div class="w-8 h-8 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
            <i class="ri-chat-3-line text-primary-600 dark:text-primary-400 text-lg"></i>
          </div>
          <span class="text-sm font-medium text-gray-700">社区互动</span>
        </div>
        <p class="text-xs text-gray-400">你的发布、收藏和评论</p>
      </div>
      <div class="card p-4 opacity-50 blur-sm select-none pointer-events-none">
        <div class="flex items-center gap-2 mb-2">
          <div class="w-8 h-8 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
            <i class="ri-settings-3-line text-primary-600 dark:text-primary-400 text-lg"></i>
          </div>
          <span class="text-sm font-medium text-gray-700">账号设置</span>
        </div>
        <p class="text-xs text-gray-400">通知偏好、隐私设置</p>
      </div>
    </div>
    </template>

    <div v-if="isLoggedIn" class="space-y-3">
      <PatientProfileSection
        :profiles="profiles"
        :module-defaults="moduleDefaults"
        @refresh="loadProfiles"
        @save-defaults="saveModuleDefaults"
      />

      <div class="card p-4">
        <div class="flex items-center justify-between gap-3 mb-3">
          <h3 class="font-medium text-gray-900"><i class="ri-bar-chart-2-line"></i> 追踪数据</h3>
          <span v-if="isLoadingTracking" class="text-xs text-gray-400 ">加载中...</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <div class="text-2xl font-bold text-gray-700">{{ trackingSummary.assessmentCount }}</div>
            <div class="text-xs text-gray-500 ">评估次数</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-gray-700">{{ trackingSummary.improvementRate }}</div>
            <div class="text-xs text-gray-500 ">改善率</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-gray-700">{{ trackingSummary.trackingDays }}</div>
            <div class="text-xs text-gray-500 ">追踪天数</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-gray-700">{{ displayedVasiScore }}</div>
            <div class="text-xs text-gray-500 ">VASI评分</div>
          </div>
        </div>
        <router-link :to="{ name: 'assessment' }" class="block text-center text-sm text-primary-600 hover:underline mt-3">
          前往测评 →
        </router-link>
      </div>

      <div class="card p-4">
        <div class="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 class="font-medium text-gray-900"><i class="ri-shield-keyhole-line"></i> 账号与安全</h3>
            <p class="mt-1 text-xs text-gray-500 ">管理登录方式、绑定信息与密码安全</p>
          </div>
          <span v-if="isLoadingCredentials" class="text-xs text-gray-400 ">加载中...</span>
        </div>

        <div v-if="credentials.length === 0 && !isLoadingCredentials" class="rounded-lg bg-gray-50 px-4 py-5 text-center text-sm text-gray-400">
          暂无可展示的账号凭证
        </div>

        <div v-else class="space-y-2">
          <div
            v-for="credential in sortedCredentials"
            :key="credential.id"
            class="flex items-center justify-between gap-3 rounded-lg bg-gray-50 px-3 py-3"
          >
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 text-sm font-medium text-gray-900">
                <span><i :class="getCredentialIcon(credential)"></i> {{ getCredentialLabel(credential) }}</span>
                <span
                  class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px]"
                  :class="credential.verified
                    ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-200'
                    : 'bg-gray-100 text-gray-500  '"
                >
                  {{ credential.verified ? '已验证' : '未验证' }}
                </span>
              </div>
              <p class="mt-1 text-sm text-gray-600">{{ getCredentialDisplay(credential) }}</p>
              <p v-if="credential.last_used_at" class="mt-1 text-xs text-gray-400 ">
                最近使用：{{ new Date(credential.last_used_at).toLocaleString('zh-CN') }}
              </p>
            </div>

            <button
              v-if="credential.cred_type !== 'password'"
              type="button"
              class="inline-flex min-h-[44px] items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors"
              :class="canUnbindCredential(credential)
                ? 'text-red-600 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-900/20'
                : 'cursor-not-allowed text-gray-300 '"
              :disabled="!canUnbindCredential(credential)"
              @click="unbindCredential(credential)"
            >
              解绑
            </button>
          </div>
        </div>

        <p v-if="bindableCredentialCount <= 1" class="mt-3 text-xs text-gray-400 ">
          至少保留一种手机号或邮箱登录方式，最后一个绑定项不可解绑。
        </p>

        <div class="mt-4 flex flex-wrap gap-2">
          <button
            v-if="!hasPhoneCredential"
            type="button"
            class="btn-ghost px-3 py-1.5 text-sm"
            @click="openSecurityModal('bind-phone')"
          >
            绑定手机号
          </button>
          <button
            v-if="!hasEmailCredential"
            type="button"
            class="btn-ghost px-3 py-1.5 text-sm"
            @click="openSecurityModal('bind-email')"
          >
            绑定邮箱
          </button>
          <button
            type="button"
            class="btn-primary px-3 py-1.5 text-sm"
            @click="openSecurityModal(hasPasswordCredential ? 'reset-password' : 'set-password')"
          >
            {{ hasPasswordCredential ? '修改密码' : '设置密码' }}
          </button>
        </div>
      </div>

      <div class="card p-4">
        <h3 class="font-medium text-gray-900 mb-3">🧭 发现</h3>
        <div class="space-y-2">
          <router-link
            v-for="item in menuItems"
            :key="item.label"
            :to="item.route"
            class="flex justify-between items-center py-2.5 text-sm text-gray-600  hover:text-primary-600 no-underline"
          >
             <span><i :class="item.icon"></i> {{ item.label }}</span>
            <div class="flex items-center gap-2">
              <span class="text-gray-400 ">{{ item.count }}</span>
              <span class="text-gray-300 ">→</span>
            </div>
          </router-link>
          <router-link
            to="/community/drafts"
            class="flex justify-between items-center py-2.5 text-sm text-gray-600  hover:text-primary-600 no-underline"
          >
            <span><i class="ri-file-edit-line"></i> 我的草稿</span>
            <div class="flex items-center gap-2">
              <span class="text-gray-400 ">{{ profileDraftCount }}</span>
              <span class="text-gray-300 ">→</span>
            </div>
          </router-link>
        </div>
      </div>

      <div class="card p-4">
        <h3 class="font-medium text-gray-900 mb-3"><i class="ri-settings-3-line"></i> 设置</h3>
        <div class="space-y-1">
          <button
            v-for="item in settingsItems"
            :key="item.label"
            type="button"
            class="flex w-full justify-between items-center py-2.5 text-sm text-gray-600  cursor-pointer hover:text-primary-600"
            @click="handleSettingsItemClick(item)"
          >
             <span><i :class="item.icon"></i> {{ item.label }}</span>
             <span class="text-gray-300 ">→</span>
           </button>
           <button class="w-full text-left py-2.5 text-sm text-red-600 hover:text-red-700" @click="authStore.logout()" data-track-id="profile_btn_logout">
             <i class="ri-logout-box-r-line"></i> 退出登录
           </button>
           </div>
         </div>

    <section class="text-center text-xs text-gray-400  py-4 border-t border-gray-100 dark:border-gray-700 space-y-1">
      <p><i class="ri-error-warning-line"></i> 本平台不构成医疗建议</p>
      <p>
        <router-link to="/terms" class="hover:underline">服务条款</router-link>
        ·
        <router-link to="/privacy" class="hover:underline">隐私政策</router-link>
      </p>
    </section>
  </div>

  <Teleport to="body">
    <div
   v-if="showProfileModal"
       class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center"
       @click.self="closeProfileModal"
     >
       <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4 max-h-[90dvh] overflow-y-auto">
         <!-- Header -->
         <div class="relative px-6 py-4 border-b border-gray-200 dark:border-gray-700">
           <h2 class="text-lg font-semibold text-gray-900">编辑资料</h2>
           <button class="absolute right-4 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 transition-colors" @click="closeProfileModal">&times;</button>
         </div>
         <div class="h-0.5 bg-gradient-to-r from-primary-400 to-primary-600 dark:from-primary-500 dark:to-primary-700"></div>

         <div class="p-6 space-y-6">
            <!-- Avatar -->
            <div class="flex justify-center">
              <div class="relative group">
                <button
                  type="button"
                  class="relative w-20 h-20 rounded-full overflow-hidden bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 text-2xl font-bold ring-3 ring-white dark:ring-gray-700 shadow-lg"
                  :disabled="isUploadingAvatar"
                  @click="triggerAvatarUpload"
                >
                  <img
                    v-if="showAvatarImage"
                    :src="userAvatar"
                    :alt="`${userName}头像`"
                    class="absolute inset-0 w-full h-full object-cover"
                    @error="onAvatarError"
                  />
                  <span v-else class="absolute inset-0 flex items-center justify-center">{{ userInitial }}</span>
                  <!-- Camera badge -->
                  <span
                    class="absolute bottom-0 right-0 w-7 h-7 rounded-full bg-primary-500 dark:bg-primary-600 flex items-center justify-center shadow-md ring-2 ring-white dark:ring-gray-700 transition-transform group-hover:scale-110"
                    :class="{ 'animate-pulse': isUploadingAvatar }"
                  >
                    <svg v-if="!isUploadingAvatar" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="white" class="w-4 h-4">
                      <path fill-rule="evenodd" d="M1 8a7 7 0 1114 0A7 7 0 011 8zm7-4a1 1 0 00-1 1v2H5a1 1 0 000 2h2v2a1 1 0 102 0V9h2a1 1 0 100-2H9V5a1 1 0 00-1-1z" clip-rule="evenodd" />
                    </svg>
                    <svg v-else class="w-3.5 h-3.5 text-white animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                  </span>
                </button>
                <input
                  ref="avatarInput"
                  type="file"
                  accept="image/*"
                  class="hidden"
                  @change="handleAvatarChange"
                />
              </div>
            </div>

           <!-- Basic Info Section -->
           <div class="space-y-4">
             <div class="flex items-center gap-2 text-xs font-medium text-gray-500  uppercase tracking-wider">
               <span class="w-4 h-px bg-gray-300"></span>
               基本信息
               <span class="flex-1 h-px bg-gray-300"></span>
             </div>

             <div>
               <label class="block text-sm font-medium text-gray-700 mb-1.5">昵称</label>
               <input
                 v-model="profileForm.username"
                 type="text"
                 class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow"
placeholder="请输入昵称"
                  @input="debouncedNicknameCheck"
                  @blur="checkNicknameAvailability"
                />
                <div v-if="nicknameCheckStatus === 'checking'" class="mt-1 text-xs text-gray-400">
                  <i class="ri-loader-4-line animate-spin mr-1"></i>检查中...
                </div>
                <div v-else-if="nicknameCheckStatus === 'duplicate'" class="mt-1 text-xs text-red-500">
                  <i class="ri-error-warning-line mr-1"></i>{{ nicknameCheckReason || '该昵称已被使用' }}
                </div>
                <div v-else-if="nicknameCheckStatus === 'available' && profileForm.username.trim() !== (authStore.user?.username ?? '')" class="mt-1 text-xs text-green-500">
                  <i class="ri-check-line mr-1"></i>昵称可用
                </div>
              </div>

             <div>
               <label class="block text-sm font-medium text-gray-700 mb-1.5">与白友关系</label>
               <select
                 v-model="profileForm.patientRelation"
                 class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white text-gray-900 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow"
               >
                 <option value="">请选择</option>
                 <option
                   v-for="option in PATIENT_RELATION_OPTIONS"
                   :key="option.value"
                   :value="option.value"
                 >
                   {{ option.label }}
                 </option>
               </select>
               <p class="text-xs text-gray-400  mt-1.5">帮助我们提供更有针对性的内容和建议</p>
             </div>
           </div>

           <!-- Contact Info -->
           <div class="rounded-xl bg-gray-50 p-4 border-l-2 border-primary-400 dark:border-primary-500">
             <div class="flex items-start justify-between gap-3">
               <div>
                 <h3 class="text-sm font-medium text-gray-900">联系方式</h3>
                 <p class="mt-1 text-xs text-gray-500 ">手机号、邮箱与密码请在"账号与安全"中管理</p>
               </div>
               <button
                 type="button"
                 class="btn-ghost text-sm shrink-0"
                 @click="openSecurityFromProfileModal"
               >
                 去管理
               </button>
             </div>

             <div class="mt-3 grid gap-2 text-sm text-gray-600">
               <p><i class="ri-smartphone-line"></i> {{ displayPhone || '未绑定手机号' }}</p>
               <p><i class="ri-mail-line mr-1"></i>{{ displayEmail || '未绑定邮箱' }}</p>
             </div>
           </div>

           <!-- Save Button -->
           <button
             type="button"
             class="btn-primary w-full py-3 text-base"
             :disabled="isSavingProfile || isUploadingAvatar"
             @click="saveProfile"
           >
             {{ isSavingProfile ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

<PrivacyModal v-model="showPrivacyModal" />
<PhotoModal v-model="showPhotoModal" />
<NotificationModal v-model="showNotificationModal" />
<InstallModal v-model="showInstallModal" :can-install="hasDeferredPrompt" @install="installApp().then(ok => { if (ok) showInstallModal = false })" @force-reset="forceResetAndReload" />

  <SecurityModal
    :visible="showSecurityModal"
    :mode="securityDialogMode"
    :credentials="credentials"
    @close="showSecurityModal = false"
    @updated="onSecurityUpdated"
  />
  </div>
</template>

<style scoped>
.theme-hue-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 28px;
  border-radius: 14px;
  outline: none;
  cursor: pointer;
  background: transparent;
}

</style>
