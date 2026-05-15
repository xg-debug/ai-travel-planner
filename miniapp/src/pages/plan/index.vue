<template>
  <view class="screen plan-page" :style="{ paddingTop: pageTop + 'px' }">
    <view class="top-bar">
      <button class="icon-button" aria-label="返回" @tap="goBack">‹</button>
    </view>

    <section class="section-block section-block--hero">
      <text class="section-title">你想去哪里？</text>
      <view class="destination-card">
        <view class="destination-input-row">
          <text class="spark-icon">✦</text>
          <input
            v-model="destination"
            class="destination-input"
            placeholder="输入目的地或告诉我你的想法"
            placeholder-class="destination-placeholder"
            confirm-type="next"
          />
        </view>
      </view>
    </section>

    <section class="section-block">
      <text class="section-title">你想去多久？</text>
      <view class="date-range-card">
        <picker mode="date" :value="startDate" :start="today" @change="handleStartDateChange">
          <view class="date-cell">
            <text class="date-icon">▣</text>
            <view>
              <text class="date-cell__label">开始日期</text>
              <text class="date-cell__value">{{ startDateLabel }}</text>
            </view>
          </view>
        </picker>
        <view class="date-divider" />
        <picker mode="date" :value="endDate" :start="startDate" @change="handleEndDateChange">
          <view class="date-cell date-cell--end">
            <view>
              <text class="date-cell__label">结束日期</text>
              <text class="date-cell__value">{{ endDateLabel }}</text>
            </view>
            <text class="chevron">›</text>
          </view>
        </picker>
      </view>
    </section>

    <section class="settings-card">
      <view class="setting-line">
        <view>
          <text class="setting-line__label">出行人数</text>
          <text class="setting-line__hint">用于估算交通、酒店和餐饮</text>
        </view>
        <view class="stepper">
          <button class="stepper__button" @tap="travelers = Math.max(1, travelers - 1)">−</button>
          <text class="stepper__value">{{ travelers }} 人</text>
          <button class="stepper__button" @tap="travelers = Math.min(20, travelers + 1)">＋</button>
        </view>
      </view>

      <view class="setting-line">
        <view>
          <text class="setting-line__label">预算（每人）</text>
          <text class="setting-line__hint">会影响住宿、餐厅和路线强度</text>
        </view>
        <view class="budget-field">
          <text>¥</text>
          <input v-model.number="budgetPerPerson" type="number" class="budget-field__input" />
        </view>
      </view>
    </section>

    <section class="section-block">
      <view class="section-head">
        <text class="section-title">旅行偏好</text>
        <text class="section-note">可多选</text>
      </view>
      <view class="preference-grid">
        <button
          v-for="item in interestsOptions"
          :key="item.id"
          class="preference-chip"
          :class="{ active: interests.includes(item.id) }"
          @tap="toggleInterest(item.id)"
        >
          <text class="preference-chip__icon">{{ item.icon }}</text>
          <text class="preference-chip__label">{{ item.label }}</text>
        </button>
      </view>
    </section>

    <section v-if="tripStore.currentTrip" class="recent-plan" @tap="openCurrentTrip">
      <view>
        <text class="recent-plan__label">最近方案</text>
        <text class="recent-plan__title">
          {{ tripStore.currentTrip.destination }} {{ tripStore.currentTrip.days.length }}日游
        </text>
      </view>
      <text class="recent-plan__arrow">›</text>
    </section>

    <view class="plan-action">
      <button class="plan-button" :disabled="!canSubmit" @tap="submit">智能规划</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useTripStore } from '@/stores/tripStore'
import { addDays, calculateDays, formatDate, todayText } from '@/utils/format'
import { parseTravelIntent } from '@/utils/travelIntent'

const tripStore = useTripStore()
const today = todayText()
const pageTop = ref(78)
const destination = ref('')
const startDate = ref(today)
const endDate = ref(addDays(today, 2))
const travelers = ref(2)
const budgetPerPerson = ref(3500)
const interests = ref<string[]>(['classic', 'food', 'history'])

const interestsOptions = [
  { id: 'classic', icon: '📍', label: '经典必玩' },
  { id: 'food', icon: '🍽️', label: '吃吃喝喝' },
  { id: 'local', icon: '🕵️', label: '小众探索' },
  { id: 'photo', icon: '📸', label: '拍照出片' },
  { id: 'shopping', icon: '🛍️', label: '逛街购物' },
  { id: 'citywalk', icon: '🚶', label: 'citywalk' },
  { id: 'nature', icon: '🏞️', label: '自然风光' },
  { id: 'art', icon: '🎨', label: '文艺展览' },
  { id: 'history', icon: '🏛️', label: '历史古建' }
]

