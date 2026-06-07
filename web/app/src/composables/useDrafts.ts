import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { communityApi } from '@/api/community'

export interface DraftItem {
  key: string
  type: 'image' | 'video' | 'text' | 'long'
  typeName: string
  icon: string
  title: string
  content: string
  contentJson?: string | null
  images: string[]
  tags?: string[]
  categoryId?: number | null
  mood?: string
  isPrivate?: boolean
  isAnonymous?: boolean
  showCity?: boolean
  timestamp: number
  serverId?: number
  expiresAt?: number
  expiringSoon?: boolean
}

const TYPE_META: Record<string, { typeName: string; icon: string }> = {
  image: { typeName: '图文', icon: 'ri-camera-line' },
  video: { typeName: '视频', icon: 'ri-video-line' },
  text: { typeName: '文字', icon: 'ri-edit-line' },
  long: { typeName: '长文', icon: 'ri-file-edit-line' },
}

const DRAFT_PREFIX = 'community-draft-'
const MAX_AGE = 30 * 24 * 60 * 60 * 1000

const drafts = ref<DraftItem[]>([])
const draftCount = computed(() => drafts.value.length)
const hasDrafts = computed(() => drafts.value.length > 0)
let _syncPromise: Promise<void> | null = null

function getDraftKeys(): string[] {
  const keys: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i)
    if (k && k.startsWith(DRAFT_PREFIX)) keys.push(k)
  }
  return keys
}

function parseDraft(key: string): DraftItem | null {
  const raw = localStorage.getItem(key)
  if (!raw) return null
  try {
    const d = JSON.parse(raw)
    if (Date.now() - (d.timestamp || 0) > MAX_AGE) {
      localStorage.removeItem(key)
      return null
    }
    const typeGuess = key.replace(DRAFT_PREFIX, '').split('-')[0]
    const type = (d.type || typeGuess || 'long') as DraftItem['type']
    const meta = TYPE_META[type] || TYPE_META.long
    return {
      key,
      type,
      typeName: meta.typeName,
      icon: meta.icon,
      title: d.title || '',
      content: d.content || '',
      contentJson: d.contentJson || null,
      images: d.images || [],
      tags: d.tags || [],
      categoryId: d.categoryId || null,
      mood: d.mood || '',
      isPrivate: d.isPrivate ?? false,
      isAnonymous: d.isAnonymous ?? false,
      showCity: d.showCity ?? true,
      timestamp: d.timestamp || 0,
      serverId: d.serverId,
    }
  } catch {
    localStorage.removeItem(key)
    return null
  }
}

async function loadServerDrafts(): Promise<DraftItem[]> {
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) return []

  try {
    const res = await communityApi.getMyDiaries(50, 0)
    return res.items
      .filter((p: any) => p.is_private === true)
      .map((p: any) => {
        const expiresAt = p.draft_expires_at ? new Date(p.draft_expires_at).getTime() : undefined
        const sevenDays = 7 * 24 * 60 * 60 * 1000
        const expiringSoon = expiresAt ? (expiresAt - Date.now()) < sevenDays && (expiresAt - Date.now()) > 0 : false
        return {
          key: `${DRAFT_PREFIX}server-${p.id}`,
          type: (p.post_type || 'long') as DraftItem['type'],
          typeName: TYPE_META[p.post_type]?.typeName || '长文',
          icon: TYPE_META[p.post_type]?.icon || 'ri-file-edit-line',
          title: p.title || '',
          content: p.content || '',
          contentJson: p.content_json || null,
          images: (p.images || []).map((img: any) => img.url || ''),
          tags: (p.tags || []).map((t: any) => t.name),
          categoryId: p.category_id || null,
          mood: p.mood || '',
          isPrivate: p.is_private ?? false,
          isAnonymous: p.is_anonymous || false,
          timestamp: new Date(p.created_at).getTime(),
          serverId: p.id,
          expiresAt,
          expiringSoon,
        }
      })
  } catch {
    return []
  }
}

function loadLocalDrafts() {
  const result: DraftItem[] = []
  for (const key of getDraftKeys()) {
    const draft = parseDraft(key)
    if (draft) result.push(draft)
  }
  result.sort((a, b) => b.timestamp - a.timestamp)
  return result
}

function loadDrafts() {
  drafts.value = loadLocalDrafts()
}

