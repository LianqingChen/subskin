<script setup lang="ts">
import { healthConsentPending, resolveHealthConsent } from '@/composables/useHealthConsent'
</script>

<template>
  <Teleport to="body">
    <div
      v-if="healthConsentPending"
      class="fixed inset-0 z-[120] flex items-end justify-center bg-black/50 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="health-consent-title"
    >
      <div class="safe-bottom w-full max-h-[90dvh] overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl dark:bg-gray-900 sm:mx-4 sm:max-w-md sm:rounded-2xl">
        <h3 id="health-consent-title" class="flex items-center gap-2 text-base font-semibold text-gray-900 dark:text-gray-100">
          <i class="ri-shield-keyhole-line text-primary-600 dark:text-primary-400" aria-hidden="true"></i>
          健康数据单独授权
        </h3>
        <p class="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
          病情照片、皮肤评估结果和体检报告属于敏感个人信息。上传前，需要你单独同意以下处理方式：
        </p>
        <ul class="mt-3 space-y-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
          <li class="flex gap-2">
            <i class="ri-image-line mt-0.5 shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true"></i>
            <span><strong class="font-medium text-gray-900 dark:text-gray-100">收集什么：</strong>你主动上传的病情照片、体检报告，以及由此生成的评估与对比结果。</span>
          </li>
          <li class="flex gap-2">
            <i class="ri-lightbulb-line mt-0.5 shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true"></i>
            <span><strong class="font-medium text-gray-900 dark:text-gray-100">用来做什么：</strong>为你生成记录、变化对比和解读。分析时会交由我们接入的 AI 模型服务处理，结果只返回给你。</span>
          </li>
          <li class="flex gap-2">
            <i class="ri-lock-line mt-0.5 shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true"></i>
            <span><strong class="font-medium text-gray-900 dark:text-gray-100">谁能看到：</strong>默认仅你本人可见；只有你主动分享时，才会对他人展示。</span>
          </li>
          <li class="flex gap-2">
            <i class="ri-settings-3-line mt-0.5 shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true"></i>
            <span><strong class="font-medium text-gray-900 dark:text-gray-100">随时撤回：</strong>可在「个人中心 → 隐私设置」撤回授权，或注销账户删除全部数据。</span>
          </li>
        </ul>
        <p class="mt-3 text-xs text-gray-500 dark:text-gray-400">
          详见
          <a href="/privacy" target="_blank" class="text-primary-600 hover:underline dark:text-primary-400">隐私政策</a>。不同意不影响问答、浏览等其他功能。
        </p>
        <div class="mt-5 flex gap-3">
          <button type="button" class="btn-secondary min-h-[44px] flex-1 text-sm" @click="resolveHealthConsent(false)">
            暂不同意
          </button>
          <button type="button" class="btn-primary min-h-[44px] flex-1 text-sm" @click="resolveHealthConsent(true)">
            同意并继续
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
