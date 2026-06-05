<template>
  <view v-if="trip" :class="['route-map-page', themeStore.themeClass]">
    <map
      v-if="hasMapData"
      class="route-map"
      :latitude="center.latitude"
      :longitude="center.longitude"
      :scale="mapScale"
      :markers="markers"
      :polyline="polylines"
      :include-points="includePoints"
      enable-zoom
      enable-scroll
      @markertap="handleMarkerTap"
    >
      <cover-view class="map-tabs">
        <cover-view class="map-tab" :class="{ active: selectedDay === -1 }" @tap="selectDay(-1)">全程</cover-view>
        <cover-view
          v-for="segment in daySegments"
          :key="segment.dayIndex"
          class="map-tab"
          :class="{ active: selectedDay === segment.dayIndex }"
          @tap="selectDay(segment.dayIndex)"
        >
          DAY {{ segment.dayIndex + 1 }}
        </cover-view>
        <cover-view v-if="showPendingTab" class="map-tab map-tab--muted" @tap="showTodoTip">待计划</cover-view>
      </cover-view>

      <cover-view class="map-locate" @tap="focusCurrentRoute">⌖</cover-view>

      <cover-view v-if="selectedDay >= 0 && currentPoint" class="place-card">
        <cover-view class="place-card__photo">
          <cover-image v-if="currentPoint.image" class="place-card__image" :src="currentPoint.image" />
          <cover-view v-else class="place-card__photo-fallback">DAY {{ currentPoint.dayIndex + 1 }}</cover-view>
        </cover-view>
        <cover-view class="place-card__body">
          <cover-view class="place-card__title">{{ currentPoint.title }}</cover-view>
          <cover-view class="place-card__meta">{{ currentCardMeta }}</cover-view>
          <cover-view class="place-card__actions">
            <cover-view class="place-card__action" @tap="showPoiTip">+</cover-view>
            <cover-view class="place-card__action" @tap="showPoiTip">↗</cover-view>
          </cover-view>
        </cover-view>
      </cover-view>

      <cover-view v-if="selectedDay >= 0 && currentSegment" class="step-rail">
        <cover-view
          v-for="(point, index) in currentSegment.points"
          :key="point.key"
          class="step-dot"
          :class="{ active: point.key === currentPoint?.key }"
          @tap="selectPoint(point.key)"
        >
          {{ index + 1 }}
        </cover-view>
      </cover-view>
    </map>

    <view v-else class="map-empty">
      <text>当前路线缺少坐标数据，暂时无法绘制地图。</text>
    </view>
  </view>

  <view v-else :class="['route-map-page route-map-page--empty', themeStore.themeClass]">
    <view class="map-empty">
      <text>暂无可展示的行程，请先生成旅行计划。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useTripStore } from '@/stores/tripStore'
import { useThemeStore } from '@/stores/themeStore'
import { tripApi } from '@/services/tripApi'
import { dayRouteStops } from '@/utils/tripDisplay'

type RoutePoint = {
  key: string
  markerId: number
  dayIndex: number
  index: number
  title: string
  latitude: number
  longitude: number
  image?: string
}

type RouteSegment = {
  dayIndex: number
  points: RoutePoint[]
}

type MapRoutePlan = {
  dayIndex: number
  distance: number
  duration: number
  polyline: Array<{ latitude: number; longitude: number }>
  legs?: Array<Record<string, unknown>>
  provider?: string
}

const routeColors = ['#32B7D9', '#21BFA4', '#FF6A7A', '#F59E0B', '#8B5CF6', '#0F172A']

const tripStore = useTripStore()
const themeStore = useThemeStore()
const selectedDay = ref(-1)
const selectedPointKey = ref('')
const routePlans = ref<Record<number, MapRoutePlan>>({})
const trip = computed(() => tripStore.currentTrip)

onShow(() => {
  themeStore.restore()
  tripStore.restoreLocal()
  selectedDay.value = -1
  selectedPointKey.value = ''
  loadMapRoutes()
})

const daySegments = computed<RouteSegment[]>(() => (trip.value?.days || []).map((day, dayIndex) => ({
  dayIndex,
  points: dayRouteStops(day)
    .map((activity, index) => {
      if (!activity.coordinates) return null
      return {
        key: `${dayIndex}-${index}`,
        markerId: dayIndex * 1000 + index,
        dayIndex,
        index,
        title: activity.location || activity.title,
        latitude: activity.coordinates.lat,
        longitude: activity.coordinates.lng,
        image: activity.image
      }
    })
    .filter(Boolean) as RoutePoint[]
})).filter((item) => item.points.length >= 2))

const visibleSegments = computed(() => {
  if (selectedDay.value < 0) return daySegments.value
  return daySegments.value.filter((item) => item.dayIndex === selectedDay.value)
})

