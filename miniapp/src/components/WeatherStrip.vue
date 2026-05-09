<template>
  <view class="weather-strip">
    <view class="weather-strip__inner">
      <view v-for="(item, index) in weather.slice(0, 5)" :key="item.date" class="weather-card">
        <text class="weather-card__date">{{ dayLabel(item.date, index) }}</text>
        <text class="weather-card__icon">{{ weatherIcon(item.dayCondition || item.condition) }}</text>
        <text class="weather-card__temp">{{ item.high }}°/{{ item.low }}°</text>
        <text class="weather-card__condition">{{ item.dayCondition || item.condition }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { WeatherForecast } from '@/types/trip'

defineProps<{
  weather: WeatherForecast[]
}>()

const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const dayLabel = (value: string, index: number) => {
  if (index === 0) return '今天'
  if (index === 1) return '明天'
  if (index === 2) return '后天'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value.slice(5) : weekDays[date.getDay()]
}

const weatherIcon = (condition: string) => {
  if (/雨|阵雨|雷/.test(condition)) return '☔'
  if (/雪/.test(condition)) return '❄'
  if (/云|阴/.test(condition)) return '☁'
  if (/雾|霾/.test(condition)) return '≋'
  return '☀'
}
</script>

<style scoped lang="scss">
.weather-strip {
  width: 100%;
}

.weather-strip__inner {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  border: 1rpx solid var(--line);
  border-radius: 16rpx;
  background: #ffffff;
}

.weather-card {
  position: relative;
  box-sizing: border-box;
  min-width: 0;
  min-height: 132rpx;
  padding: 18rpx 6rpx 16rpx;
  text-align: center;
}

.weather-card + .weather-card {
  border-left: 1rpx solid var(--line);
}

.weather-card__date,
.weather-card__temp,
.weather-card__condition {
  display: block;
}

.weather-card__date {
  color: var(--text-strong);
  font-size: 22rpx;
  font-weight: 750;
}

.weather-card__temp {
  margin-top: 8rpx;
  color: var(--text-main);
  font-size: 20rpx;
}

.weather-card__icon {
  display: block;
  margin-top: 12rpx;
  color: var(--amber);
  font-size: 36rpx;
  line-height: 1;
}

.weather-card__condition {
  margin-top: 9rpx;
  color: var(--text-muted);
  font-size: 19rpx;
}
</style>
