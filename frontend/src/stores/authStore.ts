import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { tripApi } from '@/services/api'

export interface User {
  id: string
  email: string
  name: string
  avatar?: string
  createdAt: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const AUTH_STORAGE_KEY = 'cybertravel_auth'

  // State
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const rememberMe = ref(true)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const isAuthenticated = computed(() => !!user.value && !!token.value)
  const userName = computed(() => user.value?.name || '游客')
  const userEmail = computed(() => user.value?.email || '')
  const userAvatar = computed(() => user.value?.avatar || '')

  // Actions
  const persistAuth = (usePersistentStorage: boolean) => {
    const payload = JSON.stringify({
      user: user.value,
      token: token.value,
      rememberMe: usePersistentStorage
    })
    if (usePersistentStorage) {
      localStorage.setItem(AUTH_STORAGE_KEY, payload)
      sessionStorage.removeItem(AUTH_STORAGE_KEY)
    } else {
      sessionStorage.setItem(AUTH_STORAGE_KEY, payload)
      localStorage.removeItem(AUTH_STORAGE_KEY)
    }
  }

  const login = async (email: string, password: string, remember: boolean = true) => {
    isLoading.value = true
    error.value = null

    try {
      const auth = await tripApi.login(email, password)
      user.value = auth.user
      token.value = auth.token
      rememberMe.value = remember
      persistAuth(remember)
      return auth
    } catch (err) {
      error.value = err instanceof Error ? err.message : '登录失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const register = async (email: string, password: string, name: string, remember: boolean = true) => {
    isLoading.value = true
    error.value = null

    try {
      const auth = await tripApi.register(email, password, name)
      user.value = auth.user
      token.value = auth.token
      rememberMe.value = remember
      persistAuth(remember)
      return auth
    } catch (err) {
      error.value = err instanceof Error ? err.message : '注册失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const logout = () => {
    user.value = null
    token.value = null
    error.value = null
    localStorage.removeItem(AUTH_STORAGE_KEY)
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
  }

  const updateProfile = async (updates: Partial<User>) => {
    if (!user.value) throw new Error('用户未登录')
    
    try {
      const updated = await tripApi.updateMe({
        name: updates.name,
        avatar_url: updates.avatar
      })
      user.value = {
        ...user.value,
        name: updated.name ?? user.value.name,
        avatar: updated.avatar_url ?? user.value.avatar
      }
      
      persistAuth(rememberMe.value)
      
      return user.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '更新资料失败'
      throw err
    }
  }

  // Local storage persistence
  const saveToLocalStorage = () => {
    try {
      persistAuth(rememberMe.value)
    } catch (err) {
      console.error('Failed to save auth to localStorage:', err)
    }
  }

  const loadFromLocalStorage = () => {
    try {
      const saved = localStorage.getItem(AUTH_STORAGE_KEY) || sessionStorage.getItem(AUTH_STORAGE_KEY)
      if (saved) {
        const data = JSON.parse(saved)
        user.value = data.user
        token.value = data.token
        rememberMe.value = Boolean(data.rememberMe ?? localStorage.getItem(AUTH_STORAGE_KEY))
      }
    } catch (err) {
      console.error('Failed to load auth from localStorage:', err)
    }
  }

  const refreshProfile = async () => {
    if (!token.value) return
    try {
      const me = await tripApi.getMe()
      user.value = me
      persistAuth(rememberMe.value)
    } catch (err) {
      logout()
    }
  }

  const forgotPassword = async (email: string) => {
    isLoading.value = true
    error.value = null
    try {
      return await tripApi.forgotPassword(email)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '发送重置请求失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const resetPassword = async (resetToken: string, newPassword: string) => {
    isLoading.value = true
    error.value = null
    try {
      return await tripApi.resetPassword(resetToken, newPassword)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '重置密码失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // Initialize
  loadFromLocalStorage()
  refreshProfile()

  return {
    // State
    user,
    token,
    rememberMe,
    isLoading,
    error,

    // Computed
    isAuthenticated,
    userName,
    userEmail,
    userAvatar,

    // Actions
    login,
    register,
    logout,
    updateProfile,
    refreshProfile,
    forgotPassword,
    resetPassword,
    persistAuth,
    saveToLocalStorage,
    loadFromLocalStorage
  }
})
