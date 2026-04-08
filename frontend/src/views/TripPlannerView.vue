<template>
  <div class="min-h-screen">
    <!-- 使用现有的TravelNav组件 -->
    <TravelNav />

    <!-- 主要内容区域 -->
    <div class="relative overflow-hidden">
      
      <!-- 认证模态框 -->
      <AuthModal
        v-if="showAuthModal"
        :show="showAuthModal"
        :initial-mode="authMode"
        @close="showAuthModal = false"
        @success="handleAuthSuccess"
      />
      <!-- 背景装饰 -->
      <div class="absolute top-0 left-0 w-full h-96 bg-slate-100"></div>
      <div class="absolute top-20 right-10 w-72 h-72 bg-blue-100 rounded-full opacity-20"></div>
      <div class="absolute bottom-20 left-10 w-64 h-64 bg-teal-100 rounded-full opacity-20"></div>

      <div class="container mx-auto px-4 py-12 relative z-10">
        <!-- 标题区域 -->
        <div class="text-center max-w-3xl mx-auto mb-12">
          <h1 class="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            智能旅行规划助手
          </h1>
          <p class="text-lg text-gray-600 mb-8">
            输入您的旅行需求，AI将为您生成包含景点、餐饮、酒店的完整行程计划
          </p>
          <div v-if="!authStore.isAuthenticated" class="flex items-center justify-center gap-3 mb-8">
            <button
              type="button"
              class="px-5 py-2.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100"
              @click="openAuthModal('login')"
            >
              登录
            </button>
            <button
              type="button"
              class="px-5 py-2.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
              @click="openAuthModal('register')"
            >
              注册
            </button>
          </div>
          
          <!-- 特色标签 -->
          <div class="flex flex-wrap justify-center gap-3 mb-10">
            <div class="px-4 py-2 bg-blue-50 text-blue-700 rounded-full text-sm font-medium">
              🗺️ 智能路线规划
            </div>
            <div class="px-4 py-2 bg-teal-50 text-teal-700 rounded-full text-sm font-medium">
              🏨 酒店推荐
            </div>
            <div class="px-4 py-2 bg-amber-50 text-amber-700 rounded-full text-sm font-medium">
              🍽️ 美食推荐
            </div>
            <div class="px-4 py-2 bg-purple-50 text-purple-700 rounded-full text-sm font-medium">
              💰 预算估算
            </div>
          </div>
        </div>

        <!-- 行程规划表单 -->
        <div class="max-w-4xl mx-auto">
          <div class="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden">
            <!-- 表单头部 -->
            <div class="bg-slate-900 px-8 py-6">
              <h2 class="text-2xl font-bold text-white">开始规划您的旅程</h2>
              <p class="text-slate-300 mt-2">填写以下信息，获取个性化行程建议</p>
            </div>

            <!-- 表单内容 -->
            <div class="p-8">
              <div class="space-y-8">
                <!-- 第一行：目的地和日期 -->
                <div class="grid md:grid-cols-3 gap-6">
                  <!-- 目的地 -->
                  <div class="space-y-3">
                    <label class="block text-sm font-medium text-gray-700">
                      <span class="text-red-500">*</span> 目的地
                    </label>
                    <div class="relative">
                      <div class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </div>
                      <input
                        v-model="destination"
                        type="text"
                        placeholder="例如：北京、上海、东京..."
                        class="w-full pl-10 pr-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-300"
                      />
                    </div>
                  </div>

                  <!-- 开始日期 -->
                  <div class="space-y-3">
                    <label class="block text-sm font-medium text-gray-700">
                      <span class="text-red-500">*</span> 开始日期
                    </label>
                    <div class="relative">
                      <div class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <input
                        v-model="startDate"
                        type="date"
                        :min="today"
                        class="w-full pl-10 pr-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-300"
                      />
                    </div>
                  </div>

                  <!-- 结束日期 -->
                  <div class="space-y-3">
                    <label class="block text-sm font-medium text-gray-700">
                      <span class="text-red-500">*</span> 结束日期
                    </label>
                    <div class="relative">
                      <div class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <input
                        v-model="endDate"
                        type="date"
                        :min="startDate || today"
                        class="w-full pl-10 pr-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-300"
                      />
                    </div>
                  </div>
                </div>

                <!-- 第二行：人数和预算 -->
                <div class="grid md:grid-cols-2 gap-6">
                  <!-- 旅行人数 -->
                  <div class="space-y-3">
                    <label class="block text-sm font-medium text-gray-700">
                      旅行人数
                    </label>
                    <div class="flex items-center space-x-4">
                      <button
                        @click="decrementTravelers"
                        class="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 border border-gray-300 hover:border-blue-500 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                        :disabled="travelers <= 1"
                      >
                        <svg class="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
                        </svg>
                      </button>
                      
                      <div class="flex-1">
                        <div class="text-center">
                          <span class="text-3xl font-bold text-gray-900">{{ travelers }}</span>
                          <span class="block text-sm text-gray-600">人</span>
                        </div>
                      </div>
                      
                      <button
                        @click="incrementTravelers"
                        class="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 border border-gray-300 hover:border-blue-500 transition-all duration-300"
                      >
                        <svg class="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  <!-- 预算 -->
                  <div class="space-y-3">
                    <label class="block text-sm font-medium text-gray-700">
                      预算范围
                    </label>
                    <div>
                      <div class="flex justify-between mb-2">
                        <span class="text-sm text-gray-600">¥{{ budget.toLocaleString() }}</span>
                        <span class="text-sm text-gray-600">
                          {{ budget < 3000 ? '经济型' : budget < 8000 ? '舒适型' : '豪华型' }}
                        </span>
                      </div>
                      <input
                        v-model="budget"
                        type="range"
                        min="1000"
                        max="20000"
                        step="500"
                        class="w-full h-2 bg-gray-200 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-600 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-md"
                      />
                      <div class="flex justify-between text-xs text-gray-500 mt-1">
                        <span>¥1,000</span>
                        <span>¥10,000</span>
                        <span>¥20,000</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 兴趣偏好 -->
                <div class="space-y-4">
                  <label class="block text-sm font-medium text-gray-700">
                    兴趣偏好（可多选）
                  </label>
                  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <button
                      v-for="interest in availableInterests"
                      :key="interest.id"
                      @click="toggleInterest(interest.id)"
                      class="px-4 py-3 rounded-lg border transition-all duration-300 hover:scale-105"
                      :class="[
                        interests.includes(interest.id)
                          ? 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm'
                          : 'bg-white border-gray-300 text-gray-700 hover:border-blue-300 hover:text-blue-600'
                      ]"
                    >
                      <div class="flex items-center justify-center space-x-2">
                        <span>{{ interest.icon }}</span>
                        <span>{{ interest.label }}</span>
                      </div>
                    </button>
                  </div>
                </div>

                <!-- 额外需求 -->
                <div class="space-y-3">
                  <label class="block text-sm font-medium text-gray-700">
                    额外需求（可选）
                  </label>
                  <textarea
                    v-model="additionalRequirements"
                    rows="3"
                    placeholder="例如：希望包含亲子活动、需要无障碍设施、偏好素食餐厅..."
                    class="w-full px-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-300 resize-none"
                  ></textarea>
                </div>

                <!-- 生成按钮 -->
                <div class="pt-6">
                  <!-- 加载状态 -->
                  <div v-if="isLoading" class="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-100">
                    <div class="flex items-center justify-center space-x-3">
                      <div class="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
                      <div>
                        <div class="font-medium text-blue-800">正在生成智能行程...</div>
                        <div class="text-sm text-blue-600">AI正在为您规划最佳路线，请稍候</div>
                      </div>
                    </div>
                    <div class="mt-3 text-xs text-blue-700">
                      <div class="flex items-center space-x-2">
                        <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                        <span>分析目的地信息</span>
                      </div>
                      <div class="flex items-center space-x-2 mt-1">
                        <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                        <span>规划景点路线</span>
                      </div>
                      <div class="flex items-center space-x-2 mt-1">
                        <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                        <span>推荐餐饮住宿</span>
                      </div>
                      <div class="flex items-center space-x-2 mt-1">
                        <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                        <span>计算预算费用</span>
                      </div>
                    </div>
                  </div>
                  
                  <button
                    @click="generateTrip"
                    :disabled="!canGenerate || isLoading"
                    class="w-full px-8 py-4 rounded-lg bg-blue-600 text-white font-bold text-lg transition-all duration-300 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-blue-600"
                  >
                    <div class="flex items-center justify-center space-x-3">
                      <span v-if="!isLoading">✨ 生成智能行程计划</span>
                      <span v-else>⏳ AI规划中...</span>
                      <svg
                        v-if="isLoading"
                        class="w-5 h-5 animate-spin"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    </div>
                    <p v-if="!isLoading" class="text-sm text-blue-100 mt-2">
                      点击生成包含景点、餐饮、酒店的完整行程
                    </p>
                  </button>
                  
                  <!-- 错误提示 -->
                  <div v-if="errorMessage" class="mt-4 p-3 bg-red-50 rounded-lg border border-red-100">
                    <div class="flex items-start space-x-2">
                      <span class="text-red-600">❌</span>
                      <div class="text-sm text-red-800">
                        <div class="font-medium">生成失败：</div>
                        <div>{{ errorMessage }}</div>
                        <button
                          @click="errorMessage = ''"
                          class="mt-2 text-xs text-red-600 hover:text-red-800"
                        >
                          关闭提示
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 提示信息 -->
                  <div class="mt-4 text-center">
                    <p class="text-sm text-gray-600">
                      💡 提示：填写越详细，生成的行程越符合您的需求
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 功能特色展示 -->
          <div class="mt-12 grid md:grid-cols-3 gap-6">
            <div class="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
              <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                <span class="text-2xl">🗺️</span>
              </div>
              <h3 class="font-bold text-gray-900 mb-2">智能路线规划</h3>
              <p class="text-gray-600 text-sm">基于景点位置和开放时间，优化每日游览路线</p>
            </div>
            
            <div class="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
              <div class="w-12 h-12 bg-teal-100 rounded-lg flex items-center justify-center mb-4">
                <span class="text-2xl">🏨</span>
              </div>
              <h3 class="font-bold text-gray-900 mb-2">酒店推荐</h3>
              <p class="text-gray-600 text-sm">根据预算和位置，推荐合适的住宿选择</p>
            </div>
            
            <div class="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
              <div class="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center mb-4">
                <span class="text-2xl">🍽️</span>
              </div>
              <h3 class="font-bold text-gray-900 mb-2">美食推荐</h3>
              <p class="text-gray-600 text-sm">结合当地特色和用户偏好，推荐餐厅和美食</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 页脚 -->
    <TravelFooter/>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTripStore } from '@/stores/tripStore'
