<template>
  <div class="min-h-screen bg-slate-50">
    <TravelNav @auth="goToPlanner" />
    <div class="container mx-auto px-4 py-12">
      <div class="mb-8">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 class="font-chinese text-3xl md:text-4xl font-bold text-travel-ocean mb-3">
              我的旅行历史
            </h1>
            <p class="text-travel-gray">
              查看和管理您之前规划的所有旅行
            </p>
          </div>
          
          <button
            @click="goToPlanner"
            class="px-6 py-3 rounded-xl bg-slate-900 text-white font-medium hover:bg-slate-800 transition-all duration-300 shadow-travel-card flex items-center justify-center space-x-2"
          >
            <span class="text-xl">+</span>
            <span>规划新旅行</span>
          </button>
        </div>
        
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div class="bg-white/90 backdrop-blur-sm rounded-xl border border-travel-sky/20 shadow-travel-card p-5">
            <div class="text-center">
              <div class="text-sm text-travel-gray mb-2">总旅行次数</div>
              <div class="text-2xl font-chinese font-bold text-slate-900">
                {{ tripHistory.length }}
              </div>
            </div>
          </div>
          
          <div class="bg-white/90 backdrop-blur-sm rounded-xl border border-travel-sky/20 shadow-travel-card p-5">
            <div class="text-center">
              <div class="text-sm text-travel-gray mb-2">总预算</div>
              <div class="text-2xl font-chinese font-bold text-slate-900">
                ¥{{ totalBudget.toLocaleString() }}
              </div>
            </div>
          </div>
          
          <div class="bg-white/90 backdrop-blur-sm rounded-xl border border-travel-sky/20 shadow-travel-card p-5">
            <div class="text-center">
              <div class="text-sm text-travel-gray mb-2">总天数</div>
              <div class="text-2xl font-chinese font-bold text-slate-900">
                {{ totalDays }}
              </div>
            </div>
          </div>
          
          <div class="bg-white/90 backdrop-blur-sm rounded-xl border border-travel-sky/20 shadow-travel-card p-5">
            <div class="text-center">
              <div class="text-sm text-travel-gray mb-2">最近旅行</div>
              <div class="text-xl font-chinese font-bold text-slate-900 truncate">
                {{ recentTripDate }}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div v-if="tripHistory.length > 0">
        <div class="mb-6">
          <div class="flex items-center justify-between">
            <h2 class="text-xl font-bold text-travel-ocean">所有旅行计划</h2>
            <div class="flex items-center space-x-4">
              <select
                v-model="sortBy"
                class="px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-travel-ocean focus:ring-2 focus:ring-travel-sky/20 transition-all duration-300"
              >
                <option value="date">按日期排序</option>
                <option value="budget">按预算排序</option>
                <option value="days">按天数排序</option>
              </select>
              
              <button
                @click="toggleViewMode"
                class="p-2 rounded-lg hover:bg-gray-100 transition-colors duration-300"
                :title="viewMode === 'grid' ? '切换到列表视图' : '切换到网格视图'"
              >
                <svg v-if="viewMode === 'grid'" class="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
                <svg v-else class="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
        
        <div v-if="viewMode === 'grid'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="trip in sortedTrips"
            :key="trip.id"
            class="bg-white rounded-2xl border border-gray-200 shadow-travel-card hover:shadow-travel-card-lg transition-all duration-300 overflow-hidden group flex flex-col"
          >
            <div class="p-6 flex-grow">
              <div class="flex items-start justify-between mb-4">
                <div class="flex-1 min-w-0">
                  <h3 class="text-xl font-bold text-gray-900 mb-2 group-hover:text-travel-ocean transition-colors duration-300 truncate">
                    {{ trip.destination }}
                  </h3>
                  <div class="flex flex-col space-y-1 text-sm text-gray-600">
                    <span class="flex items-center space-x-1">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span>{{ formatDate(trip.startDate) }}</span>
                    </span>
                    <span class="flex items-center space-x-1">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>{{ trip.days?.length || 0 }} 天行程</span>
                    </span>
                  </div>
                </div>
                
                <div class="text-right">
                  <div class="text-lg font-bold text-travel-ocean">
                    ¥{{ (trip.budget?.total || 0).toLocaleString() }}
                  </div>
                  <div class="text-xs text-gray-500">预估预算</div>
                </div>
              </div>
              
              <div class="flex flex-wrap gap-2 mb-4">
                <span
                  v-for="interest in trip.interests?.slice(0, 3)"
                  :key="interest"
                  class="px-3 py-1 bg-travel-sky/10 text-travel-ocean text-xs font-medium rounded-full"
                >
                  {{ interest }}
                </span>
                <span
                  v-if="trip.interests && trip.interests.length > 3"
                  class="px-3 py-1 bg-gray-100 text-gray-600 text-xs font-medium rounded-full"
                >
                  +{{ trip.interests.length - 3 }}
                </span>
              </div>
              
              <div v-if="trip.days?.[0]?.activities?.length" class="space-y-2 mb-4">
                <div
                  v-for="activity in trip.days[0].activities.slice(0, 2)"
                  :key="activity.id"
                  class="flex items-center space-x-3 text-sm text-gray-700"
                >
                  <div class="w-1.5 h-1.5 rounded-full bg-travel-mint flex-shrink-0"></div>
                  <div class="truncate">{{ activity.title }}</div>
                </div>
              </div>
            </div>
            
            <div class="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
              <div class="text-xs text-gray-500 italic">
                创建于 {{ formatRelativeDate(trip.createdAt) }}
              </div>
              
              <div class="flex items-center space-x-2">
                <button
                  @click="viewTrip(trip.id)"
                  class="px-4 py-2 rounded-lg bg-travel-ocean text-white text-sm font-medium hover:bg-travel-ocean/90 transition-colors duration-300"
                >
                  查看详情
                </button>
                <button
                  @click="confirmDelete(trip.id)"
                  class="p-2 rounded-lg hover:bg-red-50 text-red-600 hover:text-red-700 transition-colors duration-300"
                  title="删除旅行"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <div v-else class="bg-white rounded-2xl border border-gray-200 shadow-travel-card overflow-x-auto">
          <table class="w-full min-w-[800px]">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-200">
                <th class="py-4 px-6 text-left text-sm font-semibold text-gray-900">目的地</th>
                <th class="py-4 px-6 text-left text-sm font-semibold text-gray-900">旅行日期</th>
                <th class="py-4 px-6 text-left text-sm font-semibold text-gray-900">天数</th>
                <th class="py-4 px-6 text-left text-sm font-semibold text-gray-900">预算</th>
                <th class="py-4 px-6 text-left text-sm font-semibold text-gray-900">标签</th>
                <th class="py-4 px-6 text-left text-sm font-semibold text-gray-900">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="trip in sortedTrips"
                :key="trip.id"
                class="border-b border-gray-100 hover:bg-gray-50 transition-colors duration-300"
              >
                <td class="py-4 px-6">
                  <div class="font-medium text-gray-900">{{ trip.destination }}</div>
                </td>
                <td class="py-4 px-6">
                  <div class="text-sm text-gray-700">
                    {{ formatDate(trip.startDate) }}
                  </div>
                </td>
                <td class="py-4 px-6">
                  <div class="text-sm text-gray-700">{{ trip.days?.length || 0 }} 天</div>
                </td>
                <td class="py-4 px-6">
                  <div class="font-medium text-travel-ocean">
                    ¥{{ (trip.budget?.total || 0).toLocaleString() }}
                  </div>
                </td>
                <td class="py-4 px-6">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="interest in trip.interests?.slice(0, 2)"
                      :key="interest"
                      class="px-2 py-0.5 bg-travel-sky/10 text-travel-ocean text-xs rounded"
                    >
                      {{ interest }}
                    </span>
                  </div>
                </td>
                <td class="py-4 px-6">
                  <div class="flex items-center space-x-3">
                    <button
                      @click="viewTrip(trip.id)"
                      class="text-travel-ocean hover:text-travel-ocean/80 text-sm font-medium"
                    >
                      详情
                    </button>
                    <button
                      @click="confirmDelete(trip.id)"
                      class="text-red-600 hover:text-red-700 text-sm font-medium"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else class="text-center py-24 bg-white rounded-3xl border border-dashed border-gray-300">
        <div class="mb-6">
          <div class="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gray-50 mb-4">
            <svg class="w-10 h-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 class="text-xl font-bold text-gray-900 mb-2">尚未发现旅行足迹</h3>
          <p class="text-gray-500 mb-8 max-w-xs mx-auto">
            您还没有创建过任何旅行计划，现在就开启您的下一段冒险吧！
          </p>
          <button
            @click="goToPlanner"
            class="px-8 py-3 rounded-xl bg-travel-ocean text-white font-medium hover:bg-travel-ocean/90 transition-all shadow-lg"
          >
            立即规划
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTripStore } from '@/stores/tripStore'
import { useAuthStore } from '@/stores/authStore'
import TravelNav from '@/components/TravelNav.vue'

