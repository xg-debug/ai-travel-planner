<template>
  <main class="auth-page">
    <section class="auth-visual" aria-hidden="true">
      <div class="auth-visual__map">
        <span class="map-point map-point--primary"></span>
        <span class="map-point map-point--secondary"></span>
        <span class="map-point map-point--accent"></span>
        <span class="map-route map-route--a"></span>
        <span class="map-route map-route--b"></span>
        <div class="auth-visual__panel">
          <p>Admin Console</p>
          <strong>旅行平台运行中枢</strong>
          <div class="visual-metrics">
            <span style="height: 42%"></span>
            <span style="height: 68%"></span>
            <span style="height: 88%"></span>
            <span style="height: 58%"></span>
            <span style="height: 76%"></span>
          </div>
        </div>
      </div>
    </section>

    <a-card class="auth-card" :bordered="false">
      <div class="auth-brand">
        <div class="brand-mark">AI</div>
        <div>
          <p>AI Travel Planner</p>
          <h1>管理后台</h1>
        </div>
      </div>

      <a-tabs v-model:active-key="mode" class="auth-tabs">
        <a-tab-pane key="login" tab="登录" />
        <a-tab-pane key="register" tab="注册账号" />
      </a-tabs>

      <a-alert
        v-if="authStore.error"
        class="auth-alert"
        type="error"
        :message="authStore.error"
        show-icon
      />

      <a-form layout="vertical" :model="form" @finish="handleSubmit">
        <a-form-item
          label="邮箱"
          name="email"
          :rules="[{ required: true, message: '请输入邮箱' }, { type: 'email', message: '邮箱格式不正确' }]"
        >
          <a-input v-model:value="form.email" size="large" autocomplete="email" placeholder="admin@example.com">
            <template #prefix>
              <MailOutlined />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item
          label="密码"
          name="password"
          :rules="[{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少 6 位' }]"
        >
          <a-input-password
            v-model:value="form.password"
            size="large"
            autocomplete="current-password"
            placeholder="至少 6 位"
          >
            <template #prefix>
              <LockOutlined />
            </template>
          </a-input-password>
        </a-form-item>

        <a-form-item v-if="mode === 'register'" label="姓名" name="name">
          <a-input v-model:value="form.name" size="large" autocomplete="name" placeholder="系统管理员">
            <template #prefix>
              <UserOutlined />
            </template>
          </a-input>
        </a-form-item>

        <div class="auth-options">
          <a-checkbox v-model:checked="form.rememberMe">保持登录</a-checkbox>
        </div>

        <a-button
          block
          size="large"
          type="primary"
          html-type="submit"
          :loading="authStore.isLoading"
        >
          {{ mode === 'register' ? '注册并进入后台' : '进入后台' }}
        </a-button>
      </a-form>
    </a-card>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/authStore'

type AuthMode = 'login' | 'register'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const mode = ref<AuthMode>('login')

const form = reactive({
  email: '',
  password: '',
  name: '',
  rememberMe: true
})

const handleSubmit = async () => {
  if (mode.value === 'register') {
    await authStore.register(form.email, form.password, form.name, form.rememberMe)
    message.success('账号已创建')
  } else {
    await authStore.login(form.email, form.password, form.rememberMe)
    message.success('登录成功')
  }

  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/overview'
  await router.replace(redirect)
}
</script>
