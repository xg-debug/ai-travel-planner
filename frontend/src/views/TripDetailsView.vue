<template>
  <div class="min-h-screen bg-[#f6f7f9]">
    <TravelNav @auth="openAuth" />

    <AuthModal v-if="showAuthModal" :show="showAuthModal" :initial-mode="authMode" @close="showAuthModal = false" />

    <div class="py-10" v-if="trip">
      <div class="container mx-auto max-w-6xl px-5">
        <button @click="router.push('/')" class="mb-8 flex items-center space-x-2 text-sm font-semibold text-slate-500 transition-colors hover:text-violet-700">
          <span>← 返回行程规划</span>
        </button>

        <div class="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 class="mb-3 text-4xl font-black tracking-[-0.04em] text-slate-950 md:text-5xl">{{ trip.destination }}</h1>
            <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-slate-500">
              <span>📅 {{ formatDate(trip.startDate) }} - {{ formatDate(trip.endDate) }}</span>
              <span>👥 {{ trip.travelers }} 人</span>
            </div>
          </div>

          <div class="flex gap-4">
            <div class="min-w-[132px] rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm">
              <div class="mb-1 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">总预算</div>
              <div class="text-2xl font-black text-teal-700">¥{{ trip.budget?.total?.toLocaleString() }}</div>
            </div>
            <div class="flex flex-col gap-2">
              <button @click="router.push('/map')" class="rounded-xl bg-slate-950 px-4 py-2 text-white transition-colors hover:bg-slate-800">查看地图</button>
              <button @click="exportToPDF" class="rounded-xl bg-violet-600 px-4 py-2 text-white shadow-sm transition-colors hover:bg-violet-700">导出 PDF</button>
              <button @click="exportToImage" class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-slate-700 transition-colors hover:bg-slate-50">导出图片</button>
            </div>
          </div>
        </div>

        <div v-if="trip.planningWarnings?.length" role="status" class="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p v-for="warning in trip.planningWarnings" :key="warning">{{ warning }}</p>
        </div>

        <div v-if="editError" role="alert" class="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{{ editError }}</div>

        <div class="mb-8 grid gap-6 lg:grid-cols-3">
          <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
            <h2 class="mb-3 text-lg font-bold text-gray-900">行程概览</h2>
            <div
              class="trip-plan-content prose prose-slate max-w-none text-sm leading-7"
              v-html="renderedPlanHtml"
            ></div>
          </div>
          <div class="overflow-hidden rounded-2xl border border-sky-100 bg-[radial-gradient(circle_at_top_right,#dbeafe_0%,#eff6ff_38%,#ffffff_100%)] p-6 shadow-sm">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="text-lg font-bold text-slate-900">景点地图</h2>
                <p class="mt-2 text-sm text-slate-600">已识别可定位活动 {{ mappedActivityCount }} 个，按天查看路线重点与落点。</p>
              </div>
              <div class="rounded-2xl bg-white/80 px-3 py-2 text-right shadow-sm">
                <div class="text-xs uppercase tracking-[0.18em] text-slate-400">Map</div>
                <div class="text-sm font-semibold text-slate-900">{{ trip.days.length }} 天</div>
              </div>
            </div>
            <div class="mt-5 grid gap-3">
              <div
                v-for="summary in routeDaySummaries"
                :key="summary.label"
                class="rounded-2xl border border-white/80 bg-white/85 p-4 shadow-sm"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0">
                    <div class="text-sm font-semibold text-slate-900">{{ summary.label }}</div>
                    <div class="mt-1 text-sm text-slate-500">{{ summary.title }}</div>
                  </div>
                  <span class="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">{{ summary.countLabel }}</span>
                </div>
                <div class="mt-3 text-xs leading-5 text-slate-500">{{ summary.preview }}</div>
              </div>
            </div>
            <button
              @click="router.push('/map')"
              class="mt-5 w-full rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-slate-800"
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
                  <button v-if="lastDayEdit?.tripId === trip.id && lastDayEdit.index === activeDayIndex" @click="undoLastDayEdit" class="px-3 py-1 rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-50">撤销上次修改</button>
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
                  <div class="grid gap-4 md:grid-cols-[180px_1fr_0.7fr]">
                    <img
                      :src="getHotelImage(activeDay.hotel)"
                      :alt="activeDay.hotel.name"
                      class="h-40 w-full rounded-2xl object-cover md:h-full"
                      loading="lazy"
                      decoding="async"
                      @error="handleImageError"
                    />
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
                            <div class="text-lg font-bold text-slate-900">{{ mealDisplayName(meal) }}</div>
                            <div class="mt-1 text-sm text-slate-500">{{ meal.time }} · {{ meal.location }}</div>
                          </div>
                          <div class="text-right">
                            <div class="text-lg font-semibold text-teal-700">¥{{ meal.cost }}</div>
                            <div class="mt-1 text-xs text-slate-400">预计餐费</div>
                          </div>
                        </div>
                        <div v-if="mealCuisineHint(meal)" class="inline-flex rounded-full bg-white px-3 py-1 text-xs font-medium text-amber-700 shadow-sm">
                          推荐菜品：{{ mealCuisineHint(meal) }}
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
                <div
                  v-for="w in trip.weather"
                  :key="w.date"
                  class="flex items-center justify-between gap-4 rounded-xl border border-slate-100 bg-slate-50/70 p-3 hover:bg-slate-50"
                >
                  <div class="min-w-[84px]">
                    <div class="text-sm font-semibold text-slate-800">{{ formatMonthDay(w.date) }}</div>
                    <div class="mt-1 text-xs text-slate-500">{{ formatDayDate(w.date) }}</div>
                  </div>
                  <div class="flex min-w-0 flex-1 items-center gap-3">
                    <div class="text-2xl">{{ getWeatherIcon(w.dayCondition || w.condition) }}</div>
                    <div class="min-w-0 text-xs leading-5 text-slate-600">
                      <div>白天: {{ w.dayCondition || w.condition }}</div>
                      <div>夜间: {{ w.nightCondition || w.condition }}</div>
                    </div>
                  </div>
                  <div class="text-right">
                    <div class="text-sm font-semibold text-slate-900">{{ w.low }}°~{{ w.high }}°</div>
                    <div class="mt-1 text-xs text-slate-500">{{ buildWindLabel(w) }}</div>
                  </div>
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
                  class="overflow-hidden rounded-xl border border-gray-100 bg-slate-50"
                >
                  <img :src="getHotelImage(hotel)" :alt="hotel.name" class="h-32 w-full object-cover" loading="lazy" decoding="async" @error="handleImageError" />
                  <div class="p-4">
                    <div class="font-semibold leading-6 text-gray-900">{{ hotel.name }}</div>
                    <div v-if="hotel.address" class="mt-1 text-xs leading-5 text-gray-500">{{ hotel.address }}</div>
                    <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
                      <div class="rounded-full bg-white px-3 py-1 text-xs font-semibold text-teal-600 shadow-sm">
                        {{ hotel.priceText || formatPriceRange(hotel.priceRange) }}
                      </div>
                      <div class="text-xs text-amber-600">⭐ {{ hotel.rating.toFixed(1) }}</div>
                    </div>
                    <p class="mt-3 text-sm leading-6 text-gray-600">{{ hotel.description }}</p>
                  </div>
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
import type { Activity, TripDay } from '@/types/trip'

