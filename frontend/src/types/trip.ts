export interface TripRequest {
  departureCity: string
  destination: string
  startDate: string
  endDate: string
  days: number
  travelers: number
  interests: string[]
  budget: number
  preferences?: {
    pace?: 'relaxed' | 'moderate' | 'fast'
    accommodation?: 'budget' | 'mid-range' | 'luxury'
    food?: 'local' | 'international' | 'mixed'
    transportation?: 'public' | 'private' | 'mixed'
  }
}

export interface IntercityTransportLeg {
  direction: 'outbound' | 'inbound' | string
  from: string
  to: string
  mode: string
  departureDatetime?: string
  arrivalDatetime?: string
  durationMinutes: number
  durationText: string
  distanceKm: number
  costPerPerson: number
  totalCost: number
  currency: string
  estimated?: boolean
  costPending?: boolean
  source?: string
  note?: string
}

export interface IntercityTransportPlan {
  departureCity: string
  destination: string
  currency: string
  estimated?: boolean
  costPending?: boolean
  distanceKm?: number
  totalCost: number
  costPerPerson: number
  outbound?: IntercityTransportLeg
  inbound?: IntercityTransportLeg
  summary?: string
}

export interface Activity {
  id: string
  time: string
  title: string
  description: string
  location: string
  type: 'food' | 'culture' | 'outdoor' | 'shopping' | 'entertainment' | 'transport' | 'other'
  duration: number // in minutes
  cost: number
  ticketPrice?: number
  ticketLabel?: string
  notes?: string
  image?: string
  coordinates?: {
    lat: number
    lng: number
  }
}

export interface HotelRecommendation {
  name: string
  address?: string
  priceEstimate?: number | string
  reason?: string
  rating?: number
}

export interface TripDay {
  date: string
  activities: Activity[]
  hotel?: HotelRecommendation
  notes?: string
  totalCost?: number
}

export interface WeatherForecast {
  city?: string
  date: string
  high: number
  low: number
  condition: string
  dayCondition?: string
  nightCondition?: string
  precipitation: number // percentage
  humidity: number // percentage
  windSpeed: number // km/h
  dayWindDirection?: string
  nightWindDirection?: string
  dayWindPower?: string
  nightWindPower?: string
  icon?: string
}

export interface POI {
  id: string
  name: string
  type: 'attraction' | 'restaurant' | 'hotel' | 'museum' | 'park' | 'shop' | 'other'
  category: string
  location: {
    lat: number
    lng: number
  }
  rating: number
  description: string
  priceRange: 'free' | '$' | '$$' | '$$$' | '$$$$'
  priceText?: string
  address?: string
  openingHours?: string
  website?: string
  phone?: string
  images?: string[]
}

export interface BudgetCategory {
  name: string
  amount: number
  planned: number
  spent?: number
}

export interface BudgetBreakdown {
  total: number
  currency: string
  categories: BudgetCategory[]
}

export interface Trip {
  id: string
  departureCity?: string
  destination: string
  startDate: string
  endDate: string
  travelers: number
  interests: string[]
  days: TripDay[]
  weather: WeatherForecast[]
  recommendations: POI[]
  hotels?: POI[]
  budget: BudgetBreakdown
  intercityTransport?: IntercityTransportPlan
  plan?: string
  createdAt: string
  updatedAt: string
  notes?: string
  status?: 'draft' | 'planned' | 'in-progress' | 'completed' | 'cancelled'
}

export interface APIResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// 后端API响应类型
export interface TripResponse {
  plan: string
  pois: Record<string, any>
  itinerary: any[]
  weather: {
    city: string
    report_time: string
    forecast: Array<{
      date: string
      condition: string
      day_condition?: string
      night_condition?: string
      temperature: {
        min: number
        max: number
        avg: number
      }
      humidity: number
      wind_speed: number
      day_wind_direction?: string
      night_wind_direction?: string
      day_wind_power?: string
      night_wind_power?: string
      icon: string
    }>
  }
  recommendations: Array<{
    type: string
    title: string
    items: string[]
    description: string
    reasoning: string
    best_time: string
    price_range: string
    tips: string
  }>
  hotels?: Array<Record<string, any>>
  estimated_budget: {
    total: number
    per_person: number
    per_day: number
    breakdown: {
      accommodation: number
      food: number
      transportation: number
      tickets: number
      shopping: number
    }
    currency: string
    budget_level: string
    travelers: number
    days: number
    activity_adjustment: number
    tips: string[]
  }
  intercity_transport?: Record<string, any>
}
