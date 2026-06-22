<template>
  <view class="rec-grid">
    <button
      v-for="(item, index) in displayItems"
      :key="item.id || item.name"
      class="rec-card"
      :class="variantClass"
      @tap="$emit('open', item)"
    >
      <view class="rec-card__visual">
        <image :src="coverOf(item, index)" mode="aspectFill" @error="markCoverFailed(item, index)" />
        <text v-if="index < 2" class="rec-card__tag">{{ tagOf(item) }}</text>
      </view>
      <view class="rec-card__body">
        <text class="rec-card__title">{{ item.name }}</text>
        <text class="rec-card__desc">{{ descriptionOf(item) }}</text>
        <view class="rec-card__meta">
          <text v-if="item.rating">{{ item.rating.toFixed(1) }}分</text>
          <text>{{ priceOf(item) }}</text>
        </view>
      </view>
    </button>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import type { POI } from '@/types/trip'

const props = withDefaults(defineProps<{
  items: POI[]
  variant?: 'attraction' | 'food' | 'hotel'
}>(), {
  variant: 'attraction'
})

defineEmits<{
  open: [item: POI]
}>()

const fallbackImages: Record<string, string[]> = {
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

const failedCovers = reactive<Record<string, boolean>>({})

const variantClass = computed(() => props.variant)
const displayItems = computed(() => uniqueDisplayItems(props.items).slice(0, 4))

const coverOf = (item: POI, index: number) => {
  const image = normalizeCoverUrl(item.images?.[0])
  if (image && !failedCovers[coverKey(item, index)] && !isRepeatedImage(image, item, index)) return image
  return fallbackOf(item, index)
}

const markCoverFailed = (item: POI, index: number) => {
  failedCovers[coverKey(item, index)] = true
}

const coverKey = (item: POI, index: number) => `${item.id || item.name || 'poi'}_${index}`

const normalizeCoverUrl = (url?: string) => {
  const text = String(url || '').trim()
  if (!text) return ''
  if (text.startsWith('//')) return `https:${text}`
  return text
}

const fallbackOf = (item: POI, index: number) => {
  const group = item.type === 'restaurant'
    ? fallbackImages.food
    : item.type === 'hotel'
      ? fallbackImages.hotel
      : fallbackImages.attraction
  return group[index % group.length]
}

const isRepeatedImage = (image: string, item: POI, index: number) => {
  const normalized = normalizeCoverUrl(image)
  if (!normalized) return false
  return displayItems.value.slice(0, index).some((previous, previousIndex) => {
    if (canonicalPoiKey(previous) === canonicalPoiKey(item)) return true
    const previousImage = normalizeCoverUrl(previous.images?.[0])
    return previousImage && previousImage === normalized && !failedCovers[coverKey(previous, previousIndex)]
  })
}

const uniqueDisplayItems = (items: POI[]) => {
  const seen = new Set<string>()
  const result: POI[] = []
  for (const item of items || []) {
    const key = canonicalPoiKey(item)
    if (!key || seen.has(key)) continue
    seen.add(key)
    result.push(item)
  }
  return result
}

const canonicalPoiKey = (item: POI) => {
  const name = compactText(item.name)
    .replace(/^(杭州|郑州|北京|上海|广州|深圳|南京|苏州|成都|重庆|西安|天津)/, '')
    .replace(/\s+/g, '')
  if (!name) return ''
  const parent = name.split(/[-—–·]/)[0]
  if (/风景名胜区|风景区|景区|公园|度假区|古镇|古城/.test(parent)) return parent
  return name.replace(/游客中心|售票处|停车场|入口|出口|服务中心/g, '')
}

const tagOf = (item: POI) => {
  if (item.type === 'restaurant') return '美食'
  if (item.type === 'hotel') return '优选'
  if (item.type === 'museum') return '人文'
  if (item.type === 'park') return '自然'
  return '推荐'
}

const descriptionOf = (item: POI) => {
  const address = compactText(item.address)
  const name = compactText(item.name)
  const description = compactText(item.description)
    .replace(new RegExp(`^${escapeRegExp(name)}(位于|位於)?`, 'i'), '')
    .replace(/^位于|^位於/, '')
    .trim()

  const withoutRepeatedAddress = address
    ? description
        .replace(new RegExp(escapeRegExp(address), 'g'), '')
        .replace(/[；;，,\s]*$/, '')
        .trim()
    : description

  if (withoutRepeatedAddress && withoutRepeatedAddress.length >= 8) return withoutRepeatedAddress
  return address || item.category || tagOf(item)
}

const compactText = (value?: string) =>
  String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/([；;，,。])\s*\1+/g, '$1')
    .replace(/^[；;，,。\s]+|[；;，,。\s]+$/g, '')
    .trim()

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const priceOf = (item: POI) => {
  if (item.type === 'hotel') return item.priceText || item.referencePriceRange || '参考价待查'
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

.rec-card__title {
  display: block;
  overflow: hidden;
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
