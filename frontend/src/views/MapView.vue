<template>
  <div class="fixed inset-0 z-40 bg-white">
    <div ref="mapElement" class="absolute inset-0"></div>

    <div v-if="mapError" class="absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow">
      {{ mapError }}
    </div>

    <div class="absolute left-4 top-4 z-20 flex flex-col gap-3">
      <button
        @click="toggleMapStyle"
        class="rounded-xl border border-slate-200 bg-white p-3 text-slate-800 shadow-sm"
        title="切换底图"
      >
        <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      </button>

      <button
        @click="resetView"
        class="rounded-xl border border-slate-200 bg-white p-3 text-slate-800 shadow-sm"
        title="重置视图"
      >
        <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>

      <button
        @click="toggleMarkers"
        class="rounded-xl border border-slate-200 bg-white p-3 text-slate-800 shadow-sm"
        :class="showMarkers ? 'ring-2 ring-blue-500/40' : ''"
        title="显示或隐藏点位"
      >
        <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    </div>

    <div v-if="routeSummary || isDrawingRoute" class="absolute bottom-24 left-4 z-20">
      <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-800 shadow-sm">
        {{ isDrawingRoute ? '正在计算路线...' : routeSummary }}
      </div>
    </div>

    <div class="absolute bottom-4 left-4 z-20">
      <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-800 shadow-sm">
        <div>纬度: {{ coordinates.lat.toFixed(4) }}</div>
        <div>经度: {{ coordinates.lng.toFixed(4) }}</div>
        <div>缩放: {{ zoomLevel.toFixed(1) }}</div>
      </div>
    </div>

    <div v-if="routeDays.length" class="absolute bottom-4 right-4 z-20 max-w-sm">
      <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
        <div class="mb-2 font-semibold text-slate-900">路线图例</div>
        <div class="space-y-2">
          <div v-for="day in routeDays" :key="`legend-${day.dayIndex}`" class="flex items-center gap-3">
            <span class="h-3 w-3 rounded-full" :style="{ backgroundColor: day.color }"></span>
            <span>第 {{ day.dayIndex + 1 }} 天</span>
            <span class="text-xs text-slate-500">{{ day.points[0]?.name }} → {{ day.points[day.points.length - 1]?.name }}</span>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
          <span class="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">起点</span>
          <span class="rounded-full bg-rose-50 px-2 py-1 text-rose-700">终点</span>
          <span class="rounded-full bg-slate-100 px-2 py-1 text-slate-600">数字表示当天顺序</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTripStore } from '@/stores/tripStore'
import { tripApi } from '@/services/api'

const DEFAULT_CENTER = { lat: 31.2304, lng: 121.4737 }

