<template>
  <view v-if="trip" :class="['screen trip-detail', themeStore.themeClass]">
    <view class="hero">
      <view class="hero__copy">
        <text class="hero__title">{{ trip.destination }} {{ dayCount }}日游</text>
        <view class="hero__tags">
          <view v-for="tag in heroInterestTags" :key="tag.id" class="hero__tag">
            <text class="hero__tag-icon">{{ tag.icon }}</text>
            <text class="hero__tag-label">{{ tag.label }}</text>
          </view>
        </view>
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
          <text class="summary-item__value">{{ attractionCount }} 个</text>
          <text class="summary-item__label">景点与体验</text>
        </view>
      </view>
      <view class="summary-item">
        <text class="summary-item__icon summary-item__icon--teal">行</text>
        <view>
          <text class="summary-item__value">{{ distanceText }}</text>
          <text class="summary-item__label">市内动线</text>
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

    <SectionPanel v-if="intercityTransport" title="往返交通">
      <view class="transport-list">
        <view
          v-for="leg in intercityLegs"
          :key="leg.direction"
          class="transport-leg"
        >
          <view class="transport-leg__main">
            <text class="transport-leg__route">{{ transportLegTitle(leg) }}</text>
            <text class="transport-leg__time">{{ transportTimeText(leg) }}</text>
          </view>
          <view class="transport-leg__meta">
            <text>{{ formatTransportMoney(transportCostPerPerson(leg), leg.costPending) }}/人</text>
          </view>
        </view>
        <view class="transport-total">
          <text>往返交通合计</text>
          <text>{{ formatTransportMoney(intercityTransport.totalCost, intercityTransport.costPending) }}</text>
        </view>
      </view>
    </SectionPanel>

    <SectionPanel v-if="routeDays.length" title="路线地图">
      <template #action>
        <button class="section-link" @tap="openRouteMap">查看大图</button>
      </template>
      <RouteMapPreview :days="routeDays" :title="`${trip.destination}路线总览`" />
    </SectionPanel>

    <SectionPanel v-if="trip.weather.length" title="天气">
      <WeatherStrip :weather="trip.weather" />
    </SectionPanel>

    <SectionPanel v-if="trip.budget.categories.length" title="预算">
      <BudgetBars :categories="trip.budget.categories" />
    </SectionPanel>

    <SectionPanel v-if="attractionItems.length" title="推荐景点">
      <RecommendationRail :items="attractionItems" variant="attraction" @open="openRecommendation" />
    </SectionPanel>

    <SectionPanel v-if="foodItems.length" title="美食推荐">
      <RecommendationRail :items="foodItems" variant="food" @open="openRecommendation" />
    </SectionPanel>

    <SectionPanel v-if="currentHotel" title="酒店推荐">
      <template #action>
        <button v-if="hotelItems.length > 1" class="section-link" @tap="changeHotel">换一家</button>
      </template>
      <button class="hotel-choice" @tap="openRecommendation(currentHotel)">
        <view class="hotel-choice__visual">
          <image :src="currentHotelCover" mode="aspectFill" @error="hotelCoverFailed = true" />
        </view>
        <view class="hotel-choice__main">
          <text class="hotel-choice__label">{{ accommodationReason }}</text>
          <text class="hotel-choice__name">{{ currentHotel.name }}</text>
          <text v-if="currentHotel.address" class="hotel-choice__address">{{ currentHotel.address }}</text>
          <text v-if="currentHotel.referencePriceRange" class="hotel-choice__reference">{{ currentHotel.referencePriceRange }}</text>
          <text class="hotel-choice__reason">{{ hotelTouristSummary(currentHotel) }}</text>
        </view>
        <view class="hotel-choice__meta">
          <text v-if="currentHotel.rating">{{ currentHotel.rating.toFixed(1) }}分</text>
          <text>{{ hotelLivePriceLabel(currentHotel) }}</text>
        </view>
      </button>
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

  <view v-else :class="['screen', themeStore.themeClass]">
    <EmptyState
      title="还没有行程"
      description="先生成一份旅行计划，就能在这里查看每日安排、预算和天气。"
      action-text="去规划"
      @action="goPlan"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
