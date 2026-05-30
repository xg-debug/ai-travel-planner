import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { adminApi, AUTH_STORAGE_KEY } from '@/services/api'
import type { AdminUser } from '@/types/admin'

export const useAuthStore = defineStore('admin-auth', () => {
  const user = ref<AdminUser | null>(null)
  const token = ref<string | null>(null)
  const rememberMe = ref(true)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const profileLoaded = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value && user.value))
  const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
  const canManageUsers = computed(() => Boolean(user.value?.permissions?.canManageUsers))
  const userName = computed(() => user.value?.name || '管理员')

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

  const loadFromStorage = () => {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY) || sessionStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw)
      user.value = parsed.user || null
      token.value = parsed.token || null
      rememberMe.value = Boolean(parsed.rememberMe ?? localStorage.getItem(AUTH_STORAGE_KEY))
    } catch {
      logout()
    }
  }

  const assertAdminProfile = async () => {
    const adminUser = await adminApi.getAdminMe()
    user.value = adminUser
    profileLoaded.value = true
    persistAuth(rememberMe.value)
    return adminUser
  }

  const login = async (email: string, password: string, remember = true) => {
    isLoading.value = true
    error.value = null
    try {
      const auth = await adminApi.login(email, password, remember)
      token.value = auth.token
      user.value = auth.user as AdminUser
      rememberMe.value = remember
      persistAuth(remember)
      return await assertAdminProfile()
    } catch (err) {
      logout()
      error.value = err instanceof Error ? err.message : '登录失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const register = async (email: string, password: string, name = '', remember = true) => {
    isLoading.value = true
    error.value = null
    try {
      const auth = await adminApi.register(email, password, name, remember)
      token.value = auth.token
      user.value = auth.user as AdminUser
      rememberMe.value = remember
      persistAuth(remember)
      return await assertAdminProfile()
    } catch (err) {
      logout()
      error.value = err instanceof Error ? err.message : '注册失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const ensureProfile = async () => {
    if (!token.value) throw new Error('未登录')
    if (profileLoaded.value && user.value?.permissions) return user.value
    return assertAdminProfile()
  }

  function logout() {
    user.value = null
    token.value = null
    error.value = null
    profileLoaded.value = false
    localStorage.removeItem(AUTH_STORAGE_KEY)
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
  }

  loadFromStorage()

  return {
    user,
    token,
    rememberMe,
    isLoading,
    error,
    isAuthenticated,
    isSuperAdmin,
    canManageUsers,
    userName,
    login,
    register,
    ensureProfile,
    logout,
    persistAuth,
    loadFromStorage
  }
})
