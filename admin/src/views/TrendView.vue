<template>
  <a-spin :spinning="loading">
    <div class="page-stack">
      <a-card :bordered="false" class="trend-toolbar">
        <div class="trend-toolbar__main">
          <div>
            <a-typography-text>Trend Analytics</a-typography-text>
            <h1>平台趋势</h1>
            <p>按时间范围查看用户注册、登录和行程生成趋势。</p>
          </div>
          <a-button type="primary" @click="fetchTrend">
            <template #icon>
              <ReloadOutlined />
            </template>
            刷新趋势
          </a-button>
        </div>

        <a-divider />

        <div class="trend-controls">
          <a-segmented v-model:value="metric" :options="metricOptions" />
          <a-segmented v-model:value="rangeMode" :options="rangeOptions" @change="handleRangeModeChange" />
          <a-range-picker
            v-if="rangeMode === 'custom'"
            v-model:value="customRange"
            format="YYYY-MM-DD"
            :allow-clear="false"
            @change="fetchTrend"
          />
        </div>
      </a-card>

      <a-card :bordered="false" class="line-chart-card">
        <template #title>
          <span>{{ selectedMetric.label }}趋势</span>
        </template>
        <template #extra>
          <a-tag :color="selectedMetric.tagColor">{{ rangeLabel }}</a-tag>
        </template>

        <div class="line-chart">
          <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" role="img" aria-label="平台趋势折线图">
            <g class="chart-grid">
              <line
                v-for="tick in yTicks"
                :key="tick.value"
                :x1="padding.left"
                :x2="chartWidth - padding.right"
                :y1="tick.y"
                :y2="tick.y"
              />
            </g>
            <g class="chart-axis">
              <line :x1="padding.left" :x2="chartWidth - padding.right" :y1="axisBottom" :y2="axisBottom" />
              <line :x1="padding.left" :x2="padding.left" :y1="padding.top" :y2="axisBottom" />
            </g>
            <g class="chart-y-labels">
              <text v-for="tick in yTicks" :key="`label-${tick.value}`" :x="padding.left - 10" :y="tick.y + 4">
                {{ tick.value }}
              </text>
            </g>
            <polyline class="chart-line" :points="linePoints" :style="{ stroke: selectedMetric.color }" />
            <g>
              <circle
                v-for="point in chartPoints"
                :key="point.date"
                class="chart-point"
                :cx="point.x"
                :cy="point.y"
                :r="4"
                :style="{ fill: selectedMetric.color }"
              >
                <title>{{ point.date }}：{{ point.value }}</title>
              </circle>
            </g>
            <g class="chart-x-labels">
              <text
                v-for="label in xLabels"
                :key="label.date"
                :x="label.x"
                :y="chartHeight - 18"
                text-anchor="middle"
              >
                {{ label.text }}
              </text>
            </g>
          </svg>
        </div>
      </a-card>

      <a-row :gutter="[16, 16]">
        <a-col v-for="summary in summaries" :key="summary.title" :xs="24" :md="8">
          <a-card :bordered="false" class="trend-summary-card">
            <a-statistic :title="summary.title" :value="summary.value" :suffix="summary.suffix" />
            <p>{{ summary.description }}</p>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { adminApi } from '@/services/api'
import type { AdminOverview } from '@/types/admin'

type MetricKey = 'registrations' | 'logins' | 'tripGenerations'
type RangeMode = 3 | 7 | 14 | 30 | 45 | 60 | 90 | 'custom'

const loading = ref(false)
const overview = ref<AdminOverview | null>(null)
const metric = ref<MetricKey>('registrations')
const rangeMode = ref<RangeMode>(14)
const customRange = ref<any>(null)

const chartWidth = 960
const chartHeight = 360
const padding = { top: 28, right: 28, bottom: 58, left: 54 }
const axisBottom = chartHeight - padding.bottom

const metricOptions = [
  { label: '注册', value: 'registrations' },
  { label: '登录', value: 'logins' },
  { label: '行程数', value: 'tripGenerations' }
]

const metricMeta: Record<MetricKey, { label: string; color: string; tagColor: string }> = {
  registrations: { label: '用户注册', color: '#4f46e5', tagColor: 'blue' },
  logins: { label: '用户登录', color: '#10b981', tagColor: 'green' },
  tripGenerations: { label: '行程生成', color: '#f59e0b', tagColor: 'orange' }
}

