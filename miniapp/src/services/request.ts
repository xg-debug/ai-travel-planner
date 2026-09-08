const DEFAULT_API_BASE = 'http://localhost:8000/api'
const TOKEN_KEY = 'cybertravel_auth_token'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

interface RequestOptions {
  url: string
  method?: HttpMethod
  data?: unknown
  params?: Record<string, string | number | boolean | undefined | null>
  timeout?: number
}

const getBaseUrl = () => {
  const value = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE
  return value.replace(/\/$/, '')
}

export const buildApiUrl = (path: string, params?: RequestOptions['params']) => {
  const url = `${getBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`
  const cleanParams = Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null)
  if (!cleanParams.length) return url
  const query = cleanParams
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
  return `${url}${url.includes('?') ? '&' : '?'}${query}`
}

const parseApiError = (data: unknown, statusCode?: number) => {
  const detail = (data as any)?.detail
  const structured = detail && typeof detail === 'object' ? detail : null
  if (structured?.message) return String(structured.message)
  const raw = typeof data === 'string'
    ? data
    : String(detail || (data as any)?.message || '')
  const lower = raw.toLowerCase()
  if (statusCode === 401) return '登录已过期，请重新登录'
  if (statusCode === 402 || lower.includes('insufficient balance') || raw.includes('余额不足')) {
    return 'AI 服务余额不足，请检查账户余额后重试'
  }
  if (lower.includes('timeout') || lower.includes('timed out')) return 'AI 服务响应超时，请稍后重试'
  if (statusCode && statusCode >= 500) return '服务暂时不可用，请稍后重试'
  return raw || '请求失败，请稍后重试'
}

export const getAuthToken = () => uni.getStorageSync(TOKEN_KEY) as string

export const setAuthToken = (token: string) => uni.setStorageSync(TOKEN_KEY, token)

export const clearAuthToken = () => uni.removeStorageSync(TOKEN_KEY)

export function request<T>(options: RequestOptions): Promise<T> {
  const token = getAuthToken()
  return new Promise((resolve, reject) => {
    uni.request({
      url: buildApiUrl(options.url, options.params),
      method: options.method || 'GET',
      data: options.data as any,
      timeout: options.timeout || 120000,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
          return
        }
        reject(new Error(parseApiError(res.data, res.statusCode)))
      },
      fail: (err) => {
        const detail = String((err as any)?.errMsg || '').trim()
        const localHint = getBaseUrl().includes('localhost') || getBaseUrl().includes('127.0.0.1')
          ? '；真机不能使用 localhost，请在 miniapp/.env 中配置电脑局域网 IP'
          : ''
        reject(new Error(detail
          ? `无法连接后端：${detail}${localHint}`
          : `无法连接后端，请确认服务已启动${localHint}`))
      }
    })
  })
}
