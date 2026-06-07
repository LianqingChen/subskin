<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { communityApi } from '@/api/community'
import type { PostTag } from '@/types'

const props = defineProps<{
  currentTags: string[]
}>()

const emit = defineEmits<{
  (e: 'save', tags: string[]): void
  (e: 'close'): void
}>()

const tags = ref<string[]>([...props.currentTags])
const inputValue = ref('')
const suggestedTags = ref<PostTag[]>([])
const maxTags = 5

function addTag(tag: string) {
  const cleanTag = tag.trim().replace(/^#/, '')
  if (!cleanTag || tags.value.length >= maxTags) { inputValue.value = ''; return }
  if (!tags.value.includes(cleanTag)) {
    tags.value.push(cleanTag)
  }
  inputValue.value = ''
}

function removeTag(index: number) {
  tags.value.splice(index, 1)
}

function save() {
  emit('save', tags.value)
}

onMounted(async () => {
  try {
    suggestedTags.value = await communityApi.getHotTags(15)
  } catch {}
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm" @click="emit('close')" />

    <div class="fixed inset-x-0 bottom-0 z-[61] rounded-t-2xl bg-white shadow-2xl" :style="{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }">
      <div class="flex justify-center pt-3 pb-1">
        <div class="w-10 h-1 rounded-full bg-gray-300 " />
      </div>

      <div class="px-5 pb-3 pt-1">
        <h3 class="text-base font-semibold text-gray-900">编辑标签</h3>
      </div>

      <div class="px-5 pb-3">
        <div class="flex flex-wrap gap-2 mb-3">
          <span v-for="(tag, index) in tags" :key="index"
            class="inline-flex items-center px-2.5 py-1 rounded-full text-sm font-medium bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300">
            #{{ tag }}
            <button @click="removeTag(index)" class="ml-1.5 w-4 h-4 rounded-full text-primary-400 hover:bg-primary-200 dark:hover:bg-primary-800 hover:text-primary-900">
              <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
            </button>
          </span>
        </div>

        <div class="flex gap-2 mb-3">
          <input v-model="inputValue" type="text" placeholder="输入标签名称"
            class="flex-1 px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white text-gray-900 outline-none focus:border-primary-400"
            @keydown.enter.prevent="addTag(inputValue)" />
          <button @click="addTag(inputValue)" class="px-4 py-2 bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-600 transition-colors">添加</button>
        </div>

        <div v-if="suggestedTags.length > 0">
          <p class="text-xs text-gray-500  mb-2">推荐标签</p>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="tag in suggestedTags.filter(t => !tags.includes(t.name))" :key="tag.id"
              @click="addTag(tag.name)" type="button"
              class="px-2.5 py-1 rounded-full text-xs border border-gray-200 dark:border-gray-600 text-gray-600  hover:border-primary-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors">
              #{{ tag.name }}
            </button>
          </div>
        </div>

        <p class="text-[11px] text-gray-400  mt-3">已选 {{ tags.length }}/{{ maxTags }} 个标签</p>
      </div>

      <div class="flex gap-3 px-5 pb-5 pt-2">
        <button @click="emit('close')" class="flex-1 py-2.5 text-sm font-medium text-gray-500  rounded-xl hover:bg-gray-50 dark:hover:bg-gray-300 transition-colors">取消</button>
        <button @click="save" class="flex-1 py-2.5 text-sm font-medium bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-colors">保存</button>
      </div>
    </div>
  </Teleport>
</template>