// ===== 基础定义 =====
const route = useRoute()
const router = useRouter()
const tripStore = useTripStore()

// 获取 Store 中的数据
const trip = computed(() => tripStore.currentTrip)
const weatherCityLabel = computed(() => trip.value?.weather?.[0]?.city || trip.value?.destination || '当前目的地')
const routeDaySummaries = computed(() =>
  (trip.value?.days || []).map((day: any, index: number) => {
    const activities = day.activities || []
    const mappedStops = activities.filter((activity: any) => activity.coordinates?.lat && activity.coordinates?.lng).length
    const scenic = activities.filter((activity: any) => isScenicLikeActivity(activity))
    const title = day.theme || day.notes || scenic[0]?.location || scenic[0]?.title || `第 ${index + 1} 天路线`
    const previewItems = scenic.length
      ? scenic.slice(0, 3).map((item: any) => item.location || item.title)
      : activities.slice(0, 3).map((item: any) => item.location || item.title)
    return {
      label: `Day ${index + 1}`,
      title,
      countLabel: mappedStops > 0 ? `${mappedStops} 个点位` : `${activities.length} 项安排`,
      preview: previewItems.join(' → ') || '等待生成路线重点'
    }
  })
)
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
const textIncludesAny = (activity: Activity | any, keywords: string[], fields: Array<'title' | 'location' | 'description' | 'notes'> = ['title', 'location', 'description', 'notes']) => {
  const text = fields
    .map((field) => activity?.[field])
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return keywords.some((keyword) => text.includes(keyword.toLowerCase()))
}

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const renderMarkdownToHtml = (source: string) => {
  const text = String(source || '').trim()
  if (!text) {
    return '<p>已生成行程，可在下方按天查看并编辑细节。</p>'
  }

  const lines = text.split('\n')
  const blocks: string[] = []
  let listItems: string[] = []
  let paragraphLines: string[] = []

  const flushList = () => {
    if (!listItems.length) return
    blocks.push(`<ul>${listItems.map((item) => `<li>${item}</li>`).join('')}</ul>`)
    listItems = []
  }

  const flushParagraph = () => {
    if (!paragraphLines.length) return
    blocks.push(`<p>${paragraphLines.join('<br />')}</p>`)
    paragraphLines = []
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      flushList()
      flushParagraph()
      continue
    }

    const escaped = escapeHtml(trimmed)
    if (trimmed.startsWith('### ')) {
      flushList()
      flushParagraph()
      blocks.push(`<h3>${escapeHtml(trimmed.slice(4))}</h3>`)
      continue
    }
    if (trimmed.startsWith('## ')) {
      flushList()
      flushParagraph()
      blocks.push(`<h2>${escapeHtml(trimmed.slice(3))}</h2>`)
      continue
    }
    if (trimmed.startsWith('# ')) {
      flushList()
      flushParagraph()
      blocks.push(`<h1>${escapeHtml(trimmed.slice(2))}</h1>`)
      continue
    }
    if (trimmed.startsWith('- ')) {
      flushParagraph()
      listItems.push(escapeHtml(trimmed.slice(2)))
      continue
    }
    flushList()
    paragraphLines.push(escaped)
  }

  flushList()
  flushParagraph()
  return blocks.join('')
}

