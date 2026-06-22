export type AccommodationPreference = 'budget' | 'mid-range' | 'luxury'

export interface TripRequest {
  departureCity: string
  destination: string
  startDate: string
  endDate: string
  departureTime?: string
  returnArrivalTime?: string
  days: number
  travelers: number
  interests: string[]
  budgetAmount: number
  accommodationPreference: AccommodationPreference
  additionalRequirements?: string
}

export interface TransportOption {
  mode: string
  fromTerminal: string
  toTerminal: string
  departureDatetime?: string
  arrivalDatetime?: string
  durationMinutes: number
  durationText?: string
  costPerPerson: number
  totalCost: number
  currency?: string
  estimated?: boolean
  costPending?: boolean
  source?: string
  reason?: string
  recommended?: boolean
}

export interface Activity {
  id: string
  time: string
  title: string
  description: string
  location: string
  type: 'food' | 'culture' | 'outdoor' | 'shopping' | 'entertainment' | 'transport' | 'other'
  duration: number
  cost: number
  ticketPrice?: number
  ticketLabel?: string
  openingHours?: string
  priceNote?: string
  notes?: string
  reason?: string
  score?: number
  scoreFactors?: Record<string, number>
  image?: string
  coordinates?: {
    lat: number
    lng: number
  }
  isIntercityTransport?: boolean
  intercityDirection?: string
  transportation?: string
  fromTerminal?: string
  toTerminal?: string
  departureDatetime?: string
  arrivalDatetime?: string
  costPerPerson?: number
  totalCost?: number
  bestTransportOption?: TransportOption
  transportOptions?: TransportOption[]
  transportAlternatives?: TransportOption[]
}

export interface HotelRecommendation {
  name: string
  address?: string
  priceEstimate?: number | string
  referencePriceRange?: string
  budgetPricePerRoom?: number
  reason?: string
  rating?: number
  coordinates?: {
    lat: number
    lng: number
  }
}

export interface IntercityTransportLeg {
  direction: 'outbound' | 'inbound' | string
  from: string
  to: string
  mode: string
  fromTerminal?: string
  toTerminal?: string
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
  bestOption?: TransportOption
  alternatives?: TransportOption[]
  options?: TransportOption[]
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

export interface TripDay {
  date: string
  theme?: string
  summary?: string
  weatherAdvice?: string
  activities: Activity[]
  hotel?: HotelRecommendation
  budget?: DailyBudget
  notes?: string
  totalCost?: number
}

export interface DailyBudget {
  day: number
  date?: string
  total: number
  categories: Record<string, number>
  risk?: string
}

export interface RiskNotice {
  type: string
  level: 'low' | 'medium' | 'high' | string
  title: string
  content: string
  related_day?: number | null
  related_place?: string
}

export interface WeatherForecast {
  city?: string
  date: string
  high: number
  low: number
  condition: string
  dayCondition?: string
  nightCondition?: string
  precipitation: number
  humidity: number
  windSpeed: number
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
  avgCost?: number
  priceSource?: string
  priceConfidence?: string
  priceNote?: string
  referencePriceRange?: string
  budgetPricePerRoom?: number
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
  accommodationPreference?: AccommodationPreference
  days: TripDay[]
  weather: WeatherForecast[]
  recommendations: POI[]
  hotels?: POI[]
  budget: BudgetBreakdown
  dailyBudgets?: DailyBudget[]
  intercityTransport?: IntercityTransportPlan
  riskNotices?: RiskNotice[]
  qualityScore?: Record<string, number>
  plan?: string
  createdAt: string
  updatedAt: string
  notes?: string
  status?: 'draft' | 'planned' | 'in-progress' | 'completed' | 'cancelled'
}

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
    items: Array<string | Record<string, any>>
    item_details?: Array<Record<string, any>>
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
    daily_budgets?: DailyBudget[]
  }
  daily_budgets?: DailyBudget[]
  risk_notices?: RiskNotice[]
  weather_impacts?: Array<Record<string, any>>
  quality_score?: Record<string, number>
  intercity_transport?: Record<string, any>
}

export type PlanTripRequest = TripRequest

export interface AuthUser {
  id: string
  email: string
  name: string
  avatar?: string
  createdAt: string
}

export interface AuthResponse {
  user: AuthUser
  token: string
  token_expires_in_minutes: number
}
