import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 120000,  // 2 min — AI pretrain needs ~60s for VLM + SAM
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('subskin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // Let axios auto-detect Content-Type for FormData (multipart/form-data + boundary)
  // Without this, the default 'application/json' header breaks file uploads → 422
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

// Singleton refresh promise — deduplicates concurrent token refresh requests
// when multiple API calls get 401 simultaneously (e.g. Profile page loads
// avatar, /users/me, notifications, and /user/credentials all at once)
let refreshPromise: Promise<string> | null = null

async function refreshToken(): Promise<string> {
  const token = localStorage.getItem('subskin_refresh_token')
  if (!token) {
    throw new Error('No refresh token')
  }
  const { data } = await axios.post('/api/user/refresh-token', {
    refresh_token: token,
  })
  localStorage.setItem('subskin_token', data.access_token)
  if (data.refresh_token) {
    localStorage.setItem('subskin_refresh_token', data.refresh_token)
  }
  return data.access_token
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      const hasRefreshToken = !!localStorage.getItem('subskin_refresh_token')

      if (!hasRefreshToken) {
        localStorage.removeItem('subskin_token')
        localStorage.removeItem('subskin_user')
        window.location.reload()
        return Promise.reject(error)
      }

      originalRequest._retry = true

      try {
        // Use singleton promise so concurrent 401s share one refresh call
        if (!refreshPromise) {
          refreshPromise = refreshToken().finally(() => {
            refreshPromise = null
          })
        }
        const accessToken = await refreshPromise
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return apiClient(originalRequest)
      } catch {
        localStorage.removeItem('subskin_token')
        localStorage.removeItem('subskin_refresh_token')
        localStorage.removeItem('subskin_user')
        window.location.reload()
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  },
)

export default apiClient