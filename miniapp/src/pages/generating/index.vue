<template>
  <view class="screen generating-page">
    <view class="summary panel">
      <text class="summary__eyebrow">AI 正在规划</text>
      <text class="summary__title">{{ draft?.destination || '目的地' }}</text>
      <text class="summary__desc">
        {{ draft?.days || 0 }} 天 · {{ draft?.travelers || 0 }} 人 · {{ activeText }}
      </text>
    </view>

    <view class="steps panel">
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
  gap: 24rpx;
}

.summary {
  padding: 34rpx;
  background: var(--text-strong);
}

.summary__eyebrow,
.summary__title,
.summary__desc {
  display: block;
  color: #ffffff;
}

.summary__eyebrow {
  font-size: 24rpx;
  opacity: 0.82;
}

.summary__title {
  margin-top: 14rpx;
  font-size: 48rpx;
  font-weight: 850;
}

.summary__desc {
  margin-top: 12rpx;
  font-size: 27rpx;
  opacity: 0.9;
}

.steps {
  padding: 28rpx;
}

.step {
  display: flex;
  gap: 22rpx;
  padding: 18rpx 0;
}

.step + .step {
  border-top: 1rpx solid var(--line);
}

.step__marker {
  display: flex;
  flex: 0 0 52rpx;
  align-items: center;
  justify-content: center;
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  color: #111827;
  background: #f4f4f6;
  font-size: 22rpx;
  font-weight: 800;
}

.step__marker.active {
  color: #ffffff;
  background: #111827;
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
  color: var(--text-strong);
  font-size: 28rpx;
  font-weight: 700;
}

.step__state {
  color: var(--text-muted);
  font-size: 23rpx;
}

.error {
  display: grid;
  gap: 18rpx;
  padding: 30rpx;
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
