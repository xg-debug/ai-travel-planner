import type {
  Activity,
  BudgetCategory,
  HotelRecommendation,
  POI,
  Trip,
  TripDay,
  TripRequest,
  TripResponse,
  WeatherForecast
} from '@/types/trip'
import { addDays } from '@/utils/format'

export const mapBudgetLevel = (budget: number, days: number, travelers: number): string => {
  const perPersonPerDay = budget / Math.max(days, 1) / Math.max(travelers, 1)
  if (perPersonPerDay < 400) return '经济'
  if (perPersonPerDay < 1000) return '中等'
  return '豪华'
}

export const convertTripResponse = (response: TripResponse, request: TripRequest): Trip => {
  const days = convertItineraryToDays(response.itinerary || [], request, response.pois || {}, response.hotels || [])
  const weather = convertWeatherToForecast(response.weather)
  const hotels = convertHotels(response.hotels)
  return {
    id: `trip_${Date.now()}`,
    destination: request.destination,
    startDate: request.startDate,
    endDate: request.endDate || addDays(request.startDate, request.days - 1),
    travelers: request.travelers,
    interests: request.interests,
    budget: {
      total: response.estimated_budget?.total || request.budget,
      currency: response.estimated_budget?.currency || 'CNY',
      categories: convertBudgetBreakdown(response.estimated_budget?.breakdown)
    },
    days,
    weather,
    hotels,
    recommendations: [
      ...convertRecommendations(response.recommendations || []),
      ...hotels
    ],
    plan: response.plan,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    status: 'planned'
  }
}

const convertItineraryToDays = (
  itinerary: any[],
  request: TripRequest,
  poiMap: Record<string, any>,
  hotels: any[] = []
): TripDay[] => {
  const startDate = new Date(request.startDate)
  return itinerary.slice(0, request.days).map((dayData, dayIndex) => {
    const date = new Date(startDate)
    date.setDate(startDate.getDate() + dayIndex)
    const activities = (dayData.activities || []).map((activity: any, activityIndex: number) =>
      normalizeActivity(activity, dayIndex, activityIndex, dayData.theme, poiMap)
    )
    return {
      date: dayData.date || date.toISOString().split('T')[0],
      activities,
      hotel: normalizeDayHotel(dayData.hotel_recommendation || dayData.hotel, hotels),
      totalCost: activities.reduce((sum: number, item: Activity) => sum + Number(item.cost || 0), 0)
    }
  }).filter((day) => day.activities.length || day.hotel)
}

const convertWeatherToForecast = (weather: any): WeatherForecast[] => {
  if (!weather?.forecast) return []
  return weather.forecast.map((forecast: any) => ({
    city: weather.city,
    date: forecast.date,
    high: forecast.temperature?.max || 25,
    low: forecast.temperature?.min || 15,
    condition: forecast.condition || '晴朗',
    dayCondition: forecast.day_condition || forecast.condition || '晴朗',
    nightCondition: forecast.night_condition || forecast.condition || '晴朗',
    precipitation: 0,
    humidity: forecast.humidity || 60,
    windSpeed: forecast.wind_speed || 10,
    dayWindDirection: forecast.day_wind_direction || '',
    nightWindDirection: forecast.night_wind_direction || '',
    dayWindPower: forecast.day_wind_power || '',
    nightWindPower: forecast.night_wind_power || '',
    icon: forecast.icon
  }))
}

const convertBudgetBreakdown = (breakdown: any): BudgetCategory[] => {
  if (!breakdown) return []
  const items = [
    ['住宿', breakdown.accommodation ?? breakdown['住宿'] ?? 0],
    ['餐饮', breakdown.food ?? breakdown['餐饮'] ?? 0],
    ['交通', breakdown.transportation ?? breakdown['交通'] ?? 0],
    ['门票', breakdown.tickets ?? breakdown['门票'] ?? 0],
    ['购物', breakdown.shopping ?? breakdown['购物'] ?? 0]
  ] as const
  return items.map(([name, amount]) => ({
    name,
    amount: Number(amount) || 0,
    planned: Number(amount) || 0
  }))
}

const convertRecommendations = (recommendations: any[]): POI[] => {
  return recommendations.flatMap((rec, recIndex) => {
    const items = Array.isArray(rec.items) && rec.items.length ? rec.items : [rec.title || `推荐 ${recIndex + 1}`]
    return items.map((name: string, itemIndex: number) => ({
      id: `poi_${recIndex + 1}_${itemIndex + 1}`,
      name,
      type: mapRecommendationTypeToPoiType(rec.type),
      category: rec.type || 'general',
      location: { lat: 0, lng: 0 },
      rating: 4.5,
      description: buildRecommendationDescription(name, rec, itemIndex),
      priceRange: mapPriceRange(rec.price_range),
      openingHours: rec.best_time || '09:00-17:00'
    }))
  })
}

