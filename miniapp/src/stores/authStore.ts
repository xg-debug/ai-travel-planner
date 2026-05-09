import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { clearAuthToken, setAuthToken } from '@/services/request'
import { tripApi } from '@/services/tripApi'
import type { AuthUser } from '@/types/trip'

const USER_KEY = 'cybertravel_user'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const token = ref<string>('')
  const isLoading = ref(false)
  const error = ref('')

  const isAuthenticated = computed(() => Boolean(user.value && token.value))
  const userName = computed(() => user.value?.name || '旅行者')

  const persist = (nextUser: AuthUser, nextToken: string) => {
    user.value = nextUser
    token.value = nextToken
    setAuthToken(nextToken)
    uni.setStorageSync(USER_KEY, nextUser)
  }

  const restore = () => {
    const savedToken = uni.getStorageSync('cybertravel_auth_token') as string
    const savedUser = uni.getStorageSync(USER_KEY) as AuthUser | ''
    if (savedToken) token.value = savedToken
    if (savedUser) user.value = savedUser
  }

  const login = async (email: string, password: string) => {
    isLoading.value = true
    error.value = ''
    try {
      const auth = await tripApi.login(email, password, true)
      persist(auth.user, auth.token)
      return auth
    } catch (err) {
      error.value = err instanceof Error ? err.message : '登录失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const register = async (email: string, password: string, name: string) => {
    isLoading.value = true
    error.value = ''
    try {
      const auth = await tripApi.register(email, password, name, true)
      persist(auth.user, auth.token)
      return auth
    } catch (err) {
      error.value = err instanceof Error ? err.message : '注册失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const refreshProfileSilently = async () => {
    if (!token.value) return
    try {
      const me = await tripApi.getMe()
      user.value = me
      uni.setStorageSync(USER_KEY, me)
    } catch {
      logout()
    }
  }

  const logout = () => {
    user.value = null
    token.value = ''
    error.value = ''
    clearAuthToken()
    uni.removeStorageSync(USER_KEY)
  }

  return {
    user,
    token,
    isLoading,
    error,
    isAuthenticated,
    userName,
    restore,
    login,
    register,
    refreshProfileSilently,
    logout
  }
})
