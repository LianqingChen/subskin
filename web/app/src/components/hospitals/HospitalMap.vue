<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { init, use, registerMap, type EChartsType } from 'echarts/core'
import { ScatterChart } from 'echarts/charts'
import { GeoComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import chinaMap from '@/data/china-provinces.json?raw'
import { cityCoords } from '@/composables/useHospitalRegistry'
import type { HospitalView } from '@/types/hospital'
import { useThemeStore } from '@/stores/theme'
import { useToast } from '@/composables/useToast'

use([ScatterChart, GeoComponent, TooltipComponent, CanvasRenderer])
registerMap('subskin-china', chinaMap)

const props = withDefaults(defineProps<{
  hospitals: HospitalView[]
  province?: string
  city?: string
  selectedKey?: string
  comparisonKeys?: string[]
}>(), {
  province: '',
  city: '',
  selectedKey: '',
  comparisonKeys: () => [],
})

const emit = defineEmits<{
  'update:province': [name: string]
  'update:city': [name: string]
  select: [hospital: HospitalView]
  open: [hospital: HospitalView]
  write: [hospital: HospitalView]
  compare: [key: string]
}>()

const theme = useThemeStore()
const toast = useToast()

const canvas = ref<HTMLElement>()
const colorProbe = ref<HTMLElement>()
const error = ref(false)
const localSearch = ref('')

let chart: EChartsType | undefined
let observer: ResizeObserver | undefined

const PROVINCE_CENTERS: Record<string, [number, number]> = {
  北京: [116.4, 39.9], 上海: [121.47, 31.23], 天津: [117.2, 39.1], 重庆: [106.55, 29.56],
  河北: [115.0, 38.0], 山西: [112.5, 37.8], 辽宁: [123.4, 41.8], 吉林: [125.3, 43.8],
  黑龙江: [126.6, 45.7], 江苏: [119.8, 33.0], 浙江: [120.2, 29.2], 安徽: [117.2, 31.8],
  福建: [118.0, 26.0], 江西: [115.9, 28.6], 山东: [117.5, 36.6], 河南: [113.6, 34.7],
  湖北: [113.0, 31.0], 湖南: [111.7, 28.1], 广东: [113.3, 23.1], 海南: [110.3, 20.0],
  四川: [103.8, 30.6], 贵州: [106.7, 26.6], 云南: [102.7, 25.0], 陕西: [108.9, 34.3],
  甘肃: [103.8, 36.0], 青海: [101.7, 36.6], 内蒙古: [111.7, 40.8], 广西: [108.3, 22.8],
  西藏: [91.1, 29.6], 宁夏: [106.2, 38.4], 新疆: [87.6, 43.8],
}

/** 所有可用城市聚类标签 */
const cityGroups = computed(() => {
  const map = new Map<string, { count: number; reviews: number }>()
  for (const h of props.hospitals) {
    const entry = map.get(h.city) || { count: 0, reviews: 0 }
    entry.count += 1
    entry.reviews += h.stats.reviewCount
    map.set(h.city, entry)
  }
  return [...map.entries()].map(([name, stat]) => ({
    name,
    count: stat.count,
    reviews: stat.reviews,
  }))
})

/** 过滤后的当前地图医院列表 */
const visibleHospitals = computed(() => {
  let list = props.hospitals
  if (props.province) list = list.filter(h => h.province === props.province)
  if (props.city) list = list.filter(h => h.city === props.city)
  const q = localSearch.value.trim().toLowerCase()
  if (q) {
    list = list.filter(h =>
      [h.name, h.province, h.city, h.district, h.address, h.department, ...h.features].join(' ').toLowerCase().includes(q)
    )
  }
  return list
})

/** 当前选中的医院 */
const selectedHospital = computed<HospitalView | null>(() => {
  if (props.selectedKey) {
    const found = props.hospitals.find(h => h.key === props.selectedKey)
    if (found) return found
  }
  if (visibleHospitals.value.length > 0) {
    return visibleHospitals.value[0]
  }
  return props.hospitals[0] ?? null
})

function selectHospital(hospital: HospitalView) {
  emit('select', hospital)
  if (hospital.province && hospital.province !== props.province) {
    emit('update:province', hospital.province)
  }
  if (hospital.city && hospital.city !== props.city) {
    emit('update:city', hospital.city)
  }
}

function selectCity(cityName: string) {
  const match = props.hospitals.find(h => h.city === cityName)
  if (match && match.province !== props.province) {
    emit('update:province', match.province)
  }
  emit('update:city', cityName)
}

function clearRegion() {
  emit('update:province', '')
  emit('update:city', '')
}

async function copyAddress(hospital: HospitalView) {
  const fullAddress = `${hospital.name} · ${hospital.province}${hospital.city}${hospital.district || ''}${hospital.address || ''}`
  try {
    await navigator.clipboard.writeText(fullAddress)
    toast.success('已复制医院完整地址')
  } catch {
    toast.error('复制失败，请长按文本复制')
  }
}

function getNavigationUrl(hospital: HospitalView) {
  if (hospital.lng && hospital.lat) {
    return `https://uri.amap.com/marker?position=${hospital.lng},${hospital.lat}&name=${encodeURIComponent(hospital.name)}&coordinate=gaode`
  }
  return `https://www.amap.com/search?query=${encodeURIComponent(`${hospital.name} ${hospital.city} ${hospital.address || ''}`)}`
}

function render() {
  if (!chart || !colorProbe.value || !canvas.value) return
  const color = getComputedStyle(colorProbe.value).color
  const area = getComputedStyle(colorProbe.value).backgroundColor
  const border = getComputedStyle(colorProbe.value).borderTopColor
  const labelColor = getComputedStyle(canvas.value).color

  let targetCenter: [number, number] = [104, 35]
  let targetZoom = 1.15

  if (props.city) {
    const coord = cityCoords(props.city)
    if (coord) {
      targetCenter = [coord.lng, coord.lat]
      targetZoom = 3.6
    }
  } else if (props.province) {
    const provCenter = PROVINCE_CENTERS[props.province]
    if (provCenter) {
      targetCenter = provCenter
      targetZoom = 2.4
    }
  }

  // 城市散点（城市级概览）
  const cityScatterData = cityGroups.value.flatMap(group => {
    const location = cityCoords(group.name)
    if (!location) return []
    const isPicked = selectedHospital.value?.city === group.name || props.city === group.name
    return [{
      name: group.name,
      value: [location.lng, location.lat, group.count],
      symbolSize: isPicked ? 42 : 32,
      itemStyle: {
        color: isPicked ? color : '#0ea5e9',
        borderColor: '#ffffff',
        borderWidth: 2,
        opacity: 0.95,
      },
    }]
  })

  // 医院具体点位散点
  const hospitalScatterData = visibleHospitals.value.flatMap(h => {
    if (!h.lng || !h.lat) return []
    const isSelected = selectedHospital.value?.key === h.key
    return [{
      name: h.name,
      value: [h.lng, h.lat, h.stats.reviewCount + 1],
      hospitalKey: h.key,
      symbolSize: isSelected ? 30 : 20,
      itemStyle: {
        color: isSelected ? '#f59e0b' : color,
        borderColor: '#ffffff',
        borderWidth: isSelected ? 3 : 2,
        shadowBlur: isSelected ? 12 : 4,
        shadowColor: isSelected ? 'rgba(245, 158, 11, 0.6)' : 'rgba(0,0,0,0.2)',
      },
    }]
  })

  chart.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17, 24, 39, 0.92)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: '#ffffff', fontSize: 12 },
      formatter: (params: { data?: { name: string; hospitalKey?: string; value?: (number | string)[] } }) => {
        if (!params.data) return ''
        const key = params.data.hospitalKey
        if (key) {
          const h = props.hospitals.find(item => item.key === key)
          if (h) {
            return `<b>${h.name}</b><br/>${h.province} · ${h.city} ${h.district || ''}<br/>${h.address || '地址核对中'}<br/><span style="color:#38bdf8;">${h.department}</span>`
          }
        }
        return `<b>${params.data.name}</b><br/>已收录 ${params.data.value?.[2] ?? 0} 家医院`
      },
    },
    geo: {
      map: 'subskin-china',
      roam: true,
      zoom: targetZoom,
      center: targetCenter,
      scaleLimit: { min: 0.8, max: 7 },
      label: { show: false, color: labelColor },
      itemStyle: { areaColor: area, borderColor: border, borderWidth: 1 },
      emphasis: {
        label: { show: true, color: labelColor },
        itemStyle: { areaColor: color, opacity: 0.5 },
      },
      regions: props.province ? [{
        name: JSON.parse(chinaMap).features.find((f: { properties: { name: string } }) => f.properties.name.startsWith(props.province))?.properties.name,
        itemStyle: { areaColor: color, opacity: 0.35 },
      }] : [],
    },
    series: [
      {
        name: '城市分布',
        type: 'scatter',
        coordinateSystem: 'geo',
        label: {
          show: true,
          formatter: '{b}',
          position: 'bottom',
          color: labelColor,
          fontSize: 11,
          distance: 4,
        },
        data: cityScatterData,
      },
      {
        name: '医院点位',
        type: 'scatter',
        coordinateSystem: 'geo',
        zlevel: 2,
        label: {
          show: props.province !== '' || props.city !== '',
          formatter: '{b}',
          position: 'top',
          color: labelColor,
          fontSize: 11,
          distance: 5,
        },
        data: hospitalScatterData,
      },
    ],
  }, true)
}