const convertHotels = (hotels: any[] | undefined): POI[] => {
  if (!Array.isArray(hotels)) return []
  return hotels.map((hotel, index) => ({
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
    openingHours: hotel.opening_hours || '全天'
  }))
}

const normalizeDayHotel = (hotel: any, hotelOptions: any[] = []): HotelRecommendation | undefined => {
  const source = hotel || hotelOptions[0]
  const name = String(source?.name || '').trim()
  if (!name) return undefined
  const priceEstimate = source.price_estimate ?? source.price ?? source.cost ?? source.estimated_cost
  return {
    name,
    address: source.address || '',
    priceEstimate: typeof priceEstimate === 'number' ? priceEstimate : normalizePriceText(priceEstimate),
    reason: source.reason || source.description || `${name}适合作为这次行程的住宿落点。`,
    rating: Number(source.rating) || undefined
  }
}

const normalizeActivity = (
  activity: any,
  dayIndex: number,
  activityIndex: number,
  fallbackTheme?: string,
  poiMap: Record<string, any> = {}
): Activity => {
  const poi = findPoiByLocation(activity.location || '', poiMap)
  const normalizedType = mapActivityType(activity.type || fallbackTheme)
  const ticketPrice = normalizeTicketPrice(activity, poi, normalizedType)
  const lat = Number(poi?.lat ?? activity.coordinates?.lat)
  const lng = Number(poi?.lng ?? activity.coordinates?.lng)
  return {
    id: activity.id || `act_${dayIndex + 1}_${activityIndex + 1}`,
    time: normalizeTime(activity.time),
    title: activity.title || `行程活动 ${activityIndex + 1}`,
    description: activity.description || poi?.description || '这是一段适合顺路安排的旅行体验。',
    location: activity.location || activity.title || '待定地点',
    type: normalizedType,
    duration: Number(activity.duration) || 90,
    cost: Number(activity.cost ?? activity.cost_estimate ?? 0) || 0,
    ticketPrice,
    ticketLabel: buildTicketLabel(activity, poi, ticketPrice),
    notes: activity.tips || poi?.tips || activity.transportation,
    image: activity.image || activity.image_url || poi?.image_url,
    coordinates: Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : undefined
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

const normalizeTime = (time: string | undefined): string => {
  if (!time) return '09:00'
  return String(time).split('-')[0]
}

const mapActivityType = (rawType: string | undefined): Activity['type'] => {
  const value = (rawType || '').toLowerCase()
  if (value.includes('美食') || value.includes('餐')) return 'food'
  if (value.includes('文化') || value.includes('博物') || value.includes('历史') || value.includes('景点')) return 'culture'
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

const normalizeTicketPrice = (activity: any, poi: any, type: Activity['type']): number | undefined => {
  const explicit = parseNumericPrice(activity.ticket_price ?? activity.ticketPrice)
  if (explicit !== undefined) return ['food', 'transport'].includes(type) ? undefined : explicit
  const poiPrice = parseNumericPrice(poi?.price)
  if (poiPrice !== undefined && ['culture', 'outdoor', 'entertainment', 'other'].includes(type)) return poiPrice
  if (Number(activity.cost_estimate ?? activity.cost) === 0) return 0
  return ['culture', 'outdoor', 'entertainment', 'other'].includes(type)
    ? parseNumericPrice(activity.cost_estimate ?? activity.cost)
    : undefined
}

const parseNumericPrice = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const match = String(value ?? '').match(/\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : undefined
}

const buildTicketLabel = (activity: any, poi: any, ticketPrice?: number): string | undefined => {
  if (ticketPrice === undefined) return undefined
  if (ticketPrice <= 0) return '门票免费'
  const raw = String(activity.ticket_note || poi?.price || '').trim()
  return raw && raw !== '0' ? `门票 ${raw}` : `门票 ¥${ticketPrice}`
}

const buildRecommendationDescription = (name: string, rec: any, itemIndex: number) => {
  const base = String(rec?.description || '').trim()
  if (base && (!Array.isArray(rec?.items) || rec.items.length <= 1)) return base
  const type = String(rec?.type || '')
  if (type.includes('美食')) return `${name}适合安排成一顿有记忆点的本地餐食。`
  if (type.includes('文化') || type.includes('博物')) return `${name}适合补充目的地的人文背景。`
  if (type.includes('自然') || type.includes('公园')) return `${name}适合作为一天行程里的放松段落。`
  return `${name}是这次路线里值得补充的一站，第 ${itemIndex + 1} 个推荐更适合顺路安排。`
}
