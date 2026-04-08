<template>
  <div class="min-h-screen bg-slate-50 text-gray-800">
    <!-- 主要内容 -->
    <div>
      <!-- 导航栏 -->
      <!-- <TravelNav /> -->
      
      <!-- 主路由视图 -->
      <main class="container mx-auto px-4 py-8">
        <router-view />
      </main>

      <!-- 页脚 -->
      <!-- <TravelFooter /> -->
    </div>

    <!-- 全局通知 -->
    <TravelNotifications />
  </div>
</template>

<script setup>
import TravelNav from '@/components/TravelNav.vue'
import TravelFooter from '@/components/TravelFooter.vue'
import TravelNotifications from '@/components/TravelNotifications.vue'
</script>

<style scoped>
/* 清新风格的动画效果 */
.fade-in {
  animation: fadeIn 0.5s ease-out;
}

@keyframes fadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}
</style>
