<script setup lang="ts">
/**
 * MedicationReminderPanel — 用药提醒面板（问答页快捷工具）
 *
 * 从个人中心迁移至问答对话框上方（正念呼吸之后）。
 * 重设计：统一字号/间距；同一天支持多个提醒时间（逐条增删）；
 * 支持 Web Push 通知授权（网页无法写入系统闹钟，浏览器推送是最接近的机制）。
 * 页面打开期间每分钟检查一次，到点即时 toast 提醒。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { medicationApi, type MedicationReminder } from '@/api/medication'
import { useToast } from '@/composables/useToast'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const emit = defineEmits<{ close: [] }>()

const toast = useToast()
const reminders = ref<MedicationReminder[]>([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const WEEKDAYS = [
  { value: 1, label: '一' },
  { value: 2, label: '二' },
  { value: 3, label: '三' },
  { value: 4, label: '四' },
  { value: 5, label: '五' },
  { value: 6, label: '六' },
  { value: 7, label: '日' },
]

interface ReminderForm {
  medication_name: string
  dosage: string
  frequency: 'daily' | 'weekly'
  reminder_times: string[]
  reminder_days: number[]
  notes: string
}

const form = ref<ReminderForm>({
  medication_name: '',
  dosage: '',
  frequency: 'daily',
  reminder_times: ['08:00'],
  reminder_days: [],
  notes: '',
})

const MAX_TIMES = 6

// ── 通知授权 ──
const pushState = ref<'unknown' | 'granted' | 'denied' | 'unsupported'>('unknown')
const subscribing = ref(false)

// 用户手机系统识别（用于推荐对应的 Chrome 下载链接）
const platform = computed<'android' | 'ios' | 'other'>(() => {
  if (typeof navigator === 'undefined') return 'other'
  const ua = navigator.userAgent
  if (/android/i.test(ua)) return 'android'
  if (/iphone|ipad|ipod/i.test(ua)) return 'ios'
  return 'other'
})

const CHROME_LINKS = [
  { id: 'android', label: 'Chrome 安卓版', icon: 'ri-android-line', url: 'https://play.google.com/store/apps/details?id=com.android.chrome' },
  { id: 'ios', label: 'Chrome iOS 版', icon: 'ri-apple-line', url: 'https://apps.apple.com/app/google-chrome/id535886823' },
]

function refreshPushState() {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    pushState.value = 'unsupported'
    return
  }
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    pushState.value = 'unsupported'
    return
  }
  pushState.value = Notification.permission === 'granted' ? 'granted' : Notification.permission === 'denied' ? 'denied' : 'unknown'
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i)
  return outputArray
}

async function enablePush() {
  if (subscribing.value) return
  subscribing.value = true
  try {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      pushState.value = 'denied'
      toast.show('未获得通知权限，可在浏览器设置中开启', 'warning')
      return
    }
    const data = await medicationApi.getVapidPublicKey()
    if (!data.public_key) {
      toast.show('推送服务暂不可用，请稍后再试', 'error')
      return
    }
    // 部分手机自带浏览器 SW 未激活时 ready 会一直挂起，加超时保护
    const registration = await Promise.race([
      navigator.serviceWorker.ready,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('sw-not-ready')), 8000),
      ),
    ])
    if (
      !('pushManager' in registration) ||
      typeof registration.pushManager?.subscribe !== 'function'
    ) {
      pushState.value = 'unsupported'
      toast.show('当前浏览器不支持推送订阅，建议安装谷歌 Chrome', 'error')
      return
    }
    let subscription = await registration.pushManager.getSubscription()
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(data.public_key),
      })
    }
    const key = subscription.getKey('p256dh')
    const auth = subscription.getKey('auth')
    if (!key || !auth) throw new Error('bad subscription')
    await medicationApi.subscribePush(
      subscription.endpoint,
      btoa(String.fromCharCode(...new Uint8Array(key))).replace(/\+/g, '-').replace(/\//g, '_'),
      btoa(String.fromCharCode(...new Uint8Array(auth))).replace(/\+/g, '-').replace(/\//g, '_'),
    )
    pushState.value = 'granted'
    toast.show('通知提醒已开启，到点将通过浏览器推送提醒', 'success')
  } catch (err: any) {
    console.error('[medication] enablePush failed:', err)
    if (err?.name === 'NotAllowedError' || err?.name === 'AbortError') {
      pushState.value = 'denied'
      toast.show('浏览器拒绝了推送订阅：iPhone 请先「添加到主屏幕」后再开启，或使用 Chrome', 'error', 6000)
    } else {
      pushState.value = 'unsupported'
      toast.show('开启失败：当前浏览器可能不支持推送，建议安装谷歌 Chrome', 'error', 6000)
    }
  } finally {
    subscribing.value = false
  }
}

async function disablePush() {
  subscribing.value = true
  try {
    const registration = await navigator.serviceWorker.ready
    const subscription = await registration.pushManager.getSubscription()
    if (subscription) {
      await medicationApi.unsubscribePush(subscription.endpoint)
      await subscription.unsubscribe()
    }
    pushState.value = 'unknown'
    toast.show('已关闭通知提醒', 'success')
  } catch {
    toast.show('操作失败，请重试', 'error')
  } finally {
    subscribing.value = false
  }
}

// ── 数据 ──
async function loadReminders() {
  loading.value = true
  try {
    reminders.value = await medicationApi.getReminders()
  } catch {
    // 未登录静默失败
  } finally {
    loading.value = false
  }
}

function openAddForm() {
  editingId.value = null
  form.value = { medication_name: '', dosage: '', frequency: 'daily', reminder_times: ['08:00'], reminder_days: [], notes: '' }
  showForm.value = true
}

function openEditForm(r: MedicationReminder) {
  editingId.value = r.id
  form.value = {
    medication_name: r.medication_name,
    dosage: r.dosage || '',
    frequency: r.frequency === 'weekly' || r.frequency === 'custom' ? 'weekly' : 'daily',
    reminder_times: (r.reminder_times && r.reminder_times.length ? r.reminder_times : ['08:00']).slice(0, MAX_TIMES),
    reminder_days: r.reminder_days || [],
    notes: r.notes || '',
  }
  showForm.value = true
}

function addTime() {
  if (form.value.reminder_times.length >= MAX_TIMES) return
  form.value.reminder_times.push('08:00')
}

function removeTime(i: number) {
  if (form.value.reminder_times.length <= 1) return
  form.value.reminder_times.splice(i, 1)
}

function toggleDay(d: number) {
  const days = new Set(form.value.reminder_days)
  if (days.has(d)) days.delete(d)
  else days.add(d)
  form.value.reminder_days = Array.from(days).sort((a, b) => a - b)
}

const canSave = computed(() => form.value.medication_name.trim().length > 0 && form.value.reminder_times.length > 0)

async function saveReminder() {
  if (!form.value.medication_name.trim()) {
    toast.show('请输入药品名称', 'warning')
    return
  }
  const times = [...new Set(form.value.reminder_times.map((t) => t.slice(0, 5)))].sort()
  if (!times.length) {
    toast.show('请至少设置一个提醒时间', 'warning')
    return
  }
  saving.value = true
  try {
    const payload = {
      medication_name: form.value.medication_name.trim(),
      dosage: form.value.dosage.trim() || undefined,
      frequency: form.value.frequency,
      reminder_times: times,
      reminder_days: form.value.frequency === 'weekly' ? form.value.reminder_days : undefined,
      notes: form.value.notes.trim() || undefined,
    }
    if (editingId.value) {
      await medicationApi.updateReminder(editingId.value, payload)
      toast.show('用药提醒已更新', 'success')
    } else {
      await medicationApi.createReminder(payload)
      toast.show('用药提醒已添加', 'success')
    }
    showForm.value = false
    await loadReminders()
  } catch {
    toast.show('保存失败，请重试', 'error')
  } finally {
    saving.value = false
  }
}

// ── 删除 / 启停 ──
const confirmDeleteVisible = ref(false)
const pendingDeleteId = ref<number | null>(null)

function askDelete(id: number) {
  pendingDeleteId.value = id
  confirmDeleteVisible.value = true
}

async function onConfirmDelete() {
  const id = pendingDeleteId.value
  confirmDeleteVisible.value = false
  pendingDeleteId.value = null
  if (id === null) return
  try {
    await medicationApi.deleteReminder(id)
    toast.show('已删除', 'success')
    await loadReminders()
  } catch {
    toast.show('删除失败', 'error')
  }
}

async function toggleActive(r: MedicationReminder) {
  try {
    await medicationApi.updateReminder(r.id, { is_active: !r.is_active })
    r.is_active = !r.is_active
  } catch {
    toast.show('操作失败', 'error')
  }
}

function freqLabel(r: MedicationReminder) {
  if (r.frequency === 'weekly' || r.frequency === 'custom') {
    if (!r.reminder_days?.length) return '每周'
    return '每周' + r.reminder_days.map((d) => WEEKDAYS[d - 1]?.label || d).join('、')
  }
  return '每天'
}

// ── 页面打开期间的到点即时提醒 ──
const firedSlots = new Set<string>()
let dueTimer: ReturnType<typeof setInterval> | null = null

function checkDue() {
  const now = new Date()
  const hhmm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  const dow = now.getDay() === 0 ? 7 : now.getDay()
  for (const r of reminders.value) {
    if (!r.is_active) continue
    if (r.frequency === 'weekly' || r.frequency === 'custom') {
      if (r.reminder_days?.length && !r.reminder_days.includes(dow)) continue
    }
    if (!r.reminder_times?.includes(hhmm)) continue
    const key = `${r.id}-${hhmm}`
    if (firedSlots.has(key)) continue
    firedSlots.add(key)
    const dosage = r.dosage ? ` · ${r.dosage}` : ''
    toast.show(`用药提醒：该吃「${r.medication_name}」了${dosage}`, 'success', 8000)
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate([200, 100, 200])
  }
}

onMounted(() => {
  loadReminders()
  refreshPushState()
  dueTimer = setInterval(checkDue, 30_000)
})

onUnmounted(() => {
  if (dueTimer) clearInterval(dueTimer)
})
</script>

<template>
  <div class="mrp">
    <!-- 头部 -->
    <div class="mrp__head">
      <h3 class="mrp__title"><i class="ri-capsule-line"></i> 用药提醒</h3>
      <button type="button" class="mrp__close" aria-label="关闭" @click="emit('close')">
        <i class="ri-close-line"></i>
      </button>
    </div>

    <!-- 通知状态卡片 -->
    <div class="mrp__push">
      <div class="mrp__push-text">
        <i class="ri-notification-3-line"></i>
        <span>
          {{
            pushState === 'granted'
              ? '通知提醒已开启：到点将通过浏览器推送提醒'
              : pushState === 'denied'
                ? '通知权限被拒绝，请在浏览器设置中允许通知'
                : pushState === 'unsupported'
                  ? '当前浏览器不支持通知推送（可尝试安装 PWA 或更换浏览器）'
                  : '开启后，到点将通过浏览器推送提醒（网页无法直接写入系统闹钟）'
          }}
        </span>
      </div>
      <button
        v-if="pushState !== 'unsupported'"
        type="button"
        class="mrp__push-btn"
        :class="{ 'mrp__push-btn--on': pushState === 'granted' }"
        :disabled="subscribing"
        @click="pushState === 'granted' ? disablePush() : enablePush()"
      >
        {{ subscribing ? '处理中…' : pushState === 'granted' ? '关闭通知' : '开启通知' }}
      </button>
    </div>

    <!-- 不支持通知的浏览器：推荐安装 Chrome -->
    <div v-if="pushState === 'unsupported'" class="mrp__chrome">
      <div class="mrp__chrome-head">
        <i class="ri-chrome-line"></i> 推荐使用谷歌 Chrome 浏览器接收用药提醒
      </div>
      <div class="mrp__chrome-links">
        <a
          v-for="l in CHROME_LINKS"
          :key="l.id"
          :href="l.url"
          target="_blank"
          rel="noopener"
          class="mrp__chrome-link"
          :class="{ 'mrp__chrome-link--me': platform === l.id }"
        >
          <i :class="l.icon"></i>
          <span>{{ l.label }}</span>
          <em v-if="platform === l.id" class="mrp__chrome-tag">适合您的手机</em>
        </a>
      </div>
      <p class="mrp__chrome-note">
        安装后重新打开 SubSkin 即可开启通知提醒（iOS 需将网站添加到主屏幕）
      </p>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="mrp__empty">加载中...</div>

    <div v-else-if="!reminders.length" class="mrp__empty">
      <i class="ri-capsule-line"></i>
      <p>还没有用药提醒</p>
      <p class="mrp__empty-sub">添加后，同一药品可设置每天多个提醒时间</p>
    </div>

    <div v-else class="mrp__list">
      <div
        v-for="r in reminders"
        :key="r.id"
        class="mrp__item"
        :class="{ 'mrp__item--off': !r.is_active }"
      >
        <div class="mrp__item-main">
          <p class="mrp__item-name">
            {{ r.medication_name }}
            <span v-if="r.dosage" class="mrp__item-dosage">· {{ r.dosage }}</span>
          </p>
          <p class="mrp__item-meta">
            {{ freqLabel(r) }}
            <span v-for="t in r.reminder_times" :key="t" class="mrp__time-pill">{{ t }}</span>
          </p>
        </div>
        <div class="mrp__item-actions">
          <button
            type="button"
            class="mrp__icon-btn"
            :title="r.is_active ? '暂停提醒' : '恢复提醒'"
            @click="toggleActive(r)"
          >
            <i :class="r.is_active ? 'ri-pause-mini-line' : 'ri-play-mini-line'"></i>
          </button>
          <button type="button" class="mrp__icon-btn" title="编辑" @click="openEditForm(r)">
            <i class="ri-edit-line"></i>
          </button>
          <button type="button" class="mrp__icon-btn mrp__icon-btn--danger" title="删除" @click="askDelete(r.id)">
            <i class="ri-delete-bin-line"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- 添加按钮 -->
    <button type="button" class="mrp__add" @click="openAddForm">
      <i class="ri-add-line"></i> 添加用药提醒
    </button>

    <ConfirmDialog
      :visible="confirmDeleteVisible"
      title="删除确认"
      message="确定删除这条用药提醒吗？"
      confirm-text="删除"
      @confirm="onConfirmDelete"
      @cancel="confirmDeleteVisible = false"
    />

    <!-- 表单弹层 -->
    <Teleport to="body">
      <div
        v-if="showForm"
        class="fixed inset-0 z-[115] flex items-end sm:items-center justify-center bg-black/50"
        @click.self="showForm = false"
      >
        <div class="w-full sm:max-w-md bg-white dark:bg-gray-800 rounded-t-2xl sm:rounded-2xl p-5 pb-6 safe-bottom max-h-[88dvh] overflow-y-auto">
          <h4 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
            {{ editingId ? '编辑用药提醒' : '添加用药提醒' }}
          </h4>

          <div class="space-y-4">
            <div>
              <label class="mrp__label" for="med-name">药品名称 <em class="text-rose-500 not-italic">*</em></label>
              <input
                id="med-name"
                v-model="form.medication_name"
                type="text"
                placeholder="如：他克莫司软膏"
                class="mrp__input"
              />
            </div>

            <div>
              <label class="mrp__label" for="med-dosage">剂量</label>
              <input id="med-dosage" v-model="form.dosage" type="text" placeholder="如：0.1% 每日两次" class="mrp__input" />
            </div>

            <div>
              <span class="mrp__label">提醒频率</span>
              <div class="mrp__seg">
                <button
                  type="button"
                  class="mrp__seg-btn"
                  :class="{ 'mrp__seg-btn--active': form.frequency === 'daily' }"
                  @click="form.frequency = 'daily'"
                >
                  每天
                </button>
                <button
                  type="button"
                  class="mrp__seg-btn"
                  :class="{ 'mrp__seg-btn--active': form.frequency === 'weekly' }"
                  @click="form.frequency = 'weekly'"
                >
                  每周
                </button>
              </div>
              <div v-if="form.frequency === 'weekly'" class="mrp__weekdays">
                <button
                  v-for="d in WEEKDAYS"
                  :key="d.value"
                  type="button"
                  class="mrp__day"
                  :class="{ 'mrp__day--active': form.reminder_days.includes(d.value) }"
                  @click="toggleDay(d.value)"
                >
                  {{ d.label }}
                </button>
                <span class="mrp__day-hint">{{ form.reminder_days.length ? `每周${form.reminder_days.map((d) => WEEKDAYS[d - 1]?.label).join('、')}` : '未选日期则默认每天' }}</span>
              </div>
            </div>

            <div>
              <span class="mrp__label">提醒时间（同一天可设多个）</span>
              <div class="space-y-2 mt-1">
                <div v-for="(_, i) in form.reminder_times" :key="i" class="mrp__time-row">
                  <input v-model="form.reminder_times[i]" type="time" class="mrp__input mrp__time-input" aria-label="提醒时间" />
                  <button
                    type="button"
                    class="mrp__time-del"
                    :disabled="form.reminder_times.length <= 1"
                    aria-label="删除该时间"
                    @click="removeTime(i)"
                  >
                    <i class="ri-close-line"></i>
                  </button>
                </div>
              </div>
              <button
                type="button"
                class="mrp__time-add"
                :disabled="form.reminder_times.length >= MAX_TIMES"
                @click="addTime"
              >
                <i class="ri-add-line"></i> 添加时间（最多 {{ MAX_TIMES }} 个）
              </button>
            </div>

            <div>
              <label class="mrp__label" for="med-notes">备注</label>
              <textarea id="med-notes" v-model="form.notes" rows="2" placeholder="可选" class="mrp__input"></textarea>
            </div>
          </div>

          <div class="flex gap-3 mt-5">
            <button type="button" class="btn-ghost flex-1 min-h-[44px]" @click="showForm = false">取消</button>
            <button type="button" class="btn-primary flex-1 min-h-[44px]" :disabled="!canSave || saving" @click="saveReminder">
              <i v-if="saving" class="ri-loader-4-line ri-spin mr-1"></i>
              {{ saving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.mrp {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mrp__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mrp__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.mrp__title i {
  color: var(--color-primary-500);
  font-size: 18px;
}

html.dark .mrp__title {
  color: #f1f5f9;
}

.mrp__close {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mrp__close:hover {
  background: #f1f5f9;
}

html.dark .mrp__close:hover {
  background: #334155;
}

/* 通知状态卡 */
.mrp__push {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f0fdfa;
  border: 1px solid #99f6e4;
}

