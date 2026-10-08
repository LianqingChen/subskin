<script setup lang="ts">
import { computed, ref } from 'vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import HospitalCard from './HospitalCard.vue'
import HospitalMap from './HospitalMap.vue'
import type { HospitalFilterState, HospitalMark, HospitalView } from '@/types/hospital'

/** 医院目录：支持「列表找院」与「地图找院与选址」双模式，轻筛选条 + 详细地址展示与导航。 */
const props = defineProps<{
  modelValue: HospitalFilterState
  hospitals: HospitalView[]
  allHospitals?: HospitalView[]
  total: number
  provinces: string[]
  cities: string[]
  districts: string[]
  features: string[]
  marks: Record<string, HospitalMark>
  comparisonKeys: string[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: HospitalFilterState]
  open: [hospital: HospitalView]
  mark: [key: string, value: HospitalMark]
  compare: [key: string]
  create: []
  write: [hospital: HospitalView]
}>()

const viewMode = ref<'list' | 'map'>('list')
const selectedMapHospitalKey = ref('')
const moreFilters = ref(false)
const sort = ref('name')

const sortedHospitals = computed(() => [...props.hospitals].sort((a, b) =>
  (sort.value === 'experiences' ? b.stats.reviewCount - a.stats.reviewCount : 0) || a.name.localeCompare(b.name, 'zh-CN')
))

const mapSourceHospitals = computed(() => props.allHospitals && props.allHospitals.length > 0 ? props.allHospitals : props.hospitals)

const extraCount = computed(() => [
  props.modelValue.district, props.modelValue.feature, props.modelValue.onlyMarked, props.modelValue.onlyReviewed,
].filter(Boolean).length)

function patch(part: Partial<HospitalFilterState>) {
  emit('update:modelValue', { ...props.modelValue, ...part })
}

function onProvince(value: string) {
  patch({ province: value, city: '', district: '' })
}

function onCity(value: string) {
  patch({ city: value, district: '' })
}

function resetFilters() {
  emit('update:modelValue', {
    query: '', province: '', city: '', district: '', feature: '', onlyMarked: false, onlyReviewed: false,
  })
  moreFilters.value = false
}

function locateOnMap(hospital: HospitalView) {
  selectedMapHospitalKey.value = hospital.key
  if (hospital.province && hospital.province !== props.modelValue.province) {
    patch({ province: hospital.province, city: hospital.city })
  } else if (hospital.city && hospital.city !== props.modelValue.city) {
    patch({ city: hospital.city })
  }
  viewMode.value = 'map'
}

function onMapSelect(hospital: HospitalView) {
  selectedMapHospitalKey.value = hospital.key
}
</script>

