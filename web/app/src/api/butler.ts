import apiClient from './client'
import type { ButlerPreference } from '@/types'

/** 小白管家外观偏好（登录用户走后端跨设备同步，未设置时后端返回默认值） */
export const butlerApi = {
  async getPreference() {
    const { data } = await apiClient.get('/user/assistant-preference')
    return data as ButlerPreference
  },

  async updatePreference(patch: Partial<ButlerPreference>) {
    const { data } = await apiClient.put('/user/assistant-preference', patch)
    return data as ButlerPreference
  },
}
