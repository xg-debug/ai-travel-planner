export const formatMoney = (value?: number | string) => {
  const numeric = Number(value || 0)
  if (!Number.isFinite(numeric)) return String(value || '待查询')
  return `¥${Math.round(numeric).toLocaleString()}`
}

export const formatDate = (value?: string) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

export const formatDateRange = (start?: string, end?: string) => {
  if (!start && !end) return '日期待定'
  if (!end || start === end) return formatDate(start)
  return `${formatDate(start)} - ${formatDate(end)}`
}

export const calculateDays = (startDate: string, endDate: string) => {
  const start = new Date(startDate)
  const end = new Date(endDate)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 1
  return Math.max(1, Math.round((end.getTime() - start.getTime()) / 86400000) + 1)
}

export const addDays = (dateText: string, days: number) => {
  const date = new Date(dateText)
  date.setDate(date.getDate() + days)
  return date.toISOString().split('T')[0]
}

export const todayText = () => new Date().toISOString().split('T')[0]

export const activityTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    food: '餐饮',
    culture: '文化',
    outdoor: '自然',
    shopping: '购物',
    entertainment: '休闲',
    transport: '交通',
    other: '安排'
  }
  return labels[type] || '安排'
}
