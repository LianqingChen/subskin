import { computed, ref, watch } from 'vue'
import { PROVINCES } from '@/data/cities'
import { useToast } from '@/composables/useToast'
import type { HospitalNotebook, HospitalView, ReviewTarget } from '@/types/hospital'
import type { Ref } from 'vue'

/**
 * 就医经验目录筛选：省份 → 城市 → 区县/具体地址 + 关键词，并管理当前选中医院与对比列表。
 * 目录数据来自 useHospitalRegistry（后端目录 + 离线兜底）。
 */
export function useHospitalDirectory(hospitals: Ref<HospitalView[]>, notebook: Ref<HospitalNotebook>) {
  const query = ref('')
  const province = ref('')
  const city = ref('')
  const district = ref('')
  const feature = ref('')
  const target = ref<ReviewTarget | ''>('')
  const onlyMarked = ref(false)
  const onlyReviewed = ref(false)
  const selectedKey = ref('')
  const comparisonKeys = ref<string[]>([])
  const toast = useToast()

  const provinces = computed(() => {
    const fromDirectory = hospitals.value.map(h => h.province)
    const fromCityTable = PROVINCES.map(p => p.name)
    return [...new Set([...fromDirectory, ...fromCityTable])]
  })
  const cities = computed(() => {
    const existing = PROVINCES.find(p => p.name === province.value)?.cities ?? []
    const collected = hospitals.value.filter(h => h.province === province.value).map(h => h.city)
    return [...new Set([...collected, ...existing.map(c => c.name)])]
  })
  const districts = computed(() => {
    const list = hospitals.value
      .filter(h => h.province === province.value && (!city.value || h.city === city.value))
      .map(h => h.district)
      .filter(Boolean)
    return [...new Set(list)]
  })
  const features = computed(() => [...new Set(hospitals.value.flatMap(h => h.features))])

  const filtered = computed(() => hospitals.value.filter(h => {
    const words = query.value.trim().toLowerCase().split(/\s+/).filter(Boolean)
    const text = [h.name, h.province, h.city, h.district, h.address, h.department, ...h.features].join(' ').toLowerCase()
    return words.every(word => text.includes(word))
      && (!province.value || h.province === province.value)
      && (!city.value || h.city === city.value)
      && (!district.value.trim() || [h.district, h.address, h.name].join(' ').includes(district.value.trim()))
      && (!feature.value || h.features.includes(feature.value))
      && (!onlyMarked.value || Boolean(notebook.value.marks[h.key]))
      && (!onlyReviewed.value || h.stats.reviewCount > 0)
  }))

  const selected = computed(() => hospitals.value.find(h => h.key === selectedKey.value) ?? null)
  const compared = computed(() => hospitals.value.filter(h => comparisonKeys.value.includes(h.key)))
  const coverage = computed(() => new Set(hospitals.value.map(h => h.province)).size)
  const cityCount = computed(() => new Set(hospitals.value.map(h => h.city)).size)
  const withReviews = computed(() => hospitals.value.filter(h => h.stats.reviewCount > 0).length)

  watch(province, () => { city.value = ''; district.value = '' }, { flush: 'sync' })
  watch(city, () => { district.value = '' }, { flush: 'sync' })

  function reset() {
    query.value = ''; province.value = ''; city.value = ''; district.value = ''
    feature.value = ''; onlyMarked.value = false; onlyReviewed.value = false
  }
  function selectRegion(name: string) {
    const found = PROVINCES.find(p => name.startsWith(p.name))
    if (found) { province.value = found.name; city.value = ''; district.value = '' }
  }
  function selectCity(name: string) {
    const hospital = hospitals.value.find(h => h.city === name)
    province.value = hospital?.province ?? province.value
    city.value = name
    district.value = ''
  }
  function select(hospital: HospitalView | null) {
    selectedKey.value = hospital?.key ?? ''
  }
  function compare(key: string) {
    if (comparisonKeys.value.includes(key)) comparisonKeys.value = comparisonKeys.value.filter(x => x !== key)
    else if (comparisonKeys.value.length < 3) comparisonKeys.value = [...comparisonKeys.value, key]
    else toast.warning('最多同时对比 3 家医院，请先移除一家。')
  }

  return { query, province, city, district, feature, target, onlyMarked, onlyReviewed, selectedKey,
    comparisonKeys, provinces, cities, districts, features, filtered, selected, compared, coverage,
    cityCount, withReviews, total: computed(() => hospitals.value.length), reset, selectRegion,
    selectCity, select, compare }
}
