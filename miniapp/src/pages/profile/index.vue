<template>
  <view class="screen profile-page">
    <view class="profile-card panel">
      <view class="profile-card__top">
        <view class="avatar">{{ initials }}</view>
        <view class="profile-card__copy">
          <text class="profile-card__name">{{ authStore.isAuthenticated ? authStore.userName : '未登录用户' }}</text>
          <text class="profile-card__meta">
            {{ authStore.isAuthenticated ? (authStore.user?.email || '已登录') : '登录后可同步行程到云端' }}
          </text>
        </view>
      </view>
      <button v-if="!authStore.isAuthenticated" class="profile-card__action" @tap="goAuth">登录 / 注册</button>
      <button v-else class="profile-card__action profile-card__action--ghost" @tap="logout">退出登录</button>
    </view>

    <view class="stats panel">
      <view class="stats__item">
        <text class="stats__value">{{ tripStore.tripHistory.length }}</text>
        <text class="stats__label">总行程</text>
      </view>
      <view class="stats__item">
        <text class="stats__value">{{ upcomingCount }}</text>
        <text class="stats__label">待出发</text>
      </view>
      <view class="stats__item">
        <text class="stats__value">{{ visitedCities }}</text>
        <text class="stats__label">目的地</text>
      </view>
    </view>

    <view class="menu panel">
      <button class="menu__item" @tap="goTrips">
        <text>我的行程</text>
        <text>›</text>
      </button>
      <button class="menu__item" @tap="goPlan">
        <text>创建新规划</text>
        <text>›</text>
      </button>
      <button class="menu__item" @tap="showHint">
        <text>个性化设置</text>
        <text>›</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/authStore'
import { useTripStore } from '@/stores/tripStore'

const authStore = useAuthStore()
const tripStore = useTripStore()

const initials = computed(() => {
  const name = authStore.userName || '旅行者'
  return name.slice(0, 1).toUpperCase()
})

const upcomingCount = computed(() => {
  const now = new Date().getTime()
  return tripStore.tripHistory.filter((trip) => new Date(trip.startDate).getTime() >= now).length
})

const visitedCities = computed(() => new Set(tripStore.tripHistory.map((trip) => trip.destination)).size)

onShow(() => {
  authStore.restore()
  tripStore.loadHistory()
})

const goAuth = () => {
  uni.navigateTo({ url: '/pages/auth/index' })
}

const goTrips = () => {
  uni.switchTab({ url: '/pages/trips/index' })
}

const goPlan = () => {
  uni.switchTab({ url: '/pages/plan/index' })
}

const showHint = () => {
  uni.showToast({ title: '更多偏好设置即将上线', icon: 'none' })
}

const logout = () => {
  uni.showModal({
    title: '退出登录',
    content: '确认退出当前账号吗？',
    success: (res) => {
      if (!res.confirm) return
      authStore.logout()
      uni.showToast({ title: '已退出', icon: 'success' })
    }
  })
}
</script>

<style scoped lang="scss">
.profile-page {
  display: grid;
  align-content: start;
  gap: 20rpx;
}

.profile-card {
  display: grid;
  gap: 22rpx;
  padding: 30rpx;
}

.profile-card__top {
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 92rpx;
  height: 92rpx;
  border-radius: 50%;
  color: #ffffff;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  font-size: 34rpx;
  font-weight: 900;
}

.profile-card__copy {
  min-width: 0;
}

.profile-card__name,
.profile-card__meta {
  display: block;
}

.profile-card__name {
  color: var(--text-strong);
  font-size: 34rpx;
  font-weight: 900;
}

.profile-card__meta {
  margin-top: 10rpx;
  color: var(--text-muted);
  font-size: 23rpx;
}

.profile-card__action {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 76rpx;
  border-radius: 999rpx;
  color: #ffffff;
  background: #111827;
  font-size: 26rpx;
  font-weight: 850;
}

.profile-card__action--ghost {
  color: #111827;
  background: #eef2f7;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10rpx;
  padding: 14rpx;
}

.stats__item {
  padding: 20rpx 10rpx;
  border-radius: 16rpx;
  background: #f8fafe;
  text-align: center;
}

.stats__value {
  display: block;
  color: var(--text-strong);
  font-size: 34rpx;
  font-weight: 900;
}

.stats__label {
  display: block;
  margin-top: 8rpx;
  color: var(--text-muted);
  font-size: 21rpx;
}

.menu {
  display: grid;
  overflow: hidden;
}

.menu__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 90rpx;
  padding: 0 24rpx;
  border-bottom: 1rpx solid var(--line);
  color: var(--text-main);
  font-size: 27rpx;
  font-weight: 750;
}

.menu__item:last-child {
  border-bottom: 0;
}
</style>
