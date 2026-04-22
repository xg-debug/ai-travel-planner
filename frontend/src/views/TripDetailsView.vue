<template>
  <div class="min-h-screen bg-gray-50">
    <TravelNav @auth="openAuth" />

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

              <div v-if="!isEditingActivities" class="space-y-8">
                <section v-if="dayAttractions.length" class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div class="mb-5 flex items-center justify-between">
                    <div>
                      <h3 class="text-lg font-bold text-slate-900">景点安排</h3>
                      <p class="mt-1 text-sm text-slate-500">把当天重点景点集中展示，路线更好扫一眼看清。</p>
                    </div>
                    <span class="rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">{{ dayAttractions.length }} 个景点</span>
                  </div>
                  <div class="grid gap-5 md:grid-cols-2">
                    <article v-for="(activity, index) in dayAttractions" :key="activity.id" class="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50/70">
                      <div class="relative">
                        <img :src="getActivityImage(activity)" :alt="activity.title" class="h-52 w-full object-cover object-center" loading="lazy" decoding="async" @error="handleImageError" />
                        <div class="absolute left-4 top-4 rounded-full bg-white/92 px-3 py-1 text-xs font-semibold text-slate-700 shadow">
                          景点 {{ index + 1 }}
                        </div>
                        <div v-if="activity.ticketPrice !== undefined" class="absolute right-4 top-4 rounded-full bg-white/95 px-3 py-1 text-sm font-semibold text-teal-700 shadow">
                          {{ activity.ticketPrice > 0 ? `¥${activity.ticketPrice}` : '免费' }}
                        </div>
                      </div>
                      <div class="space-y-3 p-5">
                        <div class="flex items-start justify-between gap-4">
                          <div>
                            <div class="text-xl font-bold text-slate-900">{{ activity.location }}</div>
                            <div class="mt-1 text-sm text-slate-500">{{ activity.time }} · {{ activity.duration }} 分钟</div>
                          </div>
                          <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{{ activityTypeLabel(activity) }}</span>
                        </div>
                        <p class="text-sm leading-7 text-slate-600">{{ activity.description }}</p>
                        <div class="text-sm text-slate-500">地址：{{ activity.location }}</div>
                      </div>
                    </article>
                  </div>
                </section>

                <section v-if="activeDay.hotel" class="rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50 to-cyan-50 p-5 shadow-sm">
                  <div class="mb-4 text-sm font-medium text-blue-600">住宿推荐</div>
                  <div class="grid gap-4 md:grid-cols-[1.3fr_0.7fr]">
                    <div>
                      <div class="text-xl font-bold text-gray-900">{{ activeDay.hotel.name }}</div>
                      <div v-if="activeDay.hotel.address" class="mt-2 text-sm text-gray-600">📍 {{ activeDay.hotel.address }}</div>
                      <p v-if="activeDay.hotel.reason" class="mt-3 text-sm leading-6 text-gray-700">{{ activeDay.hotel.reason }}</p>
                    </div>
                    <div class="flex flex-col gap-3 rounded-2xl bg-white/80 p-4 shadow-sm">
                      <div class="text-sm text-slate-500">住宿价格</div>
                      <div class="text-xl font-bold text-teal-700">{{ formatHotelPrice(activeDay.hotel.priceEstimate) }}</div>
                      <div v-if="activeDay.hotel.rating" class="text-sm text-amber-600">评分：{{ activeDay.hotel.rating.toFixed(1) }}</div>
                    </div>
                  </div>
                </section>

                <section v-if="dayMeals.length" class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div class="mb-5 flex items-center justify-between">
                    <div>
                      <h3 class="text-lg font-bold text-slate-900">餐饮安排</h3>
                      <p class="mt-1 text-sm text-slate-500">把早餐、午餐、晚餐放在一起，方便查看整天的节奏搭配。</p>
                    </div>
                    <span class="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">{{ dayMeals.length }} 个餐饮点</span>
                  </div>
                  <div class="space-y-4">
                    <article v-for="meal in dayMeals" :key="meal.id" class="grid gap-4 rounded-2xl border border-amber-100 bg-amber-50/40 p-4 md:grid-cols-[220px_1fr]">
                      <div class="overflow-hidden rounded-2xl border border-amber-100 bg-white">
                        <img :src="getActivityImage(meal)" :alt="meal.title" class="h-40 w-full object-cover object-center" loading="lazy" decoding="async" @error="handleImageError" />
                      </div>
                      <div class="space-y-3">
                        <div class="flex items-start justify-between gap-4">
                          <div>
                            <div class="text-lg font-bold text-slate-900">{{ meal.time }} · {{ meal.title }}</div>
                            <div class="mt-1 text-sm text-slate-500">{{ meal.location }}</div>
                          </div>
                          <div class="text-right">
                            <div class="text-lg font-semibold text-teal-700">¥{{ meal.cost }}</div>
                            <div v-if="meal.ticketLabel" class="mt-1 text-xs text-slate-400">{{ meal.ticketLabel }}</div>
                          </div>
                        </div>
                        <p class="text-sm leading-7 text-slate-600">{{ meal.description }}</p>
                      </div>
                    </article>
                  </div>
                </section>

                <section v-if="dayOtherActivities.length" class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h3 class="mb-4 text-lg font-bold text-slate-900">其他安排</h3>
                  <div class="space-y-3">
                    <div v-for="activity in dayOtherActivities" :key="activity.id" class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div class="flex items-start justify-between gap-4">
                        <div>
                          <div class="font-semibold text-slate-900">{{ activity.time }} · {{ activity.title }}</div>
                          <div class="mt-1 text-sm text-slate-500">{{ activity.location }}</div>
                        </div>
                        <span class="rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold text-slate-700">{{ activity.type }}</span>
                      </div>
                      <p class="mt-3 text-sm leading-6 text-slate-600">{{ activity.description }}</p>
                    </div>
                  </div>
                </section>
              </div>

              <div v-else class="space-y-6">
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
                        :src="getActivityImage(activity)"
                        :alt="activity.title"
                        class="h-52 w-full object-cover object-center md:h-60"
                        loading="lazy"
                        decoding="async"
                        @error="handleImageError"
                      />
                    </div>
                    <div class="flex justify-between mb-2">
                      <div>
                        <div class="font-bold text-lg text-gray-800">{{ activity.time }} - {{ activity.title }}</div>
                        <div v-if="activity.ticketLabel" class="mt-2 inline-flex rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                          {{ activity.ticketLabel }}
                        </div>
                      </div>
                      <div class="text-right">
                        <div class="text-teal-600 font-medium">¥{{ activity.cost }}</div>
                        <div v-if="activity.ticketPrice !== undefined" class="mt-1 text-xs text-gray-500">
                          门票{{ activity.ticketPrice > 0 ? ` ¥${activity.ticketPrice}` : ' 免费' }}
                        </div>
                      </div>
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
                <div>
                  <h3 class="font-bold text-gray-800">天气预报</h3>
                  <p class="mt-1 text-xs text-gray-500">{{ weatherCityLabel }}</p>
                </div>
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
              <div class="mb-4 flex items-center justify-between">
                <h3 class="font-bold text-gray-800">推荐酒店</h3>
                <span class="text-xs text-gray-400">{{ trip.hotels?.length || 0 }} 家</span>
              </div>
              <div v-if="trip.hotels?.length" class="space-y-3">
                <div
                  v-for="hotel in trip.hotels"
                  :key="hotel.id"
                  class="rounded-xl border border-gray-100 bg-slate-50 p-4"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <div class="font-semibold text-gray-900">{{ hotel.name }}</div>
                      <div v-if="hotel.address" class="mt-1 text-xs text-gray-500">{{ hotel.address }}</div>
                    </div>
                    <div class="shrink-0 text-right">
                      <div class="whitespace-nowrap rounded-full bg-white px-3 py-1 text-sm font-semibold text-teal-600 shadow-sm">
                        {{ hotel.priceText || formatPriceRange(hotel.priceRange) }}
                      </div>
                      <div class="mt-1 text-xs text-amber-600">⭐ {{ hotel.rating.toFixed(1) }}</div>
                    </div>
                  </div>
                  <p class="mt-3 text-sm leading-6 text-gray-600">{{ hotel.description }}</p>
                </div>
              </div>
              <div v-else class="text-sm text-gray-500">本次行程暂无可展示的酒店推荐。</div>
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
import { tripApi } from '@/services/api'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import TravelNav from '@/components/TravelNav.vue'
import AuthModal from '@/components/AuthModal.vue'
import type { Activity } from '@/types/trip'

