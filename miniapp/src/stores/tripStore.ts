import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { tripApi, type PlanProgressEvent } from '@/services/tripApi'
import type { HotelRecommendation, POI, Trip, TripRequest } from '@/types/trip'
import { addDays } from '@/utils/format'
import { convertTripResponse } from '@/utils/tripTransform'
import { useAuthStore } from '@/stores/authStore'

type StepStatus = 'pending' | 'active' | 'done' | 'error'

export interface GenerationStep {
  key: string
  label: string
  status: StepStatus
}

const LAST_TRIP_KEY = 'cybertravel_last_trip'
const TRIP_TIMESTAMP_KEY = 'cybertravel_last_trip_ts'
const DRAFT_KEY = 'cybertravel_plan_draft'
const TRIP_MAX_AGE_MS = 24 * 60 * 60 * 1000 // 24 hours
const buildSteps = (): GenerationStep[] => [
  { key: 'request_analysis', label: '拆解旅行需求', status: 'pending' },
  { key: 'weather_lookup', label: '执行工具查询', status: 'pending' },
  { key: 'attraction_search', label: '筛选景点', status: 'pending' },
  { key: 'food_search', label: '筛选美食', status: 'pending' },
  { key: 'hotel_search', label: '匹配住宿', status: 'pending' },
  { key: 'transport_planning', label: '规划交通', status: 'pending' },
  { key: 'itinerary_review', label: '检查结果', status: 'pending' },
  { key: 'itinerary_synthesis', label: '生成每日行程', status: 'pending' },
  { key: 'budget_estimation', label: '计算预算', status: 'pending' },
  { key: 'risk_notices', label: '生成提醒', status: 'pending' },
  { key: 'summary', label: '整理结果', status: 'pending' }
]

