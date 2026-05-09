<template>
  <view class="rec-grid">
    <button
      v-for="(item, index) in items.slice(0, 4)"
      :key="item.id || item.name"
      class="rec-card"
      :class="variant"
      @tap="$emit('open', item)"
    >
      <view class="rec-card__visual">
        <image :src="coverOf(item, index)" mode="aspectFill" />
        <text v-if="index < 2" class="rec-card__tag">{{ tagOf(item) }}</text>
      </view>
      <view class="rec-card__body">
        <text class="rec-card__title">{{ item.name }}</text>
        <text class="rec-card__desc">{{ item.description }}</text>
        <view class="rec-card__meta">
          <text v-if="item.rating">{{ item.rating.toFixed(1) }}分</text>
          <text>{{ priceOf(item) }}</text>
        </view>
      </view>
    </button>
  </view>
</template>

<script setup lang="ts">
import type { POI } from '@/types/trip'

defineProps<{
  items: POI[]
  variant?: 'attraction' | 'food' | 'hotel'
}>()

defineEmits<{
  open: [item: POI]
}>()

const fallbackImages = {
  attraction: [
    '/static/recommendations/attraction-1.png',
    '/static/recommendations/attraction-2.png'
  ],
  food: [
    '/static/recommendations/food-1.png',
    '/static/recommendations/food-2.png'
  ],
  hotel: [
    '/static/recommendations/hotel-1.png',
    '/static/recommendations/hotel-2.png'
  ]
}

const coverOf = (item: POI, index: number) => {
  if (item.images?.[0]) return item.images[0]
  const group = item.type === 'restaurant'
    ? fallbackImages.food
    : item.type === 'hotel'
      ? fallbackImages.hotel
      : fallbackImages.attraction
  return group[index % group.length]
}

const tagOf = (item: POI) => {
  if (item.type === 'restaurant') return '美食'
  if (item.type === 'hotel') return '优选'
  if (item.type === 'museum') return '人文'
  if (item.type === 'park') return '自然'
  return '推荐'
}

const priceOf = (item: POI) => {
  if (item.priceText) return item.priceText
  if (item.priceRange === 'free') return '免费'
  const map: Record<string, string> = {
    '$': '经济',
    '$$': '中档',
    '$$$': '舒适',
    '$$$$': '高端'
  }
  return map[item.priceRange] || '待查'
}
</script>

<style scoped lang="scss">
.rec-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14rpx;
}

.rec-card {
  display: block;
  min-width: 0;
  overflow: hidden;
  border: 1rpx solid var(--line);
  border-radius: 16rpx;
  background: #ffffff;
  text-align: left;
}

.rec-card__visual {
  position: relative;
  height: 118rpx;
  overflow: hidden;
  background: #edf4ff;
}

.food .rec-card__visual {
  background: #fff4dc;
}

.hotel .rec-card__visual {
  background: #f0effa;
}

.rec-card__visual image {
  width: 100%;
  height: 100%;
}

.rec-card__tag {
  position: absolute;
  left: 10rpx;
  top: 10rpx;
  padding: 5rpx 10rpx;
  border-radius: 10rpx;
  color: #ffffff;
  background: rgba(17, 24, 39, 0.78);
  font-size: 18rpx;
  font-weight: 800;
}

.rec-card__body {
  padding: 14rpx;
}

.rec-card__title,
.rec-card__desc {
  display: block;
  overflow: hidden;
}

.rec-card__title {
  color: var(--text-strong);
  font-size: 24rpx;
  font-weight: 850;
  line-height: 1.32;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-card__desc {
  display: -webkit-box;
  min-height: 60rpx;
  margin-top: 8rpx;
  color: var(--text-muted);
  font-size: 20rpx;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.rec-card__meta {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 10rpx;
}

.rec-card__meta text {
  min-width: 0;
  overflow: hidden;
  color: var(--text-main);
  font-size: 20rpx;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-card__meta text:first-child {
  color: var(--teal);
}
</style>
