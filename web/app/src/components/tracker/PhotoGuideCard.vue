<script setup lang="ts">
import { ref, onMounted } from 'vue'

const STORAGE_KEY = 'hidePhotoGuide'

const dismissed = ref(false)
const expanded = ref(false)

onMounted(() => {
  if (localStorage.getItem(STORAGE_KEY) === 'true') {
    dismissed.value = true
  }
})

function dismissPermanently() {
  localStorage.setItem(STORAGE_KEY, 'true')
  dismissed.value = true
}

const tips = [
  { icon: 'ri-ruler-line', text: '保持 20-30cm 距离，正对皮肤拍摄，确保白斑完整入镜' },
  { icon: 'ri-sun-line', text: '在自然漫射光或白色柔光灯下拍摄，避免阴影和强光直射' },
  { icon: 'ri-stamp-line', text: '强烈推荐：放一枚标准一元硬币（直径25mm）在患处旁作为尺寸参考' },
  { icon: 'ri-contrast-drop-2-line', text: '确保正常皮肤与白斑同时出现在画面中，方便 AI 对比色差' },
  { icon: 'ri-camera-lens-line', text: '对焦在白斑区域，保持手稳避免模糊，照片分辨率 ≥ 640×480' },
]
</script>

<template>
  <div v-if="!dismissed" class="card p-4 mb-4 border border-primary-200 dark:border-primary-800 bg-primary-50/50 dark:bg-primary-900/10">
    <div class="flex items-center justify-between cursor-pointer select-none" @click="expanded = !expanded">
      <div class="flex items-center gap-2">
        <i class="ri-lightbulb-line text-primary-500"></i>
        <span class="text-sm font-medium text-primary-700 dark:text-primary-300">拍照技巧提示</span>
      </div>
      <i :class="expanded ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'" class="text-primary-500 text-lg"></i>
    </div>

    <div class="overflow-hidden transition-all duration-300" :class="expanded ? 'max-h-96 opacity-100 mt-3' : 'max-h-0 opacity-0'">
      <ul class="space-y-2">
        <li v-for="(tip, i) in tips" :key="i" class="flex items-start gap-2 text-sm text-gray-700">
          <i :class="tip.icon" class="text-primary-500 mt-0.5 flex-shrink-0"></i>
          <span>{{ tip.text }}</span>
        </li>
      </ul>

      <div class="mt-3 flex items-center justify-between">
        <label class="flex items-center gap-1.5 text-xs text-gray-500  cursor-pointer select-none">
          <input type="checkbox" class="rounded border-gray-300 text-primary-500 focus:ring-primary-400" @change="dismissPermanently" />
          不再显示
        </label>
        <router-link to="/photo-guide" class="text-xs text-primary-600 dark:text-primary-400 hover:underline">
          查看拍照示例 <i class="ri-arrow-right-s-line"></i>
        </router-link>
      </div>

      <slot></slot>
    </div>
  </div>
</template>
