<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="sticky top-0 z-50 bg-white/90 backdrop-blur-sm border-b border-gray-100">
      <div class="container mx-auto px-4 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <div class="w-8 h-8 bg-blue-600 rounded-lg"></div>
            <span class="text-xl font-bold text-gray-800">TravelAI</span>
          </div>
          <div class="flex items-center space-x-6">
            <router-link to="/" class="text-gray-600 hover:text-blue-600 transition-colors">首页</router-link>
            <router-link to="/history" class="text-gray-600 hover:text-blue-600 transition-colors">旅行历史</router-link>
            
            <div v-if="authStore.isAuthenticated" class="relative group flex items-center space-x-4">
              <button class="flex items-center space-x-2">
                <div class="w-8 h-8 rounded-full bg-blue-600 overflow-hidden">
                  <img v-if="authStore.userAvatar" :src="authStore.userAvatar" class="w-full h-full object-cover" />
                </div>
                <span class="text-gray-700 font-medium">{{ authStore.userName }}</span>
              </button>
              <div class="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl border border-gray-200 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50">
                <div class="p-4 border-b border-gray-100">
                  <div class="font-medium text-gray-900">{{ authStore.userName }}</div>
                  <div class="text-sm text-gray-600 truncate">{{ authStore.userEmail }}</div>
                </div>
                <div class="p-2">
                  <button @click="authStore.logout" class="w-full px-4 py-2 text-left text-red-600 hover:bg-red-50 rounded-lg flex items-center space-x-2">
                    <span>退出登录</span>
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="flex items-center space-x-3">
              <button @click="openAuth('login')" class="px-4 py-2 text-gray-700 hover:text-blue-600">登录</button>
              <button @click="openAuth('register')" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700">注册</button>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <AuthModal v-if="showAuthModal" :show="showAuthModal" :initial-mode="authMode" @close="showAuthModal = false" />

    <div class="py-8 bg-slate-50" v-if="trip">
      <div class="container mx-auto px-4">
        <button @click="router.push('/')" class="mb-6 flex items-center space-x-2 text-blue-600 hover:text-teal-500 transition-colors">
          <span>← 返回行程规划</span>
        </button>

        <div class="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 class="text-3xl md:text-4xl font-bold text-blue-900 mb-3">{{ trip.destination }}</h1>
            <div class="flex items-center space-x-6 text-gray-600">
              <span>📅 {{ formatDate(trip.startDate) }} - {{ formatDate(trip.endDate) }}</span>
              <span>👥 {{ trip.travelers }} 人</span>
            </div>
          </div>

          <div class="flex gap-4">
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5 text-center min-w-[120px]">
              <div class="text-sm text-gray-500 mb-1">总预算</div>
              <div class="text-2xl font-bold text-teal-600">¥{{ trip.budget?.total?.toLocaleString() }}</div>
            </div>
            <div class="flex flex-col gap-2">
              <button @click="router.push('/map')" class="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors">查看地图</button>
              <button @click="exportToPDF" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm">导出 PDF</button>
              <button @click="exportToImage" class="px-4 py-2 rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50 transition-colors">导出图片</button>
            </div>
          </div>
        </div>

        <div class="mb-8 grid gap-6 lg:grid-cols-3">
          <div class="lg:col-span-2 rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
            <h2 class="mb-3 text-lg font-bold text-gray-900">行程概览</h2>
            <p class="whitespace-pre-line text-sm leading-7 text-gray-700">
              {{ trip.plan || '已生成行程，可在下方按天查看并编辑细节。' }}
            </p>
          </div>
          <div class="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
            <h2 class="mb-3 text-lg font-bold text-gray-900">景点地图</h2>
            <p class="mb-4 text-sm text-gray-600">
              已识别可定位活动：{{ mappedActivityCount }} 个
            </p>
            <button
              @click="router.push('/map')"
              class="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              打开地图查看路线
            </button>
          </div>
        </div>

        <div class="grid lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2 space-y-8">
            <div class="flex space-x-3 overflow-x-auto pb-3">
              <button 
                v-for="(day, index) in trip.days" :key="day.date"
                @click="activeDayIndex = index"
                :class="['flex-shrink-0 px-5 py-3 rounded-xl border transition-all', activeDayIndex === index ? 'bg-blue-50 border-blue-600 text-blue-600' : 'bg-white text-gray-600']"
              >
                <div class="font-medium">第 {{ index + 1 }} 天</div>
                <div class="text-xs mt-1">{{ formatDayDate(day.date) }}</div>
              </button>
            </div>

            <div v-if="activeDay" class="space-y-6">
              <div class="flex items-center justify-between">
                <h2 class="text-2xl text-blue-900 font-bold">第 {{ activeDayIndex + 1 }} 天</h2>
                <div class="flex space-x-3">
                  <span class="text-gray-500 self-center mr-2">当日花费: ¥{{ calculateDayCost(activeDay) }}</span>
                  <button @click="isEditingActivities = !isEditingActivities" class="px-3 py-1 rounded border border-blue-200 text-blue-600 hover:bg-blue-50">
                    {{ isEditingActivities ? '完成编辑' : '编辑排序' }}
                  </button>
                  <button @click="openActivityModal()" class="px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700">+ 添加</button>
                </div>
              </div>

              <div class="space-y-6">
                <div v-for="(activity, index) in activeDay.activities" :key="activity.id" class="relative pl-8 pb-4 border-l-2 border-blue-100 group">
                  <div class="absolute left-[-9px] top-0 w-4 h-4 rounded-full bg-blue-500 border-2 border-white"></div>
                  
                  <div v-if="isEditingActivities" class="absolute right-0 top-0 flex space-x-2">
                    <button @click="moveActivity(index, -1)" :disabled="index === 0" class="p-1 text-blue-600 disabled:opacity-30">↑</button>
                    <button @click="moveActivity(index, 1)" :disabled="index === activeDay.activities.length - 1" class="p-1 text-blue-600 disabled:opacity-30">↓</button>
                    <button @click="openActivityModal(index)" class="p-1 text-blue-600">✎</button>
                    <button @click="removeActivity(index)" class="p-1 text-red-500">×</button>
                  </div>

                  <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                    <div v-if="activity.image" class="mb-3 overflow-hidden rounded-lg border border-gray-100">
                      <img
                        :src="getActivityImage(activity, index)"
                        :alt="activity.title"
                        class="h-44 w-full object-cover"
                        loading="lazy"
                        decoding="async"
                        @error="handleImageError"
                      />
                    </div>
                    <div class="flex justify-between mb-2">
                      <div class="font-bold text-lg text-gray-800">{{ activity.time }} - {{ activity.title }}</div>
                      <div class="text-teal-600 font-medium">¥{{ activity.cost }}</div>
                    </div>
                    <p class="text-gray-600 mb-3 text-sm">{{ activity.description }}</p>
                    <div class="flex space-x-4 text-xs text-gray-500">
                      <span>📍 {{ activity.location }}</span>
                      <span>⏱️ {{ activity.duration }} 分钟</span>
                      <span>🏷️ {{ activity.type }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-8">
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div class="flex justify-between items-center mb-4">
                <h3 class="font-bold text-gray-800">天气预报</h3>
                <button @click="refreshWeather" :disabled="isRefreshingWeather" class="text-sm text-blue-600">{{ isRefreshingWeather ? '更新中...' : '刷新' }}</button>
              </div>
              <div v-if="trip.weather?.length" class="space-y-3">
                <div v-for="w in trip.weather" :key="w.date" class="flex justify-between items-center p-2 hover:bg-gray-50 rounded">
                  <span class="text-sm text-gray-600">{{ formatDayDate(w.date) }}</span>
                  <span>{{ getWeatherIcon(w.condition) }} {{ w.condition }}</span>
                  <span class="font-medium text-gray-800">{{ w.low }}°~{{ w.high }}°</span>
                </div>
              </div>
              <div v-if="weatherTips.length" class="mt-4 p-3 bg-amber-50 rounded text-sm text-amber-800">
                💡 {{ weatherTips.join(' ') }}
              </div>
            </div>

            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
               <div class="flex justify-between items-center mb-4">
                <h3 class="font-bold text-gray-800">预算明细</h3>
                <button @click="isEditingBudget = !isEditingBudget" class="text-sm text-blue-600">{{ isEditingBudget ? '完成' : '编辑' }}</button>
              </div>
              <div class="space-y-4">
                <div v-for="cat in trip.budget?.categories" :key="cat.name">
                  <div class="flex justify-between text-sm mb-1">
                    <span class="text-gray-600">{{ cat.name }}</span>
                    <div class="flex items-center space-x-2">
                      <span class="font-medium">¥{{ cat.amount }}</span>
                      <div v-if="isEditingBudget" class="flex space-x-1">
                        <button @click="adjustBudget(cat.name, -100)" class="px-2 bg-gray-100 rounded">-</button>
                        <button @click="adjustBudget(cat.name, 100)" class="px-2 bg-gray-100 rounded">+</button>
                      </div>
                    </div>
                  </div>
                  <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div class="h-full bg-teal-500" :style="{ width: `${(cat.amount / trip.budget.total) * 100}%` }"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showActivityModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @click.self="showActivityModal = false">
      <div class="bg-white rounded-2xl w-full max-w-md p-6">
        <h3 class="text-xl font-bold mb-4">{{ editingActivityIndex >= 0 ? '编辑活动' : '添加活动' }}</h3>
        <div class="space-y-4">
          <input v-model="activityForm.time" type="time" class="w-full p-3 border rounded-xl" />
          <input v-model="activityForm.title" type="text" placeholder="活动标题" class="w-full p-3 border rounded-xl" />
          <input v-model="activityForm.location" type="text" placeholder="地点" class="w-full p-3 border rounded-xl" />
          <div class="grid grid-cols-2 gap-4">
            <input v-model="activityForm.duration" type="number" placeholder="时长(分钟)" class="p-3 border rounded-xl" />
            <input v-model="activityForm.cost" type="number" placeholder="花费(元)" class="p-3 border rounded-xl" />
          </div>
          <textarea v-model="activityForm.description" placeholder="描述" class="w-full p-3 border rounded-xl"></textarea>
          <div class="flex gap-3 pt-2">
            <button @click="saveActivity" class="flex-1 bg-blue-600 text-white p-3 rounded-xl font-medium hover:bg-blue-700">保存</button>
            <button @click="showActivityModal = false" class="flex-1 bg-gray-100 text-gray-700 p-3 rounded-xl hover:bg-gray-200">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTripStore } from '@/stores/tripStore'
