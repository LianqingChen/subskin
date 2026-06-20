import { ref } from 'vue'

const CACHE_KEY = 'subskin_user_city'
const CACHE_DURATION = 24 * 60 * 60 * 1000

interface CityCache {
  city: string
  lat: number | null
  lng: number | null
  source: 'ip' | 'gps' | 'manual'
  timestamp: number
}

const GEOCODE_CACHE_KEY = 'subskin_geocode_cache'
const GEOCODE_CACHE_DURATION = 7 * 24 * 60 * 60 * 1000

interface GeocodeCacheEntry {
  city: string
  timestamp: number
}

const city = ref<string | null>(null)
const lat = ref<number | null>(null)
const lng = ref<number | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const permissionDenied = ref(false)
const upgrading = ref(false)

function getCachedCity(): CityCache | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const cached: CityCache = JSON.parse(raw)
    if (Date.now() - cached.timestamp > CACHE_DURATION) {
      localStorage.removeItem(CACHE_KEY)
      return null
    }
    return cached
  } catch {
    return null
  }
}

function setCachedCity(c: string, source: 'ip' | 'gps' | 'manual' = 'manual', latVal: number | null = null, lngVal: number | null = null) {
  const data: CityCache = { city: c, lat: latVal, lng: lngVal, source, timestamp: Date.now() }
  localStorage.setItem(CACHE_KEY, JSON.stringify(data))
}

function loadGeocodeCache(): Map<string, GeocodeCacheEntry> {
  try {
    const raw = localStorage.getItem(GEOCODE_CACHE_KEY)
    if (!raw) return new Map()
    const entries: [string, GeocodeCacheEntry][] = JSON.parse(raw)
    const now = Date.now()
    const valid = entries.filter(([, v]) => now - v.timestamp < GEOCODE_CACHE_DURATION)
    return new Map(valid)
  } catch {
    return new Map()
  }
}

function saveGeocodeCache(cache: Map<string, GeocodeCacheEntry>) {
  const entries = Array.from(cache.entries()).slice(-100)
  localStorage.setItem(GEOCODE_CACHE_KEY, JSON.stringify(entries))
}

const geocodeCache = loadGeocodeCache()

async function reverseGeocode(lat: number, lng: number): Promise<string | null> {
  const key = `${lat.toFixed(2)},${lng.toFixed(2)}`
  const cached = geocodeCache.get(key)
  if (cached) return cached.city

  try {
    const resp = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=10&accept-language=zh`,
      { headers: { 'User-Agent': 'SubSkin/1.0' } }
    )
    if (!resp.ok) return null

    const data = await resp.json()
    const address = data?.address
    let cityName = address?.city || address?.town || address?.county || address?.state || null
    if (cityName) {
      cityName = cityName.replace(/市$/, '')
      geocodeCache.set(key, { city: cityName, timestamp: Date.now() })
      saveGeocodeCache(geocodeCache)
    }
    return cityName
  } catch {
    return null
  }
}

async function requestCityByIP(): Promise<{ city: string; latitude: number; longitude: number; region: string } | null> {
  try {
    const resp = await fetch('/api/community/user-location')
    if (!resp.ok) return null
    const data = await resp.json()
    return data.city ? data : null
  } catch {
    return null
  }
}

function getBrowserPosition(): Promise<GeolocationPosition> {
  if (!navigator.geolocation) return Promise.reject(new Error('no_geolocation'))
  return new Promise<GeolocationPosition>((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      timeout: 5000,
      maximumAge: 300000,
    })
  })
}

export function useGeolocation() {
  async function requestCity(): Promise<string | null> {
    const cached = getCachedCity()
    if (cached) {
      city.value = cached.city
      lat.value = cached.lat
      lng.value = cached.lng
      return cached.city
    }

    loading.value = true
    error.value = null

    // Strategy A: IP location first (fast, ~50ms)
    let ipResult: { city: string; latitude: number; longitude: number; region: string } | null = null
    try {
      ipResult = await requestCityByIP()
    } catch { /* IP service unavailable, continue to GPS */ }

    if (ipResult?.city) {
      city.value = ipResult.city
      lat.value = ipResult.latitude
      lng.value = ipResult.longitude
      setCachedCity(ipResult.city, 'ip', ipResult.latitude, ipResult.longitude)
      loading.value = false

      // Strategy E: Async GPS upgrade (non-blocking)
      upgradeToGPS()
      return ipResult.city
    }

    // Fallback: browser GPS geolocation (blocking, slower)
    try {
      const pos = await getBrowserPosition()
      const { latitude: gpsLat, longitude: gpsLng } = pos.coords
      lat.value = gpsLat
      lng.value = gpsLng
      const cityName = await reverseGeocode(gpsLat, gpsLng)
      if (cityName) {
        city.value = cityName
        setCachedCity(cityName, 'gps', gpsLat, gpsLng)
        return cityName
      }
      error.value = '无法识别所在城市'
      return null
    } catch (err: any) {
      if (err.code === err.PERMISSION_DENIED) {
        permissionDenied.value = true
        error.value = '定位权限被拒绝'
      } else if (err.code === err.TIMEOUT) {
        error.value = '定位超时'
      } else if (err.message === 'no_geolocation') {
        error.value = '浏览器不支持定位'
      } else {
        error.value = '定位失败'
      }
      return null
    } finally {
      loading.value = false
    }
  }

  function upgradeToGPS() {
    if (upgrading.value) return
    upgrading.value = true
    getBrowserPosition()
      .then(async (pos) => {
        const { latitude: gpsLat, longitude: gpsLng } = pos.coords
        const gpsCity = await reverseGeocode(gpsLat, gpsLng)
        if (gpsCity && gpsCity !== city.value) {
          city.value = gpsCity
          lat.value = gpsLat
          lng.value = gpsLng
          setCachedCity(gpsCity, 'gps', gpsLat, gpsLng)
        } else if (gpsCity) {
          lat.value = gpsLat
          lng.value = gpsLng
          setCachedCity(gpsCity, 'gps', gpsLat, gpsLng)
        }
      })
      .catch(() => { /* GPS upgrade failed silently — IP result still valid */ })
      .finally(() => { upgrading.value = false })
  }

  async function preloadCity() {
    if (city.value) return
    const cached = getCachedCity()
    if (cached) {
      city.value = cached.city
      lat.value = cached.lat
      lng.value = cached.lng
      return
    }
    // Preload via IP (fast, no UI impact)
    try {
      const ipResult = await requestCityByIP()
      if (ipResult?.city) {
        city.value = ipResult.city
        lat.value = ipResult.latitude
        lng.value = ipResult.longitude
        setCachedCity(ipResult.city, 'ip', ipResult.latitude, ipResult.longitude)
      }
    } catch { /* preload failure is non-critical */ }
  }

  function reset() {
    city.value = null
    lat.value = null
    lng.value = null
    error.value = null
    loading.value = false
    permissionDenied.value = false
    upgrading.value = false
    localStorage.removeItem(CACHE_KEY)
  }

  function setManualCity(name: string) {
    city.value = name
    setCachedCity(name, 'manual')
  }

  return { city, lat, lng, loading, upgrading, error, permissionDenied, requestCity, preloadCity, reset, setManualCity }
}