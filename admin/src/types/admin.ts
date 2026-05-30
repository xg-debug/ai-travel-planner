export type AdminRole = 'user' | 'admin' | 'super_admin'

export interface AuthUser {
  id: string
  email: string
  name: string
  avatar?: string | null
  role: AdminRole
  createdAt: string
}

export interface AuthResponse {
  user: AuthUser
  token: string
  token_expires_in_minutes: number
}

export interface AdminPermissions {
  canViewDashboard: boolean
  canManageSettings: boolean
  canManageUsers: boolean
}

export interface AdminUser {
  id: string
  email: string
  name: string
  role: AdminRole
  avatarUrl?: string | null
  emailVerified?: boolean
  createdAt: string
  updatedAt?: string
  lastLoginAt?: string | null
  tripCount?: number
  isSuperAdmin?: boolean
  permissions?: AdminPermissions
}

export interface DailySeriesItem {
  date: string
  registrations: number
  logins: number
  activeUsers: number
  tripGenerations: number
}

export interface RankItem {
  name: string
  count: number
}

export interface RecentTrip {
  id: string
  destination: string
  status: string
  createdAt: string
  updatedAt: string
  user: {
    id: string
    name: string
    email: string
  }
}

export interface AdminOverview {
  totals: {
    users: number
    admins: number
    superAdmins: number
    trips: number
    registrationsToday: number
    loginsToday: number
    activeToday: number
    tripsToday: number
  }
  dailySeries: DailySeriesItem[]
  topDestinations: RankItem[]
  topThemes: RankItem[]
  userTripCounts: AdminUser[]
  recentTrips: RecentTrip[]
}

export interface ProviderOption {
  id: string
  label: string
  defaultModel?: string
  hasKey: boolean
  maskedKey?: string | null
}

export interface AgentStatus {
  llm: {
    provider: string
    providerLabel: string
    model: string
    providers: ProviderOption[]
  }
  map: {
    provider: string
    providerLabel: string
    providers: ProviderOption[]
  }
  health: {
    llmConfigured: boolean
    mapConfigured: boolean
    warnings: string[]
  }
}
