import axios from 'axios'
import type { TripResponse } from '@/types/trip'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

const AUTH_STORAGE_KEY = 'cybertravel_auth'

const toFriendlyErrorMessage = (raw: string, status?: number): string => {
  const text = String(raw || '').trim()
  const lower = text.toLowerCase()
  if (!text) return '服务暂时不可用，请稍后重试'
  if (lower.includes('insufficient balance') || text.includes('余额不足') || status === 402) {
    return 'AI 服务余额不足，请检查账户余额后重试'
  }
  if (lower.includes('timeout') || lower.includes('timed out')) {
    return 'AI 服务响应超时，请稍后重试'
  }
  if (text.includes('未配置可用的AI模型密钥') || text.includes('未检测到可用的 LLM API Key')) {
    return '模型密钥未配置，请联系管理员检查后端环境变量'
  }
  if (lower.includes('network') || lower.includes('failed to fetch')) {
    return '网络连接异常，请检查网络后重试'
  }
  if (status && status >= 500) {
    return '服务暂时不可用，请稍后重试'
  }
  return text
}

const parseErrorResponseText = (text: string): { message: string; status?: number } => {
  if (!text) return { message: '服务暂时不可用，请稍后重试' }
  try {
    const parsed = JSON.parse(text)
    const message = parsed?.detail || parsed?.message || text
    return { message: String(message) }
  } catch {
    return { message: text }
  }
}

