<script setup lang="ts">
import { ref, computed } from 'vue'
import { PROVINCES, type Province, type ProvinceCity } from '@/data/cities'

const emit = defineEmits<{
  select: [city: ProvinceCity, province: string]
  close: []
}>()

const searchQuery = ref('')
const selectedProvince = ref<Province | null>(null)

const filteredProvinces = computed(() => {
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    return PROVINCES.filter(p => {
      if (p.name.includes(q)) return true
      return p.cities.some(c => c.name.includes(q) || c.name.toLowerCase().includes(q))
    }).map(p => {
      // If searching, also filter cities within province
      if (p.name.includes(q)) return p
      return {
        ...p,
        cities: p.cities.filter(c => c.name.includes(q) || c.name.toLowerCase().includes(q)),
      }
    })
  }
  return PROVINCES
})

function selectProvince(province: Province) {
  selectedProvince.value = province
  searchQuery.value = ''
}

function selectCity(city: ProvinceCity) {
  const provName = selectedProvince.value!.name
  emit('select', city, provName)
}

function goBack() {
  selectedProvince.value = null
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 bg-black/50 z-[110] flex items-center justify-center" @click.self="emit('close')">
      <div class="bg-white rounded-xl p-5 max-w-md w-full mx-4 max-h-[80vh] flex flex-col shadow-xl">
        <!-- Header -->
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <button
              v-if="selectedProvince"
              class="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-300 text-gray-500"
              @click="goBack"
            >
              <i class="ri-arrow-left-s-line text-xl"></i>
            </button>
            <h3 class="text-lg font-semibold text-gray-900">
              {{ selectedProvince ? selectedProvince.name : '选择城市' }}
            </h3>
          </div>
          <button class="p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-300 text-gray-400" @click="emit('close')">
            <i class="ri-close-line text-xl"></i>
          </button>
        </div>

        <!-- Search bar (province level only) -->
        <div v-if="!selectedProvince" class="relative mb-3">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索省份或城市..."
            class="w-full bg-gray-100 rounded-lg px-4 py-2.5 pl-10 text-sm text-gray-700 placeholder-gray-400 outline-none"
          />
          <i class="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
        </div>

        <!-- Province list or City list -->
        <div class="flex-1 overflow-y-auto -mx-2 px-2">
          <!-- Province selection -->
          <template v-if="!selectedProvince">
            <div v-for="prov in filteredProvinces" :key="prov.name">
              <button
                class="w-full flex items-center justify-between px-3 py-3 rounded-lg text-left hover:bg-gray-50 dark:hover:bg-gray-300 transition-colors"
                @click="selectProvince(prov)"
              >
                <span class="text-sm font-medium text-gray-700">{{ prov.name }}</span>
                <span class="text-xs text-gray-400 ">{{ prov.cities.length }} 个城市</span>
              </button>
            </div>
            <div v-if="filteredProvinces.length === 0" class="text-center py-8 text-sm text-gray-400">
              未找到匹配的城市
            </div>
          </template>

          <!-- City selection within a province -->
          <template v-else>
            <div class="mb-3">
              <p class="text-xs text-gray-400  px-1">
                共 {{ selectedProvince.cities.length }} 个城市
              </p>
            </div>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="city in selectedProvince.cities"
                :key="city.name"
                class="px-3 py-2.5 rounded-lg text-sm text-center transition-colors
                       text-gray-600 
                       hover:bg-primary-50 dark:hover:bg-primary-900/30
                       hover:text-primary-600 dark:hover:text-primary-400
                       border border-gray-100 dark:border-gray-700"
                @click="selectCity(city)"
              >
                {{ city.name }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>