import { useThemeStore } from '@/stores/themeStore'
import { calculateDays, formatMoney } from '@/utils/format'
import { dayRouteStops, tripAttractions, tripFood, tripHotels, tripMapActivities } from '@/utils/tripDisplay'
import type { Activity, IntercityTransportLeg, POI } from '@/types/trip'

const tripStore = useTripStore()
const themeStore = useThemeStore()
const { currentTrip: trip } = storeToRefs(tripStore)
const hotelCoverFailed = ref(false)

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
const currentHotel = computed(() => hotelItems.value[0])
const currentHotelCover = computed(() => {
  const image = normalizeCoverUrl(currentHotel.value?.images?.[0])
  if (image && !hotelCoverFailed.value) return image
  return '/static/recommendations/hotel-1.png'
})
const routeActivities = computed(() => tripMapActivities(trip.value))
const routeDays = computed(() => trip.value?.days || [])
const intercityTransport = computed(() => trip.value?.intercityTransport)
const intercityLegs = computed<IntercityTransportLeg[]>(() => {
  const transport = intercityTransport.value
  return [transport?.outbound, transport?.inbound].filter(Boolean) as IntercityTransportLeg[]
})
const attractionCount = computed(() => attractionItems.value.length || activityCount.value)
const interestTagOptions = [
  { id: 'classic', icon: '📍', label: '经典必玩' },
  { id: 'food', icon: '🍽️', label: '吃吃喝喝' },
  { id: 'local', icon: '🕵️', label: '小众探索' },
  { id: 'photo', icon: '📸', label: '拍照出片' },
  { id: 'shopping', icon: '🛍️', label: '逛街购物' },
  { id: 'citywalk', icon: '🚶', label: '城市漫步' },
  { id: 'nature', icon: '🏞️', label: '自然风光' },
  { id: 'art', icon: '🎨', label: '文艺展览' },
  { id: 'history', icon: '🏛️', label: '历史古建' }
]
const fallbackInterestTags = [
  { id: 'history', icon: '🏛️', label: '历史古建' },
  { id: 'food', icon: '🍽️', label: '吃吃喝喝' },
  { id: 'local', icon: '🕵️', label: '小众探索' }
]
const heroInterestTags = computed(() => {
  const tags = (trip.value?.interests || [])
    .map((id) => interestTagOptions.find((item) => item.id === id) || {
      id,
      icon: '✨',
      label: String(id || '').trim()
    })
    .filter((item) => item.label)
    .slice(0, 3)
  return tags.length ? tags : fallbackInterestTags
})
const distanceText = computed(() => `${estimateDistanceKm(routeActivities.value).toFixed(1)}km`)
const perPersonBudget = computed(() => {
  const total = Number(trip.value?.budget.total || 0)
  const travelers = Math.max(Number(trip.value?.travelers || 1), 1)
  return total ? `${formatMoney(total / travelers)}/人` : '待估算'
})
const accommodationPreference = computed(() =>
  trip.value?.accommodationPreference || tripStore.draft?.accommodationPreference || 'mid-range'
)
const accommodationLabel = computed(() => {
  const labels = {
    budget: '经济',
    'mid-range': '中档',
    luxury: '高档'
  } as const
  return labels[accommodationPreference.value]
})
const accommodationReason = computed(() => {
  const label = accommodationLabel.value
  const suffix = {
    budget: '控制预算，优先交通方便',
    'mid-range': '兼顾位置、舒适度和价格',
    luxury: '优先品质、景观和服务'
  } as const
  return `${label}住宿 · ${suffix[accommodationPreference.value]}`
})

const formatTransportMoney = (value?: number | string, pending?: boolean) =>
  pending ? '待估算' : formatMoney(value)
