import type { Activity, POI, Trip, TripDay } from '@/types/trip'

const textOf = (value: unknown) => String(value || '').toLowerCase()

export const isMealActivity = (activity: Activity) => {
  const text = `${activity.title} ${activity.location} ${activity.description} ${activity.notes || ''}`
  return activity.type === 'food'
    || /餐|饭|菜|食|小吃|早餐|午餐|晚餐|咖啡|茶|酒|面|粉|烤|火锅|餐厅/.test(text)
}

export const isHotelPoi = (poi: POI) => poi.type === 'hotel' || /酒店|住宿|客栈|民宿/.test(`${poi.name} ${poi.category}`)

export const isFoodPoi = (poi: POI) => poi.type === 'restaurant' || /美食|餐|食|小吃|咖啡|茶/.test(`${poi.name} ${poi.category}`)

const isBlockedFoodPoi = (poi: POI) =>
  /大学|学院|学校|校区|校园|食堂|会议中心|机关|单位|内部|员工|职工/.test(`${poi.name} ${poi.category} ${poi.address || ''} ${poi.description}`)

const attractionCategory = (poi: POI) => {
  const text = `${poi.name} ${poi.category} ${poi.address || ''} ${poi.description}`
  if (/博物馆|纪念馆|展览馆|展馆|美术馆|科技馆|文化馆/.test(text)) return 'museum'
  if (/街|巷|里|坊|古文化|风情区|步行街|商圈|广场|意式|五大道/.test(text)) return 'street'
  if (/塔|桥|楼|眼|教堂|码头|海河|地标|公园|故居|瓷房子/.test(text)) return 'landmark'
  return 'other'
}

export const isHotelActivity = (activity: Activity) => {
  const text = `${activity.title} ${activity.location} ${activity.description} ${activity.notes || ''}`.toLowerCase()
  return /入住|办理入住|返回酒店|回酒店|酒店休息|住宿|check-in|check in/.test(text)
    && /酒店|住宿|民宿|客栈|宾馆|hotel|check/.test(text)
}

export const isAttractionPoi = (poi: POI) => {
  if (isHotelPoi(poi) || isFoodPoi(poi)) return false
  return ['attraction', 'museum', 'park', 'shop', 'other'].includes(poi.type)
}

export const dayAttractions = (day?: TripDay) =>
  (day?.activities || []).filter((activity) => !isMealActivity(activity) && activity.type !== 'transport' && !isHotelActivity(activity))

export const dayMeals = (day?: TripDay) => (day?.activities || []).filter(isMealActivity)

export const dayRouteTitle = (day?: TripDay) => {
  const stops = routeActivities(day)
  const first = stops[0] || dayAttractions(day)[0] || day?.activities?.[0]
  const last = stops[stops.length - 1] || day?.activities?.[day.activities.length - 1]
  if (!first && !last) return '路线待生成'
  const firstName = displayStopName(first)
  const lastName = displayStopName(last)
  if (!last || first?.id === last?.id || firstName === lastName) return firstName
  return `${firstName} → ${lastName}`
}

export const routeActivities = (day?: TripDay) =>
  (day?.activities || []).filter((activity) => activity.type !== 'transport' && !isHotelActivity(activity)).slice(0, 6)

export const dayRouteStops = (day?: TripDay) => {
  const stops = [...routeActivities(day)]
  return uniqueRouteStops(stops).slice(0, 7)
}

export const tripAttractions = (trip?: Trip | null) => {
  const fromRecommendations = (trip?.recommendations || []).filter(isAttractionPoi)
  if (fromRecommendations.length) return diversifyAttractions(fromRecommendations)
  return diversifyAttractions(uniqueActivities(trip?.days.flatMap((day) => dayAttractions(day)) || []).map(activityToPoi))
}

export const tripFood = (trip?: Trip | null) => {
  const fromRecommendations = (trip?.recommendations || []).filter((item) => isFoodPoi(item) && !isBlockedFoodPoi(item))
  if (fromRecommendations.length) return fromRecommendations
  return uniqueActivities(trip?.days.flatMap((day) => dayMeals(day)) || [])
    .map(activityToPoi)
    .filter((item) => !isBlockedFoodPoi(item))
}