const hasMapData = computed(() => visibleSegments.value.some((item) => item.points.length >= 2))
const showPendingTab = computed(() => daySegments.value.length <= 3)

const allVisiblePoints = computed(() => visibleSegments.value.flatMap((segment) => segment.points))

const center = computed(() => {
  const first = allVisiblePoints.value[0]
  return {
    latitude: first?.latitude || 39.9042,
    longitude: first?.longitude || 116.4074
  }
})

const mapScale = computed(() => (selectedDay.value >= 0 ? 13 : 12))

const routePointsFor = (segment: RouteSegment) => {
  const planned = routePlans.value[segment.dayIndex]?.polyline || []
  if (planned.length >= 2) return planned
  return segment.points.map((point) => ({
    latitude: point.latitude,
    longitude: point.longitude
  }))
}

const includePoints = computed(() =>
  visibleSegments.value.flatMap((segment) => [
    ...segment.points.map((point) => ({
      latitude: point.latitude,
      longitude: point.longitude
    })),
    ...routePointsFor(segment)
  ])
)

const markerPointMap = computed(() => {
  const items = new Map<number, RoutePoint>()
  daySegments.value.forEach((segment) => {
    segment.points.forEach((point) => {
      items.set(point.markerId, point)
    })
  })
  return items
})

const markers = computed(() => {
  if (selectedDay.value < 0) {
    return visibleSegments.value.map((segment) => {
      const middlePoint = segment.points[Math.floor(segment.points.length / 2)] || segment.points[0]
      const color = routeColors[segment.dayIndex % routeColors.length]
      return {
        id: middlePoint.markerId,
        latitude: middlePoint.latitude,
        longitude: middlePoint.longitude,
        width: 1,
        height: 1,
        label: {
          content: `DAY ${segment.dayIndex + 1}`,
          color: '#FFFFFF',
          fontSize: 15,
          borderRadius: 10,
          bgColor: color,
          padding: 10,
          anchorX: -34,
          anchorY: -18
        }
      }
    })
  }

  return visibleSegments.value.flatMap((segment) =>
    segment.points.map((point) => {
      const color = routeColors[segment.dayIndex % routeColors.length]
      return {
        id: point.markerId,
        latitude: point.latitude,
        longitude: point.longitude,
        width: 28,
        height: 28,
        title: point.title,
        label: {
          content: `${point.index + 1}`,
          color: '#FFFFFF',
          fontSize: 13,
          borderRadius: 16,
          bgColor: color,
          padding: 6,
          anchorX: -10,
          anchorY: -28
        },
        callout: {
          content: point.title,
          display: 'BYCLICK',
          borderRadius: 8,
          padding: 8,
          fontSize: 12,
          color: '#0F172A',
          bgColor: '#FFFFFF'
        }
      }
    })
  )
})

const polylines = computed(() =>
  visibleSegments.value.map((segment) => ({
    points: routePointsFor(segment),
    color: routeColors[segment.dayIndex % routeColors.length],
    width: selectedDay.value >= 0 ? 8 : 7,
    arrowLine: true,
    borderColor: '#FFFFFF',
    borderWidth: 2
  }))
)

const currentSegment = computed(() => {
  if (selectedDay.value < 0) return null
  return daySegments.value.find((segment) => segment.dayIndex === selectedDay.value) || null
})

const currentPoint = computed(() => {
  const segment = currentSegment.value
  if (!segment) return null
  return segment.points.find((point) => point.key === selectedPointKey.value) || segment.points[0] || null
})

const currentCardMeta = computed(() => {
  const point = currentPoint.value
  if (!point) return ''
  const plan = routePlans.value[point.dayIndex]
  const distance = formatDistance(plan?.distance || 0)
  const duration = formatDuration(plan?.duration || 0)
  const routeText = distance ? ` · ${distance}${duration ? ` ${duration}` : ''}` : ''
  return `DAY ${point.dayIndex + 1} · 第 ${point.index + 1} 站${routeText}`
})

const selectDay = (dayIndex: number) => {
  selectedDay.value = dayIndex
  const segment = daySegments.value.find((item) => item.dayIndex === dayIndex)
  selectedPointKey.value = segment?.points[0]?.key || ''
}

const selectPoint = (key: string) => {
  selectedPointKey.value = key
}

const handleMarkerTap = (event: any) => {
  const markerId = Number(event?.detail?.markerId ?? event?.markerId)
  const point = markerPointMap.value.get(markerId)
  if (!point) return
  selectedDay.value = point.dayIndex
  selectedPointKey.value = point.key
}

const focusCurrentRoute = () => {
  uni.showToast({ title: '已聚焦当前路线', icon: 'none' })
}

const showTodoTip = () => {
  uni.showToast({ title: '待计划点位后续可加入路线', icon: 'none' })
}

const showPoiTip = () => {
  uni.showToast({ title: '地点操作即将开放', icon: 'none' })
}