const days = computed(() => calculateDays(startDate.value, endDate.value))
const startDateLabel = computed(() => formatDate(startDate.value))
const endDateLabel = computed(() => formatDate(endDate.value))
const totalBudget = computed(() => Math.max(0, Number(budgetPerPerson.value || 0)) * travelers.value)
const canSubmit = computed(() => Boolean(destination.value.trim() && startDate.value && totalBudget.value > 0))

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
  tripStore.restoreLocal()
})

const handleStartDateChange = (event: any) => {
  startDate.value = event.detail.value
  if (new Date(endDate.value).getTime() < new Date(startDate.value).getTime()) {
    endDate.value = startDate.value
  }
}

const handleEndDateChange = (event: any) => {
  const nextEnd = event.detail.value
  if (new Date(nextEnd).getTime() < new Date(startDate.value).getTime()) {
    uni.showToast({ title: '结束日期不能早于开始日期', icon: 'none' })
    endDate.value = startDate.value
    return
  }
  endDate.value = nextEnd
}

const toggleInterest = (id: string) => {
  interests.value = interests.value.includes(id)
    ? interests.value.filter((item) => item !== id)
    : [...interests.value, id]
}

const submit = () => {
  if (!canSubmit.value) {
    uni.showToast({ title: '请填写目的地和预算', icon: 'none' })
    return
  }
  const intent = parseTravelIntent(destination.value)
  if (!intent.destination) {
    uni.showToast({ title: '请写清目的地城市，如深圳海边两日游', icon: 'none' })
    return
  }
  if (days.value > 7) {
    uni.showToast({ title: '当前仅支持 1-7 天游', icon: 'none' })
    return
  }
  tripStore.setDraft({
    destination: intent.destination,
    startDate: startDate.value,
    endDate: endDate.value,
    days: days.value,
    travelers: travelers.value,
    interests: interests.value,
    budget: totalBudget.value,
    additionalRequirements: intent.additionalRequirements
  })
  uni.navigateTo({ url: '/pages/generating/index' })
}

const openCurrentTrip = () => {
  uni.navigateTo({ url: '/pages/trip-detail/index' })
}

const goBack = () => {
  uni.navigateBack({ delta: 1 })
}
</script>

<style scoped lang="scss">
.plan-page {
  display: grid;
  align-content: start;
  gap: 74rpx;
  padding: 86rpx 42rpx 88rpx;
  background: #f4f4f6;
}

.plan-page button {
  padding: 0;
  line-height: 1;
}

.plan-page button::after {
  border: 0;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  margin-bottom: 34rpx;
}

.icon-button {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 88rpx;
  height: 76rpx;
  color: #050505;
  background: transparent;
  font-size: 84rpx;
  font-weight: 320;
}

.section-block {
  display: grid;
  gap: 28rpx;
}

.section-block--hero {
  gap: 36rpx;
}

