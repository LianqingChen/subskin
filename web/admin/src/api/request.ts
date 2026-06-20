import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 120000  // 2 min — AI pretrain needs ~60s for VLM + SAM
})

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('admin_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token')
      // 不自动跳转，让用户在下次操作时自然发现已登出
      // window.location.hash = '#/login'
    }
    return Promise.reject(error)
  }
)

export default request
