<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import {
  createGrant,
  errorCode,
  fetchConsentStatus,
  fetchGrants,
  withdrawGrant,
  type DataGrant,
  type GrantScope,
} from '@/api/contribution'
import { CONTRIBUTION_TEXT_VERSION, TRAINING_TEXT } from '@/constants/contributionText'

/** 我的数据与贡献：每项授权的用途、范围、状态，随时开启/撤回。不展示他人数据，不做排行。 */
const auth = useAuthStore()
const toast = useToast()

const loading = ref(true)
const loadFailed = ref(false)
const grantsEnabled = ref(false)
const grants = ref<DataGrant[]>([])
const scope = ref<GrantScope>('future_only')
const busy = ref(false)
const confirmingId = ref<number | null>(null)

const active = computed(() => grants.value.find((g) => g.purpose === 'model_training' && g.state === 'active') || null)
const history = computed(() => grants.value.filter((g) => g.state !== 'active'))

const scopeLabel = (s: GrantScope) =>
  s === 'future_only' ? TRAINING_TEXT.scopeFuture : s === 'all_records' ? TRAINING_TEXT.scopeAll : '选定的记录'
const day = (iso: string) => iso.slice(0, 10)
const withdrawStatus = (s: string | null) =>
  s === 'done' ? '清理已完成' : s === 'in_progress' ? '清理中' : s ? '已进入清理流程' : ''

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    const [status, list] = await Promise.all([fetchConsentStatus(), fetchGrants()])
    grantsEnabled.value = status.grants_enabled
    grants.value = list
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function enable() {
  if (busy.value) return
  busy.value = true
  try {
    await createGrant({ purpose: 'model_training', scope: scope.value, text_version: CONTRIBUTION_TEXT_VERSION, source: 'data_page' })
    toast.success('已开启，谢谢你')
    await load()
  } catch (e) {
    const code = errorCode(e)
    toast.error(code === 'STALE_TEXT' ? '说明文字已更新，请刷新页面后再确认' : code === 'GRANTS_DISABLED' ? '该功能暂未开放' : '没有成功，请稍后重试')
  } finally {
    busy.value = false
  }
}

async function withdraw(id: number) {
  if (busy.value) return
  busy.value = true
  try {
    await withdrawGrant(id)
    confirmingId.value = null
    toast.success('已撤回')
    await load()
  } catch {
    toast.error('撤回没有成功，请稍后重试')
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  if (auth.isLoggedIn) load()
  else loading.value = false
})
</script>

<template>
  <main class="page page-narrow py-6">
    <router-link to="/profile" class="inline-flex min-h-[44px] items-center text-sm text-gray-500 dark:text-gray-400">
      <i class="ri-arrow-left-s-line" aria-hidden="true"></i> 个人中心
    </router-link>
    <h1 class="section-title mt-1">数据与贡献</h1>
    <p class="section-desc mt-1">你的记录首先属于你自己。是否让它们帮助改进识别，由你决定，随时可以改变。</p>

    <p v-if="!auth.isLoggedIn" class="mt-6 text-sm text-gray-500 dark:text-gray-400">请先登录后查看。</p>
    <p v-else-if="loading" role="status" class="mt-6 text-sm text-gray-500 dark:text-gray-400">加载中…</p>
    <div v-else-if="loadFailed" role="alert" class="card dark:bg-gray-800 mt-6 p-4 text-sm">
      加载失败。<button type="button" class="min-h-[44px] px-2 text-primary-700 dark:text-primary-300" @click="load">重试</button>
    </div>

    <template v-else>
      <section class="card dark:bg-gray-800 mt-6 p-5" aria-label="帮助改进白斑识别">
        <div class="flex items-start justify-between gap-3">
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ TRAINING_TEXT.title }}</h2>
          <span
            class="shrink-0 rounded-full px-2 py-0.5 text-xs"
            :class="active ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-300'"
          >
            {{ active ? '已开启' : '未开启' }}
          </span>
        </div>
        <p class="mt-2 text-sm text-gray-600 dark:text-gray-300">{{ TRAINING_TEXT.summary }}</p>
        <ul class="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-gray-500 dark:text-gray-400">
          <li v-for="d in TRAINING_TEXT.details" :key="d">{{ d }}</li>
        </ul>

        <template v-if="active">
          <p class="mt-3 text-sm text-gray-700 dark:text-gray-200">
            范围：{{ scopeLabel(active.scope) }}<span class="text-gray-400"> · 开启于 {{ day(active.created_at) }}</span>
          </p>
          <div v-if="confirmingId !== active.id" class="mt-3">
            <button type="button" class="btn-ghost min-h-[44px] rounded-xl px-4 text-sm" @click="confirmingId = active.id">撤回授权</button>
          </div>
          <div v-else class="mt-3 rounded-xl bg-gray-50 p-3 dark:bg-gray-900/40">
            <p class="text-xs leading-5 text-gray-600 dark:text-gray-300">{{ TRAINING_TEXT.withdrawNote }}</p>
            <div class="mt-3 flex gap-3">
              <button type="button" class="btn-primary min-h-[44px] flex-1 rounded-xl text-sm" :disabled="busy" @click="withdraw(active.id)">
                {{ busy ? '处理中…' : '确认撤回' }}
              </button>
              <button type="button" class="btn-ghost min-h-[44px] flex-1 rounded-xl text-sm" :disabled="busy" @click="confirmingId = null">取消</button>
            </div>
          </div>
        </template>

        <template v-else-if="grantsEnabled">
          <fieldset class="mt-3">
            <legend class="sr-only">授权范围</legend>
            <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
              <input v-model="scope" type="radio" value="future_only" class="accent-primary-600" />{{ TRAINING_TEXT.scopeFuture }}
            </label>
            <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
              <input v-model="scope" type="radio" value="all_records" class="accent-primary-600" />{{ TRAINING_TEXT.scopeAll }}
            </label>
          </fieldset>
          <button type="button" class="btn-primary mt-2 min-h-[44px] w-full rounded-xl text-sm sm:w-auto sm:px-6" :disabled="busy" @click="enable">
            {{ busy ? '提交中…' : '同意并开启' }}
          </button>
        </template>
        <p v-else class="mt-3 text-sm text-gray-500 dark:text-gray-400">该功能暂未开放。</p>
      </section>

      <section v-if="history.length" class="card dark:bg-gray-800 mt-4 p-5" aria-label="历史授权">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">历史记录</h2>
        <ul class="mt-2 divide-y divide-gray-100 dark:divide-gray-700">
          <li v-for="g in history" :key="g.id" class="py-3 text-sm">
            <div class="flex items-center justify-between gap-3">
              <span class="text-gray-800 dark:text-gray-100">{{ g.title }} · {{ scopeLabel(g.scope) }}</span>
              <span class="shrink-0 text-xs text-gray-500 dark:text-gray-400">{{ g.state === 'withdrawn' ? '已撤回' : '已过期' }}</span>
            </div>
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {{ day(g.created_at) }}<template v-if="withdrawStatus(g.withdrawal_status)"> · {{ withdrawStatus(g.withdrawal_status) }}</template>
            </p>
          </li>
        </ul>
      </section>
    </template>
  </main>
</template>
