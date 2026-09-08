import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { tripApi } from '@/services/api'
import type { Trip, TripRequest, TripDay, Activity, WeatherForecast, POI, BudgetCategory, TripResponse, HotelRecommendation } from '@/types/trip'
import { useAuthStore } from '@/stores/authStore'

type StreamStepStatus = 'pending' | 'active' | 'done' | 'error'
type StreamStepKey = 'request_analysis' | 'weather_lookup' | 'attraction_search' | 'food_search' | 'hotel_search' | 'transport_planning' | 'itinerary_review' | 'itinerary_synthesis' | 'budget_estimation' | 'risk_notices' | 'summary'

interface StreamStep {
  key: StreamStepKey
  label: string
  status: StreamStepStatus
}

const STREAM_STEP_ORDER: StreamStepKey[] = ['request_analysis', 'weather_lookup', 'attraction_search', 'food_search', 'hotel_search', 'transport_planning', 'itinerary_review', 'itinerary_synthesis', 'budget_estimation', 'risk_notices', 'summary']

const buildInitialStreamSteps = (): StreamStep[] => [
  { key: 'request_analysis', label: '理解需求', status: 'pending' },
  { key: 'weather_lookup', label: '查询天气', status: 'pending' },
  { key: 'attraction_search', label: '搜索景点', status: 'pending' },
  { key: 'food_search', label: '搜索美食', status: 'pending' },
  { key: 'hotel_search', label: '匹配住宿', status: 'pending' },
  { key: 'transport_planning', label: '规划交通', status: 'pending' },
  { key: 'itinerary_review', label: '检查路线', status: 'pending' },
  { key: 'itinerary_synthesis', label: '编排行程', status: 'pending' },
  { key: 'budget_estimation', label: '估算预算', status: 'pending' },
  { key: 'risk_notices', label: '整理提醒', status: 'pending' },
  { key: 'summary', label: '完成方案', status: 'pending' }
]

const LOCAL_TRIP_KEY = 'suixinyou_local_trip'

const readLocalTrip = (): Trip | null => {
  try {
    const raw = localStorage.getItem(LOCAL_TRIP_KEY)
    return raw ? JSON.parse(raw) as Trip : null
  } catch {
    return null
  }
}

