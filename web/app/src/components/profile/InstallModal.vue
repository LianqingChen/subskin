<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'

const props = defineProps<{
  modelValue: boolean
  canInstall: boolean
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'install'): void
  (e: 'forceReset'): void
}>()

const isIOS = computed(() =>
  /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
)

// Huawei, UC, QQ, Baidu etc. don't support PWA beforeinstallprompt — skip waiting
const isPWALimitedBrowser = computed(() =>
  /Huawei|HUAWEI|HarmonyOS|UCBrowser|UCWEB|MQQBrowser|QQ\/|Baidu|baidubrowser|AlipayClient|MicroMessenger/i.test(navigator.userAgent)
)

const waiting = ref(false)
const timedOut = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

function startWaiting() {
  waiting.value = true
  timedOut.value = false
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    timedOut.value = true
    waiting.value = false
  }, 4000)
}

watch(() => props.modelValue, (open) => {
  if (open && !isIOS.value && !props.canInstall) {
    if (isPWALimitedBrowser.value) {
      // These browsers never fire beforeinstallprompt — go straight to manual guide
      timedOut.value = true
    } else {
      startWaiting()
    }
  } else {
    waiting.value = false
    timedOut.value = false
    if (timer) { clearTimeout(timer); timer = null }
  }
})

// When canInstall flips to true while modal is open and waiting, auto-trigger install
watch(() => props.canInstall, (val) => {
  if (val && props.modelValue && (waiting.value || timedOut.value)) {
    emit('install')
  }
})

onUnmounted(() => {
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 bg-black/50 z-[100] flex items-end md:items-center justify-center" @click.self="emit('update:modelValue', false)">
      <div class="bg-white w-full max-w-md rounded-t-2xl md:rounded-xl shadow-xl overflow-hidden mx-0 md:mx-4 max-h-[90dvh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-semibold text-gray-900"><i class="ri-smartphone-line"></i> 添加到桌面</h2>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl" @click="emit('update:modelValue', false)">&times;</button>
        </div>

        <!-- iOS Guide -->
        <div v-if="isIOS" class="p-6 space-y-5">
          <p class="text-sm text-gray-600">按以下步骤将 SubSkin 添加到主屏幕，即可像 App 一样使用：</p>

          <div class="space-y-4">
            <div class="flex items-start gap-3">
              <span class="flex-shrink-0 w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 text-xs font-bold flex items-center justify-center">1</span>
              <div>
                <p class="text-sm font-medium text-gray-900">点击底部分享按钮</p>
                <p class="text-xs text-gray-500  mt-0.5">Safari 底部的 <svg class="inline w-4 h-4 text-gray-500" viewBox="0 0 20 20" fill="currentColor"><path d="M13 8V2H7v6H2l8 8 8-8h-5zM0 18h20v2H0v-2z"/></svg> 图标</p>
              </div>
            </div>

            <div class="flex items-start gap-3">
              <span class="flex-shrink-0 w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 text-xs font-bold flex items-center justify-center">2</span>
              <div>
                <p class="text-sm font-medium text-gray-900">向下滑动，找到「添加到主屏幕」</p>
                <p class="text-xs text-gray-500  mt-0.5">图标为 <svg class="inline w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8v8M8 12h8"/></svg> 加号样式</p>
              </div>
            </div>

            <div class="flex items-start gap-3">
              <span class="flex-shrink-0 w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 text-xs font-bold flex items-center justify-center">3</span>
              <div>
                <p class="text-sm font-medium text-gray-900">点击「添加」确认</p>
                <p class="text-xs text-gray-500  mt-0.5">桌面会出现 SubSkin 图标，点击即可打开</p>
              </div>
            </div>
          </div>

          <div class="rounded-xl bg-primary-50 dark:bg-primary-900/20 p-4 text-sm text-gray-600 leading-6">
            <i class="ri-lightbulb-line"></i> 添加后体验更流畅，支持全屏显示和离线访问
          </div>
        </div>

        <!-- Android / Other: native install -->
        <div v-else class="p-6 space-y-4">
          <!-- State: install ready -->
          <template v-if="canInstall">
            <p class="text-sm text-gray-600">点击下方按钮，一键将 SubSkin 添加到桌面：</p>
            <button class="w-full btn-primary py-3 rounded-xl text-base" @click="$emit('install')">
              添加到桌面
            </button>
          </template>

          <!-- State: waiting for beforeinstallprompt -->
          <template v-else-if="waiting">
            <div class="flex flex-col items-center py-6 space-y-3">
              <svg class="animate-spin w-8 h-8 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              <p class="text-sm text-gray-600">正在检测安装条件…</p>
            </div>
          </template>

          <!-- State: timeout fallback or PWA-limited browser -->
          <template v-else-if="timedOut">
            <div v-if="isPWALimitedBrowser" class="rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-4 mb-4">
              <p class="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-2"><i class="ri-error-warning-line"></i> 当前浏览器不支持 PWA 安装</p>
              <p class="text-xs text-amber-700 dark:text-amber-400">华为/UC/QQ 等浏览器的「添加至桌面」只是普通书签，打开后仍会显示浏览器按钮。如需真正的类 App 全屏体验，请改用 <strong>Chrome 浏览器</strong> 打开 SubSkin 后重新安装。</p>
            </div>
            <p class="text-sm text-gray-600 mb-3">请在浏览器菜单中选择「添加到主屏幕」或「安装应用」：</p>
            <div class="rounded-xl bg-gray-50  p-4 space-y-2 text-sm text-gray-600">
              <template v-if="isPWALimitedBrowser">
                <p><strong>华为浏览器：</strong>底部菜单 → <i class="ri-smartphone-line"></i> 添加至桌面（仅书签）</p>
                <p><strong>推荐 Chrome：</strong>地址栏 → <i class="ri-smartphone-line"></i> 安装应用（真 PWA）</p>
              </template>
              <template v-else>
                <p><strong>Chrome：</strong>底部弹窗或地址栏 → 安装应用</p>
                <p><strong>Samsung 浏览器：</strong>底部 ≡ → 添加至主屏幕</p>
                <p><strong>Edge：</strong>底部菜单 ··· → 添加至手机</p>
              </template>
            </div>
            <div class="space-y-2">
              <button v-if="!isPWALimitedBrowser" class="w-full btn-secondary py-3 rounded-xl text-sm" @click="startWaiting()">
                重试
              </button>
              <button class="w-full btn-primary py-3 rounded-xl text-sm" @click="$emit('forceReset')">
                清除缓存并刷新
              </button>
            </div>
          </template>
        </div>

      </div>
    </div>
  </Teleport>
</template>