import { useAuthStore } from '@/stores/authStore'
import AuthModal from '@/components/AuthModal.vue'
import TravelNav from '@/components/TravelNav.vue'
import TravelFooter from '../components/TravelFooter.vue'

const router = useRouter()
const tripStore = useTripStore()
const authStore = useAuthStore()

const destination = ref('')
const startDate = ref('')
const endDate = ref('')
const travelers = ref(2)
const budget = ref(5000)
const interests = ref([])
const additionalRequirements = ref('')
const isLoading = ref(false)
const errorMessage = ref('')
const showAuthModal = ref(false)
const authMode = ref<'login' | 'register'>('login')

const today = new Date().toISOString().split('T')[0]

const availableInterests = [
  { id: 'culture', label: '文化历史', icon: '🏛️' },
  { id: 'food', label: '美食餐饮', icon: '🍽️' },
  { id: 'nature', label: '自然风光', icon: '🌳' },
  { id: 'shopping', label: '购物逛街', icon: '🛍️' },
  { id: 'adventure', label: '冒险体验', icon: '🧗' },
  { id: 'relaxation', label: '休闲放松', icon: '🧘' },
  { id: 'family', label: '亲子活动', icon: '👨‍👩‍👧' },
  { id: 'photography', label: '摄影打卡', icon: '📸' }
]

