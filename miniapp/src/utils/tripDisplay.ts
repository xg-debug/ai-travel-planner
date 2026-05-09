import type { Activity, POI, Trip, TripDay } from '@/types/trip'

const textOf = (value: unknown) => String(value || '').toLowerCase()

export const isMealActivity = (activity: Activity) => {
  const text = `${activity.title} ${activity.location} ${activity.description} ${activity.notes || ''}`
  return activity.type === 'food'
    || /餐|饭|菜|食|小吃|早餐|午餐|晚餐|咖啡|茶|酒|面|粉|烤|火锅|餐厅/.test(text)
}

export const isHotelPoi = (poi: POI) => poi.type === 'hotel' || /酒店|住宿|客栈|民宿/.test(`${poi.name} ${poi.category}`)

export const isFoodPoi = (poi: POI) => poi.type === 'restaurant' || /美食|餐|食|小吃|咖啡|茶/.test(`${poi.name} ${poi.category}`)

export const isAttractionPoi = (poi: POI) => {
  if (isHotelPoi(poi) || isFoodPoi(poi)) return false
  return ['attraction', 'museum', 'park', 'shop', 'other'].includes(poi.type)
}

export const dayAttractions = (day?: TripDay) =>
  (day?.activities || []).filter((activity) => !isMealActivity(activity) && activity.type !== 'transport')

export const dayMeals = (day?: TripDay) => (day?.activities || []).filter(isMealActivity)

export const dayRouteTitle = (day?: TripDay) => {
  const first = dayAttractions(day)[0] || day?.activities?.[0]
  const last = day?.activities?.[day.activities.length - 1]
  if (!first && !last) return '路线待生成'
  if (!last || first?.id === last?.id) return first.location || first.title
  return `${first.location || first.title} → ${last.location || last.title}`
}

export const routeActivities = (day?: TripDay) =>
  (day?.activities || []).filter((activity) => activity.type !== 'transport').slice(0, 6)

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
  (trip?.days || []).flatMap((day) => routeActivities(day)).slice(0, 8)

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

const activityToPoi = (activity: Activity): POI => ({
  id: activity.id,
  name: activity.location || activity.title,
  type: activity.type === 'food' ? 'restaurant' : 'attraction',
  category: activity.type,
  location: activity.coordinates || { lat: 0, lng: 0 },
  rating: 4.6,
  description: activity.description,
  priceRange: activity.ticketPrice === 0 ? 'free' : '$$',
  priceText: activity.ticketLabel,
  address: activity.location,
  images: activity.image ? [activity.image] : []
})
