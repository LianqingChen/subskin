import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { authApi, type LoginResponse } from '@/api/auth'
import { trackEvent } from '@/composables/useTracking'
import { ensureFileToken, clearFileToken } from '@/utils/file-url'
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
      // 2026-08-30 隐私加固：持久化副本剔除 phone/email 等 L3 字段，
      // 需要时通过 /users/me 实时拉取
      const persisted = { ...nextUser }
      delete (persisted as Record<string, unknown>).phone
      delete (persisted as Record<string, unknown>).email
      localStorage.setItem('subskin_user', JSON.stringify(persisted))
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
      showLoginModal.value = false
      try {
        setUser(savedUser ? JSON.parse(savedUser) : null)
      } catch {
        setUser(null)
      }
      // Refresh the short-lived file token in the background; file-url.ts
      // falls back to the access token until this resolves.
      void ensureFileToken().catch(() => {})
      _startFileTokenRefresher()
    }
  }

  // Refresh the file token before it expires so long sessions keep using the
  // scoped token instead of falling back to the long-lived access token.
  let _fileTokenTimer: ReturnType<typeof setInterval> | null = null
  function _startFileTokenRefresher() {
    if (_fileTokenTimer || typeof window === 'undefined') return
    _fileTokenTimer = setInterval(() => {
      if (!token.value) return
      void ensureFileToken().catch(() => {})
    }, 4 * 60 * 1000) // refresh every 4 min (token TTL is 5 min)
  }

  function _saveTokens(loginData: LoginResponse) {
    token.value = loginData.access_token
    if (loginData.refresh_token) {
      refreshToken.value = loginData.refresh_token
      localStorage.setItem('subskin_refresh_token', loginData.refresh_token)
    }
    localStorage.setItem('subskin_token', loginData.access_token)
  }

  async function clearSensitiveCaches() {
    if (typeof window === 'undefined' || !('caches' in window)) return
    try {
      const cacheNames = await caches.keys()
      await Promise.all(
        cacheNames
          .filter((name) => name === 'api-cache' || name === 'uploads-cache')
          .map((name) => caches.delete(name)),
      )
    } catch {
      // Cache cleanup is best-effort and must never block logout.
    }
  }

  async function _completeLogin(loginData: LoginResponse) {
    _saveTokens(loginData)
    showLoginModal.value = false
    await fetchUser()
    // Prefetch a short-lived file token so file URLs use it instead of the
    // long-lived access token. Errors are non-fatal; file-url.ts falls back.
    void ensureFileToken().catch(() => {})
    _startFileTokenRefresher()
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

  async function setPassword(password: string, oldPassword?: string) {
    return authApi.setPassword(password, oldPassword)
  }

  async function resetPassword(
    credentialId: string,
    credType: 'phone' | 'email',
    code: string,
    newPassword: string,
  ) {
    const res = await authApi.resetPassword(credentialId, credType, code, newPassword)
    // 重置成功后后端已吊销全部旧令牌并为当前会话补发新令牌对，
    // 必须立即保存，否则当前 access token 过期后会被静默登出。
    if (res.access_token && res.refresh_token) {
      _saveTokens({
        access_token: res.access_token,
        refresh_token: res.refresh_token,
        token_type: res.token_type || 'bearer',
      })
    }
    return res
  }

  async function register(username: string, email: string, password: string) {
    return authApi.register(username, email, password)
  }

  async function fetchUser(isRetryAfterRefresh = false) {
    if (!token.value) return
    try {
      const userData = await authApi.getMe(token.value)
      setUser(userData)
    } catch (e: any) {
      const status = e?.response?.status
      if ((status === 401 || status === 403) && !isRetryAfterRefresh) {
        const refreshed = await tryRefreshToken()
        if (refreshed) {
          await fetchUser(true)
        } else {
          logout()
        }
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
      return true
    } catch {
      logout()
      return false
    }
  }

  async function logout() {
    // Revoke refresh tokens server-side first (the request needs the auth
    // header, which the apiClient reads from localStorage), then clear local
    // state. Best-effort: a failed network call does not block local logout.
    if (token.value) {
      try {
        await authApi.logout()
      } catch {
        // ignore — proceed with local logout
      }
    }
    token.value = null
    refreshToken.value = null
    setUser(null)
    localStorage.removeItem('subskin_token')
    localStorage.removeItem('subskin_refresh_token')
    clearFileToken()
    await clearSensitiveCaches()
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
