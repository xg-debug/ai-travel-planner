<template>
  <view class="screen trips-page" :style="{ paddingTop: pageTop + 'px' }">
    <view class="top-bar">
      <view class="top-bar__title">
        <text class="page-kicker">TRIPS</text>
        <text class="page-heading">行程</text>
      </view>
      <button class="new-button" @tap="goPlan">新建</button>
    </view>

    <view v-if="latestTrip" class="featured-trip" @tap="openTrip(latestTrip.id)">
      <view class="ticket-top">
        <view class="ticket-header">
          <text class="ticket-label">NEXT TRIP</text>
          <text class="ticket-status">{{ latestTrip.status || 'planned' }}</text>
        </view>
        <view class="ticket-dest">
          <text class="ticket-city">{{ latestTrip.destination }}</text>
          <text class="ticket-days">{{ latestTrip.days?.length || 0 }}日游</text>
        </view>
        <text class="ticket-date">{{ formatDateRange(latestTrip.startDate, latestTrip.endDate) }}</text>
      </view>
      <view class="ticket-divider">
        <view class="ticket-hole ticket-hole-left" />
        <view class="ticket-dash" />
        <view class="ticket-hole ticket-hole-right" />
      </view>
      <view class="ticket-bottom">
        <view class="ticket-stat">
          <text class="stat-value">{{ latestTrip.travelers }}</text>
          <text class="stat-label">同行人数</text>
        </view>
        <view class="ticket-stat">
          <text class="stat-value">{{ formatMoney(latestTrip.budget?.total) }}</text>
          <text class="stat-label">预估预算</text>
        </view>
        <view class="ticket-stat">
          <text class="stat-value">{{ latestTrip.recommendations?.length || 0 }}</text>
          <text class="stat-label">推荐地点</text>
        </view>
      </view>
    </view>

    <view v-if="tripStore.tripHistory.length" class="section">
      <view class="section-head">
        <text>全部行程</text>
        <text>{{ tripStore.tripHistory.length }} 份</text>
      </view>

      <view class="trip-list">
        <view v-for="trip in tripStore.tripHistory" :key="trip.id" class="trip-card">
          <view class="trip-card__main" @tap="openTrip(trip.id)">
            <view class="trip-card__date">
              <text>{{ monthOf(trip.startDate) }}</text>
              <text>{{ dayOf(trip.startDate) }}</text>
            </view>
            <view class="trip-card__body">
              <text class="trip-card__title">{{ trip.destination }} {{ trip.days?.length || 0 }}日游</text>
              <text class="trip-card__meta">{{ formatDateRange(trip.startDate, trip.endDate) }}</text>
              <view class="trip-card__tags">
                <text>{{ trip.travelers }} 人</text>
                <text>{{ formatMoney(trip.budget?.total) }}</text>
              </view>
            </view>
            <view class="trip-card__actions">
              <text class="trip-card__arrow">›</text>
              <button class="trip-card__delete" @tap.stop="removeTrip(trip.id)">删除</button>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view v-else class="empty-card">
      <text class="empty-card__icon">✦</text>
      <text class="empty-card__title">还没有行程</text>
      <text class="empty-card__desc">输入目的地和日期后，会在这里保存可继续查看的旅行方案。</text>
      <button class="empty-card__button" @tap="goPlan">开始规划</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/authStore'
import { useTripStore } from '@/stores/tripStore'
import { formatDateRange, formatMoney } from '@/utils/format'

const authStore = useAuthStore()
const tripStore = useTripStore()
const pageTop = ref(78)

const latestTrip = computed(() => tripStore.tripHistory[0] || null)

onMounted(() => {
  const menu = (uni as any).getMenuButtonBoundingClientRect?.()
  if (menu?.bottom) {
    pageTop.value = menu.bottom + 16
    return
  }

  const systemInfo = uni.getSystemInfoSync()
  pageTop.value = Number(systemInfo.statusBarHeight || 24) + 58
})

