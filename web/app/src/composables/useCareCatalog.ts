import { computed, ref } from 'vue'
import { CARE_TOPICS } from '@/data/care-catalog'

const TOPIC_ORDER = ['sun', 'food', 'nutrition', 'copper', 'tools']

export function useCareCatalog() {
  const active = ref('all')
  const query = ref('')
  const sort = ref<'default' | 'name'>('default')
  const topics = [...CARE_TOPICS].sort((a, b) => TOPIC_ORDER.indexOf(a.id) - TOPIC_ORDER.indexOf(b.id))
  const allItems = topics.flatMap(topic => topic.items.map(item => ({ item, topic })))
  const categories = [
    { id: 'all', title: '全部用品', icon: 'ri-apps-2-line', count: allItems.length },
    ...topics.map(topic => ({ id: topic.id, title: topic.title, icon: topic.icon, count: topic.items.length })),
  ]
  const items = computed(() => {
    const q = query.value.trim().toLocaleLowerCase()
    const result = allItems.filter(({ item, topic }) =>
      (active.value === 'all' || topic.id === active.value) &&
      (!q || `${item.name} ${item.why} ${item.spec ?? ''} ${topic.title}`.toLocaleLowerCase().includes(q)))
    return result.sort((a, b) => sort.value === 'name'
      ? a.item.name.localeCompare(b.item.name, 'zh-CN')
      : Number(a.item.status === 'planned') - Number(b.item.status === 'planned'))
  })
  const activeTitle = computed(() => categories.find(category => category.id === active.value)?.title ?? '全部用品')
  function reset() { active.value = 'all'; query.value = ''; sort.value = 'default' }
  return { active, query, sort, categories, items, activeTitle, reset }
}