// 定义接口，增强 TS 类型提示
interface Activity {
  id: string | number;
  title: string;
}

interface TripDay {
  activities: Activity[];
}

interface Trip {
  id: string;
  destination: string;
  startDate: string;
  endDate: string;
  createdAt: string;
  interests?: string[];
  days?: TripDay[];
  budget?: {
    total: number;
  };
}

const router = useRouter()
const tripStore = useTripStore()
const authStore = useAuthStore()

const sortBy = ref<'date' | 'budget' | 'days'>('date')
const viewMode = ref<'grid' | 'list'>('grid')

// 计算属性
const tripHistory = computed<Trip[]>(() => tripStore.tripHistory || [])

const totalBudget = computed(() => {
  return tripHistory.value.reduce((sum, trip) => sum + (trip.budget?.total || 0), 0)
})

const totalDays = computed(() => {
  return tripHistory.value.reduce((sum, trip) => sum + (trip.days?.length || 0), 0)
})

const recentTripDate = computed(() => {
  if (tripHistory.value.length === 0) return '无'
  // 找出 startDate 最大的那一个
  const sortedByDate = [...tripHistory.value].sort((a, b) => 
    new Date(b.startDate).getTime() - new Date(a.startDate).getTime()
  )
  return formatDate(sortedByDate[0].startDate)
})

