import { request } from '@/services/request'
import type { AuthResponse, AuthUser, PlanTripRequest, TripResponse } from '@/types/trip'

export interface ForgotPasswordResponse {
  message: string
  reset_token?: string | null
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
      url: '/trip/plan',
      method: 'POST',
      data: payload,
      timeout: 180000
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

  getWeather(city: string, days = 3) {
    return request<any[]>({
      url: '/trip/weather',
      params: { city, days }
    })
  },

  planTencentRoutes(payload: any) {
    return request<any>({
      url: '/trip/route/tencent',
      method: 'POST',
      data: payload,
      timeout: 60000
    })
  }
}
