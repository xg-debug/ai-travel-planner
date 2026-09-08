<template>
  <header class="site-header">
    <div class="site-header__inner">
      <router-link to="/" class="brand" aria-label="智能旅行规划首页">
        <span class="brand__mark">✦</span>
        <span class="brand__copy">
          <strong>随心游</strong>
          <small>AI TRAVEL PLANNER</small>
        </span>
      </router-link>

      <nav class="site-nav" aria-label="主要导航">
        <router-link to="/" exact-active-class="is-active">规划行程</router-link>
        <router-link to="/map" active-class="is-active">旅行地图</router-link>
        <router-link v-if="authStore.isAuthenticated" to="/history" active-class="is-active">我的行程</router-link>
        <button v-else type="button" @click="emit('auth', 'login')">我的行程</button>
      </nav>

      <div class="account-actions">
        <template v-if="!authStore.isAuthenticated">
          <button class="account-actions__text" type="button" @click="emit('auth', 'login')">登录</button>
          <button class="account-actions__primary" type="button" @click="emit('auth', 'register')">注册</button>
        </template>
        <template v-else>
          <span class="account-actions__user">{{ authStore.user?.name || '旅行者' }}</span>
          <button class="account-actions__text" type="button" @click="authStore.logout">退出</button>
        </template>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/authStore'

const emit = defineEmits<{
  (event: 'auth', mode: 'login' | 'register'): void
}>()
const authStore = useAuthStore()
</script>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 40;
  border-bottom: 1px solid rgba(226, 232, 240, 0.86);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(18px);
}
.site-header__inner {
  width: min(1180px, calc(100% - 40px));
  height: 72px;
  display: grid;
  grid-template-columns: minmax(210px, 1fr) auto minmax(210px, 1fr);
  align-items: center;
  gap: 24px;
  margin: 0 auto;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  width: fit-content;
  color: #111827;
  text-decoration: none;
}
.brand__mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: #fff;
  background: #111827;
  font-size: 18px;
  box-shadow: 0 8px 18px rgba(17, 24, 39, 0.14);
}
.brand__copy strong,
.brand__copy small { display: block; }
.brand__copy strong { font-size: 17px; font-weight: 900; letter-spacing: .02em; }
.brand__copy small { margin-top: 2px; color: #8a94a3; font-size: 9px; font-weight: 800; letter-spacing: .13em; }
.site-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px;
  border-radius: 999px;
  background: #f3f5f7;
}
.site-nav a,
.site-nav button {
  min-height: 36px;
  padding: 0 16px;
  border: 0;
  border-radius: 999px;
  color: #667085;
  background: transparent;
  font-size: 13px;
  font-weight: 750;
  line-height: 36px;
  text-decoration: none;
  cursor: pointer;
}
.site-nav a:hover,
.site-nav button:hover,
.site-nav .is-active {
  color: #111827;
  background: #fff;
  box-shadow: 0 3px 12px rgba(17, 24, 39, .07);
}
.account-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.account-actions button {
  min-height: 38px;
  padding: 0 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.account-actions__text { border: 0; color: #475467; background: transparent; }
.account-actions__primary { border: 1px solid #111827; color: #fff; background: #111827; }
.account-actions__user {
  max-width: 120px;
  overflow: hidden;
  color: #344054;
  font-size: 13px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 800px) {
  .site-header { background: #fff; backdrop-filter: none; }
  .site-header__inner { width: min(100% - 28px, 680px); grid-template-columns: 1fr auto; }
  .site-nav {
    position: fixed;
    right: 14px;
    bottom: 14px;
    left: 14px;
    z-index: 50;
    justify-content: space-around;
    border: 1px solid #e2e8f0;
    background: rgba(255, 255, 255, .96);
    box-shadow: 0 14px 36px rgba(15, 23, 42, .15);
  }
  .site-nav a,
  .site-nav button { flex: 1; padding: 0 8px; }
  .brand__copy small,
  .account-actions__text,
  .account-actions__user { display: none; }
}
</style>
