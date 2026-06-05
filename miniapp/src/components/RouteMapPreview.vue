<template>
  <view class="route-map" :class="{ compact }">
    <view class="route-map__canvas">
      <view class="route-map__river route-map__river--a" />
      <view class="route-map__river route-map__river--b" />
      <view class="route-map__park" />
      <view class="route-map__roads">
        <view v-for="line in 8" :key="line" class="route-map__road" :class="`route-map__road--${line}`" />
      </view>

      <view class="route-map__legend">
        <view v-for="group in displayGroups" :key="group.key" class="route-map__legend-row">
          <view class="route-map__legend-line" :class="`route-map__legend-line--${group.color}`" />
          <text>DAY {{ group.dayNumber }}</text>
        </view>
      </view>

      <view
        v-for="group in displayGroups"
        :key="`${group.key}-path`"
        class="route-map__path"
        :class="[`route-map__path--${group.color}`, `route-map__path--shape-${group.shape}`]"
      />

      <view
        v-for="pin in pins"
        :key="pin.key"
        class="route-map__pin"
        :class="[`route-map__pin--${pin.color}`, `route-map__pin--${pin.position}`]"
      >
        <view class="route-map__pin-dot" />
        <text v-if="pin.label" class="route-map__label">{{ pin.label }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Activity, TripDay } from '@/types/trip'
import { dayRouteStops } from '@/utils/tripDisplay'

const props = defineProps<{
  activities?: Activity[]
  days?: TripDay[]
  title?: string
  kicker?: string
  compact?: boolean
}>()

const colors = ['teal', 'amber', 'coral'] as const
const positions = [
  'a',
  'b',
  'c',
  'd',
  'e',
  'f'
] as const

const displayGroups = computed(() => {
  if (props.days?.length) {
    return props.days.slice(0, 3).map((day, index) => ({
      key: day.date || `day-${index}`,
      dayNumber: index + 1,
      color: colors[index % colors.length],
      shape: index,
      activities: dayRouteStops(day).slice(0, 4)
    })).filter((group) => group.activities.length)
  }
  return [{
    key: 'single-route',
    dayNumber: 1,
    color: 'teal' as const,
    shape: 0,
    activities: (props.activities || []).slice(0, props.compact ? 4 : 6)
  }].filter((group) => group.activities.length)
})

const pins = computed(() => displayGroups.value.flatMap((group) =>
  group.activities.map((activity, index) => ({
    key: `${group.key}-${activity.id || index}`,
    color: group.color,
    position: `${group.shape}-${positions[index % positions.length]}`,
    label: index === 0 || index === group.activities.length - 1 ? activity.location || activity.title : ''
  }))
))
</script>

<style scoped lang="scss">
.route-map {
  overflow: hidden;
  border: 1rpx solid var(--line);
  border-radius: 22rpx;
  background: #ffffff;
}

.route-map__canvas {
  position: relative;
  height: 238rpx;
  overflow: hidden;
  border-radius: 20rpx;
  background: #f7fbff;
}

.compact .route-map__canvas {
  height: 210rpx;
}

.route-map__river {
  position: absolute;
  border-radius: 999rpx;
  background: rgba(77, 164, 232, 0.18);
}

.route-map__river--a {
  left: -72rpx;
  top: 72rpx;
  width: 390rpx;
  height: 58rpx;
  transform: rotate(-10deg);
}

.route-map__river--b {
  right: -86rpx;
  bottom: 30rpx;
  width: 340rpx;
  height: 72rpx;
  transform: rotate(17deg);
}

.route-map__park {
  position: absolute;
  right: -30rpx;
  top: 0;
  width: 260rpx;
  height: 238rpx;
  border-radius: 36% 0 0 44%;
  background: rgba(93, 190, 136, 0.16);
}

.route-map__road {
  position: absolute;
  height: 2rpx;
  border-radius: 999rpx;
  background: rgba(164, 180, 197, 0.28);
}

.route-map__road--1 { left: 40rpx; top: 42rpx; width: 390rpx; transform: rotate(7deg); }
.route-map__road--2 { left: 120rpx; top: 108rpx; width: 500rpx; transform: rotate(-3deg); }
.route-map__road--3 { left: -20rpx; top: 184rpx; width: 520rpx; transform: rotate(6deg); }
.route-map__road--4 { left: 170rpx; top: -20rpx; width: 2rpx; height: 320rpx; transform: rotate(8deg); }
.route-map__road--5 { left: 322rpx; top: -34rpx; width: 2rpx; height: 320rpx; transform: rotate(-7deg); }
.route-map__road--6 { right: 150rpx; top: -30rpx; width: 2rpx; height: 320rpx; transform: rotate(13deg); }
.route-map__road--7 { left: 62rpx; bottom: 40rpx; width: 320rpx; transform: rotate(-16deg); }
.route-map__road--8 { right: 12rpx; top: 74rpx; width: 230rpx; transform: rotate(30deg); }