const tripStore = useTripStore()
const mapElement = ref(null)
const mapInstance = ref(null)
const mapReady = ref(false)
const mapError = ref('')
const isDrawingRoute = ref(false)
const coordinates = ref({ ...DEFAULT_CENTER })
const zoomLevel = ref(12)
const showMarkers = ref(true)
const currentBaseLayer = ref('standard')
const markers = ref([])
const polylines = ref([])
const routeRequestId = ref(0)
const routeStats = ref({ distance: 0, duration: 0, segments: 0, days: 0 })
const standardLayers = ref([])
const satelliteLayers = ref([])
const DAY_COLORS = ['#2563eb', '#f97316', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6']

const validPosition = (value) => {
  if (!value) return false
  const lat = Number(value.lat)
  const lng = Number(value.lng)
  return Number.isFinite(lat) && Number.isFinite(lng) && lat >= 3 && lat <= 54 && lng >= 73 && lng <= 136
}

const routeDays = computed(() => {
  const trip = tripStore.currentTrip
  if (!trip?.days?.length) return []

  return trip.days
    .map((day, dayIndex) => {
      const points = (day.activities || [])
        .filter((activity) => validPosition(activity.coordinates))
        .map((activity, activityIndex, arr) => ({
          id: activity.id || `activity_${dayIndex + 1}_${activityIndex + 1}`,
          name: activity.location || activity.title || `活动 ${activityIndex + 1}`,
          title: activity.title || `活动 ${activityIndex + 1}`,
          type: activity.type || 'other',
          dayIndex,
          activityIndex,
          order: activityIndex + 1,
          isStart: activityIndex === 0,
          isEnd: activityIndex === arr.length - 1,
          position: {
            lat: Number(activity.coordinates.lat),
            lng: Number(activity.coordinates.lng),
          },
        }))

      if (!points.length) return null

      return {
        dayIndex,
        date: day.date,
        color: DAY_COLORS[dayIndex % DAY_COLORS.length],
        points,
      }
    })
    .filter(Boolean)
})

const routePoints = computed(() => {
  return routeDays.value.flatMap((day) => day.points)
})

const routeSummary = computed(() => {
  if (!routeStats.value.segments) return ''
  return `共 ${routeStats.value.days} 天 · ${routeStats.value.segments} 段 · 约 ${(routeStats.value.distance / 1000).toFixed(1)} km · ${Math.round(routeStats.value.duration / 60)} 分钟`
})

const injectAMapScript = () =>
  new Promise((resolve, reject) => {
    if (window.AMap) {
      resolve(window.AMap)
      return
    }

    const amapKey = import.meta.env.VITE_AMAP_KEY || import.meta.env.VITE_AMAP_API_KEY
    const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE

    if (!amapKey || String(amapKey).includes('YOUR_AMAP_KEY')) {
      reject(new Error('未配置前端地图 Key'))
      return
    }

    if (securityCode) {
      window._AMapSecurityConfig = {
        ...(window._AMapSecurityConfig || {}),
        securityJsCode: securityCode,
      }
    }

    const existing = document.getElementById('amap-sdk')
    if (existing) {
      existing.addEventListener('load', () => resolve(window.AMap), { once: true })
      existing.addEventListener('error', () => reject(new Error('高德地图脚本加载失败')), { once: true })
      return
    }

    const script = document.createElement('script')
    script.id = 'amap-sdk'
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${amapKey}`
    script.async = true
    script.onload = () => resolve(window.AMap)
    script.onerror = () => reject(new Error('高德地图脚本加载失败'))
    document.head.appendChild(script)
  })

const clearMarkers = () => {
  markers.value.forEach((marker) => marker.setMap(null))
  markers.value = []
}

const clearPolylines = () => {
  polylines.value.forEach((line) => line.setMap(null))
  polylines.value = []
  routeStats.value = { distance: 0, duration: 0, segments: 0, days: 0 }
}

const updateViewportState = () => {
  if (!mapInstance.value) return
  const center = mapInstance.value.getCenter()
  coordinates.value = { lat: Number(center.lat), lng: Number(center.lng) }
  zoomLevel.value = Number(mapInstance.value.getZoom())
}

const createMarkerContent = (point, dayColor) => {
  const badgeColor = point.isStart ? '#059669' : point.isEnd ? '#e11d48' : dayColor
  const label = point.isStart ? `D${point.dayIndex + 1}起` : point.isEnd ? `D${point.dayIndex + 1}终` : String(point.order)
  return `
    <div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
      <div style="min-width:32px;height:32px;padding:0 8px;border-radius:999px;background:${badgeColor};color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(15,23,42,.18);border:2px solid #fff;">
        ${label}
      </div>
      <div style="margin-top:6px;padding:4px 8px;border-radius:999px;background:rgba(255,255,255,.96);color:#0f172a;font-size:12px;font-weight:600;white-space:nowrap;box-shadow:0 4px 12px rgba(15,23,42,.10);max-width:180px;overflow:hidden;text-overflow:ellipsis;">
        ${point.title}
      </div>
    </div>
  `
}

const buildBaseLayers = () => {
  if (!window.AMap?.TileLayer) return { standard: [], satellite: [] }
  const standard = [
    new window.AMap.TileLayer({
      zIndex: 1,
      opacity: 1,
      zooms: [3, 20],
    }),
  ]
  const satellite = [
    new window.AMap.TileLayer.Satellite({
      zIndex: 1,
      opacity: 1,
      zooms: [3, 20],
    }),
    new window.AMap.TileLayer.RoadNet({
      zIndex: 2,
      opacity: 1,
      zooms: [3, 20],
    }),
  ]
  return { standard, satellite }
}

const applyBaseLayers = (kind = 'standard') => {
  if (!mapInstance.value) return
  const target = kind === 'satellite' ? satelliteLayers.value : standardLayers.value
  if (!target.length) return
  mapInstance.value.setLayers(target)
  currentBaseLayer.value = kind
}

const renderMarkers = () => {
  if (!mapInstance.value) return
  clearMarkers()

  routeDays.value.forEach((day) => {
    day.points.forEach((point) => {
    const marker = new window.AMap.Marker({
      position: [point.position.lng, point.position.lat],
      title: point.name,
      content: createMarkerContent(point, day.color),
      map: showMarkers.value ? mapInstance.value : null,
      anchor: 'bottom-center',
    })
    markers.value.push(marker)
  })
  })
}

const buildPathFromSteps = (steps = []) => {
  const path = []
  steps.forEach((step) => {
    String(step?.polyline || '')
      .split(';')
      .forEach((pair) => {
        const [lng, lat] = pair.split(',').map(Number)
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return
        path.push([lng, lat])
      })
  })
  return path
}

const drawRoute = async () => {
  if (!mapInstance.value) return

  clearPolylines()
  if (!routeDays.value.length) return

  const requestId = Date.now()
  routeRequestId.value = requestId
  isDrawingRoute.value = true

  try {
    const daySegments = await Promise.all(
      routeDays.value.map(async (day) => {
        const points = day.points.map((item) => [item.position.lng, item.position.lat])
        if (points.length < 2) {
          return { day, segments: [] }
        }
        const segments = await Promise.all(
          points.slice(0, -1).map((point, index) =>
            tripApi.calculateRoute(`${point[0]},${point[1]}`, `${points[index + 1][0]},${points[index + 1][1]}`, 'driving').catch(() => null)
          )
        )
        return { day, points, segments }
      })
    )

    if (routeRequestId.value !== requestId || !mapInstance.value) return

    let totalDistance = 0
    let totalDuration = 0
    const overlays = [...markers.value]

    daySegments.forEach(({ day, points = [], segments = [] }) => {
      segments.forEach((segment, index) => {
        let path = []
        if (segment?.steps?.length) {
          path = buildPathFromSteps(segment.steps)
          totalDistance += Number(segment.distance || 0)
          totalDuration += Number(segment.duration || 0)
        }
        if (path.length < 2) {
          path = [points[index], points[index + 1]]
        }

        const polyline = new window.AMap.Polyline({
          path,
          strokeColor: day.color,
          strokeWeight: 6,
          strokeOpacity: 0.9,
          lineJoin: 'round',
          lineCap: 'round',
          showDir: true,
          zIndex: 20 + day.dayIndex,
          map: mapInstance.value,
        })
        polylines.value.push(polyline)
        overlays.push(polyline)
      })
    })

    routeStats.value = {
      distance: totalDistance,
      duration: totalDuration,
      segments: polylines.value.length,
      days: routeDays.value.length,
    }

    if (overlays.length) {
      mapInstance.value.setFitView(overlays, false, [80, 80, 80, 160])
    }
  } finally {
    if (routeRequestId.value === requestId) {
      isDrawingRoute.value = false
    }
  }
}

const initMap = async () => {
  try {
    mapError.value = ''
    await injectAMapScript()
    if (!mapElement.value) return

    if (mapInstance.value) {
      mapInstance.value.destroy()
      mapInstance.value = null
    }

    const first = routePoints.value[0]
    const center = first?.position || DEFAULT_CENTER

    mapInstance.value = new window.AMap.Map(mapElement.value, {
      center: [center.lng, center.lat],
      zoom: 12,
      resizeEnable: true,
      viewMode: '2D',
      zooms: [3, 20],
      jogEnable: true,
      animateEnable: true,
    })

    const { standard, satellite } = buildBaseLayers()
    standardLayers.value = standard
    satelliteLayers.value = satellite
    applyBaseLayers('standard')

    window.AMap.plugin(['AMap.ToolBar', 'AMap.Scale', 'AMap.Geolocation'], () => {
      if (!mapInstance.value) return
      mapInstance.value.addControl(new window.AMap.ToolBar())
      mapInstance.value.addControl(new window.AMap.Scale())
      mapInstance.value.addControl(
        new window.AMap.Geolocation({
          enableHighAccuracy: true,
          zoomToAccuracy: false,
          buttonPosition: 'RB',
        })
      )
    })

    mapInstance.value.on('moveend', updateViewportState)
    mapInstance.value.on('zoomend', updateViewportState)
    mapInstance.value.on('complete', async () => {
      if (!mapInstance.value) return
      mapReady.value = true
      updateViewportState()
      renderMarkers()
      await drawRoute()
    })
  } catch (error) {
    mapError.value = error instanceof Error ? error.message : '地图初始化失败'
  }
}

const toggleMapStyle = () => {
  if (!mapInstance.value) return
  applyBaseLayers(currentBaseLayer.value === 'standard' ? 'satellite' : 'standard')
}

const resetView = async () => {
  if (!mapInstance.value) return
  if (routePoints.value.length) {
    renderMarkers()
    await drawRoute()
    return
  }
  mapInstance.value.setZoomAndCenter(12, [DEFAULT_CENTER.lng, DEFAULT_CENTER.lat])
}

const toggleMarkers = () => {
  showMarkers.value = !showMarkers.value
  markers.value.forEach((marker) => marker.setMap(showMarkers.value ? mapInstance.value : null))
}

watch(
  routePoints,
  async () => {
    if (!mapReady.value || !mapInstance.value) return
    renderMarkers()
    await drawRoute()
  },
  { deep: true }
)

onMounted(() => {
  initMap()
})

onBeforeUnmount(() => {
  clearMarkers()
  clearPolylines()
  if (mapInstance.value) {
    mapInstance.value.destroy()
    mapInstance.value = null
  }
})
</script>

<style scoped>
:global(html),
:global(body),
:global(#app) {
  margin: 0;
  width: 100%;
  height: 100%;
}

:global(body) {
  background: #fff;
}

:global(.amap-layer canvas),
:global(.amap-layers canvas) {
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
}

.absolute[class*='z-20'] {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: geometricPrecision;
}
</style>
