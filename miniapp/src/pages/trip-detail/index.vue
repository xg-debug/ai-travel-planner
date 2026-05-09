<template>
  <view v-if="trip" class="screen trip-detail">
    <view class="hero">
      <view class="hero__copy">
        <text class="hero__title">{{ trip.destination }} {{ dayCount }}日游</text>
        <text class="hero__subtitle">{{ heroSubtitle }}</text>
      </view>
      <view class="hero__scene">
        <view class="hero__sun" />
        <view class="hero__mountain hero__mountain--back" />
        <view class="hero__mountain" />
        <view class="hero__temple">
          <view class="hero__roof" />
          <view class="hero__body" />
        </view>
      </view>
    </view>

    <view class="summary-card">
      <view class="summary-item">
        <text class="summary-item__icon summary-item__icon--blue">日</text>
        <view>
          <text class="summary-item__value">{{ dayCount }}天{{ nightCount }}晚</text>
          <text class="summary-item__label">行程天数</text>
        </view>
      </view>
      <view class="summary-item">
        <text class="summary-item__icon summary-item__icon--amber">景</text>
        <view>
          <text class="summary-item__value">{{ attractionCount }}+</text>
          <text class="summary-item__label">景点数量</text>
        </view>
      </view>
      <view class="summary-item">
        <text class="summary-item__icon summary-item__icon--teal">行</text>
        <view>
          <text class="summary-item__value">{{ distanceText }}</text>
          <text class="summary-item__label">动线里程</text>
        </view>
      </view>
      <view class="summary-item">
        <text class="summary-item__icon summary-item__icon--red">¥</text>
        <view>
          <text class="summary-item__value">{{ perPersonBudget }}</text>
          <text class="summary-item__label">人均预算</text>
        </view>
      </view>
    </view>

    <SectionPanel v-if="routeDays.length" title="路线地图">
      <template #action>
        <button class="section-link" @tap="openRouteMap">查看大图</button>
      </template>
      <RouteMapPreview :days="routeDays" :title="`${trip.destination}路线总览`" />
    </SectionPanel>

    <SectionPanel v-if="trip.weather.length" title="天气">
      <template #action>
        <button class="section-link" @tap="showWeatherTip">查看未来15天</button>
      </template>
      <WeatherStrip :weather="trip.weather" />
    </SectionPanel>

    <SectionPanel v-if="trip.budget.categories.length" title="预算">
      <template #action>
        <button class="section-link" @tap="showBudgetTip">明细</button>
      </template>
      <BudgetBars :categories="trip.budget.categories" />
    </SectionPanel>

    <SectionPanel v-if="attractionItems.length" title="推荐景点">
      <template #action>
        <button class="section-link" @tap="showListTip('景点')">全部景点</button>
      </template>
      <RecommendationRail :items="attractionItems" variant="attraction" @open="openRecommendation" />
    </SectionPanel>

    <SectionPanel v-if="foodItems.length" title="美食安排">
      <template #action>
        <button class="section-link" @tap="showListTip('美食')">更多美食</button>
      </template>
      <RecommendationRail :items="foodItems" variant="food" @open="openRecommendation" />
    </SectionPanel>

    <SectionPanel v-if="hotelItems.length" title="酒店推荐">
      <template #action>
        <button class="section-link" @tap="showListTip('酒店')">更多酒店</button>
      </template>
      <RecommendationRail :items="hotelItems" variant="hotel" @open="openRecommendation" />
    </SectionPanel>

    <SectionPanel title="每日行程">
      <view class="day-list">
        <TripDayCard
          v-for="(day, index) in trip.days"
          :key="day.date"
          :day="day"
          :index="index"
          @open="openDay(index)"
        />
      </view>
    </SectionPanel>
  </view>

  <view v-else class="screen">
    <EmptyState
      title="还没有行程"
      description="先生成一份旅行计划，就能在这里查看每日安排、预算和天气。"
      action-text="去规划"
      @action="goPlan"
    />
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { storeToRefs } from 'pinia'
import SectionPanel from '@/components/SectionPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import WeatherStrip from '@/components/WeatherStrip.vue'
import BudgetBars from '@/components/BudgetBars.vue'
import TripDayCard from '@/components/TripDayCard.vue'
import RouteMapPreview from '@/components/RouteMapPreview.vue'
import RecommendationRail from '@/components/RecommendationRail.vue'
import { useTripStore } from '@/stores/tripStore'
import { calculateDays, formatMoney } from '@/utils/format'
import { tripAttractions, tripFood, tripHotels, tripMapActivities } from '@/utils/tripDisplay'
import type { Activity, POI } from '@/types/trip'

const tripStore = useTripStore()
const { currentTrip: trip } = storeToRefs(tripStore)

