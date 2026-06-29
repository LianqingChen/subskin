import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'

interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('admin_token'))
  const user = ref<User | null>(null)
  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    const res = await request.post('/user/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    const accessToken = res.data.access_token
    token.value = accessToken
    localStorage.setItem('admin_token', accessToken)
    const me = await fetchUser()
    // Reject non-admins explicitly so the login form can surface a clear
    // message instead of silently bouncing via the router guard.
    if (!me?.is_admin) {
      logout()
      throw new Error('该账号没有管理员权限')
    }
    return true
  }

  async function fetchUser() {
    try {
      const res = await request.get('/users/me')
      user.value = res.data
      return res.data
    } catch {
      logout()
      return null
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('admin_token')
    const router = useRouter()
    router.push('/login')
  }

  return { token, user, isLoggedIn, login, fetchUser, logout }
})
