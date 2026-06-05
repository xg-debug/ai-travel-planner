<template>
  <view :class="['screen trips-page', themeStore.themeClass]">
    <view class="top-bar">
      <view class="top-bar__title">
        <text class="page-heading">我的行程</text>
        <text class="page-subheading">把每一次出发都收好，随时继续查看</text>
      </view>
      <button class="new-button" @tap="goPlan">
        <text class="new-button__icon">＋</text>
        <text>新建</text>
      </button>
    </view>

    <view v-if="latestTrip" class="featured-trip" @tap="openTrip(latestTrip.id)">
      <view class="featured-trip__visual">
        <view class="featured-trip__route">
          <view class="route-dot route-dot--start" />
          <view class="route-line" />
          <view class="route-dot route-dot--end" />
        </view>
        <view class="featured-trip__top">
          <view>
            <text class="featured-trip__label">下一站</text>
            <text class="featured-trip__city">{{ latestTrip.destination }}</text>
          </view>
          <text class="featured-trip__status">{{ statusLabel(latestTrip.status) }}</text>
        </view>
        <view class="featured-trip__bottom">
          <text>{{ latestTrip.days?.length || 0 }} 日游</text>
          <text>{{ formatDateRange(latestTrip.startDate, latestTrip.endDate) }}</text>
        </view>
      </view>

      <view class="featured-trip__metrics">
        <view class="metric">
          <text class="metric__value">{{ latestTrip.travelers }}</text>
          <text class="metric__label">同行</text>
        </view>
        <view class="metric">
          <text class="metric__value">{{ formatMoney(latestTrip.budget?.total) }}</text>
          <text class="metric__label">预算</text>
        </view>
        <view class="metric">
          <text class="metric__value">{{ latestTrip.recommendations?.length || 0 }}</text>
          <text class="metric__label">推荐地</text>
        </view>
      </view>
    </view>

    <view v-if="tripStore.tripHistory.length" class="section">
      <view class="section-head">
        <text>全部行程</text>
        <text>{{ tripStore.tripHistory.length }} 份计划</text>
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
                <text>{{ trip.recommendations?.length || 0 }} 地点</text>
              </view>
            </view>
            <view class="trip-card__actions">
              <button class="trip-card__delete" @tap.stop="removeTrip(trip.id)">删除</button>
              <text class="trip-card__arrow">›</text>
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
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/authStore'
import { useTripStore } from '@/stores/tripStore'
import { useThemeStore } from '@/stores/themeStore'
import { formatDateRange, formatMoney } from '@/utils/format'

const authStore = useAuthStore()
const tripStore = useTripStore()
const themeStore = useThemeStore()

const latestTrip = computed(() => tripStore.tripHistory[0] || null)

onShow(() => {
  authStore.restore()
  tripStore.loadHistory()
  themeStore.restore()
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

const statusLabel = (status?: string) => {
  if (status === 'completed') return '已完成'
  if (status === 'in-progress') return '进行中'
  if (status === 'draft') return '草稿'
  return '已规划'
}
</script>

<style scoped lang="scss">
.trips-page {
  display: grid;
  align-content: start;
  gap: 30rpx;
  padding: 34rpx 28rpx 170rpx;
  background:
    linear-gradient(180deg, #eef6ff 0%, #f7f8fb 31%, #f6f7f9 100%);
}

.trips-page button {
  padding: 0;
}

.trips-page button::after {
  border: 0;
}

.top-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
  padding: 6rpx 2rpx 2rpx;
}

.top-bar__title {
  min-width: 0;
}

.page-heading,
.page-subheading {
  display: block;
}

.page-heading {
  color: #0f172a;
  font-size: 48rpx;
  font-weight: 950;
  line-height: 1.08;
}

.page-subheading {
  margin-top: 12rpx;
  color: #64748b;
  font-size: 24rpx;
  font-weight: 650;
  line-height: 1.35;
}

.new-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
  flex: 0 0 auto;
  min-width: 136rpx;
  height: 68rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  color: #ffffff;
  background: #0f172a;
  box-shadow: 0 14rpx 28rpx rgba(15, 23, 42, 0.18);
  font-size: 25rpx;
  font-weight: 900;
  line-height: 1;
}

.new-button__icon {
  font-size: 28rpx;
  font-weight: 900;
  line-height: 1;
}

.featured-trip {
  overflow: hidden;
  display: grid;
  border: 1rpx solid rgba(226, 232, 240, 0.9);
  border-radius: 34rpx;
  background: #ffffff;
  box-shadow: 0 24rpx 58rpx rgba(15, 23, 42, 0.1);
  text-align: left;
}

.featured-trip__visual {
  position: relative;
  overflow: hidden;
  min-height: 276rpx;
  padding: 36rpx;
  background: linear-gradient(135deg, #0369a1 0%, #0f766e 52%, #134e4a 100%);
}

.featured-trip__route {
  position: absolute;
  right: 44rpx;
  bottom: 48rpx;
  display: flex;
  align-items: center;
  width: 190rpx;
  transform: rotate(-12deg);
}

.route-dot {
  width: 18rpx;
  height: 18rpx;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 0 0 8rpx rgba(255, 255, 255, 0.14);
}

.route-line {
  flex: 1;
  height: 2rpx;
  margin: 0 14rpx;
  border-bottom: 4rpx dotted rgba(255, 255, 255, 0.74);
}

.featured-trip__top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
}

.featured-trip__label,
.featured-trip__city {
  display: block;
}

.featured-trip__label {
  color: rgba(255, 255, 255, 0.74);
  font-size: 24rpx;
  font-weight: 800;
}

.featured-trip__city {
  max-width: 390rpx;
  margin-top: 14rpx;
  overflow: hidden;
  color: #ffffff;
  font-size: 58rpx;
  font-weight: 950;
  line-height: 1.08;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.featured-trip__status {
  flex: 0 0 auto;
  padding: 10rpx 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.24);
  border-radius: 999rpx;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.16);
  font-size: 21rpx;
  font-weight: 850;
  backdrop-filter: blur(16rpx);
}

