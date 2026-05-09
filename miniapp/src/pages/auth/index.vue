<template>
  <view class="screen auth-page">
    <view class="auth-head">
      <text class="page-title">{{ mode === 'login' ? '欢迎回来' : '创建账号' }}</text>
      <text class="page-subtitle">同步行程、保存草稿，也方便在多端继续查看旅行方案。</text>
    </view>

    <view class="auth-panel panel">
      <view class="mode-switch">
        <button :class="{ active: mode === 'login' }" @tap="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @tap="mode = 'register'">注册</button>
      </view>

      <view class="fields">
        <view v-if="mode === 'register'">
          <text class="field-label">昵称</text>
          <input v-model="name" class="text-field" placeholder="你的名字" />
        </view>
        <view>
          <text class="field-label">邮箱</text>
          <input v-model="email" class="text-field" type="text" placeholder="you@example.com" />
        </view>
        <view>
          <text class="field-label">密码</text>
          <input v-model="password" class="text-field" type="password" placeholder="至少 6 位" />
        </view>
      </view>

      <button class="primary-button" :disabled="authStore.isLoading" @tap="submit">
        {{ authStore.isLoading ? '处理中...' : mode === 'login' ? '登录' : '注册并登录' }}
      </button>

      <view class="auth-note">
        <text>账号仅用于保存你的旅行计划，未登录也可以先生成本地行程。</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const authStore = useAuthStore()
const mode = ref<'login' | 'register'>('login')
const name = ref('')
const email = ref('')
const password = ref('')

const submit = async () => {
  if (!email.value || password.value.length < 6) {
    uni.showToast({ title: '请填写邮箱和至少 6 位密码', icon: 'none' })
    return
  }
  try {
    if (mode.value === 'login') {
      await authStore.login(email.value, password.value)
    } else {
      await authStore.register(email.value, password.value, name.value || email.value.split('@')[0])
    }
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 500)
  } catch (err) {
    uni.showToast({
      title: err instanceof Error ? err.message : '操作失败',
      icon: 'none',
      duration: 2400
    })
  }
}
</script>

<style scoped lang="scss">
.auth-page {
  display: grid;
  align-content: start;
  gap: 24rpx;
  background: var(--app-bg);
}

.auth-head {
  padding: 42rpx 4rpx 10rpx;
}

.auth-panel {
  display: grid;
  gap: 30rpx;
  padding: 28rpx;
}

.mode-switch {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10rpx;
  padding: 8rpx;
  border-radius: 18rpx;
  background: #eef2f6;
}

.mode-switch button {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 74rpx;
  border-radius: 14rpx;
  color: var(--text-muted);
  font-size: 27rpx;
  font-weight: 750;
}

.mode-switch button.active {
  color: var(--text-strong);
  background: #ffffff;
  box-shadow: var(--shadow-soft);
}

.fields {
  display: grid;
  gap: 24rpx;
}

.auth-note {
  padding: 18rpx 20rpx;
  border-radius: 16rpx;
  color: var(--text-muted);
  background: #f6f7f9;
  font-size: 23rpx;
  line-height: 1.5;
}
</style>