onShow(() => {
  authStore.restore()
  tripStore.loadHistory()
})

const monthOf = (value?: string) => {
  const date = new Date(value || '')
  if (Number.isNaN(date.getTime())) return '--'
  return `${date.getMonth() + 1}月`
}

const dayOf = (value?: string) => {
  const date = new Date(value || '')
  if (Number.isNaN(date.getTime())) return '--'
  return String(date.getDate()).padStart(2, '0')
}

const openTrip = async (id: string) => {
  await tripStore.loadTrip(id)
  uni.navigateTo({ url: '/pages/trip-detail/index' })
}

const removeTrip = (id: string) => {
  uni.showModal({
    title: '删除行程',
    content: '删除后不可恢复，确认继续吗？',
    success: async (res) => {
      if (!res.confirm) return
      await tripStore.deleteTrip(id)
      uni.showToast({ title: '已删除', icon: 'success' })
    }
  })
}

const goPlan = () => {
  uni.switchTab({ url: '/pages/plan/index' })
}
</script>

<style scoped lang="scss">
.trips-page {
  display: grid;
  align-content: start;
  gap: 24rpx;
  padding: 86rpx 34rpx 170rpx;
  background: #f4f4f6;
}

.trips-page button {
  padding: 0;
}

.trips-page button::after {
  border: 0;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.top-bar__title {
  min-width: 0;
}

.page-kicker,
.page-heading {
  display: block;
}

.page-kicker {
  color: #8c93a0;
  font-size: 20rpx;
  font-weight: 900;
  letter-spacing: 0;
}

.page-heading {
  margin-top: 8rpx;
  color: #050505;
  font-size: 52rpx;
  font-weight: 950;
  line-height: 1.08;
}

.new-button {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 132rpx;
  height: 72rpx;
  padding: 0 28rpx;
  border-radius: 999rpx;
  color: #ffffff;
  background: #050505;
  box-shadow: 0 10rpx 22rpx rgba(5, 5, 5, 0.14);
  font-size: 26rpx;
  font-weight: 900;
}

.featured-trip {
  display: block;
  width: 100%;
  margin: 10rpx 0 16rpx;
  border-radius: 34rpx;
  background: #ffffff;
  box-shadow: 0 20rpx 48rpx rgba(17, 24, 39, 0.08);
  text-align: left;
}

.ticket-top {
  padding: 44rpx 40rpx;
  background: linear-gradient(135deg, #111827 0%, #1e1b4b 100%);
  border-radius: 34rpx 34rpx 0 0;
  color: #ffffff;
}

.ticket-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 34rpx;
}

.ticket-label {
  font-size: 23rpx;
  font-weight: 900;
  letter-spacing: 2rpx;
  color: rgba(255, 255, 255, 0.6);
}

.ticket-status {
  font-size: 20rpx;
  font-weight: 850;
  padding: 8rpx 18rpx;
  background: rgba(255, 255, 255, 0.16);
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 999rpx;
}

.ticket-dest {
  display: flex;
  align-items: baseline;
  gap: 16rpx;
}

.ticket-city {
  font-size: 58rpx;
  font-weight: 950;
  color: #ffffff;
}

.ticket-days {
  font-size: 28rpx;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.85);
}

.ticket-date {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.65);
}

.ticket-divider {
  position: relative;
  height: 44rpx;
  background: #ffffff;
  display: flex;
  align-items: center;
}

.ticket-dash {
  flex: 1;
  height: 2rpx;
  border-bottom: 4rpx dashed #e2e8f0;
  margin: 0 24rpx;
}

.ticket-hole {
  position: absolute;
  top: 50%;
  width: 44rpx;
  height: 44rpx;
  background: #f4f4f6;
  border-radius: 50%;
  transform: translateY(-50%);
}

.ticket-hole-left {
  left: -22rpx;
}

.ticket-hole-right {
  right: -22rpx;
}