import { useAuthStore } from '@/stores/authStore'
import { tripApi } from '@/services/api'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import type { Activity } from '@/types/trip'

// ===== 基础定义 =====
const route = useRoute()
const router = useRouter()
const tripStore = useTripStore()
const authStore = useAuthStore()

// 获取 Store 中的数据
const trip = computed(() => tripStore.currentTrip)
const mappedActivityCount = computed(() => {
  if (!trip.value?.days?.length) return 0
  return trip.value.days.reduce((sum: number, day: any) => {
    const count = (day.activities || []).filter((a: any) => a.coordinates?.lat && a.coordinates?.lng).length
    return sum + count
  }, 0)
})

// ===== UI 控制状态 =====
const showAuthModal = ref(false)
const authMode = ref<'login' | 'register'>('login')
const openAuth = (mode: 'login' | 'register') => {
  authMode.value = mode
  showAuthModal.value = true
}

// ===== 行程与活动逻辑 =====
const activeDayIndex = ref(0)
const activeDay = computed(() => trip.value?.days?.[activeDayIndex.value])
const isEditingActivities = ref(false)

const showActivityModal = ref(false)
const editingActivityIndex = ref(-1)
const activityForm = ref<Omit<Activity, 'id'>>({
  time: '09:00',
  title: '',
  description: '',
  location: '',
  type: 'other',
  duration: 60,
  cost: 0
})