html.dark .mrp__push {
  background: rgba(6, 78, 59, 0.25);
  border-color: rgba(16, 185, 129, 0.3);
}

.mrp__push-text {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #0f766e;
}

html.dark .mrp__push-text {
  color: #5eead4;
}

.mrp__push-text i {
  font-size: 15px;
  margin-top: 1px;
  flex-shrink: 0;
}

.mrp__push-btn {
  flex-shrink: 0;
  border: 1px solid var(--color-primary-300);
  background: white;
  color: var(--color-primary-700);
  font-size: 12px;
  font-weight: 600;
  padding: 7px 12px;
  min-height: 36px;
  border-radius: 10px;
  cursor: pointer;
}

.mrp__push-btn--on {
  border-color: #e2e8f0;
  color: #64748b;
  font-weight: 500;
}

html.dark .mrp__push-btn {
  background: #0f172a;
}

.mrp__push-btn:disabled {
  opacity: 0.6;
}

/* Chrome 推荐 */
.mrp__chrome {
  padding: 10px 12px;
  border-radius: 12px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

html.dark .mrp__chrome {
  background: rgba(30, 64, 175, 0.2);
  border-color: rgba(96, 165, 250, 0.35);
}

.mrp__chrome-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1d4ed8;
  margin-bottom: 8px;
}

