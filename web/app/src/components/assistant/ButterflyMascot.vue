<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  size?: 'sm' | 'md' | 'lg'
  animated?: boolean
}>(), {
  size: 'md',
  animated: true,
})

const sizeMap: Record<string, string> = { sm: 'w-16 h-16', md: 'w-28 h-28', lg: 'w-40 h-40' }
const containerClass = computed(() => sizeMap[props.size] || sizeMap.md)
</script>

<template>
  <div class="butterfly-container select-none flex items-center justify-center">
    <img
      src="/butterfly_mascot.png"
      alt="小金 - 金斑蝶"
      :class="[containerClass, 'object-contain drop-shadow-lg', { 'butterfly-animated': animated }]"
    />
  </div>
</template>

<style scoped>
.butterfly-container {
  display: flex;
  align-items: center;
  justify-content: center;
}

.butterfly-animated {
  animation: butterfly-float 3s ease-in-out infinite;
}

@keyframes butterfly-float {
  0%, 100% { transform: translateY(0px) scale(1); }
  50% { transform: translateY(-8px) scale(1.03); }
}
</style>
