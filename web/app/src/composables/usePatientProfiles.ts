import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { patientProfileApi, type PatientProfile, type ModuleDefaults } from '@/api/patient-profile'

export function usePatientProfiles() {
  const authStore = useAuthStore()
  const profiles = ref<PatientProfile[]>([])
  const moduleDefaults = reactive<ModuleDefaults>({} as ModuleDefaults)

  async function load() {
    if (!authStore.isLoggedIn) return
    try {
      const [profilesData, defaultsData] = await Promise.all([
        patientProfileApi.list(),
        patientProfileApi.getModuleDefaults()
      ])
      profiles.value = profilesData
      Object.assign(moduleDefaults, defaultsData)
    } catch (error) {
      console.error('Failed to load patient profiles:', error)
    }
  }

  return { profiles, moduleDefaults, load }
}
