import apiClient from './client'

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user?: {
    id: number
    uid: string | null
    username: string
    avatar_url: string | null
    email: string | null
    phone: string | null
    patient_relation: string | null
    is_active: boolean
    is_admin: boolean
    created_at: string
  }
}

export interface CredentialInfo {
  id: number
  cred_type: string
  cred_id: string
  verified: boolean
  last_used_at: string | null
  created_at: string
}

export interface UserResponse {
  id: number
  uid: string | null
  username: string
  avatar_url: string | null
  email: string | null
  phone: string | null
  patient_relation: string | null
  wechat_id: string | null
  alipay_id: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export interface UpdateProfileRequest {
  username?: string
  phone?: string | null
  email?: string | null
  patient_relation?: string | null
}

export const authApi = {
  // Phone SMS
  async sendSmsCode(phone: string) {
    const { data } = await apiClient.post('/user/send-sms', { phone })
    return data as { status: string; code?: string; message: string }
  },

  async loginByPhone(phone: string, code: string) {
    const { data } = await apiClient.post('/user/login-by-phone', { phone, code })
    return data as LoginResponse
  },

  async loginByPhonePassword(phone: string, password: string) {
    const { data } = await apiClient.post('/user/login-by-phone-password', { phone, password })
    return data as LoginResponse
  },

  async registerByPhone(phone: string, code: string, password?: string) {
    const { data } = await apiClient.post('/user/register-by-phone', { phone, code, password })
    return data as LoginResponse
  },

  // Email verification
  async sendEmailCode(email: string, purpose: 'login' | 'register' | 'reset' | 'bind' = 'login') {
    const { data } = await apiClient.post('/user/send-email-code', { email, purpose })
    return data as { status: string; code?: string; message: string }
  },

  async loginByEmail(email: string, code: string) {
    const { data } = await apiClient.post('/user/login-by-email', { email, code })
    return data as LoginResponse
  },

  async loginByEmailPassword(email: string, password: string) {
    const { data } = await apiClient.post('/user/login-by-email-password', { email, password })
    return data as LoginResponse
  },

  async registerByEmail(email: string, code: string, password: string) {
    const { data } = await apiClient.post('/user/register-by-email', { email, code, username: '', password })
    return data as LoginResponse
  },

  async bindPhone(phone: string, code: string) {
    const { data } = await apiClient.post('/user/bind-phone', { phone, code })
    return data as { detail: string; credential_id: number }
  },

  async bindEmail(email: string, code: string) {
    const { data } = await apiClient.post('/user/bind-email', { email, code })
    return data as { detail: string; credential_id: number }
  },

  async getCredentials() {
    const { data } = await apiClient.get('/user/credentials')
    return data as CredentialInfo[]
  },

  async unbindCredential(credentialId: number) {
    await apiClient.delete(`/user/credentials/${credentialId}`)
  },

  async setPassword(password: string) {
    const { data } = await apiClient.post('/user/set-password', { password })
    return data as { detail: string }
  },

  async resetPassword(
    credentialId: string,
    credType: 'phone' | 'email',
    code: string,
    newPassword: string,
  ) {
    const { data } = await apiClient.post('/user/reset-password', {
      credential_id: credentialId,
      cred_type: credType,
      code,
      new_password: newPassword,
    })
    return data as { detail: string }
  },

  // Username/password login (legacy)
  async loginByUsername(username: string, password: string) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    const { data } = await apiClient.post('/user/login', formData)
    return data as LoginResponse
  },

  // Registration
  async register(username: string, email: string, password: string) {
    const { data } = await apiClient.post('/user/register', { username, email, password })
    return data as UserResponse
  },

  // Token management
  async refreshToken(refreshToken: string) {
    const { data } = await apiClient.post('/user/refresh-token', { refresh_token: refreshToken })
    return data as LoginResponse
  },

  async logout() {
    const { data } = await apiClient.post('/user/logout')
    return data as { status: string; message: string }
  },

  // Short-lived, file-serving-only token — used by file-url.ts instead of the
  // long-lived access token so leaked URLs/referrer only expose a token that
  // grants file reads and expires within minutes.
  async getFileAccessToken(): Promise<{ token: string; expires_in: number }> {
    const { data } = await apiClient.get('/files/access-token')
    return data as { token: string; expires_in: number }
  },

  // User info
  async getMe(token: string) {
    const { data } = await apiClient.get('/users/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    return data as UserResponse
  },

  async updateMe(payload: UpdateProfileRequest) {
    const { data } = await apiClient.put('/users/me', payload)
    return data as UserResponse
  },

  async checkNickname(nickname: string) {
    const { data } = await apiClient.get('/users/check-nickname', { params: { nickname } })
    return data as { available: boolean; reason?: string }
  },

  async uploadAvatar(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post('/users/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data as UserResponse
  },
}
