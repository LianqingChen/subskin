<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  answerQuestion,
  dismissQuestion,
  nextQuestions,
  type MicroQuestion,
  type MicroTrigger,
} from '@/api/contribution'

/**
 * 微询问卡片：紧跟用户刚做完的动作，一次只问一个问题。
 * 选项均可点“不确定/不知道”，也可以点“稍后”。不弹窗、不遮挡主要内容；
 * 频率上限（每次打开 1 题、每周 3 题、跳过后冷却）由后端控制。
 */
const props = defineProps<{ trigger: MicroTrigger; bodySite?: string | null }>()

const auth = useAuthStore()
const question = ref<MicroQuestion | null>(null)
const picked = ref<string[]>([])
const busy = ref(false)
const failed = ref(false)
const thanks = ref(false)

function sessionId(): string {
  const key = 'subskin_microask_sid'
  let sid = sessionStorage.getItem(key)
  if (!sid) {
    sid = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now()) + Math.random()
    sessionStorage.setItem(key, sid)
  }
  return sid
}

onMounted(async () => {
  if (!auth.isLoggedIn) return
  try {
    const qs = await nextQuestions(props.trigger, props.bodySite ?? null, sessionId())
    question.value = qs[0] ?? null
  } catch {
    question.value = null // 询问是锦上添花，加载失败不打扰用户
  }
})

const exclusive = new Set(['none', 'unknown'])
const canSubmit = computed(() => picked.value.length > 0 && !busy.value)

function toggle(value: string) {
  if (picked.value.includes(value)) {
    picked.value = picked.value.filter((v) => v !== value)
  } else if (exclusive.has(value)) {
    picked.value = [value]
  } else {
    picked.value = [...picked.value.filter((v) => !exclusive.has(v)), value]
  }
}

async function submit(answer: string | string[]) {
  if (!question.value || busy.value) return
  busy.value = true
  failed.value = false
  try {
    await answerQuestion({
      question_id: question.value.id,
      answer,
      body_site: props.bodySite ?? null,
      session_id: sessionId(),
    })
    question.value = null
    thanks.value = true
    setTimeout(() => (thanks.value = false), 2500)
  } catch {
    failed.value = true
  } finally {
    busy.value = false
  }
}

async function later() {
  const q = question.value
  if (!q) return
  question.value = null // 先收起，不等网络
  try {
    await dismissQuestion({ question_id: q.id, body_site: props.bodySite ?? null, session_id: sessionId() })
  } catch {
    /* 跳过记录失败不影响用户 */
  }
}
</script>

<template>
  <section
    v-if="question"
    class="card dark:bg-gray-800 p-4"
    :aria-label="'小问题：' + question.text"
  >
    <div class="flex items-start justify-between gap-3">
      <h3 class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ question.text }}</h3>
      <button
        type="button"
        class="shrink-0 min-h-[44px] px-2 text-xs text-gray-500 dark:text-gray-400"
        @click="later"
      >
        稍后
      </button>
    </div>
    <div class="mt-2 flex flex-wrap gap-2">
      <template v-if="!question.multi">
        <button
          v-for="o in question.options"
          :key="o.value"
          type="button"
          class="min-h-[44px] rounded-xl border border-gray-200 px-3 text-sm text-gray-700 hover:bg-primary-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-primary-900/30"
          :disabled="busy"
          @click="submit(o.value)"
        >
          {{ o.label }}
        </button>
      </template>
      <template v-else>
        <button
          v-for="o in question.options"
          :key="o.value"
          type="button"
          :aria-pressed="picked.includes(o.value)"
          class="min-h-[44px] rounded-xl border px-3 text-sm"
          :class="
            picked.includes(o.value)
              ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
              : 'border-gray-200 text-gray-700 dark:border-gray-600 dark:text-gray-200'
          "
          @click="toggle(o.value)"
        >
          {{ o.label }}
        </button>
        <button
          type="button"
          class="btn-primary min-h-[44px] rounded-xl px-4 text-sm"
          :disabled="!canSubmit"
          @click="submit(picked)"
        >
          确定
        </button>
      </template>
    </div>
    <p v-if="failed" role="alert" class="mt-2 text-xs text-gray-500 dark:text-gray-400">没记上，稍后再试一次吧</p>
  </section>
  <p v-else-if="thanks" role="status" class="text-center text-xs text-gray-500 dark:text-gray-400">
    <i class="ri-check-line" aria-hidden="true"></i> 已记下，谢谢
  </p>
</template>