html.dark .mrp__chrome-head {
  color: #93c5fd;
}

.mrp__chrome-head i {
  font-size: 16px;
}

.mrp__chrome-links {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mrp__chrome-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 10px;
  background: white;
  border: 1px solid #e2e8f0;
  color: #334155;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
}

.mrp__chrome-link i {
  font-size: 18px;
  color: #64748b;
}

.mrp__chrome-link--me {
  border-color: #60a5fa;
  background: #dbeafe;
  color: #1e40af;
}

.mrp__chrome-link--me i {
  color: #2563eb;
}

html.dark .mrp__chrome-link {
  background: #0f172a;
  border-color: #334155;
  color: #e2e8f0;
}

.mrp__chrome-tag {
  margin-left: auto;
  font-style: normal;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 8px;
  background: #2563eb;
  color: white;
}

.mrp__chrome-note {
  margin-top: 8px;
  font-size: 11px;
  line-height: 1.5;
  color: #64748b;
}

html.dark .mrp__chrome-note {
  color: #94a3b8;
}

/* 空态 */
.mrp__empty {
  text-align: center;
  padding: 22px 8px;
  font-size: 13px;
  color: #94a3b8;
}

.mrp__empty i {
  font-size: 26px;
  display: block;
  margin-bottom: 6px;
}

