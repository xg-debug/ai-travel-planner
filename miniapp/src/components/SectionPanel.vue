<template>
  <view class="section panel">
    <view class="section__head" v-if="title || subtitle">
      <view>
        <text v-if="title" class="section__title">{{ title }}</text>
        <text v-if="subtitle" class="section__subtitle">{{ subtitle }}</text>
      </view>
      <slot name="action" />
    </view>
    <slot />
  </view>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
}>()
</script>

<style scoped lang="scss">
.section {
  padding: 26rpx;
}

.section__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
  margin-bottom: 22rpx;
}

.section__title {
  display: block;
  color: var(--text-strong);
  font-size: 31rpx;
  font-weight: 850;
}

.section__subtitle {
  display: block;
  margin-top: 8rpx;
  color: var(--text-muted);
  font-size: 24rpx;
  line-height: 1.45;
}
</style>
