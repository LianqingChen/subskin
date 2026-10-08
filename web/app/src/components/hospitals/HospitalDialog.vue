<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
defineProps<{ title: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
let previousFocus: HTMLElement | null = null
onMounted(() => { previousFocus = document.activeElement as HTMLElement | null; dialog.value?.showModal() })
onBeforeUnmount(() => { dialog.value?.close(); previousFocus?.focus() })
</script>
<template>
  <Teleport to="body">
    <dialog ref="dialog" aria-labelledby="hospital-dialog-title" class="hospital-dialog rounded-2xl bg-white p-0 text-gray-900 shadow-xl dark:bg-gray-900 dark:text-gray-100" :class="wide ? 'max-w-4xl' : 'max-w-2xl'" @cancel.prevent="emit('close')">
      <header class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-gray-100 bg-white px-5 py-3 dark:border-gray-800 dark:bg-gray-900">
        <h2 id="hospital-dialog-title" class="font-semibold">{{ title }}</h2>
        <button autofocus class="h-11 w-11 shrink-0 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800" aria-label="关闭窗口" @click="emit('close')"><i class="ri-close-line text-xl" /></button>
      </header>
      <div class="p-5"><slot /></div>
    </dialog>
  </Teleport>
</template>
<style scoped>
.hospital-dialog { width: calc(100% - 1.5rem); max-height: calc(100dvh - 3rem); overflow-y: auto; padding-bottom: env(safe-area-inset-bottom); }
.hospital-dialog::backdrop { background: rgb(0 0 0 / 45%); backdrop-filter: blur(3px); }
</style>
