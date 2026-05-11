<template>
  <view class="screen generating-page">
    <view class="summary-card">
      <view class="summary-card__content">
        <view class="summary-card__top">
          <view>
            <text class="summary-card__label">正在生成行程</text>
            <text class="summary-card__title">{{ draft?.destination || '目的地' }}</text>
          </view>
          <view class="summary-card__stamp">
            <text>{{ activeStepNumber }}</text>
            <text>/{{ tripStore.steps.length }}</text>
          </view>
        </view>

        <view class="summary-card__meta">
          <text>{{ draft?.days || 0 }} 天</text>
          <text>{{ draft?.travelers || 0 }} 人</text>
          <text>{{ activeText }}</text>
        </view>

        <view class="progress-track">
          <view class="progress-fill" :style="{ width: progressPercent + '%' }" />
        </view>
      </view>
    </view>

    <view class="steps-card">
      <view class="steps-card__head">
        <text>规划进度</text>
        <text>{{ progressPercent }}%</text>
      </view>
      <view v-for="(step, index) in tripStore.steps" :key="step.key" class="step">
        <view class="step__marker" :class="step.status">
          <text v-if="step.status === 'done'">✓</text>
          <text v-else>{{ index + 1 }}</text>
        </view>
        <view class="step__body">
          <text class="step__label">{{ step.label }}</text>
          <text class="step__state">{{ stateText(step.status) }}</text>
        </view>
      </view>
    </view>

    <view v-if="tripStore.error" class="error panel">
      <text class="error__title">生成失败</text>
      <text class="error__desc">{{ tripStore.error }}</text>
      <button class="primary-button" @tap="startGenerate">重新生成</button>
      <button class="secondary-button error__back" @tap="backToPlan">返回修改需求</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { storeToRefs } from 'pinia'
import { useTripStore } from '@/stores/tripStore'

const tripStore = useTripStore()
const { draft } = storeToRefs(tripStore)
const activeText = computed(() => tripStore.activeStepLabel)
const activeStepNumber = computed(() => Math.min(tripStore.activeStepIndex + 1, tripStore.steps.length))
const progressPercent = computed(() => {
  const total = Math.max(tripStore.steps.length, 1)
  const done = tripStore.steps.filter((step) => step.status === 'done').length
  const activeBonus = tripStore.steps.some((step) => step.status === 'active') ? 0.45 : 0
  return Math.min(100, Math.round(((done + activeBonus) / total) * 100))
})

onLoad(() => {
  tripStore.restoreLocal()
  startGenerate()
})

onUnload(() => {
  tripStore.stopLocalProgress()
})

const startGenerate = async () => {
  try {
    await tripStore.generateFromDraft()
    setTimeout(() => {
      uni.redirectTo({ url: '/pages/trip-detail/index' })
    }, 500)
  } catch (err) {
    uni.showToast({
      title: err instanceof Error ? err.message : '生成失败',
      icon: 'none',
      duration: 2400
    })
  }
}

const backToPlan = () => {
  uni.navigateBack()
}

const stateText = (status: string) => {
  if (status === 'done') return '已完成'
  if (status === 'active') return '进行中'
  if (status === 'error') return '失败'
  return '等待中'
}
</script>

<style scoped lang="scss">
.generating-page {
  display: grid;
  align-content: start;
  gap: 26rpx;
  padding: 28rpx 28rpx 64rpx;
  background: #f5f7fb;
}

.summary-card {
  position: relative;
  overflow: hidden;
  min-height: 278rpx;
  border-radius: 34rpx;
  background: linear-gradient(135deg, #0f172a 0%, #14345f 48%, #0f766e 100%);
  box-shadow: 0 28rpx 54rpx rgba(15, 23, 42, 0.18);
}

.summary-card__content {
  position: relative;
  z-index: 1;
  box-sizing: border-box;
  display: grid;
  gap: 28rpx;
  min-height: 278rpx;
  padding: 36rpx;
}

.summary-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
}

.summary-card__label,
.summary-card__title {
  display: block;
}

.summary-card__label {
  color: rgba(255, 255, 255, 0.72);
  font-size: 24rpx;
  font-weight: 750;
}

.summary-card__title {
  max-width: 420rpx;
  margin-top: 14rpx;
  overflow: hidden;
  color: #ffffff;
  font-size: 56rpx;
  font-weight: 950;
  line-height: 1.08;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-card__stamp {
  display: flex;
  align-items: baseline;
  justify-content: center;
  min-width: 104rpx;
  height: 74rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.26);
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  backdrop-filter: blur(18rpx);
}

.summary-card__stamp text:first-child {
  font-size: 36rpx;
  font-weight: 950;
}

.summary-card__stamp text:last-child {
  margin-left: 3rpx;
  color: rgba(255, 255, 255, 0.64);
  font-size: 22rpx;
  font-weight: 800;
}

.summary-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.summary-card__meta text {
  max-width: 320rpx;
  overflow: hidden;
  padding: 11rpx 18rpx;
  border-radius: 999rpx;
  color: #eaf7ff;
  background: rgba(255, 255, 255, 0.14);
  font-size: 23rpx;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-track {
  overflow: hidden;
  height: 14rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.2);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ffffff 0%, #99f6e4 100%);
  transition: width 240ms ease;
}

.steps-card {
  padding: 30rpx 26rpx;
  border: 1rpx solid #e8edf5;
  border-radius: 30rpx;
  background: #ffffff;
  box-shadow: 0 18rpx 42rpx rgba(15, 23, 42, 0.06);
}

.steps-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10rpx;
  padding: 0 4rpx 18rpx;
  border-bottom: 1rpx solid #edf1f6;
}

.steps-card__head text:first-child {
  color: #111827;
  font-size: 30rpx;
  font-weight: 900;
}

.steps-card__head text:last-child {
  color: #0f766e;
  font-size: 24rpx;
  font-weight: 900;
}

.step {
  display: flex;
  gap: 20rpx;
  padding: 20rpx 4rpx;
}

.step + .step {
  border-top: 1rpx solid #f0f3f7;
}

.step__marker {
  display: flex;
  flex: 0 0 54rpx;
  align-items: center;
  justify-content: center;
  width: 54rpx;
  height: 54rpx;
  border-radius: 50%;
  color: #7a8494;
  background: #f5f7fb;
  font-size: 22rpx;
  font-weight: 800;
}

.step__marker.active {
  color: #ffffff;
  background: #0f766e;
  box-shadow: 0 10rpx 22rpx rgba(15, 118, 110, 0.22);
}

.step__marker.done {
  color: #ffffff;
  background: #111827;
}

.step__marker.error {
  color: #ffffff;
  background: var(--danger);
}

.step__body {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
}

.step__label {
  color: #111827;
  font-size: 29rpx;
  font-weight: 850;
}

.step__state {
  flex-shrink: 0;
  color: #7a8494;
  font-size: 23rpx;
  font-weight: 700;
}

.error {
  display: grid;
  gap: 18rpx;
  padding: 30rpx;
  border: 1rpx solid #fee2e2;
  border-radius: 28rpx;
  background: #ffffff;
}

.error__title {
  color: var(--danger);
  font-size: 32rpx;
  font-weight: 800;
}

.error__desc {
  color: var(--text-main);
  font-size: 26rpx;
  line-height: 1.5;
}

.error__back {
  margin-top: 4rpx;
}
</style>