const renderedPlanHtml = computed(() => renderMarkdownToHtml(trip.value?.plan || ''))

const isMealLikeActivity = (activity: Activity | any) => {
  const mealInTitle = textIncludesAny(activity, ['饭店', '餐厅', '餐馆', '小吃', '早餐', '午餐', '晚餐', '咖啡', '面馆', '酒家', '火锅', '烧烤', '茶馆'], ['title'])
  const mealInLocation = textIncludesAny(activity, ['饭店', '餐厅', '餐馆', '小吃', '咖啡', '面馆', '酒家', '火锅', '烧烤', '茶馆'], ['location'])
  const scenicInTitle = textIncludesAny(activity, ['参观', '博物馆', '景区', '古镇', '公园', '展馆', '遗址', '街区'], ['title'])
  if (scenicInTitle) return false
  return activity?.type === 'food' || mealInTitle || mealInLocation
}

const isScenicLikeActivity = (activity: Activity | any) => {
  if (isMealLikeActivity(activity)) return false
  return activity?.type === 'culture'
    || activity?.type === 'outdoor'
    || activity?.type === 'shopping'
    || textIncludesAny(activity, ['公园', '博物馆', '旧址', '故居', '景区', '街区', '古镇', '湖', '塔', '寺', '院', '展馆', '美术馆', '遗址', '地标', '记忆'])
}

