<template>
  <div class="w-full relative">
    <!-- Tags Container -->
    <div 
      class="flex flex-wrap items-center gap-2 p-2 border rounded-md bg-white focus-within:ring-2 focus-within:ring-primary-500 focus-within:border-primary-500 transition-colors"
      :class="{ 'opacity-75 cursor-not-allowed': isMaxReached }"
    >
      <!-- Selected Tags -->
      <span 
        v-for="(tag, index) in modelValue" 
        :key="index"
        class="inline-flex items-center px-2.5 py-1 rounded-full text-sm font-medium bg-primary-50 text-primary-700"
      >
        #{{ tag }}
        <button 
          type="button" 
          @click="removeTag(index)"
          class="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full text-primary-400 hover:bg-primary-200 hover:text-primary-900 focus:outline-none focus:bg-primary-200 focus:text-primary-900"
        >
          <span class="sr-only">Remove tag</span>
          <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </span>

      <!-- Input Field -->
      <input
        ref="inputRef"
        v-model="inputValue"
        type="text"
        class="flex-1 min-w-[120px] outline-none bg-transparent text-sm text-gray-900 placeholder-gray-400"
        :placeholder="isMaxReached ? '' : '添加标签（回车添加）'"
        :disabled="isMaxReached"
        @keydown.enter.prevent="addTag(inputValue)"
        @keydown.comma.prevent="addTag(inputValue)"
        @keydown.delete="handleBackspace"
        @input="handleInput"
        @focus="showDropdown = true"
        @blur="handleBlur"
      />
    </div>

    <!-- Dropdown -->
    <div 
      v-if="showDropdown && (suggestedTags.length > 0 || isLoading)" 
      class="absolute z-10 w-full mt-1 bg-white rounded-md shadow-lg border border-gray-200 max-h-60 overflow-auto"
    >
      <div v-if="isLoading" class="p-3 text-sm text-gray-500 text-center">
        加载中...
      </div>
      <ul v-else class="py-1">
        <li 
          v-for="tag in suggestedTags" 
          :key="tag.id"
          @mousedown.prevent="addTag(tag.name)"
          class="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 cursor-pointer flex justify-between items-center"
        >
          <span>#{{ tag.name }}</span>
          <span class="text-xs text-gray-400">{{ tag.usage_count }} 次使用</span>
        </li>
      </ul>
    </div>

    <!-- Count Limit -->
    <div class="mt-1.5 text-xs text-gray-500">
      已选 {{ modelValue.length }}/{{ maxTags }} 个标签
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { communityApi } from '@/api/community'
import type { PostTag } from '@/types'

const props = withDefaults(defineProps<{
  modelValue: string[]
  maxTags?: number
}>(), {
  maxTags: 5
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const inputValue = ref('')
const showDropdown = ref(false)
const isLoading = ref(false)
const suggestedTags = ref<PostTag[]>([])
let debounceTimeout: ReturnType<typeof setTimeout> | null = null

const isMaxReached = computed(() => props.modelValue.length >= props.maxTags)

const addTag = (tag: string) => {
  const cleanTag = tag.trim().replace(/^#/, '')
  
  if (!cleanTag || isMaxReached.value) {
    inputValue.value = ''
    return
  }

  // Prevent duplicates
  if (!props.modelValue.includes(cleanTag)) {
    emit('update:modelValue', [...props.modelValue, cleanTag])
  }
  
  inputValue.value = ''
  showDropdown.value = false
  suggestedTags.value = []
}

const removeTag = (index: number) => {
  const newTags = [...props.modelValue]
  newTags.splice(index, 1)
  emit('update:modelValue', newTags)
}

const handleBackspace = () => {
  if (inputValue.value === '' && props.modelValue.length > 0) {
    removeTag(props.modelValue.length - 1)
  }
}

const fetchTags = async (query: string) => {
  if (!query.trim()) {
    suggestedTags.value = []
    return
  }

  isLoading.value = true
  try {
    const tags = await communityApi.getTags({ q: query, limit: 10 })
    // Filter out already selected tags
    suggestedTags.value = tags.filter(t => !props.modelValue.includes(t.name))
  } catch (error) {
    console.error('Failed to fetch tags:', error)
    suggestedTags.value = []
  } finally {
    isLoading.value = false
  }
}

const handleInput = () => {
  showDropdown.value = true
  
  if (debounceTimeout) {
    clearTimeout(debounceTimeout)
  }
  
  debounceTimeout = setTimeout(() => {
    fetchTags(inputValue.value)
  }, 300)
}

const handleBlur = () => {
  // Small delay to allow mousedown event on dropdown items to fire
  setTimeout(() => {
    showDropdown.value = false
  }, 200)
}

// Fetch initial suggestions when focused without input
watch(showDropdown, (newVal) => {
  if (newVal && !inputValue.value && suggestedTags.value.length === 0) {
    fetchTags('')
  }
})
</script>