const loadMapRoutes = async () => {
  const segments = daySegments.value.map((segment) => ({
    dayIndex: segment.dayIndex,
    points: segment.points.map((point) => ({
      latitude: point.latitude,
      longitude: point.longitude,
      title: point.title
    }))
  }))
  routePlans.value = {}
  if (!segments.length) return

  try {
    const response = await tripApi.planMapRoutes({ mode: 'driving', segments })
    const nextPlans: Record<number, MapRoutePlan> = {}
    ;(response?.segments || []).forEach((segment: MapRoutePlan) => {
      nextPlans[segment.dayIndex] = segment
    })
    routePlans.value = nextPlans
  } catch (error) {
    console.warn('Map route planning failed, fallback to point polyline:', error)
    routePlans.value = {}
  }
}

const formatDistance = (meters: number) => {
  if (!meters) return ''
  if (meters < 1000) return `${Math.round(meters)}米`
  return `${(meters / 1000).toFixed(1)}公里`
}

const formatDuration = (seconds: number) => {
  if (!seconds) return ''
  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes}分钟`
  const hours = Math.floor(minutes / 60)
  const restMinutes = minutes % 60
  return restMinutes ? `${hours}小时${restMinutes}分钟` : `${hours}小时`
}
</script>

<style scoped lang="scss">
.route-map-page {
  width: 100vw;
  min-height: 100vh;
  overflow: hidden;
  background: #eef2f6;
}

.route-map {
  width: 100vw;
  height: 100vh;
}

.map-tabs {
  position: absolute;
  top: 28rpx;
  left: 18rpx;
  right: 18rpx;
  display: flex;
  align-items: center;
  gap: 12rpx;
  white-space: nowrap;
}

.map-tab {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 122rpx;
  min-width: 122rpx;
  height: 74rpx;
  padding: 0;
  box-sizing: border-box;
  border-radius: 40rpx;
  background: rgba(255, 255, 255, 0.94);
  color: #0f172a;
  font-size: 28rpx;
  font-weight: 900;
  line-height: 74rpx;
}

.map-tab.active {
  background: #000000;
  color: #ffffff;
}

.map-tab--muted {
  width: 142rpx;
  min-width: 142rpx;
}

.map-locate {
  position: absolute;
  right: 32rpx;
  bottom: 254rpx;
  width: 78rpx;
  height: 78rpx;
  border-radius: 39rpx;
  background: rgba(255, 255, 255, 0.96);
  color: #0f172a;
  font-size: 40rpx;
  font-weight: 900;
  line-height: 78rpx;
  text-align: center;
}

.place-card {
  position: absolute;
  left: 34rpx;
  right: 34rpx;
  bottom: 142rpx;
  display: flex;
  min-height: 184rpx;
  overflow: hidden;
  border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.97);
}

.place-card__photo {
  width: 210rpx;
  min-height: 184rpx;
  overflow: hidden;
  background: #dbeafe;
}

.place-card__image {
  width: 210rpx;
  height: 184rpx;
}

.place-card__photo-fallback {
  width: 210rpx;
  height: 184rpx;
  background: #32b7d9;
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 900;
  line-height: 184rpx;
  text-align: center;
}

.place-card__body {
  flex: 1;
  min-width: 0;
  padding: 28rpx 26rpx;
}

.place-card__title {
  max-width: 410rpx;
  overflow: hidden;
  color: #000000;
  font-size: 36rpx;
  font-weight: 900;
  line-height: 46rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.place-card__meta {
  margin-top: 10rpx;
  color: #8a94a6;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 30rpx;
}

.place-card__actions {
  display: flex;
  gap: 18rpx;
  margin-top: 22rpx;
}

.place-card__action {
  width: 58rpx;
  height: 58rpx;
  border-radius: 29rpx;
  background: #f1f5f9;
  color: #000000;
  font-size: 34rpx;
  font-weight: 900;
  line-height: 58rpx;
  text-align: center;
}

.step-rail {
  position: absolute;
  left: 34rpx;
  right: 34rpx;
  bottom: 34rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 76rpx;
  padding: 0 18rpx;
  border-radius: 38rpx;
  background: rgba(255, 255, 255, 0.9);
}

.step-dot {
  width: 58rpx;
  height: 58rpx;
  border-radius: 29rpx;
  background: rgba(241, 245, 249, 0.95);
  color: #0f172a;
  font-size: 26rpx;
  font-weight: 900;
  line-height: 58rpx;
  text-align: center;
}

.step-dot.active {
  background: #000000;
  color: #ffffff;
}

.map-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  min-height: 100vh;
  padding: 48rpx;
  box-sizing: border-box;
  text-align: center;
}

.map-empty text {
  color: #64748b;
  font-size: 28rpx;
  line-height: 1.5;
}
</style>
