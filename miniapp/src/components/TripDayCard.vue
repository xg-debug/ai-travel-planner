<template>
  <button class="day-card" @tap="$emit('open')">
    <view class="day-card__head">
      <view class="day-card__badge" :class="`day-card__badge--${index % 3}`">
        <text>DAY {{ index + 1 }}</text>
      </view>
      <view class="day-card__title-wrap">
        <text class="day-card__title">{{ routeTitle }}</text>
        <text class="day-card__meta">{{ formatDate(day.date) }} · {{ routeStopCount }} 个路线点 · {{ formatMoney(day.totalCost || dayCost) }}</text>
      </view>
      <text class="day-card__arrow">›</text>
    </view>

    <view class="day-card__stops">
      <view v-for="activity in previewStops" :key="activity.id" class="day-card__stop">
        <text class="day-card__time">{{ activity.time }}</text>
        <view class="day-card__dot" :class="`day-card__dot--${index % 3}`" />
        <view class="day-card__stop-copy">
          <text class="day-card__spot">{{ displayStopName(activity) }}</text>
          <text class="day-card__duration">{{ durationText(activity.duration) }}</text>
        </view>
      </view>
    </view>

    <view v-if="day.hotel && !previewIncludesHotel" class="day-card__hotel">
      <view class="day-card__hotel-icon">🏨</view>
      <view class="day-card__hotel-copy">
        <text class="day-card__hotel-name">{{ day.hotel.name }}</text>
        <text v-if="hotelAddressText" class="day-card__hotel-addr">{{ hotelAddressText }}</text>
      </view>
    </view>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TripDay } from '@/types/trip'
import { formatDate, formatMoney } from '@/utils/format'
import { dayRouteStops, dayRouteTitle, displayStopName } from '@/utils/tripDisplay'

const props = defineProps<{
  day: TripDay
  index: number
}>()

defineEmits<{
  open: []
}>()

const routeStops = computed(() => dayRouteStops(props.day))
const previewStops = computed(() => routeStops.value.slice(0, 5))
const routeStopCount = computed(() => routeStops.value.length)
const previewIncludesHotel = computed(() => previewStops.value.some((item) => item.id.startsWith('hotel_')))
const dayCost = computed(() => props.day.activities.reduce((sum, item) => sum + Number(item.cost || 0), 0))
const routeTitle = computed(() => dayRouteTitle(props.day).replace(/→/g, ' · '))
const hotelAddressText = computed(() => {
  const address = String(props.day.hotel?.address || '').trim()
  const name = String(props.day.hotel?.name || '').trim()
  if (!address || address === name || address.includes(name)) return ''
  return address
})

const durationText = (minutes: number) => {
  if (minutes === 0) return '住宿点'
  if (!minutes) return '时间待定'
  if (minutes < 60) return `${minutes}分钟`
  const hours = minutes / 60
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)}小时`
}
</script>

<style scoped lang="scss">
.day-card {
  display: block;
  width: 100%;
  box-sizing: border-box;
  padding: 22rpx;
  border: 1rpx solid var(--line);
  border-radius: 18rpx;
  background: #ffffff;
  text-align: left;
}

.day-card__head {
  display: flex;
  align-items: flex-start;
  gap: 18rpx;
}

.day-card__badge {
  display: flex;
  flex: 0 0 68rpx;
  align-items: center;
  justify-content: center;
  height: 56rpx;
  border-radius: 14rpx;
  color: #ffffff;
  background: var(--teal);
}

.day-card__badge--1 {
  background: var(--amber);
}

.day-card__badge--2 {
  background: var(--coral);
}

.day-card__badge text {
  font-size: 20rpx;
  font-weight: 900;
}

.day-card__title-wrap {
  flex: 1;
  min-width: 0;
}

.day-card__title,
.day-card__meta {
  display: block;
}

.day-card__title {
  color: var(--text-strong);
  font-size: 29rpx;
  font-weight: 850;
  line-height: 1.32;
}

.day-card__meta {
  margin-top: 8rpx;
  color: var(--text-muted);
  font-size: 22rpx;
  line-height: 1.35;
}

.day-card__arrow {
  flex: 0 0 24rpx;
  color: var(--text-muted);
  font-size: 40rpx;
  line-height: 1;
}

.day-card__stops {
  display: grid;
  gap: 14rpx;
  margin-top: 22rpx;
}

.day-card__stop {
  display: grid;
  grid-template-columns: 76rpx 24rpx 1fr;
  gap: 12rpx;
  align-items: flex-start;
}

.day-card__time {
  color: var(--text-main);
  font-size: 22rpx;
  font-weight: 750;
  line-height: 1.35;
}

.day-card__dot {
  width: 14rpx;
  height: 14rpx;
  margin-top: 7rpx;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 5rpx #e8f7f5;
}

.day-card__dot--1 {
  background: var(--amber);
  box-shadow: 0 0 0 5rpx #fff4dc;
}

.day-card__dot--2 {
  background: var(--coral);
  box-shadow: 0 0 0 5rpx #ffe9ea;
}

.day-card__stop-copy {
  min-width: 0;
}

.day-card__spot,
.day-card__duration {
  display: block;
}

.day-card__spot {
  color: var(--text-strong);
  font-size: 24rpx;
  font-weight: 750;
  line-height: 1.38;
}

.day-card__duration {
  margin-top: 4rpx;
  color: var(--text-muted);
  font-size: 21rpx;
}

.day-card__hotel {
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
  margin-top: 18rpx;
  padding: 16rpx 18rpx;
  border-radius: 14rpx;
  background: linear-gradient(135deg, #f5f3ff, #efe9ff);
}

.day-card__hotel-icon {
  flex: 0 0 36rpx;
  font-size: 28rpx;
  line-height: 36rpx;
}

.day-card__hotel-copy {
  flex: 1;
  min-width: 0;
}

.day-card__hotel-name {
  display: block;
  color: var(--text-strong);
  font-size: 24rpx;
  font-weight: 750;
}

.day-card__hotel-addr {
  display: block;
  overflow: hidden;
  margin-top: 4rpx;
  color: var(--text-muted);
  font-size: 20rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
