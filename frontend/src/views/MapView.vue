<template>
  <div class="min-h-screen bg-gradient-to-b from-travel-sky/10 to-white">
    <!-- 地图容器 -->
    <div ref="mapContainer" class="h-screen w-full relative">
      <!-- 加载覆盖层 -->
      <div
        v-if="isLoading"
        class="absolute inset-0 z-10 bg-white/90 backdrop-blur-sm flex items-center justify-center"
      >
        <div class="text-center">
          <div class="relative inline-block mb-6">
            <div class="w-20 h-20 border-4 border-travel-ocean border-t-transparent rounded-full animate-spin"></div>
            <div class="absolute inset-0 flex items-center justify-center">
              <div class="w-10 h-10 bg-gradient-to-r from-travel-ocean to-travel-mint rounded-full animate-pulse"></div>
            </div>
          </div>
          <p class="font-chinese text-xl tracking-wider text-travel-ocean animate-pulse">
            正在加载地图与路线...
          </p>
        </div>
      </div>

      <div
        v-if="mapError"
        class="absolute top-20 left-1/2 z-30 -translate-x-1/2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow"
      >
        {{ mapError }}
      </div>

      <div id="amap-container" class="absolute inset-0 z-0"></div>

      <!-- 地图控制按钮 -->
      <div class="absolute top-4 left-4 z-20 space-y-3">
        <button
          @click="toggleMapStyle"
          class="p-3 rounded-xl bg-white/90 backdrop-blur-sm border border-travel-sky/30 hover:border-travel-ocean transition-all duration-300 group shadow-travel-card"
          title="切换地图样式"
        >
          <svg class="w-6 h-6 text-travel-ocean group-hover:rotate-180 transition-transform duration-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
        </button>

        <button
          @click="resetView"
          class="p-3 rounded-xl bg-white/90 backdrop-blur-sm border border-travel-sky/30 hover:border-travel-ocean transition-all duration-300 group shadow-travel-card"
          title="重置视图"
        >
          <svg class="w-6 h-6 text-travel-ocean group-hover:rotate-180 transition-transform duration-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>

        <button
          @click="togglePOIs"
          class="p-3 rounded-xl bg-white/90 backdrop-blur-sm border border-travel-sky/30 hover:border-travel-ocean transition-all duration-300 group shadow-travel-card"
          :class="[showPOIs ? 'bg-travel-ocean/10 border-travel-ocean' : '']"
          title="显示/隐藏兴趣点"
        >
          <svg class="w-6 h-6 text-travel-ocean" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>

      <!-- 搜索面板 -->
      <div class="absolute top-4 right-4 z-20">
        <div class="bg-white/90 backdrop-blur-sm rounded-xl border border-travel-sky/20 p-5 max-w-xs shadow-travel-card">
          <h3 class="font-chinese text-lg text-travel-ocean mb-3">搜索兴趣点</h3>
          
          <!-- 搜索表单 -->
          <div class="space-y-3 mb-4">
            <div class="relative">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="搜索景点、餐厅、酒店..."
                class="w-full px-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-300"
                @keyup.enter="performSearch"
              />
              <button
                @click="performSearch"
                :disabled="isSearching || !searchQuery.trim()"
                class="absolute right-2 top-2 p-2 rounded-lg bg-travel-ocean text-white hover:bg-travel-ocean/90 transition-colors duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg v-if="isSearching" class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </button>
            </div>
            
            <select
              v-model="searchCategory"
              class="w-full px-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-300"
            >
              <option value="all">所有类别</option>
              <option value="景点">景点</option>
              <option value="餐厅">餐厅</option>
              <option value="酒店">酒店</option>
              <option value="购物">购物</option>
              <option value="交通">交通</option>
            </select>
          </div>
          
          <!-- 搜索结果 -->
          <div v-if="searchPOIs.length > 0" class="space-y-3 max-h-60 overflow-y-auto">
            <div
              v-for="poi in searchPOIs"
              :key="poi.id"
              class="p-3 rounded-lg border border-gray-200 hover:border-travel-ocean transition-colors duration-300 cursor-pointer"
              @click="selectPOI(poi)"
            >
              <div class="flex items-start justify-between">
                <div>
                  <h4 class="font-medium text-gray-900 mb-1">{{ poi.name }}</h4>
                  <div class="flex items-center space-x-2 text-sm text-gray-600">
                    <span>{{ poi.type }}</span>
                    <span>•</span>
                    <span class="flex items-center">
                      <svg class="w-3 h-3 text-amber-500 mr-1" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                      </svg>
                      {{ poi.rating }}
                    </span>
                  </div>
                </div>
                <div class="text-right">
                  <div class="text-sm font-medium text-travel-ocean">{{ poi.price }}</div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 地图图例 -->
          <div class="pt-4 border-t border-gray-200">
            <h4 class="text-sm font-medium text-gray-700 mb-2">地图图例</h4>
            <div class="space-y-2">
              <div class="flex items-center space-x-3">
                <div class="w-4 h-4 rounded-full bg-travel-ocean"></div>
                <span class="text-sm text-gray-600">您的位置</span>
              </div>
              <div class="flex items-center space-x-3">
                <div class="w-4 h-4 rounded-full bg-travel-mint"></div>
                <span class="text-sm text-gray-600">景点</span>
              </div>
              <div class="flex items-center space-x-3">
                <div class="w-4 h-4 rounded-full bg-travel-sun"></div>
                <span class="text-sm text-gray-600">餐厅</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="routeSummary || isRouteLoading"
        class="absolute bottom-28 left-4 z-20"
      >
        <div class="bg-white/92 backdrop-blur-sm rounded-xl border border-travel-sky/20 px-4 py-3 shadow-travel-card text-sm text-travel-gray">
          {{ isRouteLoading ? '正在计算 LLM 路线...' : routeSummary }}
        </div>
      </div>

      <!-- 坐标显示 -->
      <div class="absolute bottom-4 left-4 z-20">
        <div class="bg-white/90 backdrop-blur-sm rounded-xl border border-travel-sky/20 p-4 shadow-travel-card">
          <div class="font-chinese text-sm text-travel-gray">
            <div>纬度: {{ coordinates.lat.toFixed(4) }}</div>
            <div>经度: {{ coordinates.lng.toFixed(4) }}</div>
            <div>缩放: {{ zoomLevel.toFixed(1) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Selected POI Panel -->
    <div
      v-if="selectedPOI"
      class="absolute bottom-4 right-4 z-30 max-w-md"
    >
      <div class="bg-white/95 backdrop-blur-sm rounded-xl border border-travel-sky/30 p-6 shadow-travel-card">
        <div class="flex items-start justify-between mb-4">
          <div>
            <h3 class="font-chinese text-xl text-travel-ocean mb-1">{{ selectedPOI.name }}</h3>
            <div class="flex items-center space-x-2">
              <span class="text-sm text-travel-gray">{{ selectedPOI.type }}</span>
              <span class="text-sm text-travel-gray">•</span>
              <div class="flex items-center space-x-1">
                <svg class="w-4 h-4 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                <span class="text-sm text-travel-gray">{{ selectedPOI.rating }}</span>
              </div>
            </div>
          </div>
          <button
            @click="selectedPOI = null"
            class="p-1 rounded-lg hover:bg-travel-sky/10 transition-colors duration-300"
          >
            <svg class="w-5 h-5 text-travel-gray" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p class="text-travel-gray mb-4">{{ selectedPOI.description }}</p>

        <div class="space-y-3">
          <div class="flex items-center space-x-2">
            <svg class="w-4 h-4 text-travel-gray" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span class="text-sm text-travel-gray">{{ selectedPOI.address }}</span>
          </div>

          <div class="flex items-center space-x-3">
            <svg class="w-5 h-5 text-travel-gray" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-sm text-travel-gray">{{ selectedPOI.hours }}</span>
          </div>

          <div class="flex items-center space-x-3">
            <svg class="w-5 h-5 text-travel-gray" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-sm text-travel-gray">{{ selectedPOI.priceRange }}</span>
          </div>
        </div>

        <div class="mt-6 flex space-x-3">
          <button
            @click="addToItinerary(selectedPOI)"
            class="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-travel-ocean to-travel-mint text-white font-medium transition-all duration-300 hover:scale-105 shadow-travel-button"
          >
            添加到行程
          </button>
          <button
            @click="viewDetails(selectedPOI)"
            class="px-4 py-3 rounded-xl border border-travel-sky/30 bg-white/80 hover:bg-travel-sky/10 hover:border-travel-ocean transition-all duration-300 text-travel-ocean"
          >
            详情
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useTripStore } from '@/stores/tripStore'
import { tripApi } from '@/services/api'

const DEFAULT_COORDINATES = { lat: 39.9042, lng: 116.4074 }

const mapContainer = ref(null)
const isLoading = ref(true)
const isRouteLoading = ref(false)
const showPOIs = ref(true)
const selectedPOI = ref(null)
const coordinates = ref({ ...DEFAULT_COORDINATES })
const zoomLevel = ref(12)
const mapInstance = ref(null)
const markers = ref([])
const routeLayers = ref([])
const routeRequestToken = ref(0)
const routeStats = ref({ distance: 0, duration: 0, segments: 0 })
const mapError = ref('')

const tripStore = useTripStore()

const hasValidPosition = (value) => {
  if (!value) return false
  return Number.isFinite(Number(value.lat)) && Number.isFinite(Number(value.lng))
}

// 从行程数据中获取可展示的 POI
const tripPOIs = computed(() => {
  if (!tripStore.currentTrip) return []

  const pois = []
  const seenNames = new Set()

  tripStore.currentTrip.days?.forEach((day) => {
    day.activities?.forEach((activity, activityIndex) => {
      if (!activity.location || seenNames.has(activity.location)) return
      seenNames.add(activity.location)
      pois.push({
        id: `poi_${pois.length + 1}_${activityIndex + 1}`,
        name: activity.location,
        type: activity.type || 'attraction',
        description: activity.description || '',
        rating: 4.5,
        address: activity.notes || `${tripStore.currentTrip.destination}市${activity.location}`,
        hours: '09:00-17:00',
        priceRange: activity.cost ? `¥${activity.cost}` : '免费',
        position: hasValidPosition(activity.coordinates)
          ? {
              lat: Number(activity.coordinates.lat),
              lng: Number(activity.coordinates.lng)
            }
          : null
      })
    })
  })

  tripStore.currentTrip.recommendations?.forEach((rec) => {
    if (!rec.name || seenNames.has(rec.name)) return
    const position = hasValidPosition(rec.location)
      ? { lat: Number(rec.location.lat), lng: Number(rec.location.lng) }
      : null

    if (!position) return

    seenNames.add(rec.name)
    pois.push({
      id: `rec_${pois.length + 1}`,
      name: rec.name,
      type: rec.category || 'attraction',
      description: rec.description || '',
      rating: rec.rating || 4.5,
      address: `${tripStore.currentTrip.destination}市${rec.name}`,
      hours: rec.openingHours || '09:00-17:00',
      priceRange: rec.priceRange || '免费',
      position
    })
  })

  return pois
})

// 只用真实活动坐标来画 LLM 路线，避免随机推荐点干扰
const routePOIs = computed(() => {
  if (!tripStore.currentTrip?.days?.length) return []

  return tripStore.currentTrip.days.flatMap((day, dayIndex) =>
    (day.activities || [])
      .filter((activity) => hasValidPosition(activity.coordinates))
      .map((activity, activityIndex) => ({
        id: activity.id || `route_${dayIndex + 1}_${activityIndex + 1}`,
        name: activity.location,
        type: activity.type || 'attraction',
        description: activity.description || '',
        position: {
          lat: Number(activity.coordinates.lat),
          lng: Number(activity.coordinates.lng)
        }
      }))
  )
})

const routeSummary = computed(() => {
  if (!routeStats.value.segments) return ''
  const distanceKm = (routeStats.value.distance / 1000).toFixed(1)
  const durationMinutes = Math.round(routeStats.value.duration / 60)
  return `LLM 路线 ${routeStats.value.segments} 段 · 约 ${distanceKm} km · ${durationMinutes} 分钟`
})

// 搜索POI数据
const searchPOIs = ref([])
const isSearching = ref(false)
const searchQuery = ref('')
const searchCategory = ref('all')

onMounted(() => {
  loadAMapAPI()
})

const loadAMapAPI = () => {
  mapError.value = ''

  if (window.AMap) {
    initMap()
    return
  }

  const amapKey = import.meta.env.VITE_AMAP_KEY || import.meta.env.VITE_AMAP_API_KEY
  const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE
  if (!amapKey || String(amapKey).includes('YOUR_AMAP_KEY')) {
    mapError.value = '未配置前端地图 Key。请在 frontend/.env 配置 VITE_AMAP_KEY 后重启前端。'
    isLoading.value = false
    return
  }

  if (securityCode) {
    window._AMapSecurityConfig = {
      ...(window._AMapSecurityConfig || {}),
      securityJsCode: securityCode
    }
  }

  const existingScript = document.getElementById('amap-sdk')
  if (existingScript) {
    existingScript.addEventListener('load', initMap, { once: true })
    return
  }

  const script = document.createElement('script')
  script.id = 'amap-sdk'
  script.type = 'text/javascript'
  script.src = `https://webapi.amap.com/maps?v=2.0&key=${amapKey}`
  script.onload = () => {
    window.AMap.plugin(['AMap.ToolBar', 'AMap.Scale', 'AMap.MapType', 'AMap.Geolocation'], () => {
      initMap()
    })
  }
  script.onerror = () => {
    console.error('Failed to load AMap API')
    mapError.value = '地图加载失败，请检查高德 Key、域名白名单、安全码和网络连接。'
    isLoading.value = false
  }
  document.head.appendChild(script)
}

const initMap = () => {
  try {
    const container = document.getElementById('amap-container')
    if (!container || container.clientWidth === 0 || container.clientHeight === 0) {
      setTimeout(initMap, 120)
      return
    }

    const firstPoi = routePOIs.value[0] || tripPOIs.value.find((poi) => poi.position)
    if (firstPoi?.position) {
      coordinates.value = {
        lat: Number(firstPoi.position.lat),
        lng: Number(firstPoi.position.lng)
      }
    }

    if (mapInstance.value) {
      mapInstance.value.destroy()
      mapInstance.value = null
    }

    mapInstance.value = new window.AMap.Map(container, {
      zoom: zoomLevel.value,
      center: [coordinates.value.lng, coordinates.value.lat],
      resizeEnable: true,
      mapStyle: 'amap://styles/normal',
      viewMode: '2D',
      features: ['bg', 'road', 'building', 'point']
    })

    mapInstance.value.addControl(new window.AMap.ToolBar())
    mapInstance.value.addControl(new window.AMap.Scale())
    mapInstance.value.addControl(new window.AMap.MapType())

    const geolocation = new window.AMap.Geolocation({
      enableHighAccuracy: true,
      timeout: 10000,
      buttonOffset: new window.AMap.Pixel(10, 20),
      zoomToAccuracy: true,
      buttonPosition: 'RB'
    })
    mapInstance.value.addControl(geolocation)

    mapInstance.value.on('moveend', updateCoordinates)
    mapInstance.value.on('zoomend', updateZoomLevel)
    mapInstance.value.on('complete', async () => {
      if (!mapInstance.value) return
      mapInstance.value.resize()
      updateCoordinates()
      updateZoomLevel()
      addPOIMarkers()
      await drawRoute()
      isLoading.value = false
    })
  } catch (error) {
    console.error('Failed to initialize map:', error)
    mapError.value = '地图初始化失败，请检查高德配置后重试。'
    isLoading.value = false
  }
}

const clearRouteLayers = () => {
  routeLayers.value.forEach((layer) => layer.setMap(null))
  routeLayers.value = []
  routeStats.value = { distance: 0, duration: 0, segments: 0 }
}

onUnmounted(() => {
  clearRouteLayers()
  if (window.searchMarkers) {
    window.searchMarkers.forEach((marker) => marker.setMap(null))
    window.searchMarkers = []
  }
  if (mapInstance.value) {
    mapInstance.value.destroy()
    mapInstance.value = null
  }
})

watch(
  [tripPOIs, routePOIs],
  async () => {
    if (!mapInstance.value) return
    addPOIMarkers()
    await drawRoute()
  },
  { deep: true }
)

const toggleMapStyle = () => {
  if (!mapInstance.value) return

  const currentStyle = mapInstance.value.getMapStyle()
  const newStyle = currentStyle.includes('whitesmoke')
    ? 'amap://styles/normal'
    : 'amap://styles/whitesmoke'

  mapInstance.value.setMapStyle(newStyle)
}

const resetView = () => {
  const firstPoi = routePOIs.value[0] || tripPOIs.value.find((poi) => poi.position)
  if (mapInstance.value && firstPoi?.position) {
    mapInstance.value.setZoomAndCenter(13, [firstPoi.position.lng, firstPoi.position.lat])
    return
  }

  coordinates.value = { ...DEFAULT_COORDINATES }
  zoomLevel.value = 12
  if (mapInstance.value) {
    mapInstance.value.setZoomAndCenter(12, [coordinates.value.lng, coordinates.value.lat])
  }
}

const togglePOIs = () => {
  showPOIs.value = !showPOIs.value
  markers.value.forEach((marker) => {
    marker.setMap(showPOIs.value ? mapInstance.value : null)
  })
}

const selectPOI = (poi) => {
  selectedPOI.value = poi
  if (mapInstance.value && poi.position) {
    mapInstance.value.setCenter([poi.position.lng, poi.position.lat])
    mapInstance.value.setZoom(16)
  }
}

const addToItinerary = async (poi) => {
  if (!tripStore.currentTrip) return

  const currentTrip = tripStore.currentTrip
  const targetDayIndex = 0
  const targetDay = currentTrip.days?.[targetDayIndex]
  const nextDays = [...(currentTrip.days || [])]

  const newActivity = {
    id: `act_map_${Date.now()}`,
    time: '14:00',
    title: `探索 ${poi.name}`,
    description: poi.description || `前往 ${poi.name} 游览`,
    location: poi.name,
    type: mapPoiTypeToActivityType(poi.type),
    duration: 90,
    cost: parsePoiCost(poi.price || poi.priceRange),
    coordinates: poi.position ? { lat: poi.position.lat, lng: poi.position.lng } : undefined,
    notes: poi.address
  }

  if (targetDay) {
    nextDays[targetDayIndex] = {
      ...targetDay,
      activities: [...targetDay.activities, newActivity]
    }
  } else {
    nextDays.push({
      date: new Date().toISOString().split('T')[0],
      activities: [newActivity]
    })
  }

  await tripStore.updateTrip({
    ...currentTrip,
    days: nextDays
  })

  selectedPOI.value = poi
}

const viewDetails = (poi) => {
  // 在实际实现中，这会导航到POI详情页面
  console.log('View details for:', poi)
  alert(`查看 ${poi.name} 的详细信息`)
}

// 搜索POI
const performSearch = async () => {
  if (!searchQuery.value.trim() || !tripStore.currentTrip?.destination) return
  
  isSearching.value = true
  
  try {
    // 调用API搜索POI
    const response = await tripApi.searchPOI(
      searchQuery.value,
      tripStore.currentTrip.destination,
      1,
      10
    )
    
    // 过滤类别
    let filteredResults = response
    if (searchCategory.value !== 'all') {
      filteredResults = response.filter(poi => {
        const typeText = String(poi.type || '')
        return typeText.includes(searchCategory.value)
      })
    }
    
    // 转换格式
    searchPOIs.value = filteredResults.map(poi => ({
      id: poi.id,
      name: poi.name,
      type: poi.type,
      description: poi.description,
      rating: poi.rating,
      address: poi.address,
      hours: poi.opening_hours,
      price: poi.price,
      position: {
        lat: poi.lat,
        lng: poi.lng
      }
    }))
    
    // 在地图上添加搜索结果标记
    addSearchMarkers()
    
  } catch (error) {
    console.error('Failed to search POIs:', error)
    searchPOIs.value = []
  } finally {
    isSearching.value = false
  }
}

// 添加搜索结果标记
const addSearchMarkers = () => {
  if (!mapInstance.value || !searchPOIs.value.length) return
  
  // 清除之前的搜索结果标记
  if (window.searchMarkers) {
    window.searchMarkers.forEach(marker => marker.setMap(null))
  }
  
  window.searchMarkers = []
  
  searchPOIs.value.forEach(poi => {
    const marker = new window.AMap.Marker({
      position: [poi.position.lng, poi.position.lat],
      title: poi.name,
      map: mapInstance.value,
      icon: getMarkerIcon(poi.type, true), // 搜索结果使用特殊图标
      zIndex: 100
    })
    
    marker.on('click', () => {
      selectPOI(poi)
    })
    
    window.searchMarkers.push(marker)
  })
}

// 获取标记图标
const getMarkerIcon = (type, isSearchResult = false) => {
  const colors = {
    'attraction': '#10b981', // travel-mint
    'culture': '#3b82f6', // travel-ocean
    'food': '#f59e0b', // travel-sun
    'shopping': '#8b5cf6', // purple
    'hotel': '#ef4444', // red
    'transportation': '#6b7280', // gray
    'outdoor': '#10b981', // travel-mint
    'entertainment': '#ec4899', // pink
    'default': '#3b82f6' // travel-ocean
  }
  
  const color = colors[type] || colors.default
  
  if (isSearchResult) {
    // 搜索结果使用带边框的图标
    return new window.AMap.Icon({
      image: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" fill="${color}" stroke="white" stroke-width="2"/>
          <circle cx="12" cy="12" r="4" fill="white"/>
        </svg>
      `)}`,
      size: new window.AMap.Size(24, 24),
      anchor: new window.AMap.Pixel(12, 12)
    })
  }
  
  // 普通标记使用简单图标
  return new window.AMap.Icon({
    image: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" fill="${color}"/>
      </svg>
    `)}`,
    size: new window.AMap.Size(20, 20),
    anchor: new window.AMap.Pixel(10, 10)
  })
}

const updateCoordinates = () => {
  if (mapInstance.value) {
    const center = mapInstance.value.getCenter()
    coordinates.value = {
      lat: center.lat,
      lng: center.lng
    }
  }
}

const updateZoomLevel = () => {
  if (mapInstance.value) {
    zoomLevel.value = mapInstance.value.getZoom()
  }
}

const addPOIMarkers = () => {
  if (!mapInstance.value) return
  
  // 清除现有标记
  markers.value.forEach(marker => marker.setMap(null))
  markers.value = []
  
  tripPOIs.value.forEach(poi => {
    if (!poi.position || !Number.isFinite(Number(poi.position.lat)) || !Number.isFinite(Number(poi.position.lng))) return
    
    const marker = new window.AMap.Marker({
      position: [poi.position.lng, poi.position.lat],
      title: poi.name,
      offset: new window.AMap.Pixel(-13, -30),
      content: createMarkerContent(poi),
      map: mapInstance.value
    })
    
    marker.on('click', () => {
      selectPOI(poi)
    })
    
    markers.value.push(marker)
  })
}

const createMarkerContent = (poi) => {
  const colorMap = {
    attraction: 'bg-travel-mint border-travel-mint',
    restaurant: 'bg-travel-sun border-travel-sun',
    park: 'bg-travel-ocean border-travel-ocean',
    museum: 'bg-travel-purple border-travel-purple',
    hotel: 'bg-travel-pink border-travel-pink'
  }
  
  const colorClass = colorMap[poi.type] || 'bg-travel-gray border-travel-gray'
  
  return `
    <div class="relative group">
      <div class="w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all duration-300 group-hover:scale-125 shadow-md ${colorClass}">
        <div class="w-3 h-3 rounded-full animate-pulse ${colorClass.split(' ')[0].replace('bg-', 'bg-')}"></div>
      </div>
      <div class="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
        <div class="bg-white/95 backdrop-blur-sm rounded-lg border border-travel-sky/20 p-3 whitespace-nowrap shadow-travel-card">
          <div class="text-sm font-medium text-travel-ocean">${poi.name}</div>
          <div class="text-xs text-travel-gray">${poi.type}</div>
        </div>
      </div>
    </div>
  `
}

const buildRoutePathFromSteps = (steps = []) => {
  const path = []

  steps.forEach((step) => {
    const points = String(step?.polyline || '')
      .split(';')
      .map((pair) => {
        const [lng, lat] = pair.split(',').map(Number)
        return Number.isFinite(lat) && Number.isFinite(lng) ? [lng, lat] : null
      })
      .filter(Boolean)

    points.forEach((point) => {
      const lastPoint = path[path.length - 1]
      if (!lastPoint || lastPoint[0] !== point[0] || lastPoint[1] !== point[1]) {
        path.push(point)
      }
    })
  })

  return path
}

const drawRoute = async () => {
  if (!mapInstance.value) return

  const requestToken = Date.now()
  routeRequestToken.value = requestToken
  clearRouteLayers()

  const points = routePOIs.value
    .filter((poi) => hasValidPosition(poi.position))
    .map((poi) => [Number(poi.position.lng), Number(poi.position.lat)])

  if (points.length === 1) {
    mapInstance.value.setZoomAndCenter(14, points[0])
    return
  }

  if (points.length < 2) return

  isRouteLoading.value = true

  try {
    const segmentResponses = await Promise.all(
      points.slice(0, -1).map((point, index) =>
        tripApi
          .calculateRoute(`${point[0]},${point[1]}`, `${points[index + 1][0]},${points[index + 1][1]}`, 'driving')
          .catch(() => null)
      )
    )

    if (routeRequestToken.value !== requestToken || !mapInstance.value) return

    let totalDistance = 0
    let totalDuration = 0
    const overlays = [...markers.value]

    segmentResponses.forEach((segment, index) => {
      let path = []
      if (segment?.steps?.length) {
        path = buildRoutePathFromSteps(segment.steps)
        totalDistance += Number(segment.distance || 0)
        totalDuration += Number(segment.duration || 0)
      }
      if (path.length < 2) {
        path = [points[index], points[index + 1]]
      }

      const layer = new window.AMap.Polyline({
        path,
        strokeColor: '#2563eb',
        strokeOpacity: 0.92,
        strokeWeight: 6,
        strokeStyle: 'solid',
        lineJoin: 'round',
        lineCap: 'round',
        showDir: true,
        zIndex: 80
      })
      layer.setMap(mapInstance.value)
      routeLayers.value.push(layer)
      overlays.push(layer)
    })

    routeStats.value = {
      distance: totalDistance,
      duration: totalDuration,
      segments: routeLayers.value.length
    }

    if (overlays.length) {
      mapInstance.value.setFitView(overlays, false, [80, 360, 80, 120])
    }
  } finally {
    if (routeRequestToken.value === requestToken) {
      isRouteLoading.value = false
    }
  }
}

const mapPoiTypeToActivityType = (poiType) => {
  const value = String(poiType || '').toLowerCase()
  if (value.includes('餐') || value.includes('food')) return 'food'
  if (value.includes('文化') || value.includes('museum')) return 'culture'
  if (value.includes('购物') || value.includes('shop')) return 'shopping'
  if (value.includes('娱乐')) return 'entertainment'
  if (value.includes('交通')) return 'transport'
  if (value.includes('自然') || value.includes('park') || value.includes('outdoor')) return 'outdoor'
  return 'other'
}

const parsePoiCost = (text) => {
  if (!text) return 0
  if (String(text).includes('免费')) return 0
  const matched = String(text).match(/\d+/)
  return matched ? Number(matched[0]) : 80
}
</script>

<style scoped>
/* 地图容器的自定义滚动条 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: rgba(30, 136, 229, 0.1);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: rgba(30, 136, 229, 0.3);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(30, 136, 229, 0.5);
}

/* 高德地图容器样式 */
#amap-container {
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, rgba(186, 230, 253, 0.55) 0%, rgba(255, 255, 255, 0.95) 100%);
}

/* 地图标记样式 */
:deep(.amap-marker) {
  cursor: pointer;
}

:deep(.amap-marker-content) {
  transition: transform 0.3s ease;
}

:deep(.amap-marker-content:hover) {
  transform: scale(1.2);
}

/* 地图控件样式 */
:deep(.amap-toolbar) {
  top: 20px;
  left: 20px;
}

:deep(.amap-scalecontrol) {
  bottom: 30px;
  left: 20px;
}

:deep(.amap-maptypecontrol) {
  top: 20px;
  right: 20px;
}
</style>