<template>
  <section aria-labelledby="hospital-picker-title" class="card p-4 dark:bg-gray-900 md:p-6">
    <h2 id="hospital-picker-title" class="sr-only">查找医院</h2>

    <!-- 顶部找院视图切换 -->
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-3 dark:border-gray-800">
      <div class="flex items-center gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800" role="tablist" aria-label="找院视图切换">
        <button
          type="button"
          role="tab"
          :aria-selected="viewMode === 'list'"
          class="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-4 text-xs font-medium transition-all"
          :class="viewMode === 'list' ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-900 dark:text-gray-100' : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200'"
          @click="viewMode = 'list'"
        >
          <i class="ri-list-check" /> 列表查找
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="viewMode === 'map'"
          class="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-4 text-xs font-medium transition-all"
          :class="viewMode === 'map' ? 'bg-white text-primary-700 shadow-sm dark:bg-gray-900 dark:text-primary-300' : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200'"
          @click="viewMode = 'map'"
        >
          <i class="ri-map-2-line" /> 地图找院与选址
        </button>
      </div>

      <span class="text-xs text-gray-500 dark:text-gray-400">
        {{ viewMode === 'map' ? '点击地图圆点或卡片可直接选择医院地址与导航' : '支持按省市、详细地址与就诊服务查找' }}
      </span>
    </div>

    <!-- 地图模式 -->
    <div v-if="viewMode === 'map'" class="space-y-4">
      <HospitalMap
        :hospitals="mapSourceHospitals"
        :province="modelValue.province"
        :city="modelValue.city"
        :selected-key="selectedMapHospitalKey"
        :comparison-keys="comparisonKeys"
        @update:province="onProvince"
        @update:city="onCity"
        @select="onMapSelect"
        @open="emit('open', $event)"
        @write="emit('write', $event)"
        @compare="emit('compare', $event)"
      />
    </div>

    <!-- 列表模式 -->
    <div v-show="viewMode === 'list'">
      <!-- 搜索和省市筛选 -->
      <div class="flex flex-col gap-2 sm:flex-row">
        <label class="relative min-w-0 flex-1">
          <span class="sr-only">按名称或地址搜索医院</span>
          <i class="ri-search-line absolute left-3 top-3.5 text-gray-400" />
          <input
            :value="modelValue.query" type="search" maxlength="100"
            class="picker-input min-w-0 pl-9"
            placeholder="医院名称、地址、科室或诊疗服务"
            @input="patch({ query: ($event.target as HTMLInputElement).value })"
          >
        </label>
        <div class="grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
          <label class="block">
            <span class="sr-only">省份</span>
            <select :value="modelValue.province" class="picker-input" @change="onProvince(($event.target as HTMLSelectElement).value)">
              <option value="">全国</option>
              <option v-for="name in provinces" :key="name" :value="name">{{ name }}</option>
            </select>
          </label>
          <label class="block">
            <span class="sr-only">城市</span>
            <select :value="modelValue.city" :disabled="!modelValue.province" class="picker-input disabled:opacity-50" @change="onCity(($event.target as HTMLSelectElement).value)">
              <option value="">{{ modelValue.province ? `全部城市（${cities.length}）` : '先选省份' }}</option>
              <option v-for="name in cities" :key="name" :value="name">{{ name }}</option>
            </select>
          </label>
        </div>
      </div>

      <!-- 更多筛选折叠面板 -->
      <button class="mt-2 flex min-h-11 w-full items-center justify-between rounded-xl bg-gray-50 px-3 text-sm text-gray-600 dark:bg-gray-800 dark:text-gray-300" :aria-expanded="moreFilters" @click="moreFilters = !moreFilters">
        <span>更多筛选<span v-if="extraCount" class="ml-2 text-primary-700 dark:text-primary-300">已启用 {{ extraCount }} 项</span></span>
        <i :class="moreFilters ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'" aria-hidden="true" />
      </button>
      <div v-show="moreFilters" class="mt-3 grid gap-3 sm:grid-cols-2">
        <label class="block text-sm text-gray-600 dark:text-gray-300">区县 / 院区地址
          <input
            :value="modelValue.district" type="text" maxlength="50" list="hospital-district-options"
            class="picker-input" placeholder="可输入，如：玄武区 / 东院区"
            @input="patch({ district: ($event.target as HTMLInputElement).value })"
          >
          <datalist id="hospital-district-options"><option v-for="name in districts" :key="name" :value="name" /></datalist>
        </label>
        <label v-if="features.length" class="text-sm text-gray-600 dark:text-gray-300">诊疗服务
          <select :value="modelValue.feature" class="picker-input" @change="patch({ feature: ($event.target as HTMLSelectElement).value })">
            <option value="">不限</option>
            <option v-for="name in features" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <label class="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          <input :checked="modelValue.onlyMarked" type="checkbox" class="h-4 w-4 accent-primary-600" @change="patch({ onlyMarked: ($event.target as HTMLInputElement).checked })">
          只看我的标记
        </label>
        <label class="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          <input :checked="modelValue.onlyReviewed" type="checkbox" class="h-4 w-4 accent-primary-600" @change="patch({ onlyReviewed: ($event.target as HTMLInputElement).checked })">
          只看有病友经验
        </label>
        <button class="min-h-11 justify-self-start text-sm text-gray-500 underline" @click="resetFilters">重置筛选</button>
      </div>

      <!-- 计数与排序栏 -->
      <div class="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-3 dark:border-gray-800">
        <div class="flex flex-wrap items-center gap-2">
          <p class="text-xs text-gray-500 dark:text-gray-400">
            匹配到 <strong class="text-gray-900 dark:text-gray-100">{{ hospitals.length }}</strong> / {{ total }} 家医院
          </p>
          <button
            class="inline-flex min-h-11 items-center gap-1 text-xs text-primary-700 underline dark:text-primary-300"
            @click="viewMode = 'map'"
          >
            <i class="ri-map-pin-line" />在地图上查看分布
          </button>
        </div>
        <label class="flex min-h-11 items-center gap-2 text-xs text-gray-600 dark:text-gray-300">排列
          <select v-model="sort" class="min-h-11 rounded-xl border border-gray-200 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-800">
            <option value="name">医院名称</option>
            <option value="experiences">经验条数较多</option>
          </select>
        </label>
      </div>

      <!-- 医院卡片列表 -->
      <LoadingSpinner v-if="loading" message="正在加载医院目录…" />
      <div v-else-if="hospitals.length" class="mt-4 grid gap-3 md:grid-cols-2 md:gap-4">
        <HospitalCard
          v-for="hospital in sortedHospitals" :key="hospital.key" :hospital="hospital"
          :mark="marks[hospital.key]" :compared="comparisonKeys.includes(hospital.key)"
          @open="emit('open', hospital)" @mark="emit('mark', hospital.key, $event)" @compare="emit('compare', hospital.key)"
          @locate="locateOnMap(hospital)"
        />
      </div>
      <div v-else class="mt-4 rounded-2xl border border-dashed border-gray-200 px-4 dark:border-gray-700">
        <EmptyState icon="ri-map-pin-search-line" title="没有符合当前条件的医院" description="试试清除筛选，或换一个医院名称、城市搜索。" action-label="清除筛选，查看全部" @action="resetFilters" />
      </div>

      <p class="mt-4 border-t border-gray-100 pt-3 text-xs leading-5 text-gray-500 dark:border-gray-800 dark:text-gray-400">
        目录持续补充，找不到不代表当地没有诊疗服务；院区、门诊和设备请以医院最新公告为准。
        <button class="min-h-11 px-1 text-primary-700 underline dark:text-primary-300" @click="emit('create')">找不到？补充这家医院</button>
      </p>
    </div>
  </section>
</template>

<style scoped>
.picker-input { @apply block min-h-11 w-full min-w-0 rounded-xl border border-gray-200 bg-white p-3 text-sm font-normal text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100; }
.picker-input[type="search"] { @apply pl-9; }
</style>
