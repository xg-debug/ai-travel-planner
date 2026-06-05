<template>
  <view v-if="activity" :class="['screen place-detail', themeStore.themeClass]">
    <view class="place-card panel">
      <text class="place-card__type">{{ isTransportActivity ? '交通' : activityTypeLabel(activity.type) }}</text>
      <text class="place-card__title">{{ isTransportActivity ? activity.title : activity.location || activity.title }}</text>
      <text class="place-card__desc">{{ activity.description }}</text>
      <view class="place-card__meta">
        <text>{{ activity.time }}</text>
        <text>{{ isTransportActivity ? `#${activity.duration}分钟` : `${activity.duration} 分钟` }}</text>
        <text>{{ formatMoney(activity.cost) }}</text>
      </view>
    </view>

    <template v-if="isTransportActivity">
      <SectionPanel v-if="bestTransportOption" title="最佳交通方式">
        <view class="transport-option transport-option--best">
          <text class="transport-option__line">{{ transportOptionLine(bestTransportOption) }}</text>
          <text class="transport-option__time">{{ transportOptionTime(bestTransportOption) }}</text>
          <text class="transport-option__price">{{ transportOptionPrice(bestTransportOption) }}</text>
          <text v-if="bestTransportOption.reason" class="transport-option__reason">{{ bestTransportOption.reason }}</text>
        </view>
      </SectionPanel>

      <SectionPanel v-if="candidateTransportOptions.length" title="候选交通方式">
        <view class="transport-options">
          <view
            v-for="(option, index) in candidateTransportOptions"
            :key="`${option.mode}_${index}`"
            class="transport-option"
          >
            <text class="transport-option__line">{{ index + 1 }}、{{ transportOptionLine(option) }}</text>
            <text class="transport-option__time">{{ transportOptionTime(option) }}</text>
            <text class="transport-option__price">{{ transportOptionPrice(option) }}</text>
            <text v-if="option.reason" class="transport-option__reason">{{ option.reason }}</text>
          </view>
        </view>
      </SectionPanel>
    </template>

    <SectionPanel v-else title="实用信息">
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
      v-if="!isTransportActivity && activity.coordinates"
      class="primary-button"
      @tap="openLocation"
    >
      打开地图位置
    </button>
  </view>

  <view v-else :class="['screen', themeStore.themeClass]">
    <EmptyState title="没有找到地点" description="返回当天行程后重新打开地点详情。" action-text="返回" @action="back" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import SectionPanel from '@/components/SectionPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useTripStore } from '@/stores/tripStore'
import { useThemeStore } from '@/stores/themeStore'
import { activityTypeLabel, formatMoney } from '@/utils/format'
import type { TransportOption } from '@/types/trip'

const tripStore = useTripStore()
const themeStore = useThemeStore()
const dayIndex = ref(0)
const activityIndex = ref(0)
const activity = computed(() => tripStore.currentTrip?.days[dayIndex.value]?.activities[activityIndex.value])
const isTransportActivity = computed(() => Boolean(activity.value?.isIntercityTransport))
const bestTransportOption = computed<TransportOption | undefined>(() => {
  if (!activity.value || !isTransportActivity.value) return undefined
  return activity.value.bestTransportOption || activity.value.transportOptions?.[0] || {
    mode: activity.value.transportation || '交通待确认',
    fromTerminal: activity.value.fromTerminal || activity.value.location?.split(' - ')[0] || '',
    toTerminal: activity.value.toTerminal || activity.value.location?.split(' - ')[1] || '',
    departureDatetime: activity.value.departureDatetime,
    arrivalDatetime: activity.value.arrivalDatetime,
    durationMinutes: activity.value.duration,
    durationText: `${activity.value.duration}分钟`,
    costPerPerson: activity.value.costPerPerson || 0,
    totalCost: activity.value.totalCost || activity.value.cost,
    currency: 'CNY'
  }
})
const candidateTransportOptions = computed(() => {
  const source = activity.value?.transportAlternatives?.length
    ? activity.value.transportAlternatives
    : activity.value?.transportOptions?.slice(1) || []
  const bestKey = bestTransportOption.value ? transportOptionKey(bestTransportOption.value) : ''
  return source.filter((option) => transportOptionKey(option) !== bestKey)
})

onLoad((query) => {
  dayIndex.value = Number(query?.day || 0)
  activityIndex.value = Number(query?.activity || 0)
})

onShow(() => {
  tripStore.restoreLocal()
  themeStore.restore()
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

const transportOptionLine = (option: TransportOption) => {
  const route = [option.fromTerminal, option.toTerminal].filter(Boolean).join(' - ')
  return [option.mode, route].filter(Boolean).join('  ')
}

const transportOptionTime = (option: TransportOption) => {
  if (option.departureDatetime && option.arrivalDatetime) {
    return `${option.departureDatetime} - ${option.arrivalDatetime}`
  }
  return option.durationText || `${option.durationMinutes}分钟`
}

const transportOptionPrice = (option: TransportOption) =>
  option.costPerPerson ? `${formatMoney(option.costPerPerson)}/人` : '费用待确认'

const transportOptionKey = (option: TransportOption) =>
  `${option.mode}|${option.fromTerminal}|${option.toTerminal}|${option.departureDatetime || ''}`

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

.transport-options {
  display: grid;
  gap: 18rpx;
}

.transport-option {
  display: grid;
  gap: 10rpx;
  padding: 22rpx;
  border: 1rpx solid var(--line);
  border-radius: 18rpx;
  background: #fbfcff;
}

.transport-option--best {
  background: #f7fafc;
}

.transport-option__line {
  color: var(--text-strong);
  font-size: 28rpx;
  font-weight: 850;
  line-height: 1.4;
}

.transport-option__time {
  color: var(--text-main);
  font-size: 24rpx;
  line-height: 1.5;
}

.transport-option__price {
  color: var(--teal);
  font-size: 26rpx;
  font-weight: 800;
}

.transport-option__reason {
  color: var(--text-muted);
  font-size: 23rpx;
  line-height: 1.55;
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
