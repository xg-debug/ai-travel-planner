import axios from 'axios'
import type { TripResponse } from '@/types/trip'

const api = axios.create({
  // In development Vite proxies /api to the backend. A relative URL also keeps
  // production and LAN access on the same host instead of pointing every
  // visitor's browser at its own localhost.
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

const AUTH_STORAGE_KEY = 'cybertravel_auth'

const normalizeErrorDetail = (raw: unknown): string => {
  if (typeof raw === 'string') return raw
  if (raw && typeof raw === 'object') {
    const detail = raw as Record<string, unknown>
    return String(detail.message || detail.detail || detail.code || JSON.stringify(detail))
  }
  return String(raw || '')
}

const toFriendlyErrorMessage = (raw: unknown, status?: number): string => {
  const text = normalizeErrorDetail(raw).trim()
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
    return { message: normalizeErrorDetail(message) }
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
      return Promise.reject(new Error('无法连接后端服务，请确认 Docker MySQL 和 8000 端口服务已启动'))
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
  departureCity?: string
  destination: string
  startDate: string
  endDate: string
  departureTime: string
  returnArrivalTime: string
  days: number
  travelers: number
  interests: string[]
  budgetAmount: number
  accommodationPreference: 'budget' | 'mid-range' | 'luxury'
  additionalRequirements?: string
}

export interface WeatherApiItem {
  city: string
  date: string
  temperature: number
  condition: string
  day_condition?: string
  night_condition?: string
  humidity: number
  wind_speed: number
  day_wind_direction?: string
  night_wind_direction?: string
  day_wind_power?: string
  night_wind_power?: string
  icon: string
}

export interface PlanStreamEvent {
  event: 'status' | 'partial_result' | 'result' | 'done' | 'error'
  data: any
}

export interface PlanProgressEvent {
  step?: string
  message?: string
  progress?: number
  partial_result?: TripResponse | null
}

interface PlanJobResponse {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  step?: string
  message?: string
  progress?: number
  result?: TripResponse | null
  partial_result?: TripResponse | null
  error?: string
  error_code?: string
  retryable?: boolean
}

export interface MapPoi {
  id: string
  name: string
  address: string
  lat: number
  lng: number
  opening_hours?: string
  verified?: boolean
}

export interface MapRoutePoint {
  latitude: number
  longitude: number
  title?: string
  poiId?: string
}

export interface MapRoutePlan {
  dayIndex: number
  distance: number
  duration: number
  polyline: MapRoutePoint[]
  legs?: Array<{
    distance?: number
    duration?: number
    mode?: string
    ok?: boolean
    instructions?: string[]
    polylines?: MapRoutePoint[][]
    polyline?: MapRoutePoint[]
    provider?: string
    error?: string
  }>
  provider?: string
  partial?: boolean
  warning?: string
}

export interface MapRouteResponse {
  mode: string
  segments: MapRoutePlan[]
}

const PLAN_MAX_WAIT_MS = 30 * 60 * 1000
const ACTIVE_PLAN_JOB_KEY = 'cybertravel_active_plan_job'
const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds))

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
    return api.post('/trip/planning', request, { timeout: PLAN_MAX_WAIT_MS })
  },

  async startPlanTripJob(request: PlanTripRequest): Promise<{ job_id: string; status: string; guest_token?: string }> {
    return api.post('/trip/planning/jobs', request, { timeout: 30000 })
  },

  async getPlanTripJob(jobId: string, guestToken?: string): Promise<PlanJobResponse> {
    return api.get(`/trip/planning/jobs/${jobId}`, {
      timeout: 30000,
      headers: guestToken ? { 'X-Planning-Token': guestToken } : {}
    })
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

  async updateTripDay(id: string, dayIndex: number, version: number, day: any): Promise<any> {
    return (await api.patch(`/trip/plans/${id}/days/${dayIndex}`, { version, day })) as any
  },

  async deleteTripPlan(id: string): Promise<{ ok: boolean }> {
    return (await api.delete(`/trip/plans/${id}`)) as { ok: boolean }
  },

  async planTripStream(
    request: PlanTripRequest,
    onEvent?: (event: PlanStreamEvent) => void
  ): Promise<TripResponse> {
    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
    const url = `${baseURL}/trip/planning/stream`
    const auth = readPersistedAuth()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    if (auth?.token) {
      headers.Authorization = `Bearer ${auth.token}`
    }

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), PLAN_MAX_WAIT_MS)
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

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

        while (buffer.includes('\n\n')) {
          const idx = buffer.indexOf('\n\n')
          const block = buffer.slice(0, idx).trim()
          buffer = buffer.slice(idx + 2)
          if (!block) continue

          const lines = block.split('\n')
          let eventName = 'message'
          const dataLines: string[] = []
          for (const line of lines) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim()
            if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
          }
          if (!dataLines.length) continue
          let parsed: any
          try {
            parsed = JSON.parse(dataLines.join('\n'))
          } catch {
            continue
          }
          const evt = { event: eventName as PlanStreamEvent['event'], data: parsed }
          onEvent?.(evt)

          if (evt.event === 'result') finalResult = parsed as TripResponse
          if (evt.event === 'error') {
            throw new Error(toFriendlyErrorMessage(parsed || '流式生成失败'))
          }
        }
      }
    } finally {
      clearTimeout(timeout)
    }

    if (!finalResult) {
      throw new Error('未收到完整行程结果，请稍后重试')
    }
    return finalResult
  },

  async planTripWithPolling(
    request: PlanTripRequest,
    onProgress?: (event: PlanProgressEvent) => void
  ): Promise<TripResponse> {
    const requestKey = JSON.stringify(request)
    let jobId = ''
    let guestToken = ''
    try {
      const saved = JSON.parse(sessionStorage.getItem(ACTIVE_PLAN_JOB_KEY) || '{}')
      if (saved.requestKey === requestKey && saved.jobId) {
        jobId = String(saved.jobId)
        guestToken = String(saved.guestToken || '')
        await this.getPlanTripJob(jobId, guestToken)
      }
    } catch (error) {
      if (jobId && !String(error).includes('不存在或已过期')) throw error
      jobId = ''
      sessionStorage.removeItem(ACTIVE_PLAN_JOB_KEY)
    }
    if (!jobId) {
      const started = await this.startPlanTripJob(request)
      if (!started.job_id) throw new Error('规划任务启动失败，请稍后重试')
      jobId = started.job_id
      guestToken = started.guest_token || ''
      sessionStorage.setItem(ACTIVE_PLAN_JOB_KEY, JSON.stringify({ requestKey, jobId, guestToken }))
    }
    const deadline = Date.now() + PLAN_MAX_WAIT_MS
    let failureCount = 0
    let pollCount = 0
    while (Date.now() < deadline) {
      await wait(pollCount++ < 5 ? 1000 : 2500)
      let job: PlanJobResponse
      try {
        job = await this.getPlanTripJob(jobId, guestToken)
        failureCount = 0
      } catch (error) {
        failureCount += 1
        if (failureCount >= 5) throw error
        continue
      }
      onProgress?.({
        step: job.step,
        message: job.message,
        progress: job.progress,
        partial_result: job.partial_result
      })
      if (job.status === 'completed') {
        if (!job.result) throw new Error('规划任务已完成，但未返回行程结果')
        sessionStorage.removeItem(ACTIVE_PLAN_JOB_KEY)
        return job.result
      }
      if (job.status === 'failed') {
        sessionStorage.removeItem(ACTIVE_PLAN_JOB_KEY)
        throw new Error(job.error || '行程规划失败，请稍后重试')
      }
    }
    throw new Error('规划任务等待超时，请稍后重试')
  },

  async planTripRealtime(
    request: PlanTripRequest,
    onProgress?: (event: PlanProgressEvent) => void
  ): Promise<TripResponse> {
    // Jobs are the canonical client transport: a dropped connection can resume
    // polling the same run instead of silently launching a second costly agent.
    return this.planTripWithPolling(request, onProgress)
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

  async nearbyPlaces(point: MapRoutePoint): Promise<{ pois: MapPoi[] }> {
    return api.post('/trip/map/around', { point, keyword: '餐厅', radius: 1500 }, { timeout: 65000 })
  },
  async poiDetail(id: string): Promise<MapPoi> {
    return api.get(`/trip/map/pois/${encodeURIComponent(id)}`, { timeout: 65000 })
  },
  async exportMap(payload: { title: string; segments: Array<{ dayIndex: number; title: string; points: MapRoutePoint[] }> }): Promise<{ url: string }> {
    return api.post('/trip/map/export', payload, { timeout: 65000 })
  },
  async planMapRoutes(payload: {
    city?: string
    mode?: string
    segments: Array<{ dayIndex: number; points: MapRoutePoint[] }>
  }): Promise<MapRouteResponse> {
    return api.post('/trip/route/map', payload, { timeout: 180000 })
  },
  
  // 健康检查
  async healthCheck() {
    return api.get('/trip/health')
  },
}

export default api