function zoom(factor: number) {
  if (!chart) return
  const option = chart.getOption() as { geo?: { zoom?: number }[] }
  const current = option.geo?.[0]?.zoom ?? 1.15
  chart.setOption({ geo: { zoom: Math.min(7, Math.max(0.8, current * factor)) } })
}

onMounted(() => {
  try {
    if (!canvas.value) return
    chart = init(canvas.value)
    render()
    chart.on('click', event => {
      const data = event.data as { hospitalKey?: string; name?: string } | undefined
      if (data?.hospitalKey) {
        const found = props.hospitals.find(h => h.key === data.hospitalKey)
        if (found) selectHospital(found)
      } else if (event.componentType === 'series' && event.name) {
        selectCity(event.name)
      } else if (event.componentType === 'geo' && event.name) {
        const provName = event.name.replace(/(省|市|自治区|特别行政区|壮族|回族|维吾尔)$/, '')
        emit('update:province', provName)
        emit('update:city', '')
      }
    })
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(canvas.value)
  } catch {
    error.value = true
  }
})

watch(() => [props.hospitals, props.province, props.city, props.selectedKey, theme.mode, theme.customHue], render, { flush: 'post' })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <section aria-label="医院地图查找与地址选择" class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900 md:p-5">
    <span ref="colorProbe" class="absolute invisible text-primary-600 bg-primary-100 border-primary-200 dark:bg-gray-800 dark:border-gray-600" />

    <!-- 顶部状态与快速跳转栏 -->
    <header class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3 dark:border-gray-800">
      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <span class="inline-flex items-center gap-1.5 text-sm font-semibold text-gray-900 dark:text-gray-100">
          <i class="ri-map-pin-2-fill text-primary-600 dark:text-primary-400" />
          {{ province ? `${province}${city ? ' · ' + city : ''}` : '全国医院分布' }}
        </span>
        <button
          v-if="province || city"
          class="inline-flex min-h-11 items-center gap-1 rounded-lg px-2.5 text-xs text-primary-700 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-gray-800"
          @click="clearRegion"
        >
          <i class="ri-arrow-go-back-line" />返回全国视图
        </button>
      </div>

      <!-- 快捷城市选项 -->
      <nav class="flex flex-wrap items-center gap-1 text-xs" aria-label="快捷城市选择">
        <button
          class="min-h-11 rounded-lg px-2.5 transition-colors"
          :class="!province && !city ? 'bg-primary-600 text-white font-medium' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'"
          @click="clearRegion"
        >全部</button>
        <button
          v-for="group in cityGroups"
          :key="group.name"
          class="min-h-11 rounded-lg px-2.5 transition-colors"
          :class="city === group.name ? 'bg-primary-600 text-white font-medium' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'"
          @click="selectCity(group.name)"
        >
          {{ group.name }}<span class="ml-1 opacity-70">{{ group.count }}</span>
        </button>
      </nav>
    </header>

    <!-- 搜索筛选条 -->
    <div class="mt-3 flex items-center gap-2">
      <label class="relative min-w-0 flex-1">
        <span class="sr-only">搜索医院或地址</span>
        <i class="ri-search-line absolute left-3 top-3.5 text-gray-400" />
        <input
          v-model="localSearch"
          type="search"
          maxlength="100"
          class="block min-h-11 w-full min-w-0 rounded-xl border border-gray-200 bg-gray-50 pl-9 pr-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
          placeholder="快速筛选医院名称、地址、科室服务…"
        >
      </label>
      <span class="shrink-0 text-xs text-gray-500 dark:text-gray-400">
        匹配 {{ visibleHospitals.length }} 家
      </span>
    </div>

    <!-- 地图视口与列表组合 -->
    <div class="mt-3 grid gap-4 lg:grid-cols-12">
      <!-- 地图主视口 -->
      <div class="relative overflow-hidden rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-950 lg:col-span-8">
        <div v-if="error" class="flex h-72 items-center justify-center p-6 text-center text-sm text-gray-500">
          地图暂时无法初始化，请使用下方的城市快捷列表与医院卡片。
        </div>
        <div
          v-show="!error"
          ref="canvas"
          class="h-[300px] w-full text-gray-600 sm:h-[380px] md:h-[440px] dark:text-gray-300"
          role="img"
          aria-label="中国地图，包含收录医院的城市圆点和院区坐标点"
        />

        <!-- 地图缩放控制按钮 -->
        <div class="absolute right-3 top-3 flex flex-col rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
          <button class="flex h-11 w-11 items-center justify-center text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800" aria-label="放大地图" @click="zoom(1.4)">
            <i class="ri-add-line" />
          </button>
          <button class="flex h-11 w-11 items-center justify-center border-t border-gray-200 text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800" aria-label="缩小地图" @click="zoom(1 / 1.4)">
            <i class="ri-subtract-line" />
          </button>
          <button class="flex h-11 w-11 items-center justify-center border-t border-gray-200 text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800" aria-label="居中复位" @click="render">
            <i class="ri-focus-3-line" />
          </button>
        </div>

        <p class="pointer-events-none absolute bottom-2 left-3 text-[11px] text-gray-400 dark:text-gray-500">
          点选省市或圆点缩放查看 · 橙色点为当前选定医院
        </p>
      </div>

      <!-- 医院列表面板（方便触摸点选） -->
      <aside aria-label="当前区域医院列表" class="flex flex-col rounded-xl border border-gray-200 bg-gray-50 p-2.5 dark:border-gray-800 dark:bg-gray-950 lg:col-span-4">
        <p class="mb-2 px-1 text-xs font-medium text-gray-500 dark:text-gray-400">
          {{ city || province || '全国' }}医院列表（{{ visibleHospitals.length }} 家）
        </p>
        <div class="max-h-[360px] space-y-1.5 overflow-y-auto pr-1 sm:max-h-[400px]">
          <button
            v-for="hospital in visibleHospitals"
            :key="hospital.key"
            class="flex min-h-11 w-full flex-col rounded-xl p-2.5 text-left transition-colors"
            :class="selectedHospital?.key === hospital.key ? 'bg-primary-50 ring-1 ring-primary-500 dark:bg-primary-900 dark:ring-primary-400' : 'bg-white hover:bg-gray-100 dark:bg-gray-900 dark:hover:bg-gray-800'"
            @click="selectHospital(hospital)"
          >
            <div class="flex items-center justify-between gap-1">
              <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ hospital.name }}</span>
              <span v-if="selectedHospital?.key === hospital.key" class="shrink-0 text-xs text-primary-600 dark:text-primary-400">
                <i class="ri-check-line font-bold" /> 已选
              </span>
            </div>
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
              <i class="ri-map-pin-line mr-0.5" />{{ hospital.city }} · {{ hospital.district || '主院区' }}
            </p>
          </button>

          <p v-if="visibleHospitals.length === 0" class="py-8 text-center text-xs text-gray-400">
            未找到符合条件的医院地址
          </p>
        </div>
      </aside>
    </div>

    <!-- 选定医院地址详情卡片 -->
    <article v-if="selectedHospital" class="mt-4 rounded-xl border border-primary-200 bg-primary-50 p-4 dark:border-primary-900 dark:bg-primary-900">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
            <span>{{ selectedHospital.province }} · {{ selectedHospital.city }}</span>
            <span v-if="selectedHospital.district">· {{ selectedHospital.district }}</span>
            <span v-if="selectedHospital.kind" class="rounded bg-gray-200 px-1.5 py-0.5 text-gray-700 dark:bg-gray-800 dark:text-gray-300">{{ selectedHospital.kind }}</span>
            <span v-if="selectedHospital.origin === 'community'" class="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">病友补充</span>
          </div>

          <h3 class="mt-1.5 text-base font-bold text-gray-900 dark:text-gray-100">
            {{ selectedHospital.name }}
          </h3>

          <!-- 详细地址栏 -->
          <div class="mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-white p-2.5 text-xs text-gray-700 dark:bg-gray-900 dark:text-gray-200">
            <i class="ri-map-pin-2-fill text-primary-600 dark:text-primary-400" />
            <span class="min-w-0 flex-1 break-all">{{ selectedHospital.address || '地址核对中，建议参考官方发布' }}</span>
            <button
              class="inline-flex min-h-11 items-center gap-1 rounded-lg bg-gray-100 px-3 font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
              @click="copyAddress(selectedHospital)"
            >
              <i class="ri-file-copy-line" />复制地址
            </button>
            <a
              :href="getNavigationUrl(selectedHospital)"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex min-h-11 items-center gap-1 rounded-lg bg-primary-600 px-3 font-medium text-white hover:bg-primary-700"
            >
              <i class="ri-navigation-line" />地图导航
            </a>
          </div>

          <div v-if="selectedHospital.features.length" class="mt-2.5 flex flex-wrap gap-1.5">
            <span v-for="tag in selectedHospital.features" :key="tag" class="rounded-md bg-white px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-900 dark:text-gray-300">
              {{ tag }}
            </span>
          </div>
        </div>
      </div>

      <!-- 操作按钮栏 -->
      <div class="mt-3 flex flex-wrap items-center gap-2 border-t border-primary-200 pt-3 dark:border-primary-900">
        <button
          class="inline-flex min-h-11 items-center gap-1.5 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700"
          @click="emit('open', selectedHospital)"
        >
          查看医院详情与病友经验 <i class="ri-arrow-right-line" />
        </button>
        <button
          class="inline-flex min-h-11 items-center gap-1 rounded-xl border border-primary-300 bg-white px-3.5 text-sm font-medium text-primary-700 hover:bg-primary-50 dark:border-primary-800 dark:bg-gray-900 dark:text-primary-300 dark:hover:bg-gray-800"
          @click="emit('write', selectedHospital)"
        >
          <i class="ri-edit-line" />写就诊经历
        </button>
        <button
          class="inline-flex min-h-11 items-center gap-1 rounded-xl px-3 text-sm text-gray-600 hover:bg-white dark:text-gray-400 dark:hover:bg-gray-800"
          @click="emit('compare', selectedHospital.key)"
        >
          <i :class="comparisonKeys.includes(selectedHospital.key) ? 'ri-checkbox-circle-fill text-primary-600' : 'ri-scales-3-line'" />
          {{ comparisonKeys.includes(selectedHospital.key) ? '已加入对比' : '加入对比' }}
        </button>
      </div>
    </article>
  </section>
</template>
