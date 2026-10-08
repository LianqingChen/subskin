<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { formatPrice } from '@/data/care-catalog'
import { useCareCart } from '@/composables/useCareCart'
import { trackClick } from '@/composables/useTracking'

const cart = useCareCart()
const dialog = ref<HTMLDialogElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const unpriced = computed(() => cart.lines.value.filter(line => line.item.price === undefined).reduce((sum, line) => sum + line.qty, 0))
let previousOverflow: string | undefined
function restoreScroll() {
  if (previousOverflow !== undefined) { document.body.style.overflow = previousOverflow; previousOverflow = undefined }
}
function close() { cart.open.value = false; dialog.value?.close(); restoreScroll() }
function trapTab(event: KeyboardEvent) {
  const controls = Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input, select, textarea, [tabindex="0"]') ?? []).filter(element => element.getClientRects().length)
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (!first || !last) return
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
watch(cart.open, async isOpen => {
  if (!isOpen) { dialog.value?.close(); restoreScroll(); return }
  await nextTick()
  if (!cart.open.value || !dialog.value) return
  if (previousOverflow === undefined) previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  // Native modal dialog handles focus trapping, Escape and making the background inert.
  dialog.value.showModal()
  closeButton.value?.focus()
  trackClick('care_cart_open', '打开购物清单', { count: cart.count.value })
})
onBeforeUnmount(close)
onDeactivated(close)
</script>

<template>
  <Teleport to="body">
    <dialog v-if="cart.open.value" ref="dialog" class="fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none border-0 bg-transparent p-0 text-gray-900 dark:text-gray-100" aria-label="购物清单" @cancel.prevent="close" @close="close" @keydown.tab="trapTab">
      <div class="flex h-full items-end justify-center bg-black/40 md:items-stretch md:justify-end" @click.self="close">
        <div class="relative flex max-h-[85dvh] w-full max-w-lg flex-col rounded-t-2xl bg-white shadow-xl dark:bg-gray-800 md:h-full md:max-h-none md:max-w-md md:rounded-none">
          <header class="border-b border-gray-100 px-4 py-3 dark:border-gray-700">
            <div class="flex items-center gap-2">
              <h2 class="min-w-0 flex-1 text-base font-semibold">购物清单 <span class="text-xs font-normal text-gray-500 dark:text-gray-400">{{ cart.count.value }} 件</span></h2>
              <button v-if="cart.lines.value.length" type="button" class="min-h-11 px-2 text-xs text-gray-500 dark:text-gray-400" @click="cart.clear()">清空</button>
              <button ref="closeButton" type="button" class="flex h-11 w-11 items-center justify-center rounded-lg text-xl text-gray-500 focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-gray-400" aria-label="关闭购物清单" @click="close"><i class="ri-close-line" aria-hidden="true"></i></button>
            </div>
            <p class="text-xs leading-5 text-gray-500 dark:text-gray-400">仅保存在此设备，按账号分开，不是订单或已提交的需求。</p>
          </header>
          <div class="min-h-0 flex-1 overflow-y-auto px-4">
            <div v-if="!cart.lines.value.length" class="py-12 text-center text-sm text-gray-500 dark:text-gray-400"><i class="ri-shopping-bag-3-line mb-3 block text-4xl" aria-hidden="true"></i>清单还是空的，先看看需要哪些用品。</div>
            <ul v-else class="divide-y divide-gray-100 dark:divide-gray-700">
              <li v-for="line in cart.lines.value" :key="line.item.id" class="flex gap-3 py-4">
                <router-link :to="`/care/${line.item.id}`" class="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-gray-50 text-2xl text-primary-700 no-underline dark:bg-gray-900/50 dark:text-primary-300" :aria-label="`查看${line.item.name}详情`" @click="close"><i :class="line.topic.icon" aria-hidden="true"></i></router-link>
                <div class="min-w-0 flex-1">
                  <div class="flex items-start gap-1">
                    <router-link :to="`/care/${line.item.id}`" class="min-h-11 min-w-0 flex-1 text-sm font-medium leading-6 text-gray-900 no-underline dark:text-gray-100" @click="close">{{ line.item.name }}</router-link>
                    <button type="button" class="-mt-2 flex h-11 w-11 shrink-0 items-center justify-center text-gray-500 dark:text-gray-400" :aria-label="`移除${line.item.name}`" @click="cart.remove(line.item.id)"><i class="ri-delete-bin-line" aria-hidden="true"></i></button>
                  </div>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{{ line.topic.title }}<template v-if="line.item.spec"> · {{ line.item.spec }}</template></p>
                  <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
                    <span class="text-xs text-gray-600 dark:text-gray-300">{{ line.item.price !== undefined ? formatPrice(line.item) : line.item.status === 'planned' ? '筹备中' : '选购参考' }}</span>
                    <div class="flex items-center gap-1">
                      <button type="button" class="flex h-11 w-11 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-600" :aria-label="`减少${line.item.name}`" @click="cart.setQty(line.item.id, line.qty - 1)"><i class="ri-subtract-line" aria-hidden="true"></i></button>
                      <span class="w-5 text-center text-sm tabular-nums" aria-live="polite">{{ line.qty }}</span>
                      <button type="button" class="flex h-11 w-11 items-center justify-center rounded-lg bg-primary-600 text-white disabled:cursor-not-allowed disabled:opacity-40" :disabled="line.qty >= cart.maxQty" :aria-label="`增加${line.item.name}`" @click="cart.add(line.item.id)"><i class="ri-add-line" aria-hidden="true"></i></button>
                    </div>
                  </div>
                  <a v-if="line.item.buyUrl && line.item.status !== 'planned'" :href="line.item.buyUrl" target="_blank" rel="noopener noreferrer sponsored" class="mt-2 inline-flex min-h-11 items-center gap-1 text-xs text-primary-700 no-underline dark:text-primary-300" @click="trackClick('care_item_buy', line.item.name, { item: line.item.id, topic: line.topic.id, from: 'cart' })">去商家购买 · 推广<i class="ri-external-link-line" aria-hidden="true"></i></a>
                  <p v-else class="mt-2 text-xs text-gray-500 dark:text-gray-400">{{ line.item.status === 'planned' ? '暂未发售' : '未接入购买，可查看选购要点' }}</p>
                </div>
              </li>
            </ul>
          </div>
          <footer class="border-t border-gray-100 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] dark:border-gray-700">
            <div v-if="cart.total.value.any" class="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm"><span class="text-gray-500 dark:text-gray-400">已标价条目参考合计</span><span class="font-semibold text-primary-700 dark:text-primary-300">¥{{ cart.total.value.amount.toFixed(2) }}</span></div>
            <p v-if="cart.total.value.any && unpriced" class="mb-1 text-xs text-gray-500 dark:text-gray-400">另有 {{ unpriced }} 件未标价，未计入参考合计。</p>
            <p class="text-xs leading-5 text-gray-500 dark:text-gray-400">站内不收款、不下单。有链接的用品由商家完成购买与售后，价格和库存以商家为准。食品和用品不能替代治疗。</p>
          </footer>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
dialog::backdrop { background: transparent; }
</style>