.mrp__empty-sub {
  margin-top: 4px;
  font-size: 12px;
}

/* 列表 */
.mrp__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mrp__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

html.dark .mrp__item {
  background: #1e293b;
  border-color: #334155;
}

.mrp__item--off {
  opacity: 0.55;
}

.mrp__item-main {
  flex: 1;
  min-width: 0;
}

.mrp__item-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

html.dark .mrp__item-name {
  color: #f1f5f9;
}

.mrp__item-dosage {
  font-weight: 400;
  color: #64748b;
}

.mrp__item-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 3px;
  font-size: 12px;
  color: #94a3b8;
}

.mrp__time-pill {
  display: inline-flex;
  padding: 1px 7px;
  border-radius: 8px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 11px;
  font-weight: 600;
}

html.dark .mrp__time-pill {
  background: rgba(14, 116, 144, 0.35);
  color: #7dd3fc;
}

.mrp__item-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.mrp__icon-btn {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mrp__icon-btn:hover {
  background: #e2e8f0;
  color: #334155;
}

.mrp__icon-btn--danger:hover {
  color: #dc2626;
  background: #fee2e2;
}

html.dark .mrp__icon-btn:hover {
  background: #334155;
  color: #e2e8f0;
}

/* 添加按钮 */
.mrp__add {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 44px;
  border-radius: 12px;
  border: 1px dashed var(--color-primary-300);
  background: transparent;
  color: var(--color-primary-600);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.mrp__add:hover {
  background: var(--color-primary-50);
}

/* 表单 */
.mrp__label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  margin-bottom: 6px;
}

html.dark .mrp__label {
  color: #cbd5e1;
}

.mrp__input {
  width: 100%;
  min-width: 0;
  padding: 9px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: white;
  color: #1e293b;
  font-size: 14px;
  min-height: 42px;
}

.mrp__input:focus {
  outline: none;
  border-color: var(--color-primary-400);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary-500) 15%, transparent);
}

