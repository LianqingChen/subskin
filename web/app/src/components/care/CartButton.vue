<script setup lang="ts">
import { useCareCart } from '@/composables/useCareCart'
const cart = useCareCart()
</script>

<template>
  <button type="button" class="flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-3 text-sm text-gray-700 focus-visible:ring-2 focus-visible:ring-primary-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200" :aria-label="`购物清单，${cart.count.value} 件`" data-track-id="care_cart_button" @click="cart.open.value = true">
    <i class="ri-shopping-bag-3-line text-lg" aria-hidden="true"></i><span>购物清单</span>
    <span v-if="cart.count.value" class="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary-600 px-1 text-[11px] font-semibold text-white">{{ cart.count.value }}</span>
  </button>
</template>
