import { request } from '@/services/request'
import type { AuthResponse, AuthUser, PlanTripRequest, TripResponse } from '@/types/trip'

export interface ForgotPasswordResponse {
  message: string
  reset_token?: string | null
}

type PlanJobStatus = 'running' | 'completed' | 'failed'

interface PlanJobStartResponse {
  job_id: string
  status: PlanJobStatus
}

export interface PlanJobResponse {
  job_id: string
  status: PlanJobStatus
  step?: string
  message?: string
  progress?: number
  updated_at?: number
  result?: TripResponse | null
  error?: string
}

const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds))
const PLAN_JOB_MAX_WAIT_MS = 30 * 60 * 1000
const PLAN_JOB_POLL_INTERVAL_MS = 2500

export const tripApi = {
  register(email: string, password: string, name?: string, rememberMe = true) {
    return request<AuthResponse>({
      url: '/auth/register',
      method: 'POST',
      data: { email, password, name, remember_me: rememberMe }
    })
  },

  login(email: string, password: string, rememberMe = true) {
    return request<AuthResponse>({
      url: '/auth/login',
      method: 'POST',
      data: { email, password, remember_me: rememberMe }
    })
  },

  getMe() {
    return request<AuthUser>({ url: '/auth/me' })
  },

  forgotPassword(email: string) {
    return request<ForgotPasswordResponse>({
      url: '/auth/forgot-password',
      method: 'POST',
      data: { email }
    })
  },

  updateMe(updates: Partial<{ name: string; avatar_url: string }>) {
    return request<AuthUser>({
      url: '/users/me',
      method: 'PUT',
      data: updates
    })
  },

  planTrip(payload: PlanTripRequest) {
    return request<TripResponse>({
      url: '/trip/plan',
      method: 'POST',
      data: payload,
      timeout: 300000
    })
  },

  startPlanTripJob(payload: PlanTripRequest) {
    return request<PlanJobStartResponse>({
      url: '/trip/plan/jobs',
      method: 'POST',
      data: payload,
      timeout: 30000
    })
  },

  getPlanTripJob(jobId: string) {
    return request<PlanJobResponse>({
      url: `/trip/plan/jobs/${jobId}`,
      timeout: 30000
    })
  },

  async planTripWithPolling(payload: PlanTripRequest, onProgress?: (job: PlanJobResponse) => void) {
    const started = await this.startPlanTripJob(payload)
    if (!started.job_id) throw new Error('规划任务启动失败，请稍后重试')

    const deadline = Date.now() + PLAN_JOB_MAX_WAIT_MS
    let pollingFailures = 0
    while (Date.now() < deadline) {
      await wait(PLAN_JOB_POLL_INTERVAL_MS)
      let job: PlanJobResponse
      try {
        job = await this.getPlanTripJob(started.job_id)
        pollingFailures = 0
      } catch (error) {
        pollingFailures += 1
        if (pollingFailures >= 5) throw error
        continue
      }
      onProgress?.(job)
      if (job.status === 'completed') {
        if (!job.result) throw new Error('规划任务已完成，但未返回行程结果')
        return job.result
      }
      if (job.status === 'failed') {
        throw new Error(job.error || '行程规划失败，请稍后重试')
      }
    }
    throw new Error('规划任务等待超时，请稍后在行程页查看或重新生成')
  },

  listTripPlans() {
    return request<any[]>({ url: '/trip/plans' })
  },

  getTripPlan(id: string) {
    return request<any>({ url: `/trip/plans/${id}` })
  },

  createTripPlan(payload: any) {
    return request<any>({
      url: '/trip/plans',
      method: 'POST',
      data: payload
    })
  },

  updateTripPlan(id: string, payload: any) {
    return request<any>({
      url: `/trip/plans/${id}`,
      method: 'PUT',
      data: payload
    })
  },

  deleteTripPlan(id: string) {
    return request<{ ok: boolean }>({
      url: `/trip/plans/${id}`,
      method: 'DELETE'
    })
  },

  getWeather(city: string, days = 3) {
    return request<any[]>({
      url: '/trip/weather',
      params: { city, days }
    })
  },

  planMapRoutes(payload: any) {
    return request<any>({
      url: '/trip/route/map',
      method: 'POST',
      data: payload,
      timeout: 60000
    })
  },

  planTencentRoutes(payload: any) {
    return this.planMapRoutes(payload)
  }
}
