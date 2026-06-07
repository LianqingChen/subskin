import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { useAuthStore } from './auth'

export const usePrivacyStore = defineStore('privacy', () => {
  const privacyMode = ref(true)

  const stored = localStorage.getItem('subskin_privacy_mode')
  if (stored !== null) {
    privacyMode.value = stored === 'true'
  }

  watch(privacyMode, (newValue) => {
    localStorage.setItem('subskin_privacy_mode', String(newValue))
  })

  const syncWithBackend = async () => {
    const authStore = useAuthStore()
    if (!authStore.isLoggedIn || !authStore.token) return

    try {
      const response = await fetch('/api/user/privacy-mode', {
        headers: {
          'Authorization': `Bearer ${authStore.token}`
        }
      })
      if (response.ok) {
        const data = await response.json()
        privacyMode.value = data.privacy_mode
      }
    } catch (error) {
      console.error('Failed to fetch privacy mode from backend:', error)
    }
  }

  const localStorageKeys = {
    defaultPostPrivate: 'subskin_default_post_private',
    shareTracking: 'subskin_share_tracking',
  }

  const syncLocalStorageToggles = () => {
    localStorage.setItem(localStorageKeys.defaultPostPrivate, String(!privacyMode.value))
    localStorage.setItem(localStorageKeys.shareTracking, String(privacyMode.value))
  }

  const togglePrivacyMode = async () => {
    privacyMode.value = !privacyMode.value
    syncLocalStorageToggles()
    
    const authStore = useAuthStore()
    if (authStore.isLoggedIn && authStore.token) {
      try {
        await fetch('/api/user/privacy-mode', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authStore.token}`
          },
          body: JSON.stringify({ privacy_mode: privacyMode.value })
        })
      } catch (error) {
        console.error('Failed to update privacy mode on backend:', error)
      }
    }
  }

  const maskPhone = (phone: string | null | undefined): string => {
    if (!phone) return ''
    if (privacyMode.value) return phone
    return phone.replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2')
  }

  const maskEmail = (email: string | null | undefined): string => {
    if (!email) return ''
    if (privacyMode.value) return email
    const atIndex = email.indexOf('@')
    if (atIndex < 0) return email
    const local = email.substring(0, atIndex)
    const domain = email.substring(atIndex + 1)
    if (local.length <= 2) return `***@${domain}`
    return `${local.substring(0, 2)}***@${domain}`
  }

  return {
    privacyMode,
    syncWithBackend,
    togglePrivacyMode,
    maskPhone,
    maskEmail
  }
})