const activityCount = computed(() =>
  trip.value?.days.reduce((sum, day) => sum + day.activities.length, 0) || 0
)
const dayCount = computed(() => {
  if (!trip.value) return 0
  return trip.value.days.length || calculateDays(trip.value.startDate, trip.value.endDate)
})
const nightCount = computed(() => Math.max(dayCount.value - 1, 0))
const attractionItems = computed(() => tripAttractions(trip.value))
const foodItems = computed(() => tripFood(trip.value))
const hotelItems = computed(() => tripHotels(trip.value))
const routeActivities = computed(() => tripMapActivities(trip.value))
const routeDays = computed(() => trip.value?.days || [])
const attractionCount = computed(() => Math.max(attractionItems.value.length, activityCount.value))
const heroSubtitle = computed(() => {
  const tags = trip.value?.interests?.filter(Boolean).slice(0, 3)
  return tags?.length ? tags.join(' · ') : '历史文化 · 在地美食 · 轻松动线'
})
const distanceText = computed(() => `${estimateDistanceKm(routeActivities.value).toFixed(1)}km`)
const perPersonBudget = computed(() => {
  const total = Number(trip.value?.budget.total || 0)
  const travelers = Math.max(Number(trip.value?.travelers || 1), 1)
  return total ? `${formatMoney(total / travelers)}/人` : '待估算'
})

onShow(() => {
  tripStore.restoreLocal()
})

const openDay = (index: number) => {
  uni.navigateTo({ url: `/pages/day-detail/index?day=${index}` })
}

const goPlan = () => {
  uni.switchTab({ url: '/pages/plan/index' })
}

const openRouteMap = () => {
  const hasDayRoute = (trip.value?.days || []).some((day) =>
    day.activities.filter((item) => item.coordinates).length >= 2
  )
  if (!hasDayRoute) {
    uni.showToast({ title: '路线坐标生成后可打开地图', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/route-map/index' })
}

const openRecommendation = (item: POI) => {
  const match = findActivityByPoi(item)
  if (!match) {
    uni.showToast({ title: `${item.name} 已加入推荐清单`, icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/place-detail/index?day=${match.dayIndex}&activity=${match.activityIndex}` })
}

const showWeatherTip = () => {
  uni.showToast({ title: '当前展示后端返回的可用天气', icon: 'none' })
}

const showBudgetTip = () => {
  uni.showToast({ title: '预算已按交通、住宿、门票等拆分', icon: 'none' })
}

const showListTip = (name: string) => {
  uni.showToast({ title: `${name}清单已展示重点推荐`, icon: 'none' })
}

const findActivityByPoi = (poi: POI) => {
  const keyword = poi.name.trim().toLowerCase()
  for (const [dayIndex, day] of (trip.value?.days || []).entries()) {
    const activityIndex = day.activities.findIndex((activity) => {
      const text = `${activity.location} ${activity.title}`.toLowerCase()
      return text.includes(keyword) || keyword.includes(activity.location.toLowerCase())
    })
    if (activityIndex >= 0) return { dayIndex, activityIndex }
  }
  return null
}

const estimateDistanceKm = (items: Activity[]) => {
  const points = items.map((item) => item.coordinates).filter(Boolean) as Array<{ lat: number; lng: number }>
  if (points.length >= 2) {
    return points.slice(1).reduce((sum, point, index) => sum + distanceBetween(points[index], point), 0)
  }
  return Math.max(3.6, items.length * 3.2)
}

const distanceBetween = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => {
  const toRad = (value: number) => (value * Math.PI) / 180
  const earth = 6371
  const dLat = toRad(b.lat - a.lat)
  const dLng = toRad(b.lng - a.lng)
  const lat1 = toRad(a.lat)
  const lat2 = toRad(b.lat)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * earth * Math.asin(Math.sqrt(h))
}
</script>

<style scoped lang="scss">
.trip-detail {
  display: grid;
  gap: 22rpx;
  background: var(--app-bg);
}

.hero {
  padding: 28rpx 4rpx 8rpx;
}

.hero__title,
.hero__subtitle {
  display: block;
}

.hero__title {
  color: var(--text-strong);
  font-size: 48rpx;
  font-weight: 900;
  line-height: 1.15;
}

.hero__subtitle {
  display: inline-block;
  margin-top: 14rpx;
  padding: 8rpx 16rpx;
  border: 1rpx solid var(--line);
  border-radius: 14rpx;
  color: var(--text-main);
  background: #ffffff;
  font-size: 25rpx;
}

.hero__scene {
  display: none;
}

.summary-card {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14rpx;
  border-radius: 22rpx;
  background: transparent;
  box-shadow: var(--shadow-soft);
}

.summary-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  min-width: 0;
  min-height: 108rpx;
  box-sizing: border-box;
  padding: 18rpx;
  border: 1rpx solid var(--line);
  border-radius: 18rpx;
  background: #ffffff;
}

.summary-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 42rpx;
  width: 42rpx;
  height: 42rpx;
  border-radius: 13rpx;
  color: #ffffff;
  font-size: 21rpx;
  font-weight: 850;
}

.summary-item__icon--blue { background: #2681f4; }
.summary-item__icon--amber { background: #ff9600; }
.summary-item__icon--teal { background: #15aba4; }
.summary-item__icon--red { background: #ef4444; border-radius: 50%; }

.summary-item__value,
.summary-item__label {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-item__value {
  color: var(--text-strong);
  font-size: 26rpx;
  font-weight: 850;
}

.summary-item__label {
  margin-top: 5rpx;
  color: var(--text-muted);
  font-size: 20rpx;
}

.section-link {
  padding: 0;
  color: var(--text-muted);
  background: transparent;
  font-size: 24rpx;
  line-height: 1.4;
}

.day-list {
  display: grid;
  gap: 14rpx;
}

</style>