.route-map__legend {
  position: absolute;
  left: 16rpx;
  top: 18rpx;
  z-index: 4;
  display: grid;
  gap: 10rpx;
  padding: 14rpx 16rpx;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12rpx 34rpx rgba(20, 32, 51, 0.08);
}

.route-map__legend-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.route-map__legend-row text {
  color: var(--text-main);
  font-size: 20rpx;
  font-weight: 750;
}

.route-map__legend-line {
  width: 30rpx;
  height: 8rpx;
  border-radius: 999rpx;
}

.route-map__legend-line--teal { background: #15aaa3; }
.route-map__legend-line--amber { background: #f59e0b; }
.route-map__legend-line--coral { background: #ff5c66; }

.route-map__path {
  position: absolute;
  z-index: 2;
  border-style: solid;
  border-color: transparent;
}

.route-map__path--teal { border-color: #15aaa3; }
.route-map__path--amber { border-color: #f59e0b; }
.route-map__path--coral { border-color: #ff5c66; }

.route-map__path--shape-0 {
  right: 108rpx;
  top: 34rpx;
  width: 220rpx;
  height: 116rpx;
  border-width: 8rpx 8rpx 0 0;
  border-radius: 40rpx 90rpx 0 0;
  transform: rotate(7deg);
}

.route-map__path--shape-1 {
  left: 222rpx;
  top: 76rpx;
  width: 220rpx;
  height: 108rpx;
  border-width: 0 0 8rpx 8rpx;
  border-radius: 0 0 86rpx 42rpx;
  transform: rotate(-12deg);
}

.route-map__path--shape-2 {
  left: 58rpx;
  bottom: 38rpx;
  width: 240rpx;
  height: 86rpx;
  border-width: 8rpx 0 0 8rpx;
  border-radius: 82rpx 0 0 38rpx;
  transform: rotate(5deg);
}

.route-map__pin {
  position: absolute;
  z-index: 3;
}

.route-map__pin-dot {
  width: 22rpx;
  height: 22rpx;
  border: 7rpx solid #ffffff;
  border-radius: 50%;
  box-shadow: 0 8rpx 18rpx rgba(20, 32, 51, 0.18);
}

.route-map__pin--teal .route-map__pin-dot { background: #15aaa3; }
.route-map__pin--amber .route-map__pin-dot { background: #f59e0b; }
.route-map__pin--coral .route-map__pin-dot { background: #ff5c66; }

.route-map__label {
  position: absolute;
  left: 28rpx;
  top: -8rpx;
  max-width: 138rpx;
  overflow: hidden;
  padding: 6rpx 10rpx;
  border-radius: 8rpx;
  color: var(--text-strong);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 8rpx 20rpx rgba(20, 32, 51, 0.1);
  font-size: 19rpx;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.route-map__pin--0-a { right: 150rpx; top: 26rpx; }
.route-map__pin--0-b { right: 92rpx; top: 82rpx; }
.route-map__pin--0-c { right: 188rpx; top: 126rpx; }
.route-map__pin--0-d { right: 282rpx; top: 92rpx; }
.route-map__pin--0-e { right: 212rpx; bottom: 34rpx; }
.route-map__pin--0-f { right: 72rpx; bottom: 46rpx; }

.route-map__pin--1-a { left: 238rpx; top: 82rpx; }
.route-map__pin--1-b { left: 292rpx; top: 136rpx; }
.route-map__pin--1-c { left: 390rpx; top: 112rpx; }
.route-map__pin--1-d { left: 452rpx; top: 62rpx; }
.route-map__pin--1-e { left: 338rpx; bottom: 36rpx; }
.route-map__pin--1-f { left: 508rpx; bottom: 68rpx; }

.route-map__pin--2-a { left: 62rpx; bottom: 56rpx; }
.route-map__pin--2-b { left: 112rpx; bottom: 96rpx; }
.route-map__pin--2-c { left: 190rpx; bottom: 72rpx; }
.route-map__pin--2-d { left: 274rpx; bottom: 112rpx; }
.route-map__pin--2-e { left: 326rpx; bottom: 52rpx; }
.route-map__pin--2-f { left: 140rpx; top: 64rpx; }
</style>
