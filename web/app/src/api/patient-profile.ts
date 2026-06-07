import apiClient from './client'

export interface PatientProfile {
  id: number
  name: string
  relationship: string
  gender: string | null
  birth_date: string | null
  diagnosis_date: string | null
  vitiligo_type: string | null
  notes: string | null
  is_self: boolean
  created_at: string
}

export interface ModuleDefaults {
  tracker_profile_id: number | null
  report_profile_id: number | null
  diary_profile_id: number | null
}

export const patientProfileApi = {
  async list(): Promise<PatientProfile[]> {
    const { data } = await apiClient.get('/patient-profiles/')
    return data
  },

  async create(profileData: Partial<PatientProfile>): Promise<PatientProfile> {
    const { data } = await apiClient.post('/patient-profiles/', profileData)
    return data
  },

  async update(id: number, profileData: Partial<PatientProfile>): Promise<PatientProfile> {
    const { data } = await apiClient.put(`/patient-profiles/${id}`, profileData)
    return data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/patient-profiles/${id}`)
  },

  async getModuleDefaults(): Promise<ModuleDefaults> {
    const { data } = await apiClient.get('/user/module-defaults')
    return data
  },

  async setModuleDefaults(defaultsData: Partial<ModuleDefaults>): Promise<ModuleDefaults> {
    const { data } = await apiClient.put('/user/module-defaults', defaultsData)
    return data
  }
}
