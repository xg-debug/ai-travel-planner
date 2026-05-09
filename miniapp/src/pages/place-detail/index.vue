<template>
  <view v-if="activity" class="screen place-detail">
    <view class="place-card panel">
      <text class="place-card__type">{{ activityTypeLabel(activity.type) }}</text>
      <text class="place-card__title">{{ activity.location || activity.title }}</text>
      <text class="place-card__desc">{{ activity.description }}</text>
      <view class="place-card__meta">
        <text>{{ activity.time }}</text>
        <text>{{ activity.duration }} 分钟</text>
        <text>{{ formatMoney(activity.cost) }}</text>
      </view>
    </view>

    <SectionPanel title="实用信息">
      <view class="info-list">
        <view class="info-row">
          <text>活动名称</text>
          <text>{{ activity.title }}</text>
        </view>
        <view v-if="activity.ticketLabel" class="info-row">
          <text>门票</text>
          <text>{{ activity.ticketLabel }}</text>
        </view>
        <view v-if="activity.notes" class="info-row info-row--block">
          <text>提示</text>
          <text>{{ activity.notes }}</text>
        </view>
      </view>
    </SectionPanel>

    <button
      v-if="activity.coordinates"
      class="primary-button"
      @tap="openLocation"
    >
      打开地图位置
    </button>
  </view>

  <view v-else class="screen">
    <EmptyState title="没有找到地点" description="返回当天行程后重新打开地点详情。" action-text="返回" @action="back" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import SectionPanel from '@/components/SectionPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useTripStore } from '@/stores/tripStore'
import { activityTypeLabel, formatMoney } from '@/utils/format'

const tripStore = useTripStore()
const dayIndex = ref(0)
const activityIndex = ref(0)
const activity = computed(() => tripStore.currentTrip?.days[dayIndex.value]?.activities[activityIndex.value])

onLoad((query) => {
  dayIndex.value = Number(query?.day || 0)
  activityIndex.value = Number(query?.activity || 0)
})

onShow(() => {
  tripStore.restoreLocal()
})

const openLocation = () => {
  if (!activity.value?.coordinates) return
  uni.openLocation({
    latitude: activity.value.coordinates.lat,
    longitude: activity.value.coordinates.lng,
    name: activity.value.location || activity.value.title,
    address: activity.value.location
  })
}

const back = () => {
  uni.navigateBack()
}
</script>

<style scoped lang="scss">
.place-detail {
  display: grid;
  align-content: start;
  gap: 24rpx;
}

.place-card {
  padding: 36rpx;
}

.place-card__type,
.place-card__title,
.place-card__desc {
  display: block;
}

.place-card__type {
  color: var(--primary);
  font-size: 24rpx;
  font-weight: 800;
}

.place-card__title {
  margin-top: 14rpx;
  color: var(--text-strong);
  font-size: 44rpx;
  font-weight: 850;
  line-height: 1.18;
}

.place-card__desc {
  margin-top: 22rpx;
  color: var(--text-main);
  font-size: 27rpx;
  line-height: 1.65;
}

.place-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 26rpx;
}

.place-card__meta text {
  padding: 10rpx 16rpx;
  border-radius: 999rpx;
  color: var(--primary);
  background: #eaf3ff;
  font-size: 24rpx;
  font-weight: 650;
}

.info-list {
  display: grid;
  gap: 18rpx;
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 22rpx;
  color: var(--text-main);
  font-size: 26rpx;
}

.info-row text:first-child {
  flex: 0 0 150rpx;
  color: var(--text-muted);
}

.info-row text:last-child {
  flex: 1;
  text-align: right;
}

.info-row--block {
  display: block;
}

.info-row--block text {
  display: block;
  text-align: left !important;
}

.info-row--block text:last-child {
  margin-top: 10rpx;
  line-height: 1.55;
}
</style>
