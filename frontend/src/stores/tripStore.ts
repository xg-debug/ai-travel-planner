import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { tripApi } from '@/services/api'
import type { Trip, TripRequest, TripDay, Activity, WeatherForecast, POI, BudgetCategory, TripResponse } from '@/types/trip'
import { useAuthStore } from '@/stores/authStore'

type StreamStepStatus = 'pending' | 'active' | 'done' | 'error'
type StreamStepKey = 'query_agent' | 'scenic_agent' | 'hotel_agent' | 'planning_agent' | 'poi_agent' | 'weather_tool' | 'budget' | 'summary'

interface StreamStep {
  key: StreamStepKey
  label: string
  status: StreamStepStatus
}

const STREAM_STEP_ORDER: StreamStepKey[] = ['query_agent', 'scenic_agent', 'hotel_agent', 'planning_agent', 'poi_agent', 'weather_tool', 'budget', 'summary']

const buildInitialStreamSteps = (): StreamStep[] => [
  { key: 'query_agent', label: '理解需求', status: 'pending' },
  { key: 'scenic_agent', label: '搜索景点', status: 'pending' },
  { key: 'hotel_agent', label: '推荐酒店', status: 'pending' },
  { key: 'planning_agent', label: '生成行程', status: 'pending' },
  { key: 'poi_agent', label: '补全景点', status: 'pending' },
  { key: 'weather_tool', label: '获取天气', status: 'pending' },
  { key: 'budget', label: '预算计算', status: 'pending' },
  { key: 'summary', label: '整理结果', status: 'pending' }
]

