import type { Activity, POI, Trip, TripDay } from '@/types/trip'

const textOf = (value: unknown) => String(value || '').toLowerCase()

export const isMealActivity = (activity: Activity) => {
  const text = `${activity.title} ${activity.location} ${activity.description} ${activity.notes || ''}`
  return activity.type === 'food'
    || /餐|饭|菜|食|小吃|早餐|午餐|晚餐|咖啡|茶|酒|面|粉|烤|火锅|餐厅/.test(text)
}

export const isHotelPoi = (poi: POI) => poi.type === 'hotel' || /酒店|住宿|客栈|民宿/.test(`${poi.name} ${poi.category}`)

export const isFoodPoi = (poi: POI) => poi.type === 'restaurant' || /美食|餐|食|小吃|咖啡|茶/.test(`${poi.name} ${poi.category}`)

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
  const stops = dayRouteStops(day)
  const first = stops[0] || dayAttractions(day)[0] || day?.activities?.[0]
  const last = stops[stops.length - 1] || day?.activities?.[day.activities.length - 1]
  if (!first && !last) return '路线待生成'
  if (!last || first?.id === last?.id) return first.location || first.title
  return `${first.location || first.title} → ${last.location || last.title}`
}

export const routeActivities = (day?: TripDay) =>
  (day?.activities || []).filter((activity) => activity.type !== 'transport' && !isHotelActivity(activity)).slice(0, 6)

export const dayRouteStops = (day?: TripDay) => {
  const stops = [...routeActivities(day)]
  const hotelStop = hotelToRouteStop(day)
  if (hotelStop) stops.push(hotelStop)
  return uniqueRouteStops(stops).slice(0, 7)
}

export const tripAttractions = (trip?: Trip | null) => {
  const fromRecommendations = (trip?.recommendations || []).filter(isAttractionPoi)
  if (fromRecommendations.length) return fromRecommendations.slice(0, 8)
  return uniqueActivities(trip?.days.flatMap((day) => dayAttractions(day)) || []).map(activityToPoi).slice(0, 8)
}

export const tripFood = (trip?: Trip | null) => {
  const fromRecommendations = (trip?.recommendations || []).filter(isFoodPoi)
  if (fromRecommendations.length) return fromRecommendations.slice(0, 8)
  return uniqueActivities(trip?.days.flatMap((day) => dayMeals(day)) || []).map(activityToPoi).slice(0, 8)
}

export const tripHotels = (trip?: Trip | null) => {
  const hotels = trip?.hotels?.length ? trip.hotels : (trip?.recommendations || []).filter(isHotelPoi)
  return hotels.slice(0, 6)
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
      : textOf(item.location || item.title)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const hotelToRouteStop = (day?: TripDay): Activity | null => {
  const hotel = day?.hotel
  if (!hotel?.coordinates) return null
  return {
    id: `hotel_${day?.date || hotel.name}`,
    time: '20:00',
    title: '入住酒店',
    description: hotel.reason || `${hotel.name}是当天住宿点。`,
    location: hotel.name,
    type: 'other',
    duration: 0,
    cost: 0,
    notes: hotel.address,
    coordinates: hotel.coordinates
  }
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
