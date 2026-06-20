import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { authApi, type LoginResponse } from '@/api/auth'
import { trackEvent } from '@/composables/useTracking'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const user = ref<User | null>(null)
  const isLoggedIn = computed(() => !!token.value)
  const _loginModalState = sessionStorage.getItem('subskin_login_modal')
const showLoginModal = ref(_loginModalState === 'true')

watch(showLoginModal, (val: boolean) => {
  if (val) {
    sessionStorage.setItem('subskin_login_modal', 'true')
  } else {
    sessionStorage.removeItem('subskin_login_modal')
  }
})

  function setUser(nextUser: User | null) {
    user.value = nextUser
    if (nextUser) {
      localStorage.setItem('subskin_user', JSON.stringify(nextUser))
      return
    }
    localStorage.removeItem('subskin_user')
  }

  function initFromStorage() {
    const savedToken = localStorage.getItem('subskin_token')
    const savedRefreshToken = localStorage.getItem('subskin_refresh_token')
    const savedUser = localStorage.getItem('subskin_user')
    if (savedToken) {
      token.value = savedToken
      refreshToken.value = savedRefreshToken
      try {
        setUser(savedUser ? JSON.parse(savedUser) : null)
      } catch {
        setUser(null)
      }
    }
  }

  function _saveTokens(loginData: LoginResponse) {
    token.value = loginData.access_token
    if (loginData.refresh_token) {
      refreshToken.value = loginData.refresh_token
      localStorage.setItem('subskin_refresh_token', loginData.refresh_token)
    }
    localStorage.setItem('subskin_token', loginData.access_token)
  }

  async function _completeLogin(loginData: LoginResponse) {
    _saveTokens(loginData)
    await fetchUser()
  }

  async function loginByPhone(phone: string, code: string) {
    const data = await authApi.loginByPhone(phone, code)
    await _completeLogin(data)
    trackEvent({ event_type: 'login_success' })
    return data
  }

  async function loginByPhonePassword(phone: string, password: string) {
    const data = await authApi.loginByPhonePassword(phone, password)
    await _completeLogin(data)
    trackEvent({ event_type: 'login_success' })
    return data
  }

  async function registerByPhone(phone: string, code: string, password?: string) {
    const data = await authApi.registerByPhone(phone, code, password)
    await _completeLogin(data)
    trackEvent({ event_type: 'register_success' })
    return data
  }

  async function loginByEmail(email: string, code: string) {
    const data = await authApi.loginByEmail(email, code)
    await _completeLogin(data)
    trackEvent({ event_type: 'login_success' })
    return data
  }

  async function loginByEmailPassword(email: string, password: string) {
    const data = await authApi.loginByEmailPassword(email, password)
    await _completeLogin(data)
    trackEvent({ event_type: 'login_success' })
    return data
  }

  async function registerByEmail(email: string, code: string, password: string) {
    const data = await authApi.registerByEmail(email, code, password)
    await _completeLogin(data)
    trackEvent({ event_type: 'register_success' })
    return data
  }

  async function loginByUsername(username: string, password: string) {
    const data = await authApi.loginByUsername(username, password)
    await _completeLogin(data)
    trackEvent({ event_type: 'login_success' })
    return data
  }

  async function sendSmsCode(phone: string) {
    return authApi.sendSmsCode(phone)
  }

  async function sendEmailCode(email: string, purpose: 'login' | 'register' | 'reset' | 'bind' = 'login') {
    return authApi.sendEmailCode(email, purpose)
  }

  async function bindPhone(phone: string, code: string) {
    return authApi.bindPhone(phone, code)
  }

  async function bindEmail(email: string, code: string) {
    return authApi.bindEmail(email, code)
  }

  async function getCredentials() {
    return authApi.getCredentials()
  }

  async function unbindCredential(credentialId: number) {
    return authApi.unbindCredential(credentialId)
  }

  async function setPassword(password: string) {
    return authApi.setPassword(password)
  }

  async function resetPassword(
    credentialId: string,
    credType: 'phone' | 'email',
    code: string,
    newPassword: string,
  ) {
    return authApi.resetPassword(credentialId, credType, code, newPassword)
  }

  async function register(username: string, email: string, password: string) {
    return authApi.register(username, email, password)
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      const userData = await authApi.getMe(token.value)
      setUser(userData)
    } catch (e: any) {
      const status = e?.response?.status
      if (status === 401 || status === 403) {
        const refreshed = await tryRefreshToken()
        if (!refreshed) logout()
      }
    }
  }

  async function updateProfile(payload: { username?: string; phone?: string | null; email?: string | null; patient_relation?: string | null }) {
    const userData = await authApi.updateMe(payload)
    setUser(userData)
    return userData
  }

  async function uploadAvatar(file: File) {
    const userData = await authApi.uploadAvatar(file)
    setUser(userData)
    return userData
  }

  async function tryRefreshToken(): Promise<boolean> {
    if (!refreshToken.value) return false
    try {
      const data = await authApi.refreshToken(refreshToken.value)
      _saveTokens(data)
      await fetchUser()
      return true
    } catch {
      logout()
      return false
    }
  }

  function logout() {
    token.value = null
    refreshToken.value = null
    setUser(null)
    localStorage.removeItem('subskin_token')
    localStorage.removeItem('subskin_refresh_token')
  }

  return {
    token,
    refreshToken,
    user,
    isLoggedIn,
    showLoginModal,
    initFromStorage,
    loginByPhone,
    loginByPhonePassword,
    registerByPhone,
    loginByEmail,
    loginByEmailPassword,
    registerByEmail,
    loginByUsername,
    sendSmsCode,
    sendEmailCode,
    bindPhone,
    bindEmail,
    getCredentials,
    unbindCredential,
    setPassword,
    resetPassword,
    register,
    fetchUser,
    updateProfile,
    uploadAvatar,
    tryRefreshToken,
    logout,
  }
})
