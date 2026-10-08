import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { trackClick } from '@/composables/useTracking'
import { CARE_ITEM_INDEX } from '@/data/care-catalog'

/**
 * 「调养」购物车：仅保存在本机（按账号分开），不上传；购买跳转外部链接，站内不下单。
 * 状态为模块级单例，商品卡片、详情页、购物车抽屉共享同一份。
 * 加购/移除会记埋点，作为需求信号。
 */
const MAX_QTY = 9
const qtyById = ref<Record<string, number>>({})
const open = ref(false)
let loadedKey = ''
let readable = true

function parseCart(raw: string): Record<string, number> {
  const parsed: unknown = JSON.parse(raw)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Invalid cart')
  const next: Record<string, number> = {}
  for (const [id, qty] of Object.entries(parsed as Record<string, unknown>)) {
    if (id in CARE_ITEM_INDEX && typeof qty === 'number' && qty >= 1) next[id] = Math.min(Math.floor(qty), MAX_QTY)
  }
  return next
}

export function useCareCart() {
  const auth = useAuthStore()
  const toast = useToast()
  const uid = () => auth.user?.id ?? 'guest'
  const key = computed(() => `subskin-care-cart-v1:${uid()}`)

  watch(key, (k) => {
    if (k === loadedKey) return
    loadedKey = k
    qtyById.value = {}
    readable = true
    try {
      const raw = localStorage.getItem(k)
      if (raw) { qtyById.value = parseCart(raw); return }
      // 迁移旧版「想要清单」（数组）：每件按 1 份放入购物车
      const legacy = localStorage.getItem(`subskin-care-wish-v1:${uid()}`)
      if (legacy) {
        const ids: unknown = JSON.parse(legacy)
        if (Array.isArray(ids)) qtyById.value = Object.fromEntries(ids.filter((id): id is string => typeof id === 'string' && id in CARE_ITEM_INDEX).map(id => [id, 1]))
      }
    } catch {
      readable = false
      toast.warning('本机购物清单暂时无法读取，原内容未删除。')
    }
  }, { immediate: true, flush: 'sync' })

  function persist(next: Record<string, number>): boolean {
    if (!readable) { toast.error('原购物清单无法读取，为避免覆盖，暂不保存。'); return false }
    try { localStorage.setItem(key.value, JSON.stringify(next)); qtyById.value = next; return true }
    catch { toast.error('浏览器未能保存，请检查存储空间或隐私模式。'); return false }
  }

  const qty = (id: string) => qtyById.value[id] ?? 0
  function add(id: string) {
    if (!(id in CARE_ITEM_INDEX)) return
    if (qty(id) >= MAX_QTY) { toast.warning(`同一商品最多 ${MAX_QTY} 件`); return }
    if (!persist({ ...qtyById.value, [id]: qty(id) + 1 })) return
    const { item, topic } = CARE_ITEM_INDEX[id]
    trackClick('care_cart_add', item.name, { item: id, topic: topic.id })
    toast.success('已加入本机购物清单')
  }
  function setQty(id: string, n: number) {
    if (!(id in qtyById.value)) return
    if (n < 1) return remove(id)
    persist({ ...qtyById.value, [id]: Math.min(n, MAX_QTY) })
  }
  function remove(id: string) {
    if (!(id in qtyById.value)) return
    const { [id]: _removed, ...rest } = qtyById.value
    if (!persist(rest)) return
    const info = CARE_ITEM_INDEX[id]
    if (info) trackClick('care_cart_remove', info.item.name, { item: id, topic: info.topic.id })
  }
  function clear() { persist({}) }

  const lines = computed(() => Object.entries(qtyById.value)
    .filter(([id]) => id in CARE_ITEM_INDEX)
    .map(([id, n]) => ({ ...CARE_ITEM_INDEX[id], qty: n })))
  const count = computed(() => lines.value.reduce((sum, line) => sum + line.qty, 0))
  /** 仅统计已标价的商品；存在未标价商品时 partial 为 true */
  const total = computed(() => {
    const priced = lines.value.filter(line => line.item.price !== undefined)
    return {
      amount: priced.reduce((sum, line) => sum + (line.item.price as number) * line.qty, 0),
      partial: priced.length !== lines.value.length,
      any: priced.length > 0,
    }
  })
  return { open, qty, add, setQty, remove, clear, lines, count, total, maxQty: MAX_QTY }
}