.featured-trip__bottom {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 58rpx;
}

.featured-trip__bottom text {
  padding: 12rpx 18rpx;
  border-radius: 999rpx;
  color: #ecfeff;
  background: rgba(255, 255, 255, 0.16);
  font-size: 24rpx;
  font-weight: 850;
}

.featured-trip__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
  padding: 26rpx;
}

.metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 104rpx;
  border-radius: 24rpx;
  background: #f7f9fc;
}

.metric__value {
  max-width: 170rpx;
  overflow: hidden;
  color: #0f172a;
  font-size: 31rpx;
  font-weight: 950;
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric__label {
  margin-top: 8rpx;
  color: #7a8494;
  font-size: 22rpx;
  font-weight: 800;
}

.section {
  display: grid;
  gap: 20rpx;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4rpx;
}

.section-head text:first-child {
  color: #0f172a;
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
  gap: 18rpx;
}

.trip-card {
  overflow: hidden;
  border: 1rpx solid #e6edf5;
  border-radius: 28rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 30rpx rgba(15, 23, 42, 0.055);
}

.trip-card__main {
  display: grid;
  grid-template-columns: 88rpx minmax(0, 1fr) 82rpx;
  align-items: center;
  gap: 20rpx;
  box-sizing: border-box;
  width: 100%;
  min-height: 148rpx;
  padding: 24rpx;
  text-align: left;
}

.trip-card__date {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 88rpx;
  height: 96rpx;
  border-radius: 24rpx;
  background: linear-gradient(180deg, #eff8ff 0%, #f7fbff 100%);
  box-shadow: inset 0 0 0 1rpx #dbeafe;
}

.trip-card__date text:first-child {
  color: #64748b;
  font-size: 19rpx;
  font-weight: 900;
}

.trip-card__date text:last-child {
  margin-top: 4rpx;
  color: #0f172a;
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
  color: #0f172a;
  font-size: 31rpx;
  font-weight: 900;
  line-height: 1.2;
}

.trip-card__meta {
  margin-top: 8rpx;
  color: #7a8494;
  font-size: 23rpx;
  font-weight: 750;
  line-height: 1.2;
}

.trip-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 12rpx;
}

.trip-card__tags text {
  max-width: 142rpx;
  min-width: 0;
  overflow: hidden;
  padding: 7rpx 13rpx;
  border-radius: 999rpx;
  color: #334155;
  background: #f2f6fb;
  font-size: 20rpx;
  font-weight: 850;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trip-card__actions {
  display: grid;
  align-items: center;
  justify-items: end;
  gap: 12rpx;
}

.trip-card__arrow {
  color: #94a3b8;
  font-size: 40rpx;
  line-height: 1;
}

.trip-card__delete {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 74rpx;
  height: 42rpx;
  padding: 0 14rpx;
  border: 1rpx solid #fecdd3;
  border-radius: 999rpx;
  color: #be123c;
  background: #fff5f6;
  font-size: 19rpx;
  font-weight: 850;
  line-height: 1.1;
}

.empty-card {
  display: grid;
  justify-items: center;
  margin-top: 10rpx;
  padding: 76rpx 48rpx;
  border: 1rpx solid #e6edf5;
  border-radius: 38rpx;
  background: #ffffff;
  box-shadow: 0 18rpx 42rpx rgba(15, 23, 42, 0.06);
  text-align: center;
}

.empty-card__icon {
  color: #0f766e;
  font-size: 54rpx;
  font-weight: 950;
}

.empty-card__title,
.empty-card__desc {
  display: block;
}

.empty-card__title {
  margin-top: 24rpx;
  color: #0f172a;
  font-size: 38rpx;
  font-weight: 950;
}

.empty-card__desc {
  margin-top: 14rpx;
  color: #64748b;
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
  background: #0f172a;
  font-size: 27rpx;
  font-weight: 900;
}
</style>
