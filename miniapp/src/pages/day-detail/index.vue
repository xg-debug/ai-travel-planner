<template>
  <view v-if="day" :class="['screen day-detail', themeStore.themeClass]">
    <view class="day-head panel">
      <view>
        <text class="day-head__label">{{ trip?.destination }}</text>
        <text class="day-head__title">第 {{ dayIndex + 1 }} 天</text>
        <text class="day-head__date">{{ formatDate(day.date) }} · {{ day.activities.length }} 个安排</text>
      </view>
      <text class="day-head__cost">{{ formatMoney(dayCost) }}</text>
    </view>

    <SectionPanel title="时间线" subtitle="按当天实际出行顺序查看">
      <view class="timeline">
        <button
          v-for="(activity, index) in day.activities"
          :key="activity.id"
          class="activity"
          @tap="openPlace(index)"
        >
          <view class="activity__time">
            <text>{{ activity.time }}</text>
          </view>
          <view class="activity__content">
            <view class="activity__top">
              <text class="activity__title">{{ activity.title }}</text>
              <text class="activity__price">{{ formatMoney(activity.cost) }}</text>
            </view>
            <text class="activity__location">{{ activity.location }}</text>
            <text class="activity__desc">{{ activity.description }}</text>
            <view class="activity__tags">
              <text>{{ activityTagLabel(activity) }}</text>
              <text>{{ activityDurationTag(activity) }}</text>
              <text v-if="activity.ticketLabel">{{ activity.ticketLabel }}</text>
            </view>
          </view>
        </button>
      </view>
    </SectionPanel>

    <SectionPanel v-if="day.hotel" title="住宿推荐">
      <view class="hotel">
        <text class="hotel__name">{{ day.hotel.name }}</text>
        <text v-if="day.hotel.address" class="hotel__line">{{ day.hotel.address }}</text>
        <text v-if="day.hotel.reason" class="hotel__desc">{{ day.hotel.reason }}</text>
        <text v-if="day.hotel.priceEstimate" class="hotel__price">{{ formatHotelPrice(day.hotel.priceEstimate) }}</text>
      </view>
    </SectionPanel>
  </view>

  <view v-else :class="['screen', themeStore.themeClass]">
    <EmptyState
      title="没有找到当天行程"
      description="返回行程详情，重新选择某一天查看。"
      action-text="返回"
      @action="back"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import SectionPanel from '@/components/SectionPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useTripStore } from '@/stores/tripStore'
import { useThemeStore } from '@/stores/themeStore'
import { activityTypeLabel, formatDate, formatMoney } from '@/utils/format'
import type { Activity } from '@/types/trip'

const tripStore = useTripStore()
const themeStore = useThemeStore()
const dayIndex = ref(0)
const trip = computed(() => tripStore.currentTrip)
const day = computed(() => trip.value?.days[dayIndex.value])
const dayCost = computed(() => day.value?.activities.reduce((sum, item) => sum + Number(item.cost || 0), 0) || 0)

onLoad((query) => {
  dayIndex.value = Number(query?.day || 0)
})

onShow(() => {
  tripStore.restoreLocal()
  themeStore.restore()
})

const openPlace = (activityIndex: number) => {
  uni.navigateTo({ url: `/pages/place-detail/index?day=${dayIndex.value}&activity=${activityIndex}` })
}

const formatHotelPrice = (value: number | string) => {
  return typeof value === 'number' ? `${formatMoney(value)}/晚` : value
}

const activityTagLabel = (activity: Activity) =>
  activity.isIntercityTransport ? '#交通' : activityTypeLabel(activity.type)

const activityDurationTag = (activity: Activity) =>
  activity.isIntercityTransport ? `#${activity.duration}分钟` : `${activity.duration} 分钟`

const back = () => {
  uni.navigateBack()
}
</script>

<style scoped lang="scss">
.day-detail {
  display: grid;
  gap: 24rpx;
}

.day-head {
  display: flex;
  justify-content: space-between;
  gap: 24rpx;
  padding: 34rpx;
}

.day-head__label,
.day-head__title,
.day-head__date {
  display: block;
}

.day-head__label {
  color: var(--text-muted);
  font-size: 24rpx;
}

.day-head__title {
  margin-top: 10rpx;
  color: var(--text-strong);
  font-size: 46rpx;
  font-weight: 850;
}

.day-head__date {
  margin-top: 10rpx;
  color: var(--text-main);
  font-size: 26rpx;
}

.day-head__cost {
  color: var(--teal);
  font-size: 34rpx;
  font-weight: 850;
}

.timeline {
  display: grid;
  gap: 22rpx;
}

.activity {
  display: grid;
  grid-template-columns: 98rpx 1fr;
  gap: 18rpx;
  width: 100%;
  text-align: left;
}

.activity__time {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 18rpx;
}

.activity__time text {
  color: var(--primary);
  font-size: 25rpx;
  font-weight: 800;
}

.activity__content {
  padding: 24rpx;
  border: 1rpx solid var(--line);
  border-radius: 24rpx;
  background: #fbfcff;
}

.activity__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18rpx;
}

.activity__title {
  color: var(--text-strong);
  font-size: 30rpx;
  font-weight: 800;
  line-height: 1.35;
}

.activity__price {
  color: var(--teal);
  font-size: 26rpx;
  font-weight: 800;
}

.activity__location,
.activity__desc {
  display: block;
  margin-top: 12rpx;
  color: var(--text-main);
  font-size: 25rpx;
  line-height: 1.55;
}

.activity__location {
  color: var(--text-muted);
}

.activity__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 18rpx;
}

.activity__tags text {
  padding: 8rpx 14rpx;
  border-radius: 999rpx;
  color: var(--primary);
  background: #eaf3ff;
  font-size: 22rpx;
}

.hotel {
  display: grid;
  gap: 12rpx;
}

.hotel__name {
  color: var(--text-strong);
  font-size: 32rpx;
  font-weight: 800;
}

.hotel__line,
.hotel__desc {
  color: var(--text-main);
  font-size: 26rpx;
  line-height: 1.55;
}

.hotel__price {
  color: var(--teal);
  font-size: 30rpx;
  font-weight: 800;
}
</style>
