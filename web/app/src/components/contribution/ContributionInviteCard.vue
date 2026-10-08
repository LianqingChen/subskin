<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { createGrant, errorCode, fetchConsentStatus, type GrantScope } from '@/api/contribution'
import { CONTRIBUTION_TEXT_VERSION, INVITE, TRAINING_TEXT } from '@/constants/contributionText'

/**
 * 贡献邀请卡：只在“价值时刻”（刚看完对比结果）出现，且：
 * - 用户已登录、后端已开放授权、用户当前没有有效授权；
 * - 拒绝后 30 天内不再出现（记在本机，换设备可能再次出现一次）。
 * 默认不勾选；拒绝或忽略不影响任何功能。
 */
const COOLDOWN_KEY = 'subskin_contrib_invite_dismissed_at'

const auth = useAuthStore()
const toast = useToast()
const visible = ref(false)
const scope = ref<GrantScope>('future_only')
const busy = ref(false)

function inCooldown(): boolean {
  const raw = localStorage.getItem(COOLDOWN_KEY)
  const at = raw ? Number(raw) : 0
  return !!at && Date.now() - at < INVITE.cooldownDays * 86400000
}

onMounted(async () => {
  if (!auth.isLoggedIn || inCooldown()) return
  try {
    const s = await fetchConsentStatus()
    visible.value = s.grants_enabled && !s.active.model_training
  } catch {
    visible.value = false
  }
})

function later() {
  localStorage.setItem(COOLDOWN_KEY, String(Date.now()))
  visible.value = false
}

async function agree() {
  if (busy.value) return
  busy.value = true
  try {
    await createGrant({
      purpose: 'model_training',
      scope: scope.value,
      text_version: CONTRIBUTION_TEXT_VERSION,
      source: 'compare_invite',
    })
    visible.value = false
    toast.success('已记录你的选择，谢谢你！可随时在「数据与贡献」撤回')
  } catch (e) {
    const code = errorCode(e)
    toast.error(
      code === 'STALE_TEXT'
        ? '说明文字已更新，请刷新页面后再确认'
        : code === 'GRANTS_DISABLED'
          ? '该功能暂未开放'
          : '没有成功，请稍后重试',
    )
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section v-if="visible" class="card dark:bg-gray-800 p-5" aria-label="邀请：帮助改进白斑识别">
    <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ INVITE.title }}</h3>
    <p class="mt-1 text-sm text-gray-600 dark:text-gray-300">{{ INVITE.lead }}</p>

    <div class="mt-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
      <h4 class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ TRAINING_TEXT.title }}</h4>
      <p class="mt-1 text-xs leading-5 text-gray-600 dark:text-gray-300">{{ TRAINING_TEXT.summary }}</p>
      <ul class="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-gray-500 dark:text-gray-400">
        <li v-for="d in TRAINING_TEXT.details" :key="d">{{ d }}</li>
      </ul>
      <fieldset class="mt-3">
        <legend class="sr-only">授权范围</legend>
        <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
          <input v-model="scope" type="radio" value="future_only" class="accent-primary-600" />
          {{ TRAINING_TEXT.scopeFuture }}
        </label>
        <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
          <input v-model="scope" type="radio" value="all_records" class="accent-primary-600" />
          {{ TRAINING_TEXT.scopeAll }}
        </label>
      </fieldset>
    </div>

    <div class="mt-4 flex gap-3">
      <button type="button" class="btn-primary min-h-[44px] flex-1 rounded-xl text-sm" :disabled="busy" @click="agree">
        {{ busy ? '提交中…' : INVITE.agree }}
      </button>
      <button type="button" class="btn-ghost min-h-[44px] flex-1 rounded-xl text-sm" :disabled="busy" @click="later">
        {{ INVITE.later }}
      </button>
    </div>
    <p class="mt-3 text-xs text-gray-500 dark:text-gray-400">{{ INVITE.footnote }}</p>
  </section>
</template>
