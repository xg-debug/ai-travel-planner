<template>
  <div class="fixed bottom-4 right-4 z-50 space-y-3">
    <!-- 通知项 -->
    <div 
      v-for="notification in notifications" 
      :key="notification.id"
      class="travel-alert max-w-sm animate-slide-up"
      :class="{
        'travel-alert-info': notification.type === 'info',
        'travel-alert-success': notification.type === 'success',
        'travel-alert-warning': notification.type === 'warning',
        'travel-alert-error': notification.type === 'error'
      }"
    >
      <div class="flex items-start">
        <!-- 图标 -->
        <div class="flex-shrink-0 mr-3">
          <svg 
            v-if="notification.type === 'success'" 
            class="w-5 h-5 text-green-600" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <svg 
            v-else-if="notification.type === 'error'" 
            class="w-5 h-5 text-red-600" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <svg 
            v-else-if="notification.type === 'warning'" 
            class="w-5 h-5 text-yellow-600" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.998-.833-2.732 0L4.342 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <svg 
            v-else 
            class="w-5 h-5 text-blue-600" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        
        <!-- 内容 -->
        <div class="flex-1">
          <h4 class="font-medium mb-1">{{ notification.title }}</h4>
          <p class="text-sm opacity-90">{{ notification.message }}</p>
        </div>
        
        <!-- 关闭按钮 -->
        <button 
          @click="removeNotification(notification.id)"
          class="ml-4 flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

// 通知数据
const notifications = ref([
  {
    id: 1,
    type: 'info',
    title: '欢迎使用智能旅行规划',
    message: '开始规划您的完美旅程吧！',
    timeout: 5000
  }
])

// 移除通知
const removeNotification = (id) => {
  notifications.value = notifications.value.filter(n => n.id !== id)
}

// 添加通知
const addNotification = (notification) => {
  const id = Date.now()
  const newNotification = {
    id,
    ...notification,
    timeout: notification.timeout || 5000
  }
  
  notifications.value.push(newNotification)
  
  // 自动移除
  if (newNotification.timeout > 0) {
    setTimeout(() => {
      removeNotification(id)
    }, newNotification.timeout)
  }
}

// 全局事件监听
const handleNotification = (event) => {
  if (event.detail) {
    addNotification(event.detail)
  }
}

// 生命周期
onMounted(() => {
  window.addEventListener('travel-notification', handleNotification)
})

onUnmounted(() => {
  window.removeEventListener('travel-notification', handleNotification)
})

// 导出方法供其他组件使用
defineExpose({
  addNotification
})
</script>

<style scoped>
/* 通知组件特定样式 */
</style>