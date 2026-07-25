import apiClient from './client'

export interface MedicationReminder {
  id: number
  medication_name: string
  dosage: string | null
  frequency: string
  reminder_times: string[] | null
  reminder_days: number[] | null
  notes: string | null
  is_active: boolean
  created_at: string
}

export interface ReminderCreateRequest {
  medication_name: string
  dosage?: string
  frequency: string
  reminder_times?: string[]
  reminder_days?: number[]
  notes?: string
}

export interface ReminderUpdateRequest {
  medication_name?: string
  dosage?: string
  frequency?: string
  reminder_times?: string[]
  reminder_days?: number[]
  notes?: string
  is_active?: boolean
}

export const medicationApi = {
  async getReminders(): Promise<MedicationReminder[]> {
    const { data } = await apiClient.get('/medication/reminders')
    return data
  },

  async createReminder(payload: ReminderCreateRequest): Promise<MedicationReminder> {
    const { data } = await apiClient.post('/medication/reminders', payload)
    return data
  },

  async updateReminder(id: number, payload: ReminderUpdateRequest): Promise<MedicationReminder> {
    const { data } = await apiClient.put(`/medication/reminders/${id}`, payload)
    return data
  },

  async deleteReminder(id: number): Promise<void> {
    await apiClient.delete(`/medication/reminders/${id}`)
  },

  async subscribePush(endpoint: string, p256dhKey: string, authKey: string): Promise<{ success: boolean; subscription_id: number }> {
    const { data } = await apiClient.post('/medication/push/subscribe', {
      endpoint,
      p256dh_key: p256dhKey,
      auth_key: authKey,
      user_agent: navigator.userAgent,
    })
    return data
  },

  async unsubscribePush(endpoint: string): Promise<void> {
    await apiClient.delete('/medication/push/unsubscribe', { params: { endpoint } })
  },

  async getVapidPublicKey(): Promise<{ public_key: string }> {
    const { data } = await apiClient.get('/medication/push/vapid-public-key')
    return data
  },
}