const transportBestOption = (leg: IntercityTransportLeg) => leg.bestOption || leg.options?.[0]
const transportLegTitle = (leg: IntercityTransportLeg) => {
  const option = transportBestOption(leg)
  const mode = option?.mode || leg.mode || '交通待确认'
  return `${transportDirectionLabel(leg.direction)}：${leg.from} → ${leg.to}   ${mode}`
}
const transportTimeText = (leg: IntercityTransportLeg) => {
  const option = transportBestOption(leg)
  const departure = option?.departureDatetime || leg.departureDatetime
  const arrival = option?.arrivalDatetime || leg.arrivalDatetime
  if (departure && arrival) {
    return `${departure} - ${arrival}`
  }
  return option?.durationText || leg.durationText || `${option?.durationMinutes || leg.durationMinutes}分钟`
}
const transportCostPerPerson = (leg: IntercityTransportLeg) =>
  transportBestOption(leg)?.costPerPerson || leg.costPerPerson

onShow(() => {
  tripStore.restoreLocal()
  themeStore.restore()
})

const openDay = (index: number) => {
  uni.navigateTo({ url: `/pages/day-detail/index?day=${index}` })
}

const goPlan = () => {
  uni.switchTab({ url: '/pages/plan/index' })
}

const openRouteMap = () => {
  const hasDayRoute = (trip.value?.days || []).some((day) =>
    dayRouteStops(day).filter((item) => item.coordinates).length >= 2
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
    uni.navigateTo({ url: `/pages/place-detail/index?poi=${encodeURIComponent(item.id || item.name)}` })
    return
  }
  uni.navigateTo({ url: `/pages/place-detail/index?day=${match.dayIndex}&activity=${match.activityIndex}` })
}

const changeHotel = () => {
  const nextHotel = hotelItems.value[1]
  if (!nextHotel) {
    uni.showToast({ title: '暂无更多酒店可替换', icon: 'none' })
    return
  }
  tripStore.setTripHotel(nextHotel)
  uni.showToast({ title: `已换成${nextHotel.name}`, icon: 'none' })
}

watch(() => currentHotel.value?.id || currentHotel.value?.name, () => {
  hotelCoverFailed.value = false
})

const showWeatherTip = () => {
  uni.showToast({ title: '当前展示后端返回的可用天气', icon: 'none' })
}

const showBudgetTip = () => {
  uni.showToast({ title: '预算已按交通、住宿、门票等拆分', icon: 'none' })
}

const showListTip = (name: string) => {
  uni.showToast({ title: `${name}清单已展示重点推荐`, icon: 'none' })
}

const transportDirectionLabel = (direction: string) => direction === 'inbound' ? '返程' : '去程'

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

const hotelPriceLabel = (hotel: POI) => {
  if (hotel.priceRange === 'free') return '待查询'
  const map: Record<string, string> = {
    '$': '经济',
    '$$': '中档',
    '$$$': '舒适',
    '$$$$': '高端'
  }
  return map[hotel.priceRange] || '待查询'
}

const hotelLivePriceLabel = (hotel: POI) => {
  if (hotel.type === 'hotel' && (hotel.priceText || '').includes('实时')) return '实时价待查'
  return hotel.priceText || hotelPriceLabel(hotel)
}

const hotelTouristSummary = (hotel: POI) => {
  const area = compactHotelArea(hotel.address)
  const raw = String(hotel.description || '').replace(/匹配[^，。；]*[，。；:]?/g, '').trim()
  const sentences = raw.split(/[。；]/).map((item) => item.trim()).filter(Boolean)
  const useful = sentences.find((item) => /步行|地铁|湖滨|西湖|商圈|景区|交通|安静|亲子|拍照|夜游|餐饮/.test(item))
  if (useful && useful.length <= 54) return useful
  const label = accommodationLabel.value
  if (area) return `住在${area}，方便衔接当天景点和晚间用餐，适合${label}预算游客。`
  return `位置便于串联主要景点，适合${label}预算游客，价格以预订平台实时价为准。`
}