export const useTripStore = defineStore('trip', () => {
  const authStore = useAuthStore()
  // State
  const currentTrip = ref<Trip | null>(null)
  const tripHistory = ref<Trip[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const streamingStatus = ref<string>('')
  const streamSteps = ref<StreamStep[]>(buildInitialStreamSteps())
  const activeStep = ref<'input' | 'generating' | 'review' | 'complete'>('input')

  // Computed
  const hasCurrentTrip = computed(() => currentTrip.value !== null)
  const tripDays = computed(() => currentTrip.value?.days || [])
  const totalBudget = computed(() => currentTrip.value?.budget?.total || 0)
  const remainingBudget = computed(() => {
    if (!currentTrip.value?.budget) return 0
    const spent = currentTrip.value.budget.categories.reduce((sum: number, cat: BudgetCategory) => sum + cat.amount, 0)
    return currentTrip.value.budget.total - spent
  })

  // Actions
  const createTrip = async (tripRequest: TripRequest) => {
    isLoading.value = true
    error.value = null
    streamingStatus.value = '准备开始生成...'
    streamSteps.value = buildInitialStreamSteps()
    activeStep.value = 'generating'

    try {
      // 调用真实的后端API
      const apiRequest = {
        query: `${tripRequest.destination} ${tripRequest.days}日游`,
        city: tripRequest.destination,
        days: tripRequest.days,
        preferences: tripRequest.interests,
        budget: mapBudgetLevel(tripRequest.budget),
        travelers: tripRequest.travelers,
        start_date: tripRequest.startDate
      }

      const response: TripResponse = await tripApi.planTripStream(apiRequest, (evt) => {
        if (evt.event === 'status') {
          updateStreamStep(evt.data?.step, evt.data?.message)
          streamingStatus.value = evt.data?.message || '正在生成中...'
        }
      })
      const parsedDays = convertItineraryToDays(response.itinerary || [], tripRequest, response.pois || {})

      if (!parsedDays.length) {
        throw new Error(response.plan || 'AI 未生成可用行程，请稍后重试')
      }

      let weather = convertWeatherToForecast(response.weather)
      if (!weather.length) {
        try {
          const weatherData = await tripApi.getWeather(tripRequest.destination, tripRequest.days)
          weather = weatherData.map((item) => ({
            date: item.date,
            high: Number(item.temperature) + 3,
            low: Number(item.temperature) - 3,
            condition: item.condition || '晴朗',
            precipitation: 0,
            humidity: Number(item.humidity) || 60,
            windSpeed: Number(item.wind_speed) || 10,
            icon: item.icon
          }))
        } catch {
          // ignore weather fallback failure
        }
      }
      
      // 将API响应转换为前端Trip格式
      const trip: Trip = {
        id: `trip_${Date.now()}`,
        destination: tripRequest.destination,
        startDate: tripRequest.startDate,
        endDate: calculateEndDate(tripRequest.startDate, tripRequest.days),
        travelers: tripRequest.travelers,
        interests: tripRequest.interests,
        budget: {
          total: response.estimated_budget?.total || tripRequest.budget,
          currency: response.estimated_budget?.currency || 'CNY',
          categories: convertBudgetBreakdown(response.estimated_budget?.breakdown)
        },
        days: parsedDays,
        weather,
        hotels: convertHotels(response.hotels),
        recommendations: [
          ...convertRecommendations(response.recommendations),
          ...convertHotels(response.hotels)
        ],
        plan: response.plan,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }

      const savedTrip = await tripApi.createTripPlan(trip)
      currentTrip.value = savedTrip as Trip
      tripHistory.value = [savedTrip as Trip, ...tripHistory.value.filter((item) => item.id !== savedTrip.id)]
      streamingStatus.value = '生成完成'
      markAllStreamStepsDone()
      activeStep.value = 'review'

      return savedTrip as Trip
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create trip'
      markCurrentStepError()
      streamingStatus.value = ''
      activeStep.value = 'input'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const updateTrip = async (updates: Partial<Trip>) => {
    if (!currentTrip.value) return

    try {
      const nextTrip = {
        ...currentTrip.value,
        ...updates,
        updatedAt: new Date().toISOString()
      }
      if (authStore.isAuthenticated && nextTrip.id) {
        const saved = await tripApi.updateTripPlan(nextTrip.id, nextTrip)
        currentTrip.value = saved as Trip
        tripHistory.value = tripHistory.value.map((item) =>
          item.id === saved.id ? (saved as Trip) : item
        )
      } else {
        currentTrip.value = nextTrip
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update trip'
      throw err
    }
  }

  const deleteTrip = async (tripId: string) => {
    try {
      if (authStore.isAuthenticated) {
        await tripApi.deleteTripPlan(tripId)
      }
      tripHistory.value = tripHistory.value.filter(trip => trip.id !== tripId)
      if (currentTrip.value?.id === tripId) {
        currentTrip.value = null
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete trip'
      throw err
    }
  }

  const loadTrip = async (tripId: string) => {
    const trip = tripHistory.value.find(t => t.id === tripId)
    if (trip) {
      currentTrip.value = trip
      activeStep.value = 'review'
      return
    }

    if (!authStore.isAuthenticated) return
    try {
      const remote = await tripApi.getTripPlan(tripId)
      currentTrip.value = remote as Trip
      const exists = tripHistory.value.some((t) => t.id === remote.id)
      if (!exists) {
        tripHistory.value.unshift(remote as Trip)
      }
      activeStep.value = 'review'
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load trip'
    }
  }

  const clearCurrentTrip = () => {
    currentTrip.value = null
    activeStep.value = 'input'
  }

  const reset = () => {
    currentTrip.value = null
    tripHistory.value = []
    isLoading.value = false
    error.value = null
    streamSteps.value = buildInitialStreamSteps()
    activeStep.value = 'input'
  }

  const loadTripsFromServer = async () => {
    if (!authStore.isAuthenticated) {
      reset()
      return
    }
    try {
      const items = await tripApi.listTripPlans()
      tripHistory.value = (items || []) as Trip[]
      currentTrip.value = tripHistory.value[0] || null
      activeStep.value = currentTrip.value ? 'review' : 'input'
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载行程失败'
    }
  }

  // Helper functions for data conversion
  const mapBudgetLevel = (budget: number): string => {
    if (budget < 1000) return '经济'
    if (budget < 3000) return '中等'
    return '豪华'
  }

  const calculateEndDate = (startDate: string, days: number): string => {
    const date = new Date(startDate)
    date.setDate(date.getDate() + days - 1)
    return date.toISOString().split('T')[0]
  }

  const convertBudgetBreakdown = (breakdown: any): BudgetCategory[] => {
    if (!breakdown) return []
    
    return [
      { name: '住宿', amount: breakdown.accommodation || 0, planned: breakdown.accommodation || 0 },
      { name: '餐饮', amount: breakdown.food || 0, planned: breakdown.food || 0 },
      { name: '交通', amount: breakdown.transportation || 0, planned: breakdown.transportation || 0 },
      { name: '门票', amount: breakdown.tickets || 0, planned: breakdown.tickets || 0 },
      { name: '购物', amount: breakdown.shopping || 0, planned: breakdown.shopping || 0 }
    ]
  }

  const normalizeStepKey = (step?: string): StreamStepKey | null => {
    if (!step) return null
    if (step === 'planning_agent_done') return 'planning_agent'
    if (STREAM_STEP_ORDER.includes(step as StreamStepKey)) return step as StreamStepKey
    return null
  }

  const updateStreamStep = (rawStep?: string, message?: string) => {
    const stepKey = normalizeStepKey(rawStep)
    if (!stepKey) return
    const stepIndex = STREAM_STEP_ORDER.indexOf(stepKey)
    const isDoneSignal = rawStep === 'planning_agent_done'
    streamSteps.value = streamSteps.value.map((step, index) => {
      if (step.status === 'error') return step
      if (index < stepIndex) return { ...step, status: 'done' }
      if (index > stepIndex) return step
      return { ...step, status: isDoneSignal ? 'done' : 'active' }
    })
    if (message) streamingStatus.value = message
  }

  const markAllStreamStepsDone = () => {
    streamSteps.value = streamSteps.value.map((step) => ({ ...step, status: 'done' }))
  }

  const markCurrentStepError = () => {
    const active = streamSteps.value.find((step) => step.status === 'active')
    if (!active) return
    streamSteps.value = streamSteps.value.map((step) =>
      step.key === active.key ? { ...step, status: 'error' } : step
    )
  }

  const convertItineraryToDays = (itinerary: any[], request: TripRequest, poiMap: Record<string, any>): TripDay[] => {
    const days: TripDay[] = []
    const startDate = new Date(request.startDate)
    
    // 如果API返回了有效的行程，使用API数据
    if (itinerary && itinerary.length > 0) {
      for (let i = 0; i < Math.min(itinerary.length, request.days); i++) {
        const dayData = itinerary[i]
        const date = new Date(startDate)
        date.setDate(startDate.getDate() + i)
        
        const activities = (dayData.activities || []).map((activity: any, activityIndex: number) =>
          normalizeActivity(activity, i, activityIndex, dayData.theme, poiMap, request.destination)
        )
        days.push({
          date: dayData.date || date.toISOString().split('T')[0],
          activities
        })
      }
    } else {
      return []
    }
    
    return days
  }

  const convertWeatherToForecast = (weather: any): WeatherForecast[] => {
    if (!weather || !weather.forecast) return []
    
    return weather.forecast.map((forecast: any) => ({
      date: forecast.date,
      high: forecast.temperature?.max || 25,
      low: forecast.temperature?.min || 15,
      condition: forecast.condition || '晴朗',
      precipitation: 0, // API可能不提供降水概率
      humidity: forecast.humidity || 60,
      windSpeed: forecast.wind_speed || 10,
      icon: forecast.icon
    }))
  }

  const convertRecommendations = (recommendations: any[]): POI[] => {
    if (!recommendations || recommendations.length === 0) return []
    
    return recommendations.flatMap((rec: any, recIndex: number) => {
      const items: string[] = Array.isArray(rec.items) && rec.items.length > 0
        ? rec.items
        : [rec.title || `推荐 ${recIndex + 1}`]

      return items.map((name, itemIndex) => ({
        id: `poi_${recIndex + 1}_${itemIndex + 1}`,
        name,
        type: mapRecommendationTypeToPoiType(rec.type),
        category: rec.type || 'general',
        location: { lat: 0, lng: 0 }, // API可能不提供坐标
        rating: 4.5,
        description: buildRecommendationDescription(name, rec, itemIndex),
        priceRange: mapPriceRange(rec.price_range),
        openingHours: rec.best_time || '09:00-17:00'
      }))
    })
  }

  const convertHotels = (hotels: any[] | undefined): POI[] => {
    if (!Array.isArray(hotels) || hotels.length === 0) return []
    return hotels.map((hotel: any, index: number) => ({
      id: hotel.id || `hotel_${index + 1}`,
      name: hotel.name || `酒店 ${index + 1}`,
      type: 'hotel',
      category: 'hotel',
      location: {
        lat: Number(hotel.lat) || 0,
        lng: Number(hotel.lng) || 0
      },
      rating: Number(hotel.rating) || 4.5,
      description: hotel.description || `${hotel.name || '该酒店'}适合作为本次路线的住宿落点。`,
      priceRange: mapPriceRange(hotel.price),
      openingHours: hotel.opening_hours || '全天'
    }))
  }

  const findPoiByLocation = (location: string, poiMap: Record<string, any>) => {
    if (!location) return null
    if (poiMap[location]) return poiMap[location]
    const normalized = location.trim().toLowerCase()
    const fuzzyKey = Object.keys(poiMap).find((key) => {
      const left = key.trim().toLowerCase()
      return left.includes(normalized) || normalized.includes(left)
    })
    return fuzzyKey ? poiMap[fuzzyKey] : null
  }

  const isGenericActivityDescription = (description: string | undefined) => {
    const text = String(description || '').trim()
    if (!text) return true
    return ['围绕', '核心体验安排', '简要描述', '推荐描述'].some((keyword) => text.includes(keyword))
  }

  const buildScenicImageUrl = (city: string, location: string, seed: string) => {
    const safeSeed = encodeURIComponent(seed || `${city}-${location}`)
    return `https://picsum.photos/seed/${safeSeed}/1200/800`
  }

  const buildRecommendationDescription = (name: string, rec: any, itemIndex: number) => {
    const base = String(rec?.description || '').trim()
    if (base && (!Array.isArray(rec?.items) || rec.items.length <= 1)) return base

    const type = String(rec?.type || '')
    if (type.includes('美食')) return `${name}适合安排成一顿有记忆点的本地餐食，能更直接感受目的地的风味。`
    if (type.includes('博物') || type.includes('文化')) return `${name}更适合慢慢逛，能补充这座城市的人文背景，而不只是到此一游。`
    if (type.includes('公园') || type.includes('自然')) return `${name}节奏相对轻松，适合作为一天行程里的放松段落。`
    if (type.includes('购物')) return `${name}适合边逛边吃边买伴手礼，安排上也比较灵活。`
    return `${name}是这次路线里值得补充的一站，第 ${itemIndex + 1} 个推荐更适合搭配周边活动顺路安排。`
  }

  const normalizeActivity = (
    activity: any,
    dayIndex: number,
    activityIndex: number,
    fallbackTheme?: string,
    poiMap: Record<string, any> = {},
    city: string = ''
  ): Activity => {
    const cost = Number(activity.cost ?? activity.cost_estimate ?? 0) || 0
    const normalizedType = mapActivityType(activity.type || fallbackTheme)
    const poi = findPoiByLocation(activity.location || '', poiMap)
    const lat = Number(poi?.lat)
    const lng = Number(poi?.lng)
    const description = !isGenericActivityDescription(activity.description)
      ? activity.description
      : (poi?.description || activity.description || '')
    const image = activity.image || activity.image_url || poi?.image_url
    return {
      id: activity.id || `act_${dayIndex + 1}_${activityIndex + 1}`,
      time: normalizeTime(activity.time),
      title: activity.title || `行程活动 ${activityIndex + 1}`,
      description,
      location: activity.location || '待定地点',
      type: normalizedType,
      duration: Number(activity.duration) || 90,
      cost,
      notes: activity.tips || poi?.tips || activity.transportation,
      image: image || buildScenicImageUrl(city, activity.location || `day-${dayIndex + 1}`, `${dayIndex + 1}-${activityIndex + 1}`),
      coordinates: Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : undefined
    }
  }

  const normalizeTime = (time: string | undefined): string => {
    if (!time) return '09:00'
    return String(time).split('-')[0]
  }

  const mapActivityType = (rawType: string | undefined): Activity['type'] => {
    const value = (rawType || '').toLowerCase()
    if (value.includes('美食') || value.includes('餐')) return 'food'
    if (value.includes('文化') || value.includes('博物') || value.includes('历史')) return 'culture'
    if (value.includes('户外') || value.includes('自然')) return 'outdoor'
    if (value.includes('购物')) return 'shopping'
    if (value.includes('娱乐')) return 'entertainment'
    if (value.includes('交通')) return 'transport'
    return 'other'
  }

  const mapRecommendationTypeToPoiType = (rawType: string | undefined): POI['type'] => {
    const value = (rawType || '').toLowerCase()
    if (value.includes('美食')) return 'restaurant'
    if (value.includes('酒店') || value.includes('住宿')) return 'hotel'
    if (value.includes('博物')) return 'museum'
    if (value.includes('公园') || value.includes('自然')) return 'park'
    if (value.includes('购物')) return 'shop'
    return 'attraction'
  }

  const mapPriceRange = (priceRange: string | undefined): POI['priceRange'] => {
    if (!priceRange) return '$$'
    if (priceRange.includes('免费')) return 'free'
    if (priceRange.includes('豪华')) return '$$$$'
    if (priceRange.includes('经济')) return '$'
    return '$$'
  }

  watch(
    () => authStore.isAuthenticated,
    (authed) => {
      if (authed) {
        loadTripsFromServer()
      } else {
        reset()
      }
    },
    { immediate: true }
  )

  return {
    // State
    currentTrip,
    tripHistory,
    isLoading,
    error,
    streamingStatus,
    streamSteps,
    activeStep,

    // Computed
    hasCurrentTrip,
    tripDays,
    totalBudget,
    remainingBudget,

    // Actions
    createTrip,
    updateTrip,
    deleteTrip,
    loadTrip,
    loadTripsFromServer,
    clearCurrentTrip,
    reset,
  }
})
