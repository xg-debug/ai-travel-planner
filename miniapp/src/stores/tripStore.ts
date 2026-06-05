import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { tripApi, type PlanJobResponse } from '@/services/tripApi'
import type { Trip, TripRequest } from '@/types/trip'
import { addDays } from '@/utils/format'
import { convertTripResponse, mapBudgetLevel } from '@/utils/tripTransform'
import { useAuthStore } from '@/stores/authStore'

type StepStatus = 'pending' | 'active' | 'done' | 'error'

export interface GenerationStep {
  key: string
  label: string
  status: StepStatus
}

const LAST_TRIP_KEY = 'cybertravel_last_trip'
const DRAFT_KEY = 'cybertravel_plan_draft'
const STEP_ALIASES: Record<string, string> = {
  synthesizer_agent_done: 'synthesizer_agent',
  route_grounding: 'poi_agent',
  reflection_rerun: 'reviewer_agent'
}

const buildDateTime = (date?: string, time?: string) => (
  date && time ? `${date} ${time}` : undefined
)

const buildSteps = (): GenerationStep[] => [
  { key: 'planner_agent', label: '拆解旅行需求', status: 'pending' },
  { key: 'weather_tool', label: '获取天气', status: 'pending' },
  { key: 'attraction_agent', label: '搜索景点', status: 'pending' },
  { key: 'food_agent', label: '安排餐饮', status: 'pending' },
  { key: 'hotel_agent', label: '推荐住宿', status: 'pending' },
  { key: 'scoring', label: '评分排序', status: 'pending' },
  { key: 'transport_agent', label: '评估往返交通', status: 'pending' },
  { key: 'synthesizer_agent', label: '生成每日行程', status: 'pending' },
  { key: 'poi_agent', label: '补全地点信息', status: 'pending' },
  { key: 'reviewer_agent', label: '审查行程质量', status: 'pending' },
  { key: 'budget', label: '计算预算', status: 'pending' },
  { key: 'risk_notice', label: '生成提醒', status: 'pending' },
  { key: 'summary', label: '整理结果', status: 'pending' }
]

export const useTripStore = defineStore('trip', () => {
  const currentTrip = ref<Trip | null>(null)
  const tripHistory = ref<Trip[]>([])
  const draft = ref<TripRequest | null>(null)
  const isGenerating = ref(false)
  const isLoadingHistory = ref(false)
  const error = ref('')
  const steps = ref<GenerationStep[]>(buildSteps())
  const activeStepIndex = ref(0)
  let localTimer: ReturnType<typeof setInterval> | null = null

  const hasCurrentTrip = computed(() => Boolean(currentTrip.value))
  const activeStepLabel = computed(() => steps.value[activeStepIndex.value]?.label || '准备生成')

  const restoreLocal = () => {
    const savedTrip = uni.getStorageSync(LAST_TRIP_KEY) as Trip | ''
    const savedDraft = uni.getStorageSync(DRAFT_KEY) as TripRequest | ''
    if (savedTrip) currentTrip.value = savedTrip
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

  const applyRemoteProgress = (job: PlanJobResponse) => {
    const rawStep = String(job.step || '').trim()
    const normalizedStep = STEP_ALIASES[rawStep] || rawStep
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
    startLocalProgress()
    try {
      const departureCity = draft.value.departureCity || ''
      const outboundDepartureDatetime = buildDateTime(draft.value.startDate, draft.value.departureTime)
      const returnArrivalDatetime = buildDateTime(draft.value.endDate, draft.value.returnArrivalTime)
      const payload = {
        query: [
          `${draft.value.destination} ${draft.value.days}日游`,
          draft.value.additionalRequirements || ''
        ].filter(Boolean).join('，'),
        city: draft.value.destination,
        departure_city: departureCity,
        days: draft.value.days,
        preferences: draft.value.interests,
        budget: mapBudgetLevel(draft.value.budget, draft.value.days, draft.value.travelers),
        budget_amount: draft.value.budget,
        travelers: draft.value.travelers,
        start_date: draft.value.startDate,
        outbound_departure_datetime: outboundDepartureDatetime,
        return_arrival_datetime: returnArrivalDatetime
      }
      const response = await tripApi.planTripWithPolling(payload, applyRemoteProgress)
      const trip = convertTripResponse(response, draft.value)
      if (!trip.days.length) throw new Error(response.plan || 'AI 未生成可用行程，请稍后重试')

      const authStore = useAuthStore()
      const savedTrip = authStore.isAuthenticated
        ? await tripApi.createTripPlan(trip)
        : trip

      currentTrip.value = savedTrip as Trip
      uni.setStorageSync(LAST_TRIP_KEY, currentTrip.value)
      tripHistory.value = [
        currentTrip.value,
        ...tripHistory.value.filter((item) => item.id !== currentTrip.value?.id)
      ]
      markDone()
      return currentTrip.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成失败'
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
      return local
    }
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) return null
    const remote = await tripApi.getTripPlan(id)
    currentTrip.value = remote as Trip
    uni.setStorageSync(LAST_TRIP_KEY, currentTrip.value)
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
    steps,
    activeStepIndex,
    hasCurrentTrip,
    activeStepLabel,
    restoreLocal,
    setDraft,
    generateFromDraft,
    loadHistory,
    loadTrip,
    deleteTrip,
    clearLocal,
    stopLocalProgress
  }
})