const readPersistedAuth = () => {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY) || sessionStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const parsed = readPersistedAuth()
    if (parsed?.token) {
      config.headers.Authorization = `Bearer ${parsed.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    
    if (error.response) {
      // 服务器返回错误状态码
      const rawMessage = error.response.data?.detail || error.response.data?.message || '服务器错误'
      const message = toFriendlyErrorMessage(rawMessage, error.response.status)
      return Promise.reject(new Error(message))
    } else if (error.code === 'ECONNABORTED') {
      return Promise.reject(new Error('请求超时，请稍后重试'))
    } else if (error.request) {
      // 请求已发送但没有收到响应
      return Promise.reject(new Error('网络连接错误，请检查网络连接'))
    } else {
      // 请求配置错误
      return Promise.reject(new Error('请求配置错误'))
    }
  }
)

export interface AuthUser {
  id: string
  email: string
  name: string
  avatar?: string
  createdAt: string
}

export interface AuthResponse {
  user: AuthUser
  token: string
  token_expires_in_minutes: number
}

export interface ForgotPasswordResponse {
  message: string
  reset_token?: string | null
}

export interface PlanTripRequest {
  query: string
  city: string
  days: number
  preferences?: string[]
  budget?: string
  travelers?: number
  start_date?: string
}

export interface WeatherApiItem {
  city: string
  date: string
  temperature: number
  condition: string
  humidity: number
  wind_speed: number
  icon: string
}

export interface PlanStreamEvent {
  event: 'status' | 'result' | 'done' | 'error'
  data: any
}

export const tripApi = {
  async register(email: string, password: string, name?: string, rememberMe: boolean = true): Promise<AuthResponse> {
    return (await api.post('/auth/register', { email, password, name, remember_me: rememberMe })) as AuthResponse
  },

  async login(email: string, password: string, rememberMe: boolean = true): Promise<AuthResponse> {
    return (await api.post('/auth/login', { email, password, remember_me: rememberMe })) as AuthResponse
  },

  async getMe(): Promise<AuthUser> {
    return (await api.get('/auth/me')) as AuthUser
  },

  async forgotPassword(email: string): Promise<ForgotPasswordResponse> {
    return (await api.post('/auth/forgot-password', { email })) as ForgotPasswordResponse
  },

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    return (await api.post('/auth/reset-password', { token, new_password: newPassword })) as {
      message: string
    }
  },

  async updateMe(updates: Partial<{ name: string; avatar_url: string }>): Promise<any> {
    return api.put('/users/me', updates)
  },

  // 规划行程
  async planTrip(request: PlanTripRequest): Promise<TripResponse> {
    return api.post('/trip/plan', request, { timeout: 180000 })
  },

  async listTripPlans(): Promise<any[]> {
    return (await api.get('/trip/plans')) as any[]
  },

  async getTripPlan(id: string): Promise<any> {
    return (await api.get(`/trip/plans/${id}`)) as any
  },

  async createTripPlan(payload: any): Promise<any> {
    return (await api.post('/trip/plans', payload)) as any
  },

  async updateTripPlan(id: string, payload: any): Promise<any> {
    return (await api.put(`/trip/plans/${id}`, payload)) as any
  },

  async deleteTripPlan(id: string): Promise<{ ok: boolean }> {
    return (await api.delete(`/trip/plans/${id}`)) as { ok: boolean }
  },

  async planTripStream(
    request: PlanTripRequest,
    onEvent?: (event: PlanStreamEvent) => void
  ): Promise<TripResponse> {
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'
    const url = `${baseURL}/trip/plan/stream`
    const auth = readPersistedAuth()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    if (auth?.token) {
      headers.Authorization = `Bearer ${auth.token}`
    }

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 180000)
    let response: Response
    try {
      response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
        signal: controller.signal
      })
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        throw new Error('生成超时，请稍后重试')
      }
      throw new Error(toFriendlyErrorMessage(err?.message || '网络请求失败'))
    } finally {
      clearTimeout(timeout)
    }

    if (!response.ok || !response.body) {
      const text = await response.text()
      const { message } = parseErrorResponseText(text)
      throw new Error(toFriendlyErrorMessage(message, response.status))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let finalResult: TripResponse | null = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      while (buffer.includes('\n\n')) {
        const idx = buffer.indexOf('\n\n')
        const block = buffer.slice(0, idx).trim()
        buffer = buffer.slice(idx + 2)
        if (!block) continue

        const lines = block.split('\n')
        let eventName = 'message'
        let dataText = ''
        for (const line of lines) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          if (line.startsWith('data:')) dataText += line.slice(5).trim()
        }
        if (!dataText) continue
        let parsed: any
        try {
          parsed = JSON.parse(dataText)
        } catch {
          continue
        }
        const evt = { event: eventName as PlanStreamEvent['event'], data: parsed }
        onEvent?.(evt)

        if (evt.event === 'result') {
          finalResult = parsed as TripResponse
        }
        if (evt.event === 'error') {
          throw new Error(toFriendlyErrorMessage(parsed?.message || '流式生成失败'))
        }
      }
    }

    if (!finalResult) {
      throw new Error('未收到完整行程结果，请稍后重试')
    }
    return finalResult
  },
  
  // 获取天气预报
  async getWeather(city: string, days: number = 3): Promise<WeatherApiItem[]> {
    return (await api.get('/trip/weather', {
      params: { city, days }
    })) as WeatherApiItem[]
  },
  
  // 搜索POI
  async searchPOI(keyword: string, city: string, page: number = 1, size: number = 10): Promise<any[]> {
    return (await api.get('/trip/pois/search', {
      params: { keyword, city, page, size }
    })) as any[]
  },
  
  // 获取推荐
  async getRecommendations(city: string, preferences?: string[]): Promise<{ recommendations: any[] }> {
    const prefString = preferences?.join(',')
    return (await api.get('/trip/recommendations', {
      params: { 
        city, 
        preferences: prefString 
      }
    })) as { recommendations: any[] }
  },
  
  // 估算预算
  async estimateBudget(itinerary: any[], travelers: number = 1, budgetLevel: string = "中等") {
    return api.post('/trip/budget/estimate', {
      itinerary,
      travelers,
      budget_level: budgetLevel
    })
  },
  
  // 优化路线
  async optimizeRoute(pois: any[], constraints?: any) {
    return api.post('/trip/route/optimize', {
      pois,
      constraints
    })
  },
  
  // 计算路线
  async calculateRoute(origin: string, destination: string, mode: string = "driving") {
    return api.post('/trip/route/calculate', {
      origin,
      destination,
      mode
    })
  },
  
  // 健康检查
  async healthCheck() {
    return api.get('/trip/health')
  },
}

export default api
