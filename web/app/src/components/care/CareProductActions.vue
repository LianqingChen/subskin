<script setup lang="ts">
import { type CareItem, type CareTopic } from '@/data/care-catalog'
import { useCareCart } from '@/composables/useCareCart'
import { trackClick } from '@/composables/useTracking'
defineProps<{ item: CareItem; topic: CareTopic }>()
const cart = useCareCart()
function showSelection() { document.getElementById('care-selection')?.scrollIntoView({ block: 'start' }) }
</script>
<template>
  <div class="flex items-center gap-2">
    <button type="button" class="min-h-11 min-w-0 flex-1 rounded-xl border border-primary-600 px-3 text-sm font-medium text-primary-700 focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-primary-300" :disabled="cart.qty(item.id) >= cart.maxQty" @click="cart.add(item.id)">加入清单<template v-if="cart.qty(item.id)">（{{ cart.qty(item.id) }}）</template></button>
    <a v-if="item.buyUrl && item.status !== 'planned'" :href="item.buyUrl" target="_blank" rel="noopener noreferrer sponsored" class="inline-flex min-h-11 min-w-0 flex-1 items-center justify-center gap-1 rounded-xl bg-primary-600 px-3 text-sm font-medium text-white no-underline focus-visible:ring-2 focus-visible:ring-primary-400" @click="trackClick('care_item_buy', item.name, { item: item.id, topic: topic.id, from: 'detail' })">去商家购买<i class="ri-external-link-line" aria-hidden="true"></i></a>
    <button v-else type="button" class="min-h-11 min-w-0 flex-1 rounded-xl bg-primary-600 px-3 text-sm font-medium text-white focus-visible:ring-2 focus-visible:ring-primary-400" @click="showSelection">查看选购要点</button>
  </div>
</template>