const uniqueActivitiesByLocation = (activities: (Activity | any)[]) => {
  const seen = new Set<string>()
  return activities.filter((activity) => {
    const sourceId = String(activity?.source_id || '').trim()
    const location = String(activity?.location || activity?.title || '').trim()
    const key = `${sourceId || location}::${location}`
    if (!location || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const dayAttractions = computed(() =>
  uniqueActivitiesByLocation((activeDay.value?.activities || []).filter((activity) => isScenicLikeActivity(activity)))
)
const dayMeals = computed(() =>
  (activeDay.value?.activities || []).filter((activity) => isMealLikeActivity(activity))
)
const dayOtherActivities = computed(() =>
  (activeDay.value?.activities || []).filter((activity) => !isScenicLikeActivity(activity) && !isMealLikeActivity(activity))
)
const isEditingActivities = ref(false)

const mealDisplayName = (activity: Activity | any) => {
  const location = String(activity?.location || '').trim()
  const title = String(activity?.title || '').trim()
  if (location && location !== title) return location
  return title.replace(/^\d{1,2}:\d{2}\s*[·\-]\s*/, '').replace(/（第\d+天）/g, '').trim() || '餐饮点'
}

const mealCuisineHint = (activity: Activity | any) => {
  const text = [activity?.notes, activity?.description].filter(Boolean).join(' ')
  const matches = text.match(/(?:招牌|推荐|必点|特色)[：:\s]*([^，。；]{2,20})/g)
  if (!matches?.length) return ''
  return matches
    .map((item) => item.replace(/^(招牌|推荐|必点|特色)[：:\s]*/, '').trim())
    .filter(Boolean)
    .slice(0, 2)
    .join(' / ')
}

const showActivityModal = ref(false)
const editError = ref('')
const lastDayEdit = ref<{ tripId: string; index: number; day: TripDay } | null>(null)

const rememberDay = (day: TripDay) => {
  if (trip.value) lastDayEdit.value = { tripId: trip.value.id, index: activeDayIndex.value, day: JSON.parse(JSON.stringify(day)) as TripDay }
}

const undoLastDayEdit = async () => {
  const previous = lastDayEdit.value
  if (!previous || previous.tripId !== trip.value?.id) return
  try {
    editError.value = ''
    await tripStore.updateTripDay(previous.index, previous.day)
    lastDayEdit.value = null
  } catch (error) {
    editError.value = error instanceof Error ? error.message : '撤销失败'
  }
}
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
  editError.value = ''
  
  // 深拷贝当前活动列表
  const newActivities = [...activeDay.value.activities]
  
  if (editingActivityIndex.value >= 0) {
    newActivities[editingActivityIndex.value] = { ...activityForm.value, id: newActivities[editingActivityIndex.value].id }
  } else {
    newActivities.push({ ...activityForm.value, id: `act_${Date.now()}` })
  }
  // 按时间排序
  newActivities.sort((a, b) => a.time.localeCompare(b.time))

  try {
    const previous = activeDay.value
    await tripStore.updateTripDay(activeDayIndex.value, { ...activeDay.value, activities: newActivities })
    rememberDay(previous)
    showActivityModal.value = false
  } catch (error) {
    editError.value = error instanceof Error ? error.message : '保存活动失败'
  }
}

// 移动活动排序
const moveActivity = async (index: number, direction: -1 | 1) => {
  if (!activeDay.value || !trip.value) return
  const newActivities = [...activeDay.value.activities]
  const targetIndex = index + direction
  
  if (targetIndex >= 0 && targetIndex < newActivities.length) {
    [newActivities[index], newActivities[targetIndex]] = [newActivities[targetIndex], newActivities[index]]
    try {
      editError.value = ''
      const previous = activeDay.value
      await tripStore.updateTripDay(activeDayIndex.value, { ...activeDay.value, activities: newActivities })
      rememberDay(previous)
    } catch (error) {
      editError.value = error instanceof Error ? error.message : '调整顺序失败'
    }
  }
}

const removeActivity = async (index: number) => {
  if (!activeDay.value || !trip.value || !confirm('确定要删除这个活动吗？')) return
  const newActivities = [...activeDay.value.activities]
  newActivities.splice(index, 1)
  try {
    editError.value = ''
    const previous = activeDay.value
    await tripStore.updateTripDay(activeDayIndex.value, { ...activeDay.value, activities: newActivities })
    rememberDay(previous)
  } catch (error) {
    editError.value = error instanceof Error ? error.message : '删除活动失败'
  }
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

  try {
    editError.value = ''
    await tripStore.updateTrip({
      ...trip.value,
      budget: { ...trip.value.budget, categories: newCategories, total: newTotal }
    })
  } catch (error) {
    editError.value = error instanceof Error ? error.message : '更新预算失败'
  }
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
        dayCondition: item.day_condition || item.condition || '晴朗',
        nightCondition: item.night_condition || item.condition || '晴朗',
        precipitation: 0,
        humidity: Number(item.humidity) || 60,
        windSpeed: Number(item.wind_speed) || 10,
        dayWindDirection: item.day_wind_direction || '',
        nightWindDirection: item.night_wind_direction || '',
        dayWindPower: item.day_wind_power || '',
        nightWindPower: item.night_wind_power || '',
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

const getHotelImage = (hotel: any) => {
  const matched = trip.value?.hotels?.find((item: any) => item.name === hotel?.name)
  return hotel?.image || hotel?.images?.[0] || matched?.images?.[0] || fallbackImage
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
const formatMonthDay = (date: string) => {
  if (!date) return ''
  const d = new Date(date)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

const buildWindLabel = (weather: any) => {
  const dayDirection = weather?.dayWindDirection || weather?.nightWindDirection || ''
  const dayPower = weather?.dayWindPower || weather?.nightWindPower || ''
  if (dayDirection && dayPower) return `${dayDirection} ${dayPower}级`
  return `${weather?.windSpeed || 0}级`
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

<style scoped>
.trip-plan-content :deep(h1) {
  margin: 0 0 1rem;
  font-size: 1.9rem;
  line-height: 1.2;
  font-weight: 800;
  color: #0f172a;
}

.trip-plan-content :deep(h2) {
  margin: 1.75rem 0 0.9rem;
  font-size: 1.2rem;
  line-height: 1.4;
  font-weight: 700;
  color: #0f172a;
}

.trip-plan-content :deep(h3) {
  margin: 1.25rem 0 0.7rem;
  font-size: 1rem;
  line-height: 1.5;
  font-weight: 700;
  color: #1e293b;
}

.trip-plan-content :deep(p) {
  margin: 0.85rem 0;
  color: #475569;
}

.trip-plan-content :deep(ul) {
  margin: 0.8rem 0 1rem;
  padding-left: 1.2rem;
  color: #475569;
  list-style: disc;
}

.trip-plan-content :deep(li) {
  margin: 0.35rem 0;
}
</style>
