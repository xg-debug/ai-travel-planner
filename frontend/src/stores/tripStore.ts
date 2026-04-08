import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { tripApi } from '@/services/api'
import type { Trip, TripRequest, TripDay, Activity, WeatherForecast, POI, BudgetCategory, TripResponse } from '@/types/trip'

export const useTripStore = defineStore('trip', () => {
  // State
  const currentTrip = ref<Trip | null>(null)
  const tripHistory = ref<Trip[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
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

      const response: TripResponse = await tripApi.planTrip(apiRequest)
      
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
        days: convertItineraryToDays(response.itinerary || [], tripRequest),
        weather: convertWeatherToForecast(response.weather),
        recommendations: convertRecommendations(response.recommendations),
        plan: response.plan,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }

      currentTrip.value = trip
      tripHistory.value.unshift(trip)
      activeStep.value = 'review'
      
      // Save to localStorage
      saveToLocalStorage()
      
      return trip
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create trip'
      activeStep.value = 'input'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const updateTrip = async (updates: Partial<Trip>) => {
    if (!currentTrip.value) return

    try {
      currentTrip.value = {
        ...currentTrip.value,
        ...updates,
        updatedAt: new Date().toISOString()
      }
      
      saveToLocalStorage()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update trip'
      throw err
    }
  }

  const deleteTrip = async (tripId: string) => {
    try {
      tripHistory.value = tripHistory.value.filter(trip => trip.id !== tripId)
      if (currentTrip.value?.id === tripId) {
        currentTrip.value = null
      }
      
      saveToLocalStorage()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete trip'
      throw err
    }
  }

  const loadTrip = (tripId: string) => {
    const trip = tripHistory.value.find(t => t.id === tripId)
    if (trip) {
      currentTrip.value = trip
      activeStep.value = 'review'
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
    activeStep.value = 'input'
    localStorage.removeItem('cybertravel_trips')
  }

  // Local storage persistence
  const saveToLocalStorage = () => {
    try {
      localStorage.setItem('cybertravel_trips', JSON.stringify({
        currentTrip: currentTrip.value,
        tripHistory: tripHistory.value
      }))
    } catch (err) {
      console.error('Failed to save trips to localStorage:', err)
    }
  }

  const loadFromLocalStorage = () => {
    try {
      const saved = localStorage.getItem('cybertravel_trips')
      if (saved) {
        const data = JSON.parse(saved)
        currentTrip.value = data.currentTrip
        tripHistory.value = data.tripHistory || []
      }
    } catch (err) {
      console.error('Failed to load trips from localStorage:', err)
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

  const convertItineraryToDays = (itinerary: any[], request: TripRequest): TripDay[] => {
    const days: TripDay[] = []
    const startDate = new Date(request.startDate)
    
    // 如果API返回了有效的行程，使用API数据
    if (itinerary && itinerary.length > 0) {
      for (let i = 0; i < Math.min(itinerary.length, request.days); i++) {
        const dayData = itinerary[i]
        const date = new Date(startDate)
        date.setDate(startDate.getDate() + i)
        
        const activities = (dayData.activities || []).map((activity: any, activityIndex: number) =>
          normalizeActivity(activity, i, activityIndex, dayData.theme)
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
        description: rec.description || '',
        priceRange: mapPriceRange(rec.price_range),
        openingHours: rec.best_time || '09:00-17:00'
      }))
    })
  }

  const normalizeActivity = (activity: any, dayIndex: number, activityIndex: number, fallbackTheme?: string): Activity => {
    const cost = Number(activity.cost ?? activity.cost_estimate ?? 0) || 0
    const normalizedType = mapActivityType(activity.type || fallbackTheme)
    return {
      id: activity.id || `act_${dayIndex + 1}_${activityIndex + 1}`,
      time: normalizeTime(activity.time),
      title: activity.title || `行程活动 ${activityIndex + 1}`,
      description: activity.description || '',
      location: activity.location || '待定地点',
      type: normalizedType,
      duration: Number(activity.duration) || 90,
      cost,
      notes: activity.tips || activity.transportation
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

  // Initialize
  loadFromLocalStorage()

  return {
    // State
    currentTrip,
    tripHistory,
    isLoading,
    error,
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
    clearCurrentTrip,
    reset,
    saveToLocalStorage,
    loadFromLocalStorage
  }
})