const canGenerate = computed(() => {
  return destination.value.trim() !== '' && 
         startDate.value !== '' && 
         endDate.value !== ''
})

const incrementTravelers = () => {
  travelers.value++
}

const decrementTravelers = () => {
  if (travelers.value > 1) {
    travelers.value--
  }
}

const toggleInterest = (interestId) => {
  const index = interests.value.indexOf(interestId)
  if (index === -1) {
    interests.value.push(interestId)
  } else {
    interests.value.splice(index, 1)
  }
}

const generateTrip = async () => {
  // 清除之前的错误信息
  errorMessage.value = ''
  
  if (!canGenerate.value) {
    showValidationError()
    return
  }

  // 验证日期合理性
  const days = calculateDays()
  if (days > 30) {
    errorMessage.value = '行程天数不能超过30天'
    return
  }
  
  if (days < 1) {
    errorMessage.value = '结束日期不能早于开始日期'
    return
  }

  isLoading.value = true

  try {
    const tripRequest = {
      destination: destination.value,
      startDate: startDate.value,
      endDate: endDate.value,
      days: days,
      travelers: travelers.value,
      interests: interests.value,
      budget: budget.value,
      additionalRequirements: additionalRequirements.value,
      preferences: {
        pace: 'moderate',
        accommodation: 'mid-range',
        food: 'mixed',
        transportation: 'mixed'
      }
    }

    await tripStore.createTrip(tripRequest)
    
    // Navigate to trip details
    if (tripStore.currentTrip) {
      router.push(`/trip/${tripStore.currentTrip.id}`)
    }
  } catch (error) {
    console.error('Failed to generate trip:', error)
    errorMessage.value = error.message || '生成行程失败，请检查网络连接或稍后重试'
    
    // 如果是网络错误，提供更多帮助
    if (error.message?.includes('network') || error.message?.includes('Network')) {
      errorMessage.value = '网络连接失败，请检查您的网络连接后重试'
    } else if (error.message?.includes('timeout')) {
      errorMessage.value = '请求超时，服务器响应较慢，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}

const showValidationError = () => {
  let message = '请填写以下必填信息：'
  const errors = []
  
  if (!destination.value.trim()) errors.push('• 目的地')
  if (!startDate.value) errors.push('• 开始日期')
  if (!endDate.value) errors.push('• 结束日期')
  
  if (errors.length > 0) {
    errorMessage.value = `请填写以下必填信息：\n${errors.join('\n')}`
  }
}

const calculateDays = () => {
  if (!startDate.value || !endDate.value) return 0
  const start = new Date(startDate.value)
  const end = new Date(endDate.value)
  const diffTime = Math.abs(end - start)
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1
}

const handleAuthSuccess = () => {
  // 认证成功后的处理
  console.log('Authentication successful')
}

const openAuthModal = (mode) => {
  authMode.value = mode
  showAuthModal.value = true
}
</script>