function loadDraftsWithSync() {
  if (_syncPromise) return _syncPromise

  _syncPromise = (async () => {
    try {
      const localDrafts = loadLocalDrafts()
      const serverDrafts = await loadServerDrafts()

      const merged = new Map<string, DraftItem>()
      for (const d of serverDrafts) {
        merged.set(`server-${d.serverId}`, d)
      }
      for (const d of localDrafts) {
        if (d.serverId) {
          if (merged.has(`server-${d.serverId}`)) continue
        }
        const isDup = serverDrafts.some(
          sd => sd.title === d.title && Math.abs(sd.timestamp - d.timestamp) < 60000
        )
        if (!isDup) {
          merged.set(`local-${d.key}`, d)
        }
      }

      const mergedList = Array.from(merged.values())
      mergedList.sort((a, b) => b.timestamp - a.timestamp)
      drafts.value = mergedList
    } finally {
      _syncPromise = null
    }
  })()

  return _syncPromise
}

function saveDraft(data: {
  type: DraftItem['type']
  title: string
  content: string
  contentJson?: string | null
  images?: string[]
  tags?: string[]
  categoryId?: number | null
  mood?: string
  isPrivate?: boolean
  isAnonymous?: boolean
  showCity?: boolean
  existingKey?: string
}) {
  const ts = Date.now()
  const key = data.existingKey || `${DRAFT_PREFIX}${data.type}-${ts}`
  const payload = {
    type: data.type,
    title: data.title,
    content: data.content,
    contentJson: data.contentJson || null,
    images: data.images || [],
    tags: data.tags || [],
    categoryId: data.categoryId || null,
    mood: data.mood || '',
    isPrivate: data.isPrivate ?? false,
    isAnonymous: data.isAnonymous ?? false,
    showCity: data.showCity ?? true,
    timestamp: ts,
  }
  localStorage.setItem(key, JSON.stringify(payload))
  return key
}

async function syncDraftToServer(data: {
  type: DraftItem['type']
  title: string
  content: string
  contentJson?: string | null
  images?: string[]
  tags?: string[]
  categoryId?: number | null
  mood?: string
  isPrivate?: boolean
  isAnonymous?: boolean
  existingKey?: string
  serverId?: number
}) {
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) return null

  try {
    if (data.serverId) {
      await communityApi.updatePost(data.serverId, {
        title: data.title,
        content: data.content,
        content_json: data.contentJson || undefined,
        is_private: data.isPrivate ?? true,
        post_type: data.type,
        tag_names: data.tags && data.tags.length > 0 ? data.tags : undefined,
        category_id: data.categoryId ?? undefined,
        mood: data.mood || undefined,
        is_anonymous: data.isAnonymous ?? undefined,
        images: data.images && data.images.length > 0 ? data.images : undefined,
      })
      return data.serverId
    } else {
      const post = await communityApi.createPost({
        title: data.title || '未命名草稿',
        content: data.content,
        content_json: data.contentJson || undefined,
        post_type: data.type,
        is_private: data.isPrivate ?? true,
        category_id: data.categoryId ?? 1,
        tag_names: data.tags && data.tags.length > 0 ? data.tags : undefined,
        mood: data.mood || undefined,
        is_anonymous: data.isAnonymous ?? undefined,
        images: data.images && data.images.length > 0 ? data.images : undefined,
      })
      return post.id
    }
  } catch {
    return null
  }
}

async function saveDraftWithSync(data: {
  type: DraftItem['type']
  title: string
  content: string
  contentJson?: string | null
  images?: string[]
  tags?: string[]
  categoryId?: number | null
  mood?: string
  isPrivate?: boolean
  isAnonymous?: boolean
  showCity?: boolean
  existingKey?: string
  serverId?: number
}) {
  const key = saveDraft(data)

  // Capture serverId from sync so publish can update instead of duplicate
  syncDraftToServer(data).then((serverId) => {
    if (serverId && !data.serverId) {
      const raw = localStorage.getItem(key)
      if (raw) {
        try {
          const d = JSON.parse(raw)
          d.serverId = serverId
          localStorage.setItem(key, JSON.stringify(d))
        } catch {}
      }
    }
  }).catch(() => {})

  return key
}

function deleteDraft(key: string) {
  const draft = drafts.value.find(d => d.key === key)
  localStorage.removeItem(key)
  drafts.value = drafts.value.filter(d => d.key !== key)

  if (draft?.serverId) {
    const authStore = useAuthStore()
    if (authStore.isLoggedIn) {
      communityApi.deletePost(draft.serverId).catch(() => {})
    }
  }
}

function clearAllDrafts() {
  for (const d of drafts.value) {
    localStorage.removeItem(d.key)
    if (d.serverId) {
      const authStore = useAuthStore()
      if (authStore.isLoggedIn) {
        communityApi.deletePost(d.serverId).catch(() => {})
      }
    }
  }
  drafts.value = []
}

export function useDrafts() {
  return {
    drafts, draftCount, hasDrafts,
    loadDrafts, loadDraftsWithSync,
    saveDraft, saveDraftWithSync,
    deleteDraft, clearAllDrafts,
  }
}