.section-title {
  display: block;
  color: #050505;
  font-size: 46rpx;
  font-weight: 950;
  line-height: 1.08;
  letter-spacing: 0;
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.section-note {
  color: #8c93a0;
  font-size: 24rpx;
  font-weight: 700;
}

.destination-card {
  box-sizing: border-box;
  min-height: 120rpx;
  padding: 24rpx 34rpx;
  border-radius: 48rpx;
  background: #ffffff;
  box-shadow: 0 20rpx 52rpx rgba(60, 82, 108, 0.08);
  display: flex;
  align-items: center;
}

.destination-input-row {
  display: flex;
  align-items: center;
  gap: 22rpx;
  width: 100%;
}

.spark-icon {
  flex: 0 0 auto;
  color: #7b4ff6;
  font-size: 54rpx;
  font-weight: 900;
  line-height: 1;
}

.destination-input {
  flex: 1;
  min-width: 0;
  height: 66rpx;
  color: #050505;
  font-size: 36rpx;
  font-weight: 850;
}

.destination-placeholder {
  color: #b9c1cc;
  font-weight: 850;
}

.date-range-card {
  display: grid;
  grid-template-columns: 1fr 1rpx 1fr;
  align-items: center;
  box-sizing: border-box;
  min-height: 124rpx;
  padding: 0 30rpx;
  border-radius: 999rpx;
  background: #ffffff;
}

.date-cell {
  display: flex;
  align-items: center;
  gap: 18rpx;
  min-width: 0;
}

.date-cell--end {
  justify-content: space-between;
  padding-left: 26rpx;
}

.date-icon {
  flex: 0 0 auto;
  color: #050505;
  font-size: 40rpx;
  font-weight: 900;
  line-height: 1;
}

.date-cell__label,
.date-cell__value {
  display: block;
}

.date-cell__label {
  color: #b7c0cc;
  font-size: 24rpx;
  font-weight: 900;
  line-height: 1.1;
}

.date-cell__value {
  margin-top: 10rpx;
  color: #050505;
  font-size: 30rpx;
  font-weight: 950;
}

.date-divider {
  width: 1rpx;
  height: 56rpx;
  background: #ededf0;
}

.chevron {
  flex: 0 0 auto;
  color: #d5dae2;
  font-size: 48rpx;
  font-weight: 500;
}

.settings-card {
  display: grid;
  gap: 0;
  padding: 4rpx 30rpx;
  border-radius: 34rpx;
  background: #ffffff;
}

.setting-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  min-height: 112rpx;
  border-bottom: 1rpx solid #ededf0;
}

.setting-line:last-child {
  border-bottom: 0;
}

.setting-line__label,
.setting-line__hint {
  display: block;
}

.setting-line__label {
  color: #050505;
  font-size: 27rpx;
  font-weight: 900;
}

.setting-line__hint {
  margin-top: 8rpx;
  color: #8c93a0;
  font-size: 21rpx;
  line-height: 1.25;
}

.stepper {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 18rpx;
}

.stepper__button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 54rpx;
  height: 54rpx;
  border-radius: 999rpx;
  color: #050505;
  background: #f2f3f5;
  font-size: 34rpx;
  font-weight: 900;
}

.stepper__value {
  min-width: 76rpx;
  text-align: center;
  color: #050505;
  font-size: 27rpx;
  font-weight: 900;
}

.budget-field {
  display: flex;
  flex: 0 0 190rpx;
  align-items: center;
  justify-content: flex-end;
  gap: 8rpx;
  color: #050505;
  font-size: 27rpx;
  font-weight: 900;
}

.budget-field__input {
  width: 128rpx;
  height: 62rpx;
  text-align: right;
  color: #050505;
  font-size: 29rpx;
  font-weight: 900;
}

.preference-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22rpx 18rpx;
}

.preference-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9rpx;
  min-width: 0;
  min-height: 80rpx;
  padding: 0 10rpx;
  border: 2rpx solid #e9e9ec;
  border-radius: 999rpx;
  color: #050505;
  background: #ffffff;
  box-shadow: 0 4rpx 10rpx rgba(5, 5, 5, 0.03);
}

.preference-chip.active {
  border-color: #050505;
  color: #ffffff;
  background: #050505;
  box-shadow: none;
}

.preference-chip__icon {
  flex: 0 0 auto;
  font-size: 25rpx;
  line-height: 1;
}

.preference-chip__label {
  min-width: 0;
  overflow: hidden;
  color: inherit;
  font-size: 25rpx;
  font-weight: 900;
  line-height: 1.1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-plan {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 26rpx 30rpx;
  border-radius: 30rpx;
  background: #ffffff;
}

.recent-plan__label,
.recent-plan__title {
  display: block;
}

.recent-plan__label {
  color: #8c93a0;
  font-size: 22rpx;
  font-weight: 800;
}

.recent-plan__title {
  margin-top: 10rpx;
  color: #050505;
  font-size: 30rpx;
  font-weight: 950;
}

.recent-plan__arrow {
  color: #b7bec8;
  font-size: 48rpx;
}

.plan-action {
  display: flex;
  justify-content: center;
  margin-top: 12rpx;
  padding-bottom: calc(12rpx + env(safe-area-inset-bottom));
}

.plan-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 88rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  color: #ffffff;
  background: #050505;
  box-shadow: none;
  font-size: 30rpx;
  font-weight: 900;
  letter-spacing: 0;
}

.plan-button[disabled] {
  color: #ffffff;
  background: #050505;
  box-shadow: none;
}
</style>