.ticket-bottom {
  display: flex;
  justify-content: space-between;
  padding: 24rpx 40rpx 44rpx;
  background: #ffffff;
  border-radius: 0 0 34rpx 34rpx;
}

.ticket-stat {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.stat-value {
  font-size: 34rpx;
  font-weight: 950;
  color: #050505;
}

.stat-label {
  font-size: 22rpx;
  font-weight: 800;
  color: #8c93a0;
}

.section {
  display: grid;
  gap: 18rpx;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4rpx;
}

.section-head text:first-child {
  color: #050505;
  font-size: 34rpx;
  font-weight: 950;
}

.section-head text:last-child {
  color: #8c93a0;
  font-size: 23rpx;
  font-weight: 800;
}

.trip-list {
  display: grid;
  gap: 14rpx;
}

.trip-card {
  overflow: hidden;
  border: 1rpx solid #e9edf3;
  border-radius: 26rpx;
  background: #ffffff;
  box-shadow: 0 8rpx 22rpx rgba(17, 24, 39, 0.05);
}

.trip-card__main {
  display: grid;
  grid-template-columns: 92rpx minmax(0, 1fr) auto;
  align-items: center;
  gap: 18rpx;
  box-sizing: border-box;
  width: 100%;
  min-height: 138rpx;
  padding: 22rpx;
  text-align: left;
}

.trip-card__date {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 92rpx;
  height: 92rpx;
  border-radius: 24rpx;
  background: linear-gradient(180deg, #f6f8fc 0%, #f1f4f9 100%);
}

.trip-card__date text:first-child {
  color: #8c93a0;
  font-size: 19rpx;
  font-weight: 900;
}

.trip-card__date text:last-child {
  margin-top: 4rpx;
  color: #050505;
  font-size: 32rpx;
  font-weight: 950;
}

.trip-card__body {
  min-width: 0;
}

.trip-card__title,
.trip-card__meta {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trip-card__title {
  color: #111827;
  font-size: 32rpx;
  font-weight: 900;
  line-height: 1.2;
}

.trip-card__meta {
  margin-top: 8rpx;
  color: #8c93a0;
  font-size: 23rpx;
  font-weight: 750;
  line-height: 1.2;
}

.trip-card__tags {
  display: flex;
  gap: 10rpx;
  margin-top: 12rpx;
}

.trip-card__tags text {
  max-width: 170rpx;
  min-width: 0;
  overflow: hidden;
  padding: 7rpx 14rpx;
  border-radius: 999rpx;
  color: #1f2937;
  background: #f5f7fb;
  font-size: 20rpx;
  font-weight: 850;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trip-card__actions {
  display: grid;
  justify-items: end;
  gap: 10rpx;
}

.trip-card__arrow {
  color: #b7bfca;
  font-size: 36rpx;
  line-height: 1;
}

.trip-card__delete {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 82rpx;
  height: 48rpx;
  padding: 0 16rpx;
  border: 1rpx solid #f3cdcf;
  border-radius: 999rpx;
  color: #b42318;
  background: #fff7f8;
  font-size: 20rpx;
  font-weight: 850;
  line-height: 1.1;
}

.empty-card {
  display: grid;
  justify-items: center;
  padding: 72rpx 52rpx;
  border-radius: 38rpx;
  background: #ffffff;
  text-align: center;
}

.empty-card__icon {
  color: #7b4ff6;
  font-size: 54rpx;
  font-weight: 950;
}

.empty-card__title,
.empty-card__desc {
  display: block;
}

.empty-card__title {
  margin-top: 24rpx;
  color: #050505;
  font-size: 38rpx;
  font-weight: 950;
}

.empty-card__desc {
  margin-top: 14rpx;
  color: #8c93a0;
  font-size: 25rpx;
  line-height: 1.45;
}

.empty-card__button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 260rpx;
  height: 82rpx;
  margin-top: 36rpx;
  border-radius: 999rpx;
  color: #ffffff;
  background: #050505;
  font-size: 27rpx;
  font-weight: 900;
}
</style>