export const useTripStore = defineStore('trip', () => {
  const authStore = useAuthStore()
  // State
  const localTrip = readLocalTrip()
  const currentTrip = ref<Trip | null>(localTrip)
  const tripHistory = ref<Trip[]>(localTrip ? [localTrip] : [])
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
        departureCity: tripRequest.departureCity,
        destination: tripRequest.destination,
        startDate: tripRequest.startDate,
        endDate: tripRequest.endDate,
        departureTime: tripRequest.departureTime,
        returnArrivalTime: tripRequest.returnArrivalTime,
        days: tripRequest.days,
        travelers: tripRequest.travelers,
        interests: tripRequest.interests,
        budgetAmount: tripRequest.budget,
        accommodationPreference: tripRequest.accommodationPreference,
        additionalRequirements: tripRequest.additionalRequirements
      }

      const response: TripResponse = await tripApi.planTripRealtime(apiRequest, (evt) => {
        updateStreamStep(evt.step, evt.message)
        if (evt.message) streamingStatus.value = evt.message
      })
      const parsedDays = convertItineraryToDays(response.itinerary || [], tripRequest, response.pois || {}, response.hotels || [])

      if (!parsedDays.length) {
        throw new Error(response.plan || 'AI 未生成可用行程，请稍后重试')
      }

      let weather = convertWeatherToForecast(response.weather)
      if (!weather.length) {
        try {
          const weatherData = await tripApi.getWeather(tripRequest.destination, tripRequest.days)
          weather = weatherData.map((item) => ({
            city: tripRequest.destination,
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
        planningWarnings: response.planning_warnings || [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }

      const savedTrip = authStore.isAuthenticated
        ? await tripApi.createTripPlan(trip)
        : trip
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
  const calculateEndDate = (startDate: string, days: number): string => {
    const date = new Date(startDate)
    date.setDate(date.getDate() + days - 1)
    return date.toISOString().split('T')[0]
  }

  const convertBudgetBreakdown = (breakdown: any): BudgetCategory[] => {
    if (!breakdown) return []
    const accommodation = breakdown.accommodation ?? breakdown['住宿'] ?? 0
    const food = breakdown.food ?? breakdown['餐饮'] ?? 0
    const transportation = breakdown.transportation ?? breakdown['交通'] ?? 0
    const tickets = breakdown.tickets ?? breakdown['门票'] ?? 0
    const shopping = breakdown.shopping ?? breakdown['购物'] ?? 0
    
    return [
      { name: '住宿', amount: accommodation, planned: accommodation },
      { name: '餐饮', amount: food, planned: food },
      { name: '交通', amount: transportation, planned: transportation },
      { name: '门票', amount: tickets, planned: tickets },
      { name: '购物', amount: shopping, planned: shopping }
    ]
  }

  const normalizeStepKey = (step?: string): StreamStepKey | null => {
    if (!step) return null
    if (step === 'workflow_error') return 'summary'
    if (STREAM_STEP_ORDER.includes(step as StreamStepKey)) return step as StreamStepKey
    return null
  }

  const updateStreamStep = (rawStep?: string, message?: string) => {
    const stepKey = normalizeStepKey(rawStep)
    if (!stepKey) {
      if (message) streamingStatus.value = message
      return
    }
    const stepIndex = STREAM_STEP_ORDER.indexOf(stepKey)
    const activeIndex = streamSteps.value.findIndex((step) => step.status === 'active')
    const targetIndex = Math.max(stepIndex, activeIndex)
    streamSteps.value = streamSteps.value.map((step, index) => {
      if (step.status === 'error') return step
      if (index < targetIndex) return { ...step, status: 'done' }
      if (index > targetIndex) return step.status === 'active' ? { ...step, status: 'pending' } : step
      return { ...step, status: 'active' }
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

  const convertItineraryToDays = (itinerary: any[], request: TripRequest, poiMap: Record<string, any>, hotels: any[] = []): TripDay[] => {
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
          activities,
          hotel: normalizeDayHotel(dayData.hotel_recommendation || dayData.hotel, hotels)
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
      city: weather.city,
      date: forecast.date,
      high: forecast.temperature?.max || 25,
      low: forecast.temperature?.min || 15,
      condition: forecast.condition || '晴朗',
      dayCondition: forecast.day_condition || forecast.condition || '晴朗',
      nightCondition: forecast.night_condition || forecast.condition || '晴朗',
      precipitation: 0, // API可能不提供降水概率
      humidity: forecast.humidity || 60,
      windSpeed: forecast.wind_speed || 10,
      dayWindDirection: forecast.day_wind_direction || '',
      nightWindDirection: forecast.night_wind_direction || '',
      dayWindPower: forecast.day_wind_power || '',
      nightWindPower: forecast.night_wind_power || '',
      icon: forecast.icon
    }))
  }

  const convertRecommendations = (recommendations: any[] | undefined): POI[] => {
    if (!recommendations || recommendations.length === 0) return []
    
    return recommendations.flatMap((rec: any, recIndex: number) => {
      const items: any[] = Array.isArray(rec.items) && rec.items.length > 0
        ? rec.items
        : [rec.title || `推荐 ${recIndex + 1}`]

      return items.map((rawItem, itemIndex) => {
        const name = typeof rawItem === 'string'
          ? rawItem
          : String(rawItem?.name || rawItem?.title || rec.title || `推荐 ${recIndex + 1}`).trim()
        const details = [
          ...(Array.isArray(rec.item_details) ? rec.item_details : []),
          ...(Array.isArray(rec.itemDetails) ? rec.itemDetails : [])
        ]
        const normalizedName = name.toLowerCase()
        const detail = (rawItem && typeof rawItem === 'object')
          ? rawItem
          : details.find((item: any) => {
              const detailName = String(item?.name || item?.title || '').trim().toLowerCase()
              return detailName && (detailName === normalizedName || detailName.includes(normalizedName) || normalizedName.includes(detailName))
            }) || {}
        const lat = Number(detail.lat ?? detail.latitude ?? detail.coordinates?.lat)
        const lng = Number(detail.lng ?? detail.lon ?? detail.longitude ?? detail.coordinates?.lng)
        return {
          id: String(detail.id || `poi_${recIndex + 1}_${itemIndex + 1}`),
          name,
          type: mapRecommendationTypeToPoiType(detail.type || rec.type),
          category: rec.type || detail.category || 'general',
          location: {
            lat: Number.isFinite(lat) ? lat : 0,
            lng: Number.isFinite(lng) ? lng : 0
          },
          rating: Number(detail.rating) || 4.5,
          description: detail.description || buildRecommendationDescription(name, rec, itemIndex),
          priceRange: mapPriceRange(detail.price || detail.price_range || rec.price_range),
          address: detail.address || '',
          openingHours: detail.opening_hours || detail.openingHours || rec.best_time || '09:00-17:00',
          images: normalizeImageList(detail)
        }
      })
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
      priceText: normalizePriceText(hotel.price),
      address: hotel.address || '',
      openingHours: hotel.opening_hours || '全天',
      images: normalizeImageList(hotel)
    }))
  }

  const normalizeDayHotel = (hotel: any, hotelOptions: any[] = []): HotelRecommendation | undefined => {
    const matched = hotel?.name
      ? hotelOptions.find((item) => String(item?.name || '').trim() === String(hotel.name).trim())
      : undefined
    const source = hotel ? { ...(matched || {}), ...hotel } : hotelOptions[0]
    if (!source) return undefined
    const name = String(source.name || '').trim()
    if (!name) return undefined
    const priceEstimate = source.price_estimate ?? source.price ?? source.cost ?? source.estimated_cost
    return {
      name,
      address: source.address || '',
      priceEstimate: typeof priceEstimate === 'number' ? priceEstimate : normalizePriceText(priceEstimate),
      reason: source.reason || source.description || `${name}适合作为这次行程的住宿落点。`,
      rating: Number(source.rating) || undefined,
      image: normalizeImageList(source)[0]
    }
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

  const buildScenicImageUrl = (city: string, location: string, _seed: string) => {
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#dbeafe"/>
            <stop offset="50%" stop-color="#f0fdf4"/>
            <stop offset="100%" stop-color="#fef3c7"/>
          </linearGradient>
        </defs>
        <rect width="1200" height="800" fill="url(#g)"/>
        <circle cx="940" cy="180" r="120" fill="rgba(59,130,246,0.12)"/>
        <circle cx="240" cy="620" r="160" fill="rgba(16,185,129,0.12)"/>
        <text x="80" y="380" font-size="52" font-family="Arial, sans-serif" fill="#0f172a" font-weight="700">${city || 'Travel'}</text>
        <text x="80" y="450" font-size="30" font-family="Arial, sans-serif" fill="#334155">${location || 'Scenic View'}</text>
        <text x="80" y="520" font-size="22" font-family="Arial, sans-serif" fill="#64748b">AI Travel Planner</text>
      </svg>`
    )}`
  }

  const isValidImageUrl = (value: unknown) => {
    const text = String(value || '').trim()
    return /^https?:\/\//.test(text) || text.startsWith('data:image/')
  }

  const normalizeImageList = (source: any): string[] => {
    const candidates = [
      source?.image,
      source?.image_url,
      source?.imageUrl,
      source?.cover,
      source?.thumbnail,
      ...(Array.isArray(source?.images) ? source.images : []),
      ...(Array.isArray(source?.image_urls) ? source.image_urls : []),
      ...(Array.isArray(source?.photos) ? source.photos.map((photo: any) => photo?.url || photo?.image_url || photo) : [])
    ]
    return [...new Set(candidates.map(normalizeImageUrl).filter(Boolean))]
  }

  const normalizeImageUrl = (value: unknown): string => {
    const url = String(value || '').trim()
    if (url.startsWith('//')) return `https:${url}`
    if (url.startsWith('http://')) return `https://${url.slice(7)}`
    return /^https:\/\//.test(url) || url.startsWith('data:image/') ? url : ''
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
    const ticketPrice = normalizeTicketPrice(activity, poi, normalizedType)
    const ticketLabel = buildTicketLabel(activity, poi, ticketPrice)
    const activityCoordinates = activity.coordinates || {}
    const lat = Number(poi?.lat ?? activityCoordinates.lat)
    const lng = Number(poi?.lng ?? activityCoordinates.lng)
    const description = !isGenericActivityDescription(activity.description)
      ? activity.description
      : (poi?.description || activity.description || '')
    const image = [activity.image, activity.image_url, poi?.image_url].find(isValidImageUrl)
    return {
      id: activity.id || `act_${dayIndex + 1}_${activityIndex + 1}`,
      time: normalizeTime(activity.time),
      title: activity.title || `行程活动 ${activityIndex + 1}`,
      description,
      location: activity.location || '待定地点',
      type: normalizedType,
      duration: Number(activity.duration) || 90,
      cost,
      ticketPrice,
      ticketLabel,
      notes: activity.tips || poi?.tips || activity.transportation,
      image: image || buildScenicImageUrl(city, activity.location || `day-${dayIndex + 1}`, `${dayIndex + 1}-${activityIndex + 1}`),
      source_id: String(activity.source_id || activity.poi_id || poi?.id || ""),
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
    if (
      value.includes('文化')
      || value.includes('博物')
      || value.includes('历史')
      || value.includes('景点')
      || value.includes('游览')
      || value.includes('地标')
      || value.includes('古镇')
      || value.includes('街区')
      || value.includes('寺')
      || value.includes('院')
      || value.includes('展馆')
      || value.includes('美术馆')
      || value.includes('遗址')
      || value.includes('记忆')
    ) return 'culture'
    if (value.includes('户外') || value.includes('自然') || value.includes('公园') || value.includes('风景')) return 'outdoor'
    if (value.includes('购物')) return 'shopping'
    if (value.includes('娱乐') || value.includes('休闲')) return 'entertainment'
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
    if (/\d{3,}/.test(priceRange)) return '$$$'
    return '$$'
  }

  const normalizePriceText = (value: unknown): string => {
    const text = String(value ?? '').trim()
    if (!text) return '待查询'
    if (text.includes('免费')) return '免费'
    if (text.startsWith('¥') || text.startsWith('￥')) return text
    if (/^\d+(\.\d+)?$/.test(text)) return `¥${text}/晚`
    return text
  }

  const parseNumericPrice = (value: unknown): number | undefined => {
    if (typeof value === 'number' && Number.isFinite(value)) return value
    const match = String(value ?? '').match(/\d+(?:\.\d+)?/)
    if (!match) return undefined
    return Number(match[0])
  }

  const normalizeTicketPrice = (activity: any, poi: any, type: Activity['type']): number | undefined => {
    const explicit = parseNumericPrice(activity.ticket_price ?? activity.ticketPrice)
    if (explicit !== undefined) return ['food', 'transport'].includes(type) ? undefined : explicit
    const poiPrice = parseNumericPrice(poi?.price)
    if (poiPrice !== undefined && ['culture', 'outdoor', 'entertainment', 'other'].includes(type)) return poiPrice
    if (type === 'food' || type === 'transport') return undefined
    if (Number(activity.cost_estimate ?? activity.cost) === 0) return 0
    return ['culture', 'outdoor', 'entertainment', 'other'].includes(type) ? (parseNumericPrice(activity.cost_estimate ?? activity.cost) ?? undefined) : undefined
  }

  const buildTicketLabel = (activity: any, poi: any, ticketPrice?: number): string | undefined => {
    if (ticketPrice === undefined) return undefined
    if (ticketPrice <= 0) return '门票免费'
    const raw = String(activity.ticket_note || poi?.price || '').trim()
    return raw && raw !== '0' ? `门票 ${raw}` : `门票 ¥${ticketPrice}`
  }

  watch(
    () => authStore.isAuthenticated,
    (authed) => {
      if (authed) {
        loadTripsFromServer()
      }
    },
    { immediate: true }
  )

  watch(
    currentTrip,
    (trip) => {
      if (authStore.isAuthenticated) return
      if (trip) localStorage.setItem(LOCAL_TRIP_KEY, JSON.stringify(trip))
      else localStorage.removeItem(LOCAL_TRIP_KEY)
    },
    { deep: true }
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
