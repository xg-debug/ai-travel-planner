import axios from 'axios'
import type { TripResponse } from '@/types/trip'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

const AUTH_STORAGE_KEY = 'cybertravel_auth'

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
      const message = error.response.data?.detail || error.response.data?.message || '服务器错误'
      return Promise.reject(new Error(message))
    } else if (error.request) {
      // 请求已发送但没有收到响应
      return Promise.reject(new Error('网络连接错误，请检查网络连接'))
    } else {
      // 请求配置错误
      return Promise.reject(new Error('请求配置错误'))
    }
  }
)

// 反馈接口类型
export interface FeedbackRequest {
  trip_id?: string
  rating: number
  category: string
  comment: string
  user_email?: string
  user_name?: string
}

export interface FeedbackResponse {
  id: string
  trip_id?: string
  rating: number
  category: string
  comment: string
  user_email?: string
  user_name?: string
  created_at: string
  updated_at: string
}

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

export const tripApi = {
  async register(email: string, password: string, name: string): Promise<AuthResponse> {
    return (await api.post('/auth/register', { email, password, name })) as AuthResponse
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    return (await api.post('/auth/login', { email, password })) as AuthResponse
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
    return api.post('/trip/plan', request)
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
  
  // 提交反馈
  async submitFeedback(feedback: FeedbackRequest): Promise<FeedbackResponse> {
    return api.post('/feedback/', feedback)
  },
  
  // 获取反馈统计
  async getFeedbackStats() {
    return api.get('/feedback/stats')
  }
}

export default api
