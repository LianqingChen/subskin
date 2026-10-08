<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'

interface SortOption {
  key: string
  label: string
}

const props = defineProps<{
  modelValue: string
  options: ReadonlyArray<SortOption>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)
const btnRef = ref<HTMLElement | null>(null)
const menuStyle = ref<{ left: string; top: string }>({ left: '0px', top: '0px' })

const activeOption = computed(() => props.options.find((o) => o.key === props.modelValue))
const activeLabel = computed(() => activeOption.value?.label ?? props.modelValue)

function openMenu() {
  open.value = true
  const rect = (btnRef.value ?? root.value)?.getBoundingClientRect()
  if (rect) {
    const left = Math.min(rect.left, window.innerWidth - 164)
    menuStyle.value = { left: `${Math.max(left, 8)}px`, top: `${rect.bottom + 4}px` }
  }
}

function toggle() {
  open.value ? (open.value = false) : openMenu()
}

function select(key: string) {
  emit('update:modelValue', key)
  open.value = false
}

function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) {
    open.value = false
  }
}

function onScrollOrResize() {
  // 父容器（横向滚动标签行）或页面滚动时关闭菜单，避免 fixed 菜单与按钮错位
  open.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  window.addEventListener('scroll', onScrollOrResize, true)
  window.addEventListener('resize', onScrollOrResize)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})
</script>

<template>
  <div ref="root" class="relative flex-shrink-0">
    <button
      ref="btnRef"
      type="button"
      class="control-slim"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggle"
    >
      <span>{{ activeLabel }}</span>
      <i
        class="ri-arrow-down-s-line text-xs transition-transform duration-150"
        :class="open ? 'rotate-180' : ''"
      ></i>
    </button>

    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="open"
          :style="menuStyle"
          class="fixed z-[80] w-36 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1"
          role="listbox"
        >
          <button
            v-for="opt in options"
            :key="opt.key"
            type="button"
            role="option"
            :aria-selected="modelValue === opt.key"
            class="flex w-full items-center justify-between px-3 py-1.5 text-[13px] transition-colors"
            :class="modelValue === opt.key
              ? 'text-primary-700 dark:text-primary-300 font-medium bg-primary-50 dark:bg-primary-900/30'
              : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
            @click="select(opt.key)"
          >
            <span>{{ opt.label }}</span>
            <i v-if="modelValue === opt.key" class="ri-check-line text-primary-500"></i>
          </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