const calculateDayCost = (day: any) => day?.activities?.reduce((sum: number, act: any) => sum + act.cost, 0) || 0

// 打开表单
const openActivityModal = (index = -1) => {
  editingActivityIndex.value = index
  if (index >= 0 && activeDay.value) {
    const activityWithoutId = { ...activeDay.value.activities[index] } as any
    delete activityWithoutId.id
    activityForm.value = activityWithoutId
  } else {
    activityForm.value = { time: '09:00', title: '', description: '', location: '', type: 'other', duration: 60, cost: 0 }
  }
  showActivityModal.value = true
}

// 保存活动（修复原版突变 computed 属性的问题）
const saveActivity = async () => {
  if (!trip.value || !activeDay.value || !activityForm.value.title) return
  
  // 深拷贝当前活动列表
  const newActivities = [...activeDay.value.activities]
  
  if (editingActivityIndex.value >= 0) {
    newActivities[editingActivityIndex.value] = { ...activityForm.value, id: newActivities[editingActivityIndex.value].id }
  } else {
    newActivities.push({ ...activityForm.value, id: `act_${Date.now()}` })
  }
  // 按时间排序
  newActivities.sort((a, b) => a.time.localeCompare(b.time))

  // 深拷贝整个 Days 数组并替换，通过 Store 统一更新以保证数据流清晰
  const newDays = [...trip.value.days]
  newDays[activeDayIndex.value] = { ...activeDay.value, activities: newActivities }
  
  await tripStore.updateTrip({ ...trip.value, days: newDays })
  showActivityModal.value = false
}

