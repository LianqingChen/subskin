import { computed, ref } from 'vue'
import { fetchHospitals, createHospital as createHospitalApi } from '@/api/hospital'
import { HOSPITALS, HOSPITAL_CITIES } from '@/data/hospitals'
import { CITIES } from '@/data/cities'
import { EMPTY_STATS, type HospitalCreatePayload, type HospitalView } from '@/types/hospital'

/**
 * 医院目录：优先后端 `/api/hospitals`（含病友补充条目与评价统计），
 * 请求失败时退化为随包静态目录，保证 PWA 离线或后端异常时地图与列表仍可用。
 */

const cityCoordMap = new Map<string, { lat: number; lng: number }>()
for (const city of CITIES) cityCoordMap.set(city.name, { lat: city.lat, lng: city.lng })
for (const city of HOSPITAL_CITIES) cityCoordMap.set(city.name, { lat: city.lat, lng: city.lng })

const officialSeedMap = new Map(HOSPITALS.map(h => [h.id, h]))

// 静态兜底中出现的城市，同样并入坐标表（含旧城市表遗漏的地级市首府）
const fallbackHospitals: HospitalView[] = HOSPITALS.map(h => {
  const coord = cityCoordMap.get(h.city)
  return {
    key: h.id, id: null, slug: h.id, name: h.name, province: h.province, city: h.city,
    district: h.district ?? '', address: h.address ?? '', department: h.department, kind: h.kind, features: h.features,
    summary: h.summary, source: h.source, checkedAt: h.checkedAt, origin: 'official',
    lat: h.lat ?? coord?.lat ?? null, lng: h.lng ?? coord?.lng ?? null, stats: { ...EMPTY_STATS },
  }
})

export function cityCoords(city: string) {
  return cityCoordMap.get(city) ?? null
}

export function useHospitalRegistry() {
  const hospitals = ref<HospitalView[]>(fallbackHospitals)
  const offline = ref(false)
  const loading = ref(true)
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const result = await fetchHospitals()
      if (result.items.length) {
        hospitals.value = result.items.map(item => {
          const seed = officialSeedMap.get(item.slug)
          const coord = cityCoordMap.get(item.city)
          return {
            ...item,
            district: item.district || seed?.district || '',
            address: item.address || seed?.address || '',
            lat: item.lat ?? seed?.lat ?? coord?.lat ?? null,
            lng: item.lng ?? seed?.lng ?? coord?.lng ?? null,
          }
        })
        offline.value = false
      }
    } catch {
      // 后端不可用：保留静态目录，页面顶部给出「离线目录」提示而不是空白页
      offline.value = true
      error.value = '目录服务暂时不可用，正在展示随包离线目录。'
    } finally {
      loading.value = false
    }
  }

  async function create(payload: HospitalCreatePayload) {
    const created = await createHospitalApi(payload)
    hospitals.value = [...hospitals.value.filter(h => h.key !== created.key), created]
    return created
  }

  /** 病友补充条目在列表末尾集中展示前，先按官方优先排序 */
  const sorted = computed(() => [...hospitals.value].sort((a, b) => {
    if (a.origin !== b.origin) return a.origin === 'official' ? -1 : 1
    return b.stats.reviewCount - a.stats.reviewCount
  }))

  const provinces = computed(() => [...new Set(hospitals.value.map(h => h.province))])
  const reviewTotal = computed(() => hospitals.value.reduce((sum, h) => sum + h.stats.reviewCount, 0))
  const communityTotal = computed(() => hospitals.value.filter(h => h.origin === 'community').length)

  return { hospitals: sorted, offline, loading, error, load, create, provinces, reviewTotal, communityTotal }
}
