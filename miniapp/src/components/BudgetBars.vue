<template>
  <view class="budget-summary">
    <view class="budget-grid">
      <view v-for="item in visibleCategories" :key="item.name" class="budget-item">
        <text class="budget-item__icon" :class="`budget-item__icon--${iconKey(item.name)}`">
          {{ iconOf(item.name) }}
        </text>
        <text class="budget-item__name">{{ item.name }}</text>
        <text class="budget-item__amount">{{ formatMoney(item.amount) }}</text>
      </view>
    </view>
    <view class="budget-total">
      <text>总计</text>
      <text>{{ formatMoney(totalAmount) }}</text>
    </view>
    <view class="budget-tip">
      <text>小贴士：提前预订门票和酒店可节省约15%费用</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BudgetCategory } from '@/types/trip'
import { formatMoney } from '@/utils/format'

const props = defineProps<{
  categories: BudgetCategory[]
}>()

const visibleCategories = computed(() => props.categories.filter((item) => Number(item.amount) > 0).slice(0, 5))
const totalAmount = computed(() => visibleCategories.value.reduce((sum, item) => sum + Number(item.amount || 0), 0))

const iconOf = (name: string) => {
  if (/交通/.test(name)) return '交'
  if (/住宿|酒店/.test(name)) return '住'
  if (/门票|景点/.test(name)) return '票'
  if (/餐|食/.test(name)) return '餐'
  if (/购物/.test(name)) return '购'
  return '其'
}

const iconKey = (name: string) => {
  if (/交通/.test(name)) return 'transport'
  if (/住宿|酒店/.test(name)) return 'hotel'
  if (/门票|景点/.test(name)) return 'ticket'
  if (/餐|食/.test(name)) return 'food'
  if (/购物/.test(name)) return 'shop'
  return 'other'
}
</script>

<style scoped lang="scss">
.budget-summary {
  display: grid;
  overflow: hidden;
  border: 1rpx solid var(--line);
  border-radius: 16rpx;
  background: #ffffff;
}

.budget-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.budget-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 118rpx;
  padding: 16rpx 4rpx;
  text-align: center;
}

.budget-item + .budget-item {
  border-left: 1rpx solid var(--line);
}

.budget-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42rpx;
  height: 42rpx;
  border-radius: 13rpx;
  color: #ffffff;
  font-size: 21rpx;
  font-weight: 850;
}

.budget-item__icon--transport { background: #22b8b2; }
.budget-item__icon--hotel { background: #ff8a00; }
.budget-item__icon--ticket { background: #2d7ff9; }
.budget-item__icon--food { background: #ef5372; }
.budget-item__icon--shop { background: #f6b51d; }
.budget-item__icon--other { background: #8c9aac; }

.budget-item__name,
.budget-item__amount {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.budget-item__name {
  margin-top: 10rpx;
  color: var(--text-main);
  font-size: 20rpx;
}

.budget-item__amount {
  margin-top: 6rpx;
  color: var(--text-strong);
  font-size: 21rpx;
  font-weight: 800;
}

.budget-total {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 14rpx;
  padding: 0 22rpx 18rpx;
}

.budget-total text:first-child {
  color: var(--text-muted);
  font-size: 22rpx;
}

.budget-total text:last-child {
  color: #ef3030;
  font-size: 38rpx;
  font-weight: 900;
}

.budget-tip {
  padding: 14rpx 22rpx;
  color: #0fa29a;
  background: #edf9f8;
  font-size: 22rpx;
}
</style>