export const useTripStore = defineStore('trip', () => {
  const currentTrip = ref<Trip | null>(null)
  const tripHistory = ref<Trip[]>([])
  const draft = ref<TripRequest | null>(null)
  const isGenerating = ref(false)
  const isLoadingHistory = ref(false)
  const error = ref('')
  const errorCode = ref('')
  const errorRetryable = ref(true)
  const steps = ref<GenerationStep[]>(buildSteps())
  const activeStepIndex = ref(0)
  let localTimer: ReturnType<typeof setInterval> | null = null

  const hasCurrentTrip = computed(() => Boolean(currentTrip.value))
  const isTripStale = computed(() => {
    if (!currentTrip.value) return false
    const savedAt = uni.getStorageSync(TRIP_TIMESTAMP_KEY) as number | ''
    if (!savedAt) return false
    return Date.now() - Number(savedAt) > TRIP_MAX_AGE_MS
  })
  const activeStepLabel = computed(() => steps.value[activeStepIndex.value]?.label || '准备生成')

  const restoreLocal = () => {
    const savedTrip = uni.getStorageSync(LAST_TRIP_KEY) as Trip | ''
    const savedDraft = uni.getStorageSync(DRAFT_KEY) as TripRequest | ''
    if (savedTrip) {
      currentTrip.value = savedTrip
      if (isTripStale.value) {
        uni.showToast({ title: '行程天气数据可能已过期，建议重新规划', icon: 'none', duration: 2500 })
      }
    }
    if (savedDraft) draft.value = savedDraft
  }

  const setDraft = (payload: TripRequest) => {
    draft.value = {
      ...payload,
      endDate: payload.endDate || addDays(payload.startDate, payload.days - 1),
      departureTime: payload.departureTime || '08:00',
      returnArrivalTime: payload.returnArrivalTime || '20:00'
    }
    uni.setStorageSync(DRAFT_KEY, draft.value)
  }

  const startLocalProgress = () => {
    stopLocalProgress()
    steps.value = buildSteps()
    activeStepIndex.value = 0
    steps.value[0].status = 'active'
  }

  const stopLocalProgress = () => {
    if (localTimer) clearInterval(localTimer)
    localTimer = null
  }

  const markDone = () => {
    stopLocalProgress()
    steps.value = steps.value.map((step) => ({ ...step, status: 'done' }))
    activeStepIndex.value = steps.value.length - 1
  }

  const markError = () => {
    stopLocalProgress()
    activeStepIndex.value = steps.value.length - 1
    steps.value = steps.value.map((step, index) => ({
      ...step,
      status: index === activeStepIndex.value ? 'error' : step.status
    }))
  }

  const applyRemoteProgress = (event: PlanProgressEvent) => {
    const rawStep = String(event.step || '').trim()
    const normalizedStep = rawStep
    if (!normalizedStep) return

    const nextIndex = steps.value.findIndex((step) => step.key === normalizedStep)
    if (nextIndex < 0) return

    const targetIndex = Math.max(activeStepIndex.value, nextIndex)
    activeStepIndex.value = targetIndex
    steps.value = steps.value.map((step, index) => ({
      ...step,
      status: index < targetIndex ? 'done' : index === targetIndex ? 'active' : 'pending'
    }))
  }

  const generateFromDraft = async () => {
    if (!draft.value) throw new Error('请先填写旅行需求')
    isGenerating.value = true
    error.value = ''
    errorCode.value = ''
    errorRetryable.value = true
    startLocalProgress()
    try {
      const response = await tripApi.planTripRealtime(draft.value, applyRemoteProgress)
      const trip = convertTripResponse(response, draft.value)
      if (!trip.days.length) throw new Error(response.plan || 'AI 未生成可用行程，请稍后重试')

      const authStore = useAuthStore()
      const savedTrip = authStore.isAuthenticated
        ? await tripApi.createTripPlan(trip)
        : trip

      currentTrip.value = savedTrip as Trip
      uni.setStorageSync(LAST_TRIP_KEY, currentTrip.value)
      uni.setStorageSync(TRIP_TIMESTAMP_KEY, Date.now())
      tripHistory.value = [
        currentTrip.value,
        ...tripHistory.value.filter((item) => item.id !== currentTrip.value?.id)
      ]
      markDone()
      return currentTrip.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成失败'
      errorCode.value = String((err as any)?.code || '')
      errorRetryable.value = (err as any)?.retryable !== false
      markError()
      throw err
    } finally {
      isGenerating.value = false
    }
  }

  const loadHistory = async () => {
    const authStore = useAuthStore()
    restoreLocal()
    if (!authStore.isAuthenticated) {
      tripHistory.value = currentTrip.value ? [currentTrip.value] : []
      return
    }
    isLoadingHistory.value = true
    try {
      const items = await tripApi.listTripPlans()
      tripHistory.value = (items || []) as Trip[]
      if (!currentTrip.value && tripHistory.value.length) {
        currentTrip.value = tripHistory.value[0]
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载行程失败'
    } finally {
      isLoadingHistory.value = false
    }
  }

  const loadTrip = async (id: string) => {
    const local = tripHistory.value.find((item) => item.id === id)
    if (local) {
      currentTrip.value = local
      uni.setStorageSync(LAST_TRIP_KEY, local)
      uni.setStorageSync(TRIP_TIMESTAMP_KEY, Date.now())
      return local
    }
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) return null
    const remote = await tripApi.getTripPlan(id)
    currentTrip.value = remote as Trip
    uni.setStorageSync(LAST_TRIP_KEY, currentTrip.value)
    uni.setStorageSync(TRIP_TIMESTAMP_KEY, Date.now())
    return currentTrip.value
  }

  const deleteTrip = async (id: string) => {
    const authStore = useAuthStore()
    if (authStore.isAuthenticated) {
      await tripApi.deleteTripPlan(id)
    }
    tripHistory.value = tripHistory.value.filter((item) => item.id !== id)
    if (currentTrip.value?.id === id) {
      currentTrip.value = tripHistory.value[0] || null
      if (currentTrip.value) uni.setStorageSync(LAST_TRIP_KEY, currentTrip.value)
      else uni.removeStorageSync(LAST_TRIP_KEY)
    }
  }

  const updateCurrentTrip = (updater: (trip: Trip) => Trip) => {
    if (!currentTrip.value) return null
    currentTrip.value = updater(currentTrip.value)
    uni.setStorageSync(LAST_TRIP_KEY, currentTrip.value)
    uni.setStorageSync(TRIP_TIMESTAMP_KEY, Date.now())
    tripHistory.value = tripHistory.value.map((item) =>
      item.id === currentTrip.value?.id ? currentTrip.value : item
    )
    return currentTrip.value
  }

  const setTripHotel = (hotel: POI) => {
    const recommendation: HotelRecommendation = {
      name: hotel.name,
      address: hotel.address || '',
      priceEstimate: hotel.priceText || '',
      referencePriceRange: hotel.referencePriceRange || hotel.priceText || '',
      budgetPricePerRoom: hotel.budgetPricePerRoom,
      reason: hotel.description || `${hotel.name}适合作为本次路线的住宿落点。`,
      rating: hotel.rating,
      coordinates: hotel.location?.lat && hotel.location?.lng
        ? { lat: hotel.location.lat, lng: hotel.location.lng }
        : undefined
    }
    return updateCurrentTrip((trip) => ({
      ...trip,
      hotels: [
        hotel,
        ...(trip.hotels || []).filter((item) => item.id !== hotel.id && item.name !== hotel.name)
      ],
      days: trip.days.map((day) => ({ ...day, hotel: recommendation })),
      updatedAt: new Date().toISOString()
    }))
  }

  const clearLocal = () => {
    currentTrip.value = null
    draft.value = null
    tripHistory.value = []
    uni.removeStorageSync(LAST_TRIP_KEY)
    uni.removeStorageSync(DRAFT_KEY)
  }

  return {
    currentTrip,
    tripHistory,
    draft,
    isGenerating,
    isLoadingHistory,
    error,
    errorCode,
    errorRetryable,
    steps,
    activeStepIndex,
    hasCurrentTrip,
    isTripStale,
    activeStepLabel,
    restoreLocal,
    setDraft,
    generateFromDraft,
    loadHistory,
    loadTrip,
    deleteTrip,
    setTripHotel,
    clearLocal,
    stopLocalProgress
  }
})
