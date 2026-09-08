import { request, buildApiUrl } from '@/services/request'
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
  partial_result?: TripResponse | null
  error?: string
  error_code?: string
  retryable?: boolean
}

type PlanStreamEventName = 'status' | 'partial_result' | 'result' | 'done' | 'error'

export interface PlanStreamEvent {
  event: PlanStreamEventName
  data: any
}

export interface PlanProgressEvent {
  step?: string
  message?: string
  progress?: number
  partial_result?: TripResponse | null
}

type PlanningError = Error & {
  code?: string
  retryable?: boolean
  operatorAction?: string
}

type ChunkedRequestTask = UniApp.RequestTask & {
  onChunkReceived?: (callback: (response: { data: ArrayBuffer }) => void) => void
}

const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds))
const PLAN_JOB_MAX_WAIT_MS = 30 * 60 * 1000
const PLAN_JOB_POLL_INTERVAL_INITIAL_MS = 1000
const PLAN_JOB_POLL_INTERVAL_MS = 2500

const parseSseChunk = (chunk: string, onEvent: (event: PlanStreamEvent) => void) => {
  const blocks = chunk.replace(/\r\n/g, '\n').split('\n\n')
  const rest = blocks.pop() || ''
  for (const block of blocks) {
    const lines = block.split('\n')
    let event: PlanStreamEventName = 'status'
    const dataLines: string[] = []
    for (const line of lines) {
      if (line.startsWith('event:')) event = line.slice(6).trim() as PlanStreamEventName
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (!dataLines.length) continue
    try {
      onEvent({ event, data: JSON.parse(dataLines.join('\n')) })
    } catch (error) {
      console.warn('Failed to parse planning SSE event:', error)
    }
  }
  return rest
}

const createPlanningError = (payload: any, fallback = '行程规划失败，请稍后重试'): PlanningError => {
  const error = new Error(String(payload?.message || payload?.error || fallback)) as PlanningError
  error.code = String(payload?.code || payload?.error_code || '')
  error.retryable = payload?.retryable !== false
  error.operatorAction = String(payload?.operator_action || payload?.operatorAction || '')
  return error
}

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
      url: '/trip/planning',
      method: 'POST',
      data: payload,
      timeout: 300000
    })
  },

  startPlanTripJob(payload: PlanTripRequest) {
    return request<PlanJobStartResponse>({
      url: '/trip/planning/jobs',
      method: 'POST',
      data: payload,
      timeout: 30000
    })
  },

  getPlanTripJob(jobId: string) {
    return request<PlanJobResponse>({
      url: `/trip/planning/jobs/${jobId}`,
      timeout: 30000
    })
  },

  async planTripWithPolling(payload: PlanTripRequest, onProgress?: (job: PlanJobResponse) => void) {
    const started = await this.startPlanTripJob(payload)
    if (!started.job_id) throw new Error('规划任务启动失败，请稍后重试')

    const deadline = Date.now() + PLAN_JOB_MAX_WAIT_MS
    let pollingFailures = 0
    let pollCount = 0
    while (Date.now() < deadline) {
      // Adaptive polling: start fast (1s) then slow down (2.5s) after 5 polls
      const interval = pollCount < 5 ? PLAN_JOB_POLL_INTERVAL_INITIAL_MS : PLAN_JOB_POLL_INTERVAL_MS
      pollCount += 1
      await wait(interval)
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
        throw createPlanningError({
          message: job.error || '行程规划失败，请稍后重试',
          code: job.error_code,
          retryable: job.retryable
        })
      }
    }
    throw new Error('规划任务等待超时，请稍后在行程页查看或重新生成')
  },

  planTripWithSse(payload: PlanTripRequest, onProgress?: (event: PlanProgressEvent) => void) {
    return new Promise<TripResponse>((resolve, reject) => {
      let buffer = ''
      let settled = false
      let requestTask: ChunkedRequestTask | null = null

      const finish = (callback: () => void) => {
        if (settled) return
        settled = true
        callback()
      }

      requestTask = uni.request({
        url: buildApiUrl('/trip/planning/stream'),
        method: 'POST',
        data: payload as any,
        timeout: PLAN_JOB_MAX_WAIT_MS,
        enableChunked: true,
        header: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream'
        },
        success: (res) => {
          if (settled) return
          if (res.statusCode < 200 || res.statusCode >= 300) {
            finish(() => reject(new Error('规划服务暂时不可用，请稍后重试')))
          }
        },
        fail: (err) => {
          finish(() => reject(new Error(String((err as any)?.errMsg || 'SSE 连接失败'))))
        }
      }) as ChunkedRequestTask

      if (!requestTask?.onChunkReceived) {
        finish(() => reject(new Error('当前微信基础库不支持流式生成')))
        return
      }

      requestTask.onChunkReceived((response: { data: ArrayBuffer }) => {
        const text = arrayBufferToText(response.data)
        buffer = parseSseChunk(buffer + text, (event) => {
          if (event.event === 'status') {
            onProgress?.(event.data || {})
            return
          }
          if (event.event === 'partial_result') {
            onProgress?.({ partial_result: event.data || null })
            return
          }
          if (event.event === 'result') {
            finish(() => resolve(event.data as TripResponse))
            return
          }
          if (event.event === 'error') {
            finish(() => reject(createPlanningError(event.data)))
          }
        })
      })
    })
  },

  async planTripRealtime(payload: PlanTripRequest, onProgress?: (event: PlanProgressEvent) => void) {
    // Keep one durable backend job per user action. Falling back from an SSE
    // POST would otherwise create a second agent run after a connection drop.
    return this.planTripWithPolling(payload, (job) => {
      onProgress?.({
        step: job.step,
        message: job.message,
        progress: job.progress,
        partial_result: job.partial_result
      })
    })
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

  nearbyPlaces(point: any) {
    return request<any>({ url: '/trip/map/around', method: 'POST', data: { point, keyword: '餐厅', radius: 1500 }, timeout: 65000 })
  },
  poiDetail(id: string) {
    return request<any>({ url: `/trip/map/pois/${encodeURIComponent(id)}`, method: 'GET', timeout: 65000 })
  },
  exportMap(payload: any) {
    return request<{ url: string }>({ url: '/trip/map/export', method: 'POST', data: payload, timeout: 65000 })
  },
  planMapRoutes(payload: any) {
    return request<any>({
      url: '/trip/route/map',
      method: 'POST',
      data: payload,
      timeout: 180000
    })
  }
}

const arrayBufferToText = (buffer: ArrayBuffer) => {
  const decoder = typeof TextDecoder !== 'undefined' ? new TextDecoder('utf-8') : null
  if (decoder) return decoder.decode(buffer)
  const bytes = new Uint8Array(buffer)
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  try {
    return decodeURIComponent(escape(binary))
  } catch {
    return binary
  }
}
