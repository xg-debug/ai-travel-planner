import axios from 'axios'
import type { AdminOverview, AdminUser, RuntimeStatus, AuthResponse, AgentRunPage, AgentRunDetail } from '@/types/admin'

const AUTH_STORAGE_KEY = 'travel_admin_auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

const readPersistedAuth = () => {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY) || sessionStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

const toErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail || error.response?.data?.message
    if (detail) return String(detail)
    if (error.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    if (!error.response) return '网络连接异常，请确认后端服务是否可用'
    if (error.response.status === 401) return '登录已过期，请重新登录'
    if (error.response.status === 403) return '当前账号没有操作权限'
    return `服务请求失败：${error.response.status}`
  }
  return error instanceof Error ? error.message : '请求失败'
}

api.interceptors.request.use((config) => {
  const parsed = readPersistedAuth()
  if (parsed?.token) {
    config.headers.Authorization = `Bearer ${parsed.token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => Promise.reject(new Error(toErrorMessage(error)))
)

export const adminApi = {
  async login(email: string, password: string, rememberMe = true): Promise<AuthResponse> {
    return (await api.post('/auth/login', { email, password, remember_me: rememberMe })) as AuthResponse
  },

  async register(email: string, password: string, name = '', rememberMe = true): Promise<AuthResponse> {
    return (await api.post('/auth/register', { email, password, name, remember_me: rememberMe })) as AuthResponse
  },

  async getAdminMe(): Promise<AdminUser> {
    return (await api.get('/admin/me')) as AdminUser
  },

  async getOverview(params?: { days?: number; start_date?: string; end_date?: string }): Promise<AdminOverview> {
    return (await api.get('/admin/overview', { params })) as AdminOverview
  },

  async getRuntimeStatus(): Promise<RuntimeStatus> {
    return (await api.get('/admin/runtime-status')) as RuntimeStatus
  },

  async listAgentRuns(params?: { page?: number; page_size?: number; status?: string; search?: string }): Promise<AgentRunPage> {
    return (await api.get('/admin/agent-runs', { params })) as AgentRunPage
  },

  async getAgentRun(runId: string): Promise<AgentRunDetail> {
    return (await api.get(`/admin/agent-runs/${runId}`)) as AgentRunDetail
  },

  async updateSettings(payload: {
    llm?: { provider?: string; model?: string; api_key?: string }
    map?: { provider?: string; api_key?: string }
  }): Promise<RuntimeStatus> {
    return (await api.put('/admin/settings', payload)) as RuntimeStatus
  },

  async listUsers(): Promise<{ users: AdminUser[] }> {
    return (await api.get('/admin/users')) as { users: AdminUser[] }
  },

  async updateUserRole(userId: string, role: 'user' | 'admin'): Promise<AdminUser> {
    return (await api.patch(`/admin/users/${userId}/role`, { role })) as AdminUser
  }
}

export { AUTH_STORAGE_KEY }
export default api
