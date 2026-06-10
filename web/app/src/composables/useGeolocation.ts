/**
 * 地理位置 composable
 * 获取用户所在城市，缓存到 localStorage
 */
import { ref } from 'vue'

const CACHE_KEY = 'subskin_user_city'
const CACHE_DURATION = 24 * 60 * 60 * 1000 // 24 小时

interface CityCache {
  city: string
  timestamp: number
}

const city = ref<string | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const permissionDenied = ref(false)

function getCachedCity(): string | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const cached: CityCache = JSON.parse(raw)
    if (Date.now() - cached.timestamp > CACHE_DURATION) {
      localStorage.removeItem(CACHE_KEY)
      return null
    }
    return cached.city
  } catch {
    return null
  }
}

function setCachedCity(c: string) {
  const data: CityCache = { city: c, timestamp: Date.now() }
  localStorage.setItem(CACHE_KEY, JSON.stringify(data))
}

export function useGeolocation() {
  async function requestCity(): Promise<string | null> {
    // 检查缓存
    const cached = getCachedCity()
    if (cached) {
      city.value = cached
      return cached
    }

    // 检查浏览器支持
    if (!navigator.geolocation) {
      error.value = '浏览器不支持定位'
      return null
    }

    loading.value = true
    error.value = null

    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: false,
          timeout: 10000,
          maximumAge: 300000, // 5 分钟缓存
        })
      })

      const { latitude, longitude } = pos.coords
      const cityName = await reverseGeocode(latitude, longitude)

      if (cityName) {
        city.value = cityName
        setCachedCity(cityName)
        return cityName
      } else {
        error.value = '无法识别所在城市'
        return null
      }
    } catch (err: any) {
      if (err.code === err.PERMISSION_DENIED) {
        permissionDenied.value = true
        error.value = '定位权限被拒绝'
      } else if (err.code === err.TIMEOUT) {
        error.value = '定位超时'
      } else {
        error.value = '定位失败'
      }
      return null
    } finally {
      loading.value = false
    }
  }

  function reset() {
    city.value = null
    error.value = null
    loading.value = false
    permissionDenied.value = false
    localStorage.removeItem(CACHE_KEY)
  }

  return { city, loading, error, permissionDenied, requestCity, reset }
}

/**
 * 经纬度 → 城市名（使用 Nominatim）
 * 缓存请求结果避免 API 限速
 */
const geocodeCache = new Map<string, string>()

async function reverseGeocode(lat: number, lng: number): Promise<string | null> {
  const key = `${lat.toFixed(2)},${lng.toFixed(2)}`
  if (geocodeCache.has(key)) return geocodeCache.get(key)!

  try {
    const resp = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=10&accept-language=zh`,
      {
        headers: { 'User-Agent': 'SubSkin/1.0' },
      }
    )
    if (!resp.ok) return null

    const data = await resp.json()
    const address = data?.address
    // 优先取城市，其次取省份
    let cityName = address?.city || address?.town || address?.county || address?.state || null

    if (cityName) {
      // 去掉"市"后缀
      cityName = cityName.replace(/市$/, '')
      geocodeCache.set(key, cityName)
    }
    return cityName
  } catch {
    return null
  }
}