// ===== 基础定义 =====
const route = useRoute()
const router = useRouter()
const tripStore = useTripStore()

// 获取 Store 中的数据
const trip = computed(() => tripStore.currentTrip)
const weatherCityLabel = computed(() => trip.value?.weather?.[0]?.city || trip.value?.destination || '当前目的地')
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
const textIncludesAny = (activity: Activity | any, keywords: string[]) => {
  const text = [activity?.title, activity?.location, activity?.description, activity?.notes]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return keywords.some((keyword) => text.includes(keyword.toLowerCase()))
}

const isMealLikeActivity = (activity: Activity | any) => {
  return activity?.type === 'food' || textIncludesAny(activity, ['饭店', '餐厅', '餐馆', '小吃', '早餐', '午餐', '晚餐', '咖啡', '面馆', '酒家'])
}

const isScenicLikeActivity = (activity: Activity | any) => {
  if (isMealLikeActivity(activity)) return false
  return activity?.type === 'culture'
    || activity?.type === 'outdoor'
    || activity?.type === 'shopping'
    || textIncludesAny(activity, ['公园', '博物馆', '旧址', '故居', '景区', '街区', '古镇', '湖', '塔', '寺', '展馆', '美术馆', '遗址'])
}

const dayAttractions = computed(() =>
  (activeDay.value?.activities || []).filter((activity) => isScenicLikeActivity(activity))
)
const dayMeals = computed(() =>
  (activeDay.value?.activities || []).filter((activity) => isMealLikeActivity(activity))
)
const dayOtherActivities = computed(() =>
  (activeDay.value?.activities || []).filter((activity) => !isScenicLikeActivity(activity) && !isMealLikeActivity(activity))
)
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
const formatHotelPrice = (value: string | number | undefined) => {
  if (value === undefined || value === null || value === '') return '价格待查询'
  if (typeof value === 'number') return `¥${value}/晚`
  const text = String(value).trim()
  if (!text) return '价格待查询'
  if (text.includes('免费')) return text
  if (text.startsWith('¥') || text.startsWith('￥')) return text
  if (/^\d+(\.\d+)?$/.test(text)) return `¥${text}/晚`
  return text
}

