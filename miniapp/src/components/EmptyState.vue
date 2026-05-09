<template>
  <view class="empty panel">
    <view class="empty__mark">{{ mark || 'AI' }}</view>
    <text class="empty__title">{{ title }}</text>
    <text class="empty__desc">{{ description }}</text>
    <button v-if="actionText" class="primary-button empty__button" @tap="$emit('action')">
      {{ actionText }}
    </button>
  </view>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description: string
  actionText?: string
  mark?: string
}>()

defineEmits<{
  action: []
}>()
</script>

<style scoped lang="scss">
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56rpx 34rpx;
  text-align: center;
}

.empty__mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 112rpx;
  height: 112rpx;
  border-radius: 32rpx;
  color: #ffffff;
  background: var(--text-strong);
  font-size: 30rpx;
  font-weight: 800;
}

.empty__title {
  margin-top: 28rpx;
  color: var(--text-strong);
  font-size: 34rpx;
  font-weight: 800;
}

.empty__desc {
  margin-top: 14rpx;
  color: var(--text-muted);
  font-size: 26rpx;
  line-height: 1.55;
}

.empty__button {
  width: 100%;
  margin-top: 34rpx;
}
</style>