const sortedTrips = computed(() => {
  const trips = [...tripHistory.value]
  
  switch (sortBy.value) {
    case 'date':
      return trips.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    case 'budget':
      return trips.sort((a, b) => (b.budget?.total || 0) - (a.budget?.total || 0))
    case 'days':
      return trips.sort((a, b) => (b.days?.length || 0) - (a.days?.length || 0))
    default:
      return trips
  }
})

// 方法
const goToPlanner = () => {
  router.push('/')
}

const viewTrip = (tripId: string) => {
  tripStore.loadTrip(tripId)
  router.push(`/trip/${tripId}`)
}

const confirmDelete = (tripId: string) => {
  if (window.confirm('确定要删除这个旅行计划吗？此操作不可撤销。')) {
    deleteTrip(tripId)
  }
}

const deleteTrip = async (tripId: string) => {
  try {
    await tripStore.deleteTrip(tripId)
    // 如果有全局通知组件，可以在这里触发 success toast
  } catch (error) {
    console.error('Failed to delete trip:', error)
    alert('删除失败，请重试')
  }
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'grid' ? 'list' : 'grid'
}

const formatDate = (dateString: string | undefined) => {
  if (!dateString) return '待定'
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

const formatRelativeDate = (dateString: string | undefined) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  
  // 使用 getTime() 进行数值减法
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))
  
  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}个月前`
  return `${Math.floor(diffDays / 365)}年前`
}

onMounted(() => {
  if (!authStore.isAuthenticated) {
    router.push('/')
    return
  }
  tripStore.loadTripsFromServer()
})
</script>

<style scoped>
.shadow-travel-card {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.shadow-travel-card-lg {
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}

/* 针对移动端的滚动条美化 */
.overflow-x-auto::-webkit-scrollbar {
  height: 4px;
}
.overflow-x-auto::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}
</style>