const formatPriceRange = (value: string | undefined) => {
  if (value === 'free') return '免费'
  if (!value) return '价格待查询'
  const mapping: Record<string, string> = {
    '$': '经济型',
    '$$': '中档',
    '$$$': '舒适型',
    '$$$$': '高端型'
  }
  return mapping[value] || value
}

const activityTypeLabel = (activity: Activity | any) => {
  if (isMealLikeActivity(activity)) return '餐饮'
  if (textIncludesAny(activity, ['博物馆', '旧址', '故居', '展馆', '美术馆', '遗址'])) return '人文'
  if (textIncludesAny(activity, ['公园', '湿地', '湖', '山', '森林'])) return '自然'
  if (textIncludesAny(activity, ['街区', '古镇', '商圈', '步行街'])) return '街区'
  if (activity?.type === 'shopping') return '街区'
  if (activity?.type === 'culture') return '人文'
  if (activity?.type === 'outdoor') return '自然'
  return '体验'
}

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
        city: trip.value?.destination,
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

const fallbackImage = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#e0f2fe"/>
        <stop offset="100%" stop-color="#fef3c7"/>
      </linearGradient>
    </defs>
    <rect width="1200" height="800" fill="url(#g)"/>
    <text x="80" y="390" font-size="56" font-family="Arial, sans-serif" fill="#0f172a" font-weight="700">Travel Image</text>
    <text x="80" y="460" font-size="28" font-family="Arial, sans-serif" fill="#475569">Image unavailable</text>
  </svg>`
)}`

const getActivityImage = (activity: any) => {
  if (activity?.image) {
    return activity.image
  }
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#dbeafe"/>
          <stop offset="100%" stop-color="#dcfce7"/>
        </linearGradient>
      </defs>
      <rect width="1200" height="800" fill="url(#g)"/>
      <text x="80" y="360" font-size="52" font-family="Arial, sans-serif" fill="#0f172a" font-weight="700">${trip.value?.destination || 'Trip'}</text>
      <text x="80" y="430" font-size="28" font-family="Arial, sans-serif" fill="#334155">${activity?.location || activity?.title || 'Activity'}</text>
      <text x="80" y="490" font-size="22" font-family="Arial, sans-serif" fill="#64748b">AI Travel Planner</text>
    </svg>`
  )}`
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
      if (day.hotel?.name) {
        const hotelLine = `Hotel: ${day.hotel.name} | ${formatHotelPrice(day.hotel.priceEstimate)}`
        const hotelLines = pdf.splitTextToSize(hotelLine, 180)
        pdf.text(hotelLines, 16, y)
        y += lineHeight * hotelLines.length
      }
      pdf.setFontSize(10)

      for (const activity of day.activities) {
        if (y > 280) {
          pdf.addPage()
          y = 16
        }
        const ticketSuffix = activity.ticketPrice !== undefined ? ` | Ticket ${activity.ticketPrice > 0 ? `CNY ${activity.ticketPrice}` : 'Free'}` : ''
        const text = `${activity.time} ${activity.title} | ${activity.location} | CNY ${activity.cost}${ticketSuffix}`
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