// 移动活动排序
const moveActivity = async (index: number, direction: -1 | 1) => {
  if (!activeDay.value || !trip.value) return
  const newActivities = [...activeDay.value.activities]
  const targetIndex = index + direction
  
  if (targetIndex >= 0 && targetIndex < newActivities.length) {
    [newActivities[index], newActivities[targetIndex]] = [newActivities[targetIndex], newActivities[index]]
    const newDays = [...trip.value.days]
    newDays[activeDayIndex.value] = { ...activeDay.value, activities: newActivities }
    await tripStore.updateTrip({ ...trip.value, days: newDays })
  }
}

const removeActivity = async (index: number) => {
  if (!activeDay.value || !trip.value || !confirm('确定要删除这个活动吗？')) return
  const newActivities = [...activeDay.value.activities]
  newActivities.splice(index, 1)
  const newDays = [...trip.value.days]
  newDays[activeDayIndex.value] = { ...activeDay.value, activities: newActivities }
  await tripStore.updateTrip({ ...trip.value, days: newDays })
}


// ===== 预算逻辑 =====
const isEditingBudget = ref(false)

const adjustBudget = async (categoryName: string, amount: number) => {
  if (!trip.value?.budget) return
  
  const newCategories = trip.value.budget.categories.map((c: any) => {
    if (c.name === categoryName) return { ...c, amount: Math.max(0, c.amount + amount) }
    return c
  })
  const newTotal = newCategories.reduce((sum: number, cat: any) => sum + cat.amount, 0)

  await tripStore.updateTrip({
    ...trip.value,
    budget: { ...trip.value.budget, categories: newCategories, total: newTotal }
  })
}


// ===== 天气逻辑 =====
const isRefreshingWeather = ref(false)
const weatherTips = ref<string[]>([])

const refreshWeather = async () => {
  if (!trip.value?.destination || isRefreshingWeather.value) return
  isRefreshingWeather.value = true
  try {
    const weatherData = await tripApi.getWeather(trip.value.destination, trip.value.days?.length || 3)
    if (weatherData?.length) {
      const normalizedWeather = weatherData.map((item) => ({
        date: item.date,
        high: Number(item.temperature) + 3,
        low: Number(item.temperature) - 3,
        condition: item.condition || '晴朗',
        precipitation: 0,
        humidity: Number(item.humidity) || 60,
        windSpeed: Number(item.wind_speed) || 10,
        icon: item.icon
      }))
      // 通过 Store 更新状态，避免直接修改 computed 属性
      await tripStore.updateTrip({ ...trip.value, weather: normalizedWeather })
      generateWeatherTips(normalizedWeather)
    }
  } catch (error) {
    console.error('刷新天气失败', error)
  } finally {
    isRefreshingWeather.value = false
  }
}

