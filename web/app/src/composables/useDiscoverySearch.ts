import { nextTick, onUnmounted, ref, type Ref } from 'vue'
import { communityApi } from '@/api/community'
import type { PostTag } from '@/types'

export function useDiscoverySearch(searchQuery: Ref<string>, reload: () => Promise<void>) {
  const showSearch = ref(false)
  const searchInputRef = ref<HTMLInputElement | null>(null)
  const tagSuggestions = ref<PostTag[]>([])
  const showSuggestions = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  let blurTimer: ReturnType<typeof setTimeout> | undefined
  let generation = 0
  async function suggest() {
    const current = ++generation
    const query = searchQuery.value.trim()
    if (!query) { tagSuggestions.value = []; showSuggestions.value = false; return }
    try {
      const tags = await communityApi.getTags({ q: query, limit: 6 })
      if (current !== generation || query !== searchQuery.value.trim()) return
      tagSuggestions.value = tags
      showSuggestions.value = tags.length > 0
    } catch (error) {
      if (current !== generation) return
      console.error('Failed to suggest discovery tags:', error)
      tagSuggestions.value = []; showSuggestions.value = false
    }
  }
  function onSearchInput() { clearTimeout(timer); timer = setTimeout(suggest, 200) }
  async function handleSearch() { generation++; showSuggestions.value = false; await reload() }
  async function clearSearch() { searchQuery.value = ''; tagSuggestions.value = []; await handleSearch() }
  function selectTagSuggestion(tag: PostTag) { searchQuery.value = tag.name; void handleSearch() }
  function onSearchBlur() { blurTimer = setTimeout(() => { showSuggestions.value = false }, 200) }
  async function toggleSearch() {
    showSearch.value = !showSearch.value
    if (showSearch.value) { await nextTick(); searchInputRef.value?.focus() }
  }
  onUnmounted(() => { generation++; clearTimeout(timer); clearTimeout(blurTimer) })
  return { showSearch, searchInputRef, tagSuggestions, showSuggestions, onSearchInput, handleSearch, clearSearch, selectTagSuggestion, onSearchBlur, toggleSearch }
}