export const tripHotels = (trip?: Trip | null) => {
  const hotels = trip?.hotels?.length ? trip.hotels : (trip?.recommendations || []).filter(isHotelPoi)
  return hotels
}

export const tripMapActivities = (trip?: Trip | null) =>
  (trip?.days || []).flatMap((day) => dayRouteStops(day)).slice(0, 10)

export const mealHint = (activity: Activity) => {
  const text = `${activity.notes || ''} ${activity.description || ''}`
  const match = text.match(/(?:招牌|推荐|必点|特色)[：:\s]*([^，。；]{2,18})/)
  return match?.[1]?.trim() || ''
}

const uniqueActivities = (items: Activity[]) => {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = textOf(item.location || item.title)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const uniqueRouteStops = (items: Activity[]) => {
  const seen = new Set<string>()
  return items.filter((item) => {
    const coord = item.coordinates
    const key = coord
      ? `${coord.lat.toFixed(5)},${coord.lng.toFixed(5)}`
      : textOf(displayStopName(item))
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const diversifyAttractions = (items: POI[]) => {
  const buckets: Record<string, POI[]> = {
    landmark: [],
    street: [],
    other: [],
    museum: []
  }
  items.forEach((item) => {
    if (/服务中心|游客中心|售票|票务|停车场|卫生间|管理处|办公室|入口|出口/.test(`${item.name} ${item.category} ${item.address || ''}`)) {
      return
    }
    buckets[attractionCategory(item)].push(item)
  })
  const result: POI[] = []
  const seen = new Set<string>()
  const museumLimit = 2
  const take = (category: string, limit = 1) => {
    let taken = 0
    for (const item of buckets[category] || []) {
      const key = textOf(item.name)
      if (!key || seen.has(key)) continue
      if (category === 'museum' && result.filter((poi) => attractionCategory(poi) === 'museum').length >= museumLimit) return
      result.push(item)
      seen.add(key)
      taken += 1
      if (taken >= limit) return
    }
  }
  ;(['landmark', 'street', 'other', 'museum'] as const).forEach((category) => take(category, category === 'museum' ? museumLimit : 2))
  while (result.length < items.length) {
    const before = result.length
    ;(['landmark', 'street', 'other', 'museum'] as const).forEach((category) => take(category))
    if (result.length === before) break
  }
  return result
}

const activityToPoi = (activity: Activity, index = 0): POI => ({
  id: activity.id,
  name: activity.location || activity.title,
  type: activity.type === 'food' ? 'restaurant' : 'attraction',
  category: activity.type,
  location: activity.coordinates || { lat: 0, lng: 0 },
  rating: activityRating(activity, index),
  description: activity.description,
  priceRange: activity.ticketPrice === 0 ? 'free' : '$$',
  priceText: activityPriceText(activity),
  address: activity.location,
  images: activity.image ? [activity.image] : []
})

const activityRating = (activity: Activity, index: number) => {
  const score = Number(activity.score)
  if (Number.isFinite(score) && score > 0) {
    const rating = score > 5 ? 4.4 + Math.min(score, 100) * 0.006 : score
    return Math.round(Math.max(0, Math.min(5, rating)) * 10) / 10
  }
  return activity.type === 'food' ? Math.max(4.6, Math.round((5.0 - index * 0.1) * 10) / 10) : 4.6
}

const activityPriceText = (activity: Activity) => {
  if (activity.type !== 'food') return activity.ticketLabel
  const cost = Number(activity.cost)
  return Number.isFinite(cost) && cost > 0 ? `¥${cost.toFixed(2)}/人` : activity.ticketLabel
}

export const displayStopName = (activity?: Activity): string => {
  if (!activity) return ''
  return compactDisplayName(activity.location || activity.title)
}

const compactDisplayName = (value: string): string => {
  const parts = String(value || '')
    .split(/[-·•—]/)
    .map((part) => part.trim())
    .filter(Boolean)
  if (parts.length <= 1) return String(value || '').trim()
  const last = parts[parts.length - 1]
  const previous = parts[parts.length - 2]
  if (last && previous && (last.includes(previous) || previous.includes(last))) return last
  return last.length >= 2 ? last : parts.slice(-2).join('·')
}