const compactHotelArea = (value?: string) => {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.replace(/浙江省|杭州市|中国|附近|周边/g, '').split(/[，,]/)[0].slice(0, 14)
}

const normalizeCoverUrl = (url?: string) => {
  const text = String(url || '').trim()
  if (!text) return ''
  if (text.startsWith('//')) return `https:${text}`
  return text
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

.hero__title {
  display: block;
}

.hero__title {
  color: var(--text-strong);
  font-size: 48rpx;
  font-weight: 900;
  line-height: 1.15;
}

.hero__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 14rpx;
}

.hero__tag {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  max-width: 210rpx;
  min-height: 46rpx;
  box-sizing: border-box;
  padding: 0 14rpx;
  border: 1rpx solid var(--line);
  border-radius: 999rpx;
  color: var(--text-main);
  background: var(--surface);
  box-shadow: 0 4rpx 12rpx rgba(17, 24, 39, 0.04);
}

.hero__tag-icon {
  flex: 0 0 auto;
  font-size: 20rpx;
  line-height: 1;
}

.hero__tag-label {
  min-width: 0;
  overflow: hidden;
  color: inherit;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  background: var(--surface);
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

.transport-list {
  display: grid;
  gap: 14rpx;
}

.transport-leg,
.transport-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  min-width: 0;
  padding: 20rpx;
  border: 1rpx solid var(--line);
  border-radius: 18rpx;
  background: var(--surface);
}

.transport-leg__main,
.transport-leg__meta {
  display: grid;
  min-width: 0;
}

.transport-leg__label {
  color: var(--text-muted);
  font-size: 21rpx;
  font-weight: 800;
}

.transport-leg__route {
  overflow: hidden;
  color: var(--text-strong);
  font-size: 28rpx;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.transport-leg__time {
  margin-top: 8rpx;
  color: var(--text-main);
  font-size: 22rpx;
  font-weight: 650;
}

.transport-leg__meta {
  flex: 0 0 auto;
  justify-items: end;
  gap: 5rpx;
  color: var(--text-main);
  font-size: 22rpx;
  font-weight: 750;
}

.transport-total {
  color: var(--text-strong);
  background: var(--surface-soft);
  font-size: 26rpx;
  font-weight: 900;
}

.hotel-choice {
  display: flex;
  width: 100%;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18rpx;
  padding: 18rpx;
  border: 1rpx solid var(--line);
  border-radius: 18rpx;
  background: var(--surface);
  text-align: left;
}

.hotel-choice::after {
  border: 0;
}

.hotel-choice__main {
  display: grid;
  flex: 1;
  min-width: 0;
  gap: 8rpx;
}

.hotel-choice__visual {
  flex: 0 0 136rpx;
  width: 136rpx;
  height: 136rpx;
  overflow: hidden;
  border-radius: 14rpx;
  background: #f0effa;
}

.hotel-choice__visual image {
  width: 100%;
  height: 100%;
}

.hotel-choice__label {
  color: var(--teal);
  font-size: 22rpx;
  font-weight: 850;
  line-height: 1.35;
}

.hotel-choice__name {
  overflow: hidden;
  color: var(--text-strong);
  font-size: 30rpx;
  font-weight: 900;
  line-height: 1.28;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotel-choice__address,
.hotel-choice__reference,
.hotel-choice__reason {
  display: block;
  color: var(--text-main);
  font-size: 23rpx;
  line-height: 1.45;
}

.hotel-choice__address {
  overflow: hidden;
  color: var(--text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotel-choice__reference {
  color: var(--teal);
  font-weight: 800;
}

.hotel-choice__reason {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.hotel-choice__meta {
  display: grid;
  flex: 0 0 auto;
  justify-items: end;
  gap: 8rpx;
  color: var(--text-main);
  font-size: 22rpx;
  font-weight: 800;
}

.day-list {
  display: grid;
  gap: 14rpx;
}

</style>
