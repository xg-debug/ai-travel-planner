<template>
  <view v-if="trip" class="screen route-map-page">
    <view class="map-head panel">
      <text class="map-head__title">{{ trip.destination }} 路线大图</text>
      <text class="map-head__meta">按天查看完整动线，支持全部/单日切换</text>
    </view>

    <view class="day-tabs">
      <button class="day-tabs__item" :class="{ active: selectedDay === -1 }" @tap="selectedDay = -1">全部</button>
      <button
        v-for="segment in daySegments"
        :key="segment.dayIndex"
        class="day-tabs__item"
        :class="{ active: selectedDay === segment.dayIndex }"
        @tap="selectedDay = segment.dayIndex"
      >
        DAY {{ segment.dayIndex + 1 }}
      </button>
    </view>

    <view v-if="hasMapData" class="map-card panel">
      <map
        class="map-canvas"
        :latitude="center.latitude"
        :longitude="center.longitude"
        :scale="12"
        :markers="markers"
        :polyline="polylines"
        :include-points="includePoints"
        show-location
      />
    </view>
    <view v-else class="map-empty panel">
      <text>当前路线缺少坐标数据，暂时无法绘制地图。</text>
    </view>

    <view class="route-list panel">
      <view
        v-for="segment in visibleSegments"
        :key="segment.dayIndex"
        class="route-day"
      >
        <view class="route-day__head">
          <text class="route-day__title">DAY {{ segment.dayIndex + 1 }}</text>
          <text class="route-day__count">{{ segment.points.length }} 个点位</text>
        </view>
        <view class="route-day__line">
          <text
            v-for="(point, index) in segment.points"
            :key="`${segment.dayIndex}-${index}`"
            class="route-day__point"
          >
            {{ index + 1 }}. {{ point.title }}
          </text>
        </view>
      </view>
    </view>
  </view>

  <view v-else class="screen">
    <view class="map-empty panel">
      <text>暂无可展示的行程，请先生成旅行计划。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useTripStore } from '@/stores/tripStore'

type RoutePoint = {
  dayIndex: number
  index: number
  title: string
  latitude: number
  longitude: number
}

const colors = ['#15AAA3', '#F59E0B', '#FF5C66', '#3B82F6', '#8B5CF6']

const tripStore = useTripStore()
const selectedDay = ref(-1)
const trip = computed(() => tripStore.currentTrip)

onShow(() => {
  tripStore.restoreLocal()
})

const daySegments = computed(() => (trip.value?.days || []).map((day, dayIndex) => ({
  dayIndex,
  points: day.activities
    .map((activity, index) => {
      if (!activity.coordinates) return null
      return {
        dayIndex,
        index,
        title: activity.location || activity.title,
        latitude: activity.coordinates.lat,
        longitude: activity.coordinates.lng
      }
    })
    .filter(Boolean) as RoutePoint[]
})).filter((item) => item.points.length >= 2))

const visibleSegments = computed(() => {
  if (selectedDay.value < 0) return daySegments.value
  return daySegments.value.filter((item) => item.dayIndex === selectedDay.value)
})

const hasMapData = computed(() => visibleSegments.value.some((item) => item.points.length >= 2))

const allVisiblePoints = computed(() =>
  visibleSegments.value.flatMap((segment) => segment.points)
)

const center = computed(() => {
  const first = allVisiblePoints.value[0]
  return {
    latitude: first?.latitude || 39.9042,
    longitude: first?.longitude || 116.4074
  }
})

const includePoints = computed(() =>
  allVisiblePoints.value.map((point) => ({
    latitude: point.latitude,
    longitude: point.longitude
  }))
)

const markers = computed(() =>
  visibleSegments.value.flatMap((segment, segmentIndex) =>
    segment.points.map((point, pointIndex) => ({
      id: segment.dayIndex * 100 + pointIndex,
      latitude: point.latitude,
      longitude: point.longitude,
      width: 24,
      height: 24,
      title: point.title,
      callout: {
        content: `D${segment.dayIndex + 1}-${pointIndex + 1} ${point.title}`,
        display: 'BYCLICK',
        borderRadius: 8,
        padding: 6,
        fontSize: 11,
        color: '#111827',
        bgColor: '#FFFFFF'
      },
      label: {
        content: `${pointIndex + 1}`,
        color: '#FFFFFF',
        fontSize: 10,
        borderRadius: 10,
        anchorX: -8,
        anchorY: -26,
        bgColor: colors[segmentIndex % colors.length],
        padding: 4
      }
    }))
  )
)

const polylines = computed(() =>
  visibleSegments.value.map((segment, segmentIndex) => ({
    points: segment.points.map((point) => ({
      latitude: point.latitude,
      longitude: point.longitude
    })),
    color: colors[segmentIndex % colors.length],
    width: 4,
    arrowLine: true,
    borderColor: '#FFFFFF',
    borderWidth: 1
  }))
)
</script>

<style scoped lang="scss">
.route-map-page {
  display: grid;
  align-content: start;
  gap: 20rpx;
}

.map-head {
  display: grid;
  gap: 10rpx;
  padding: 24rpx;
}

.map-head__title {
  color: var(--text-strong);
  font-size: 34rpx;
  font-weight: 900;
}

.map-head__meta {
  color: var(--text-muted);
  font-size: 24rpx;
}

.day-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.day-tabs__item {
  min-width: 108rpx;
  height: 64rpx;
  padding: 0 20rpx;
  border: 1rpx solid var(--line);
  border-radius: 999rpx;
  color: var(--text-main);
  background: #ffffff;
  font-size: 24rpx;
  font-weight: 800;
}

.day-tabs__item.active {
  border-color: #111827;
  color: #ffffff;
  background: #111827;
}

.map-card {
  overflow: hidden;
  padding: 10rpx;
}

.map-canvas {
  width: 100%;
  height: 560rpx;
  border-radius: 18rpx;
}

.map-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180rpx;
  padding: 24rpx;
  text-align: center;
}

.map-empty text {
  color: var(--text-muted);
  font-size: 24rpx;
  line-height: 1.5;
}

.route-list {
  display: grid;
  gap: 14rpx;
  padding: 20rpx;
}

.route-day {
  padding: 20rpx;
  border: 1rpx solid var(--line);
  border-radius: 16rpx;
  background: #ffffff;
}

.route-day__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.route-day__title {
  color: var(--text-strong);
  font-size: 26rpx;
  font-weight: 900;
}

.route-day__count {
  color: var(--text-muted);
  font-size: 22rpx;
}

.route-day__line {
  display: grid;
  gap: 10rpx;
  margin-top: 14rpx;
}

.route-day__point {
  color: var(--text-main);
  font-size: 23rpx;
  line-height: 1.45;
}
</style>