const generateWeatherTips = (weatherArray: any[]) => {
  const tips = []
  const hasRain = weatherArray.some(w => w.condition?.includes('雨'))
  if (hasRain) tips.push('行程中有雨天，建议携带雨具。')
  weatherTips.value = tips
}

const getWeatherIcon = (condition: string) => {
  const iconMap: Record<string, string> = { '晴朗': '☀️', '多云': '⛅', '雨': '🌧️', '雪': '❄️' }
  return iconMap[condition] || '🌤️'
}

const fallbackImage = 'https://picsum.photos/seed/travel-fallback/1200/800'

const getActivityImage = (activity: any, index: number) => {
  if (activity?.image) return activity.image
  const seed = encodeURIComponent(`${trip.value?.destination || 'trip'}-${activeDayIndex.value}-${index}`)
  return `https://picsum.photos/seed/${seed}/1200/800`
}

const handleImageError = (event: Event) => {
  const target = event.target as HTMLImageElement | null
  if (!target) return
  if (target.src !== fallbackImage) {
    target.src = fallbackImage
  }
}


// ===== 导出与工具方法 =====
const formatDate = (date: string) => date ? new Date(date).toLocaleDateString('zh-CN') : ''
const formatDayDate = (date: string) => {
  if (!date) return ''
  const d = new Date(date)
  return `周${['日','一','二','三','四','五','六'][d.getDay()]} ${d.getMonth() + 1}/${d.getDate()}`
}

const exportToPDF = async () => {
  if (!trip.value) return
  try {
    const pdf = new jsPDF('p', 'mm', 'a4')
    let y = 16
    const lineHeight = 7

    pdf.setFontSize(16)
    pdf.text(`${trip.value.destination} Trip Plan`, 14, y)
    y += lineHeight
    pdf.setFontSize(11)
    pdf.text(`Date: ${trip.value.startDate} - ${trip.value.endDate}`, 14, y)
    y += lineHeight
    pdf.text(`Travelers: ${trip.value.travelers}  Budget: CNY ${trip.value.budget?.total || 0}`, 14, y)
    y += lineHeight + 2

    pdf.setFontSize(13)
    pdf.text('Daily Itinerary', 14, y)
    y += lineHeight
    pdf.setFontSize(10)

    for (const [index, day] of trip.value.days.entries()) {
      if (y > 275) {
        pdf.addPage()
        y = 16
      }
      pdf.setFontSize(11)
      pdf.text(`Day ${index + 1} - ${day.date}`, 14, y)
      y += lineHeight
      pdf.setFontSize(10)

      for (const activity of day.activities) {
        if (y > 280) {
          pdf.addPage()
          y = 16
        }
        const text = `${activity.time} ${activity.title} | ${activity.location} | CNY ${activity.cost}`
        const lines = pdf.splitTextToSize(text, 180)
        pdf.text(lines, 16, y)
        y += lineHeight * lines.length
      }
      y += 2
    }

    if (y > 250) {
      pdf.addPage()
      y = 16
    }
    pdf.setFontSize(13)
    pdf.text('Budget Breakdown', 14, y)
    y += lineHeight
    pdf.setFontSize(10)
    trip.value.budget?.categories?.forEach((cat: any) => {
      pdf.text(`${cat.name}: CNY ${cat.amount}`, 16, y)
      y += lineHeight
    })

    pdf.save(`${trip.value.destination}_travel_plan.pdf`)
  } catch (err) {
    alert('导出失败')
  }
}

const exportToImage = async () => {
  const el = document.querySelector('.container') as HTMLElement
  if (!el) return
  const canvas = await html2canvas(el, { scale: 2, useCORS: true })
  const link = document.createElement('a')
  link.download = `${trip.value?.destination}_旅行计划.png`
  link.href = canvas.toDataURL('image/png')
  link.click()
}


// ===== 生命周期 =====
onMounted(() => {
  const tripId = route.params.id as string
  if (tripId && tripStore.currentTrip?.id !== tripId) {
    tripStore.loadTrip(tripId)
  }
  // 首次加载若存在天气数据，生成一下 Tips
  if (trip.value?.weather?.length) {
    generateWeatherTips(trip.value.weather)
  } else {
    refreshWeather()
  }
})
</script>