const rangeOptions = [
  { label: '3 天', value: 3 },
  { label: '7 天', value: 7 },
  { label: '14 天', value: 14 },
  { label: '30 天', value: 30 },
  { label: '45 天', value: 45 },
  { label: '60 天', value: 60 },
  { label: '90 天', value: 90 },
  { label: '自定义', value: 'custom' }
]

const selectedMetric = computed(() => metricMeta[metric.value])
const series = computed(() => overview.value?.dailySeries || [])
const values = computed(() => series.value.map((item) => Number(item[metric.value] || 0)))
const maxValue = computed(() => Math.max(1, ...values.value))

const chartPoints = computed(() => {
  const items = series.value
  const width = chartWidth - padding.left - padding.right
  const height = axisBottom - padding.top
  const denominator = Math.max(1, items.length - 1)
  return items.map((item, index) => {
    const value = Number(item[metric.value] || 0)
    return {
      date: item.date,
      value,
      x: padding.left + (index / denominator) * width,
      y: axisBottom - (value / maxValue.value) * height
    }
  })
})

const linePoints = computed(() => chartPoints.value.map((point) => `${point.x},${point.y}`).join(' '))

const yTicks = computed(() => {
  const ticks = 4
  return Array.from({ length: ticks + 1 }, (_, index) => {
    const value = Math.round((maxValue.value / ticks) * index)
    const y = axisBottom - (value / maxValue.value) * (axisBottom - padding.top)
    return { value, y }
  }).reverse()
})

const xLabels = computed(() => {
  const items = chartPoints.value
  if (!items.length) return []
  const labelCount = Math.min(7, items.length)
  const step = Math.max(1, Math.floor((items.length - 1) / Math.max(1, labelCount - 1)))
  const labels = items.filter((_, index) => index % step === 0)
  const last = items[items.length - 1]
  if (labels[labels.length - 1]?.date !== last.date) labels.push(last)
  return labels.map((item) => ({ ...item, text: formatDay(item.date) }))
})

const rangeLabel = computed(() => {
  if (rangeMode.value !== 'custom') return `最近 ${rangeMode.value} 天`
  const dates = getCustomDates()
  if (!dates) return '自定义时间'
  return `${dates.start_date} 至 ${dates.end_date}`
})

const summaries = computed(() => {
  const currentValue = values.value.reduce((sum, value) => sum + value, 0)
  const average = values.value.length ? Math.round((currentValue / values.value.length) * 10) / 10 : 0
  const peak = Math.max(0, ...values.value)
  return [
    { title: `${selectedMetric.value.label}总量`, value: currentValue, suffix: '次', description: '当前时间范围内累计值' },
    { title: '日均值', value: average, suffix: '次', description: '按所选日期区间计算' },
    { title: '单日峰值', value: peak, suffix: '次', description: '所选区间内最高单日数据' }
  ]
})

const formatDay = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '-' : `${date.getMonth() + 1}/${date.getDate()}`
}

const formatDateParam = (value: any) => {
  if (!value) return ''
  if (typeof value.format === 'function') return value.format('YYYY-MM-DD')
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toISOString().slice(0, 10)
}

const getCustomDates = () => {
  if (!customRange.value || customRange.value.length !== 2) return null
  const startDate = formatDateParam(customRange.value[0])
  const endDate = formatDateParam(customRange.value[1])
  if (!startDate || !endDate) return null
  return { start_date: startDate, end_date: endDate }
}

const fetchTrend = async () => {
  loading.value = true
  try {
    const customDates = rangeMode.value === 'custom' ? getCustomDates() : null
    overview.value = await adminApi.getOverview(
      customDates || {
        days: Number(rangeMode.value)
      }
    )
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载趋势失败')
  } finally {
    loading.value = false
  }
}

const handleRangeModeChange = () => {
  if (rangeMode.value !== 'custom') {
    fetchTrend()
  }
}

onMounted(() => {
  fetchTrend()
  window.addEventListener('admin-refresh', fetchTrend)
})

onBeforeUnmount(() => {
  window.removeEventListener('admin-refresh', fetchTrend)
})
</script>
