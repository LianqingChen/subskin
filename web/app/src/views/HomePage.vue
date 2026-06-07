<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'


const router = useRouter()
const authStore = useAuthStore()

const previewPosts = [
  { id: 1, name: '小王', desc: '308激光3个月心得', avatar: '王', bgColor: 'bg-blue-500' },
  { id: 2, name: '李姐', desc: '他克莫司使用记录', avatar: '李', bgColor: 'bg-purple-500' },
  { id: 3, name: '张哥', desc: '3年康复心路', avatar: '张', bgColor: 'bg-green-500' },
  { id: 4, name: '陈姐', desc: '协和就诊体验', avatar: '陈', bgColor: 'bg-pink-500' },
]

const chatInput = ref('')

const suggestions = [
  '白癜风会传染吗？',
  '最新管理方法有什么进展？',
  '日常饮食需要注意什么？',
  '308激光治疗效果怎么样？',
  '我刚确诊，该怎么办？',
  '白癜风会遗传给孩子吗？',
]

const trustItems = [
  { icon: 'ri-file-text-line', label: '基于2000+文献', desc: '科学依据' },
  { icon: 'ri-lock-line', label: '隐私保护', desc: '照片加密存储' },
  { icon: 'ri-stethoscope-line', label: '专业参考', desc: '医学顾问审核' },
]

function handleSuggestionClick(text: string) {
  chatInput.value = text
  startChat()
}

function startChat() {
  if (!authStore.isLoggedIn) {
    authStore.showLoginModal = true
    return
  }
  router.push({ path: '/chat', query: chatInput.value ? { q: chatInput.value } : {} })
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-6 space-y-8 pb-24 md:pb-6">
    <section class="text-center py-8">
      <div class="flex items-center justify-center gap-3 mb-4">
        <span class="text-4xl"><i class="ri-leaf-line"></i></span>
        <h1 class="text-3xl font-bold text-gray-900">SubSkin · 白癜风智能助手</h1>
      </div>
      <p class="text-gray-500  text-base">
        基于 2000+ 篇医学研究文献与小白真实经验，为你提供专业解答
      </p>
    </section>

    <section class="card p-6">
      <div class="relative">
        <textarea
          v-model="chatInput"
          placeholder="输入你的问题，AI为你智能解答..."
          class="w-full px-4 py-3 pr-20 rounded-xl border border-gray-200 dark:border-gray-600 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 dark:focus:border-primary-500 text-base resize-none"
          rows="2"
          @keydown.enter="startChat"
        />
        <button
          class="absolute right-3 bottom-3 bg-primary-600 dark:bg-primary-500 text-white rounded-lg px-4 py-2 hover:bg-primary-700 dark:hover:bg-primary-600 transition-colors disabled:opacity-50"
          :disabled="!chatInput.trim()"
          @click="startChat"
        >
          发送
        </button>
      </div>
      <div class="flex flex-wrap gap-2 mt-3">
        <button
          v-for="s in suggestions"
          :key="s"
          class="px-3 py-1.5 rounded-full text-sm border border-gray-200 dark:border-gray-600 text-gray-600 hover:border-primary-500 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors"
          @click="handleSuggestionClick(s)"
        >
          {{ s }}
        </button>
      </div>
      <p class="text-xs text-gray-400  mt-2 text-center">* 回答仅供参考，具体诊疗请遵医嘱</p>
    </section>

    <section class="card p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-900"><i class="ri-team-line"></i> 小白动态</h2>
        <router-link to="/community" class="text-sm text-primary-600 dark:text-primary-400 hover:underline no-underline">查看更多 →</router-link>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div v-for="post in previewPosts" :key="post.id" class="text-center p-3 rounded-lg bg-gray-50 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors cursor-pointer">
          <div class="w-10 h-10 rounded-full mx-auto mb-2 flex items-center justify-center text-white text-sm font-medium" :class="post.bgColor">
            {{ post.avatar }}
          </div>
          <div class="text-xs font-medium text-gray-900">{{ post.name }}</div>
          <div class="text-xs text-gray-500  mt-0.5">{{ post.desc }}</div>
        </div>
      </div>
    </section>

    <section>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-bold text-gray-900"><i class="ri-hand-heart-line"></i> 信任保障</h2>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div v-for="item in trustItems" :key="item.label" class="card p-4 text-center">
          <div class="text-2xl mb-2"><i :class="item.icon"></i></div>
          <div class="font-medium text-gray-900 text-sm">{{ item.label }}</div>
          <div class="text-gray-500  text-xs">{{ item.desc }}</div>
        </div>
      </div>
    </section>

    <section class="text-center text-xs text-gray-400  py-4 border-t border-gray-100 dark:border-gray-800">
      <i class="ri-error-warning-line"></i> 本平台不构成医疗建议，所有内容仅供参考。具体诊疗请遵医嘱。
    </section>
  </div>
</template>
