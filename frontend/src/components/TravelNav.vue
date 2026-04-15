<template>
  <nav class="sticky top-0 z-50 bg-white/80 backdrop-blur-light border-b border-travel-border">
    <div class="container mx-auto px-4">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <div class="flex items-center space-x-2">
          <div class="travel-icon-container">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </div>
          <span class="text-xl font-display font-bold text-slate-900">智能旅行规划</span>
        </div>

        <!-- 导航链接 -->
        <div class="hidden md:flex items-center space-x-8">
          <router-link 
            to="/" 
            class="text-gray-600 hover:text-travel-primary transition-colors duration-300 font-medium"
            active-class="text-travel-primary"
          >
            首页
          </router-link>
          <!-- <router-link 
            to="/" 
            class="text-gray-600 hover:text-travel-primary transition-colors duration-300 font-medium"
            active-class="text-travel-primary"
          >
            规划行程
          </router-link> -->
          <router-link 
            to="/map" 
            class="text-gray-600 hover:text-travel-primary transition-colors duration-300 font-medium"
            active-class="text-travel-primary"
          >
            旅行地图
          </router-link>
          <router-link 
            v-if="authStore.isAuthenticated"
            to="/history" 
            class="text-gray-600 hover:text-travel-primary transition-colors duration-300 font-medium"
            active-class="text-travel-primary"
          >
            行程历史
          </router-link>
          <button
            v-else
            type="button"
            class="text-gray-600 hover:text-travel-primary transition-colors duration-300 font-medium"
            @click="emit('auth', 'login')"
          >
            行程历史
          </button>
        </div>

        <!-- 用户操作 -->
        <div class="flex items-center space-x-4">
          <button
            v-if="!authStore.isAuthenticated"
            type="button"
            class="travel-btn-outline px-4 py-2 text-sm"
            @click="emit('auth', 'login')"
          >
            登录
          </button>
          <button
            v-if="!authStore.isAuthenticated"
            type="button"
            class="travel-btn px-4 py-2 text-sm"
            @click="emit('auth', 'register')"
          >
            注册
          </button>
          <button
            v-else
            type="button"
            class="px-4 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50"
            @click="authStore.logout"
          >
            退出
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useAuthStore } from '@/stores/authStore'

const emit = defineEmits(['auth'])
const authStore = useAuthStore()
</script>

<style scoped>
/* 导航栏特定样式 */
</style>