html.dark .mrp__input {
  background: #0f172a;
  border-color: #334155;
  color: #f1f5f9;
}

.mrp__seg {
  display: flex;
  gap: 6px;
}

.mrp__seg-btn {
  flex: 1;
  min-height: 40px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.mrp__seg-btn--active {
  background: var(--color-primary-500);
  border-color: var(--color-primary-500);
  color: white;
  font-weight: 600;
}

html.dark .mrp__seg-btn {
  background: #1e293b;
  border-color: #334155;
  color: #cbd5e1;
}

.mrp__weekdays {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.mrp__day {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid #e2e8f0;
  background: white;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
}

.mrp__day--active {
  background: var(--color-primary-500);
  border-color: var(--color-primary-500);
  color: white;
  font-weight: 600;
}

html.dark .mrp__day {
  background: #0f172a;
  border-color: #334155;
  color: #cbd5e1;
}

.mrp__day-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-left: 2px;
}

.mrp__time-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mrp__time-input {
  flex: 1;
}

.mrp__time-del {
  width: 40px;
  height: 40px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: white;
  color: #94a3b8;
  font-size: 17px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mrp__time-del:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

html.dark .mrp__time-del {
  background: #0f172a;
  border-color: #334155;
}

.mrp__time-add {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-top: 8px;
  border: none;
  background: transparent;
  color: var(--color-primary-600);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  padding: 6px 4px;
}

.mrp__time-add:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
