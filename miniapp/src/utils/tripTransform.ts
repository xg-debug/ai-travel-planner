import type {
  Activity,
  BudgetCategory,
  HotelRecommendation,
  IntercityTransportLeg,
  IntercityTransportPlan,
  POI,
  Trip,
  TripDay,
  TripRequest,
  TripResponse,
  TransportOption,
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
  const dailyBudgets = response.daily_budgets || response.estimated_budget?.daily_budgets || []
  const days = convertItineraryToDays(response.itinerary || [], request, response.pois || {}, response.hotels || [], dailyBudgets)
  const weather = convertWeatherToForecast(response.weather)
  const hotels = convertHotels(response.hotels)
  return {
    id: `trip_${Date.now()}`,
    departureCity: request.departureCity,
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
    dailyBudgets,
    intercityTransport: convertIntercityTransport(response.intercity_transport),
    riskNotices: response.risk_notices || [],
    qualityScore: response.quality_score,
    hotels,
    recommendations: [
      ...convertRecommendations(response.recommendations || [], response.pois || {}),
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
  hotels: any[] = [],
  dailyBudgets: any[] = []
): TripDay[] => {
  const startDate = new Date(request.startDate)
  return itinerary.slice(0, request.days).map((dayData, dayIndex) => {
    const date = new Date(startDate)
    date.setDate(startDate.getDate() + dayIndex)
    const activities = (dayData.activities || [])
      .filter((activity: any) => !isHotelLikeActivity(activity))
      .map((activity: any, activityIndex: number) =>
        normalizeActivity(activity, dayIndex, activityIndex, dayData.theme, poiMap)
      )
      .sort((left: Activity, right: Activity) => timeSortValue(left.time) - timeSortValue(right.time))
    return {
      date: dayData.date || date.toISOString().split('T')[0],
      theme: dayData.theme || '',
      summary: dayData.summary || '',
      weatherAdvice: dayData.weather_advice || dayData.weatherAdvice || '',
      activities,
      hotel: normalizeDayHotel(dayData.hotel_recommendation || dayData.hotel, hotels, activities),
      budget: dayData.budget || dailyBudgets.find((item) => Number(item?.day) === dayIndex + 1),
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

const convertRecommendations = (recommendations: any[], poiMap: Record<string, any> = {}): POI[] => {
  return recommendations.flatMap((rec, recIndex) => {
    const items = Array.isArray(rec.items) && rec.items.length ? rec.items : [rec.title || `推荐 ${recIndex + 1}`]
    return items.map((rawItem: any, itemIndex: number) => {
      const name = recommendationItemName(rawItem, rec, recIndex)
      const detail = recommendationDetail(rec, rawItem, name) || findPoiByLocation(name, poiMap) || {}
      const poiType = mapRecommendationTypeToPoiType(detail.type || rec.type)
      const lat = Number(detail.lat ?? detail.latitude ?? detail.coordinates?.lat)
      const lng = Number(detail.lng ?? detail.lon ?? detail.longitude ?? detail.coordinates?.lng)
      const priceText = normalizeOptionalPriceText(detail.price_text ?? detail.priceText ?? detail.price, poiType)
      return {
        id: String(detail.id || `poi_${recIndex + 1}_${itemIndex + 1}`),
        name,
        type: poiType,
        category: rec.type || detail.category || 'general',
        location: {
          lat: Number.isFinite(lat) ? lat : 0,
          lng: Number.isFinite(lng) ? lng : 0
        },
        rating: normalizePoiRating(detail, itemIndex, poiType),
        description: detail.description || buildRecommendationDescription(name, rec, itemIndex),
        priceRange: mapPriceRange(detail.price || detail.price_range || rec.price_range),
        ...(priceText ? { priceText } : {}),
        address: detail.address || '',
        openingHours: detail.opening_hours || detail.openingHours || rec.best_time || '09:00-17:00',
        images: normalizeImageList(detail)
      }
    })
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
      lat: Number(hotel.coordinates?.lat ?? hotel.lat) || 0,
      lng: Number(hotel.coordinates?.lng ?? hotel.lng ?? hotel.lon) || 0
    },
    rating: normalizePoiRating(hotel, index, 'hotel'),
    description: hotel.description || `${hotel.name || '该酒店'}适合作为本次路线的住宿落点。`,
    priceRange: mapPriceRange(hotel.price),
    priceText: normalizePriceText(hotel.price, 'hotel'),
    address: hotel.address || '',
    openingHours: hotel.opening_hours || '全天',
    images: normalizeImageList(hotel)
  }))
}

const normalizeDayHotel = (hotel: any, hotelOptions: any[] = [], activities: Activity[] = []): HotelRecommendation | undefined => {
  const source = enrichDayHotelSource(hotel, hotelOptions, activities)
  const name = String(source?.name || '').trim()
  if (!name) return undefined
  const priceEstimate = source.price_estimate ?? source.price ?? source.cost ?? source.estimated_cost
  const lat = Number(source?.coordinates?.lat ?? source?.lat)
  const lng = Number(source?.coordinates?.lng ?? source?.lng ?? source?.lon)
  return {
    name,
    address: source.address || '',
    priceEstimate: typeof priceEstimate === 'number' ? priceEstimate : normalizePriceText(priceEstimate, 'hotel'),
    reason: source.reason || source.description || `${name}适合作为这次行程的住宿落点。`,
    rating: Number(source.rating) || undefined,
    coordinates: Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : undefined
  }
}

const convertIntercityTransport = (source: any): IntercityTransportPlan | undefined => {
  if (!source || typeof source !== 'object') return undefined
  const outbound = convertIntercityLeg(source.outbound)
  const inbound = convertIntercityLeg(source.inbound)
  const totalCost = Number(source.total_cost ?? source.totalCost ?? 0) || 0
  if (!outbound && !inbound && !totalCost) return undefined
  return {
    departureCity: String(source.departure_city ?? source.departureCity ?? ''),
    destination: String(source.destination ?? ''),
    currency: String(source.currency || 'CNY'),
    estimated: Boolean(source.estimated),
    costPending: Boolean(source.cost_pending ?? source.costPending),
    distanceKm: Number(source.distance_km ?? source.distanceKm) || undefined,
    totalCost,
    costPerPerson: Number(source.cost_per_person ?? source.costPerPerson ?? 0) || 0,
    outbound,
    inbound,
    summary: source.summary || ''
  }
}

const convertIntercityLeg = (source: any): IntercityTransportLeg | undefined => {
  if (!source || typeof source !== 'object') return undefined
  const bestOption = convertTransportOption(source.best_option ?? source.bestOption)
  const alternatives = convertTransportOptions(source.alternatives)
  const options = convertTransportOptions(source.options)
  return {
    direction: String(source.direction || ''),
    from: String(source.from || ''),
    to: String(source.to || ''),
    mode: String(source.mode || ''),
    fromTerminal: String(source.from_terminal ?? source.fromTerminal ?? bestOption?.fromTerminal ?? ''),
    toTerminal: String(source.to_terminal ?? source.toTerminal ?? bestOption?.toTerminal ?? ''),
    departureDatetime: String(source.departure_datetime ?? source.departureDatetime ?? ''),
    arrivalDatetime: String(source.arrival_datetime ?? source.arrivalDatetime ?? ''),
    durationMinutes: Number(source.duration_minutes ?? source.durationMinutes ?? 0) || 0,
    durationText: String(source.duration_text ?? source.durationText ?? ''),
    distanceKm: Number(source.distance_km ?? source.distanceKm ?? 0) || 0,
    costPerPerson: Number(source.cost_per_person ?? source.costPerPerson ?? 0) || 0,
    totalCost: Number(source.total_cost ?? source.totalCost ?? 0) || 0,
    currency: String(source.currency || 'CNY'),
    estimated: Boolean(source.estimated),
    costPending: Boolean(source.cost_pending ?? source.costPending),
    source: String(source.source || ''),
    note: source.note || '',
    bestOption,
    alternatives,
    options: options.length ? options : ([bestOption, ...alternatives].filter(Boolean) as TransportOption[])
  }
}

const convertTransportOptions = (source: any): TransportOption[] => {
  if (!Array.isArray(source)) return []
  return source
    .map(convertTransportOption)
    .filter((item): item is TransportOption => Boolean(item))
}

const convertTransportOption = (source: any): TransportOption | undefined => {
  if (!source || typeof source !== 'object') return undefined
  return {
    mode: String(source.mode || ''),
    fromTerminal: String(source.from_terminal ?? source.fromTerminal ?? ''),
    toTerminal: String(source.to_terminal ?? source.toTerminal ?? ''),
    departureDatetime: String(source.departure_datetime ?? source.departureDatetime ?? ''),
    arrivalDatetime: String(source.arrival_datetime ?? source.arrivalDatetime ?? ''),
    durationMinutes: Number(source.duration_minutes ?? source.durationMinutes ?? 0) || 0,
    durationText: String(source.duration_text ?? source.durationText ?? ''),
    costPerPerson: Number(source.cost_per_person ?? source.costPerPerson ?? 0) || 0,
    totalCost: Number(source.total_cost ?? source.totalCost ?? 0) || 0,
    currency: String(source.currency || 'CNY'),
    estimated: Boolean(source.estimated),
    costPending: Boolean(source.cost_pending ?? source.costPending),
    source: String(source.source || ''),
    reason: String(source.reason || source.note || ''),
    recommended: Boolean(source.recommended ?? source.is_best ?? source.isBest)
  }
}

const enrichDayHotelSource = (hotel: any, hotelOptions: any[], activities: Activity[]) => {
  const source = hotel || hotelOptions[0]
  if (!source) return source
  if (hasCoordinates(source)) return source

  const matched = findHotelOption(source, hotelOptions)
  if (matched && hasCoordinates(matched)) {
    return { ...matched, ...source, coordinates: matched.coordinates || { lat: matched.lat, lng: matched.lng ?? matched.lon } }
  }

  const nearest = findNearestHotelOption(hotelOptions, activities)
  if (nearest && hasCoordinates(nearest)) {
    return { ...nearest, ...source, coordinates: nearest.coordinates || { lat: nearest.lat, lng: nearest.lng ?? nearest.lon } }
  }
  return source
}

const hasCoordinates = (source: any): boolean => {
  const lat = Number(source?.coordinates?.lat ?? source?.lat)
  const lng = Number(source?.coordinates?.lng ?? source?.lng ?? source?.lon)
  return Number.isFinite(lat) && Number.isFinite(lng) && lat !== 0 && lng !== 0
}

const findHotelOption = (hotel: any, hotelOptions: any[]) => {
  const id = String(hotel?.source_id || hotel?.id || '').trim()
  if (id) {
    const byId = hotelOptions.find((item) => String(item?.id || item?.source_id || '').trim() === id)
    if (byId) return byId
  }
  const key = compactName(hotel?.name)
  if (!key) return null
  return hotelOptions.find((item) => {
    const nextKey = compactName(item?.name)
    return nextKey && (nextKey === key || nextKey.includes(key) || key.includes(nextKey))
  })
}

const findNearestHotelOption = (hotelOptions: any[], activities: Activity[]) => {
  const center = activityCenter(activities)
  if (!center) return null
  return hotelOptions
    .filter(hasCoordinates)
    .map((hotel) => ({
      hotel,
      distance: distanceBetween(center, {
        lat: Number(hotel.coordinates?.lat ?? hotel.lat),
        lng: Number(hotel.coordinates?.lng ?? hotel.lng ?? hotel.lon)
      })
    }))
    .sort((left, right) => left.distance - right.distance)[0]?.hotel || null
}

const activityCenter = (activities: Activity[]) => {
  const coords = activities.map((item) => item.coordinates).filter(Boolean) as Array<{ lat: number; lng: number }>
  if (!coords.length) return null
  return {
    lat: coords.reduce((sum, item) => sum + item.lat, 0) / coords.length,
    lng: coords.reduce((sum, item) => sum + item.lng, 0) / coords.length
  }
}

const compactName = (value: unknown): string => String(value || '').replace(/[^\w\u4e00-\u9fff]/g, '').toLowerCase()

const distanceBetween = (left: { lat: number; lng: number }, right: { lat: number; lng: number }): number => {
  const toRad = (value: number) => (value * Math.PI) / 180
  const dLat = toRad(right.lat - left.lat)
  const dLng = toRad(right.lng - left.lng)
  const lat1 = toRad(left.lat)
  const lat2 = toRad(right.lat)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(a))
}

const normalizeActivity = (
  activity: any,
  dayIndex: number,
  activityIndex: number,
  fallbackTheme?: string,
  poiMap: Record<string, any> = {}
): Activity => {
  const isIntercityTransport = Boolean(activity.is_intercity_transport ?? activity.isIntercityTransport)
  const poi = isIntercityTransport ? null : findPoiByLocation(activity.location || '', poiMap)
  const normalizedType = isIntercityTransport ? 'transport' : mapActivityType(activity.type || fallbackTheme)
  const ticketPrice = normalizeTicketPrice(activity, poi, normalizedType)
  const lat = isIntercityTransport ? Number.NaN : Number(poi?.lat ?? activity.coordinates?.lat)
  const lng = isIntercityTransport ? Number.NaN : Number(poi?.lng ?? activity.coordinates?.lng)
  const time = normalizeTime(activity.time)
  const location = activity.location || activity.title || '待定地点'
  const bestTransportOption = convertTransportOption(activity.best_transport_option ?? activity.bestTransportOption)
  const transportOptions = convertTransportOptions(activity.transport_options ?? activity.transportOptions)
  const transportAlternatives = convertTransportOptions(activity.transport_alternatives ?? activity.transportAlternatives)
  const normalizedTransportOptions: TransportOption[] = transportOptions.length
    ? transportOptions
    : ([bestTransportOption, ...transportAlternatives].filter(Boolean) as TransportOption[])
  return {
    id: activity.id || `act_${dayIndex + 1}_${activityIndex + 1}`,
    time,
    title: normalizeActivityTitle(activity.title || `行程活动 ${activityIndex + 1}`, normalizedType, time, location),
    description: activity.description || poi?.description || '这是一段适合顺路安排的旅行体验。',
    location,
    type: normalizedType,
    duration: Number(activity.duration) || 90,
    cost: Number(activity.cost ?? activity.cost_estimate ?? activity.total_cost ?? activity.totalCost ?? 0) || 0,
    ticketPrice,
    ticketLabel: buildTicketLabel(activity, poi, ticketPrice),
    notes: activity.tips || poi?.tips || activity.transportation,
    reason: activity.reason || activity.recommendation_reason || '',
    score: Number(activity.score) || undefined,
    scoreFactors: activity.score_factors || activity.scoreFactors,
    image: activity.image || activity.image_url || poi?.image_url,
    coordinates: Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : undefined,
    isIntercityTransport,
    intercityDirection: String(activity.intercity_direction ?? activity.intercityDirection ?? ''),
    transportation: String(activity.transportation || bestTransportOption?.mode || ''),
    fromTerminal: String(activity.from_terminal ?? activity.fromTerminal ?? bestTransportOption?.fromTerminal ?? ''),
    toTerminal: String(activity.to_terminal ?? activity.toTerminal ?? bestTransportOption?.toTerminal ?? ''),
    departureDatetime: String(activity.departure_datetime ?? activity.departureDatetime ?? bestTransportOption?.departureDatetime ?? ''),
    arrivalDatetime: String(activity.arrival_datetime ?? activity.arrivalDatetime ?? bestTransportOption?.arrivalDatetime ?? ''),
    costPerPerson: Number(activity.cost_per_person ?? activity.costPerPerson ?? bestTransportOption?.costPerPerson ?? 0) || undefined,
    totalCost: Number(activity.total_cost ?? activity.totalCost ?? bestTransportOption?.totalCost ?? activity.cost_estimate ?? activity.cost ?? 0) || undefined,
    bestTransportOption,
    transportOptions: normalizedTransportOptions,
    transportAlternatives: transportAlternatives.length ? transportAlternatives : normalizedTransportOptions.slice(1)
  }
}

const isHotelLikeActivity = (activity: any): boolean => {
  const text = `${activity?.title || ''} ${activity?.type || ''} ${activity?.description || ''} ${activity?.location || ''}`.toLowerCase()
  return /入住|办理入住|返回酒店|回酒店|酒店休息|住宿|check-in|check in/.test(text)
    && /酒店|住宿|民宿|客栈|宾馆|hotel|check/.test(text)
}

const normalizeActivityTitle = (title: string, type: Activity['type'], time: string, location: string): string => {
  if (type !== 'food') return title
  const hour = parseHour(time, 12)
  const label = hour < 10
    ? '早餐'
    : hour < 14
      ? '午餐'
      : hour < 17
        ? '下午茶'
        : '晚餐'
  const cleaned = String(title || location)
    .replace(/^(早餐|早茶|早午茶|午餐|午饭|下午茶|晚餐|晚饭|夜宵)[：:\s-]*/, '')
    .trim()
  const mealTitle = looksLikeTransportTitle(cleaned) ? location : cleaned
  return `${label}：${mealTitle || location || '餐饮安排'}`
}

const looksLikeTransportTitle = (value: string): boolean =>
  /前往|驱车|打车|乘车|坐车|自驾|抵达|出发|返程|返回|上岛|离岛|交通|路线/.test(value)

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

const recommendationItemName = (item: any, rec: any, recIndex: number): string => {
  if (typeof item === 'string') return item
  return String(item?.name || item?.title || rec.title || `推荐 ${recIndex + 1}`).trim()
}

const recommendationDetail = (rec: any, rawItem: any, name: string) => {
  if (rawItem && typeof rawItem === 'object') return rawItem
  const details = [
    ...(Array.isArray(rec.item_details) ? rec.item_details : []),
    ...(Array.isArray(rec.itemDetails) ? rec.itemDetails : []),
    ...(Array.isArray(rec.details) ? rec.details : [])
  ]
  const normalizedName = name.trim().toLowerCase()
  return details.find((item) => {
    const detailName = String(item?.name || item?.title || '').trim().toLowerCase()
    return detailName && (detailName === normalizedName || detailName.includes(normalizedName) || normalizedName.includes(detailName))
  })
}

const normalizeImageList = (source: any): string[] => {
  const candidates = [
    source?.image,
    source?.image_url,
    source?.imageUrl,
    source?.cover,
    source?.cover_image_url,
    source?.coverImageUrl,
    source?.thumbnail,
    source?.photo,
    ...(Array.isArray(source?.images) ? source.images : []),
    ...(Array.isArray(source?.image_urls) ? source.image_urls : []),
    ...(Array.isArray(source?.photos) ? source.photos.map((photo: any) => photo?.url || photo?.image_url || photo) : [])
  ]
  const seen = new Set<string>()
  return candidates
    .map(normalizeImageUrl)
    .filter((url): url is string => {
      if (!url || seen.has(url)) return false
      seen.add(url)
      return true
    })
}

const normalizeImageUrl = (value: unknown): string => {
  if (value && typeof value === 'object') {
    const item = value as Record<string, any>
    return normalizeImageUrl(item.url ?? item.image_url ?? item.imageUrl ?? item.cover ?? item.thumbnail)
  }
  const url = String(value || '').trim()
  if (!url) return ''
  if (url.startsWith('//')) return `https:${url}`
  return url
}

const normalizeTime = (time: string | undefined): string => {
  if (!time) return '09:00'
  return String(time).split('-')[0]
}

const parseHour = (time: string | undefined, fallback = 24): number => {
  const match = String(time || '').match(/(\d{1,2})(?::(\d{2}))?/)
  if (!match) return fallback
  return Number(match[1]) + Number(match[2] || 0) / 60
}

const timeSortValue = (time: string | undefined): number => parseHour(time, 24)

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

const mapRecommendationTypeToPoiType = (rawType: unknown): POI['type'] => {
  const value = String(rawType || '').toLowerCase()
  if (value.includes('美食') || value.includes('餐')) return 'restaurant'
  if (value.includes('酒店') || value.includes('住宿')) return 'hotel'
  if (value.includes('博物')) return 'museum'
  if (value.includes('公园') || value.includes('自然')) return 'park'
  if (value.includes('购物')) return 'shop'
  return 'attraction'
}

const mapPriceRange = (priceRange: unknown): POI['priceRange'] => {
  const text = String(priceRange || '')
  if (!text) return '$$'
  if (text.includes('免费')) return 'free'
  if (text.includes('豪华')) return '$$$$'
  if (text.includes('经济')) return '$'
  if (/\d{3,}/.test(text)) return '$$$'
  return '$$'
}

type PriceContext = POI['type'] | Activity['type'] | 'person' | 'night'

const priceUnitOf = (context?: PriceContext): string => {
  if (context === 'hotel' || context === 'night') return '/晚'
  if (context === 'restaurant' || context === 'food' || context === 'person') return '/人'
  return ''
}

const formatNumericPrice = (value: number, context?: PriceContext): string => {
  if (context === 'restaurant' || context === 'food' || context === 'person') return value.toFixed(2)
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

const normalizePriceText = (value: unknown, context?: PriceContext): string => {
  const text = String(value ?? '').trim()
  if (!text) return '待查询'
  if (text.includes('免费')) return '免费'
  if (/\/晚|\/人|每晚|人均|待查询/.test(text)) return text
  const unit = priceUnitOf(context)
  if (text.startsWith('¥') || text.startsWith('￥')) return unit ? `${text}${unit}` : text
  if (/^\d+(\.\d+)?$/.test(text)) return `¥${formatNumericPrice(Number(text), context)}${unit}`
  return text
}

const normalizeOptionalPriceText = (value: unknown, context?: PriceContext): string | undefined => {
  const text = String(value ?? '').trim()
  return text ? normalizePriceText(text, context) : undefined
}

const normalizePoiRating = (source: any, index: number, type: POI['type']): number => {
  const explicit = firstPositiveNumber(source?.rating, source?.display_rating, source?.displayRating)
  if (explicit !== undefined && explicit > 0) {
    return roundRating(explicit > 5 ? explicit / 20 : explicit)
  }
  const score = firstPositiveNumber(source?.score, source?.recommendation_score, source?.recommendationScore)
  if (score !== undefined && score > 0) {
    if (score <= 5) return roundRating(score)
    if (score <= 10) return roundRating(4.4 + Math.min(score, 10) * 0.06)
    return roundRating(4.4 + Math.min(score, 100) * 0.006)
  }
  if (type === 'restaurant') return roundRating(Math.max(4.6, 5.0 - index * 0.1))
  return 4.5
}

const roundRating = (value: number): number => Math.round(Math.max(0, Math.min(5, value)) * 10) / 10

const firstPositiveNumber = (...values: unknown[]): number | undefined => {
  for (const value of values) {
    const parsed = parseNumericPrice(value)
    if (parsed !== undefined && parsed > 0) return parsed
  }
  return undefined
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
  if (type.includes('美食') || type.includes('餐')) return `${name}适合安排成一顿有记忆点的本地餐食。`
  if (type.includes('文化') || type.includes('博物')) return `${name}适合补充目的地的人文背景。`
  if (type.includes('自然') || type.includes('公园')) return `${name}适合作为一天行程里的放松段落。`
  return `${name}是这次路线里值得补充的一站，第 ${itemIndex + 1} 个推荐更适合顺路安排。`
}
