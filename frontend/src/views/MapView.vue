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
const routeStats = ref({ distance: 0, duration: 0, segments: 0 })
const standardLayers = ref([])
const satelliteLayers = ref([])

const validPosition = (value) => {
  if (!value) return false
  const lat = Number(value.lat)
  const lng = Number(value.lng)
  return Number.isFinite(lat) && Number.isFinite(lng) && lat >= 3 && lat <= 54 && lng >= 73 && lng <= 136
}

const routePoints = computed(() => {
  const trip = tripStore.currentTrip
  if (!trip?.days?.length) return []

  return trip.days.flatMap((day, dayIndex) =>
    (day.activities || [])
      .filter((activity) => validPosition(activity.coordinates))
      .map((activity, activityIndex) => ({
        id: activity.id || `activity_${dayIndex + 1}_${activityIndex + 1}`,
        name: activity.location || activity.title || `活动 ${activityIndex + 1}`,
        type: activity.type || 'other',
        position: {
          lat: Number(activity.coordinates.lat),
          lng: Number(activity.coordinates.lng),
        },
      }))
  )
})

const routeSummary = computed(() => {
  if (!routeStats.value.segments) return ''
  return `LLM 路线 ${routeStats.value.segments} 段 · 约 ${(routeStats.value.distance / 1000).toFixed(1)} km · ${Math.round(routeStats.value.duration / 60)} 分钟`
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
  routeStats.value = { distance: 0, duration: 0, segments: 0 }
}

const updateViewportState = () => {
  if (!mapInstance.value) return
  const center = mapInstance.value.getCenter()
  coordinates.value = { lat: Number(center.lat), lng: Number(center.lng) }
  zoomLevel.value = Number(mapInstance.value.getZoom())
}

const createMarkerIcon = (type) => {
  const colors = {
    food: '#f59e0b',
    culture: '#3b82f6',
    outdoor: '#10b981',
    shopping: '#8b5cf6',
    entertainment: '#ec4899',
    transport: '#64748b',
    other: '#2563eb',
  }
  const color = colors[type] || colors.other
  return new window.AMap.Icon({
    image: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 26 26">
        <circle cx="13" cy="13" r="11" fill="${color}" stroke="white" stroke-width="3" />
      </svg>
    `)}`,
    size: new window.AMap.Size(26, 26),
    imageSize: new window.AMap.Size(26, 26),
  })
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

  routePoints.value.forEach((point) => {
    const marker = new window.AMap.Marker({
      position: [point.position.lng, point.position.lat],
      title: point.name,
      icon: createMarkerIcon(point.type),
      map: showMarkers.value ? mapInstance.value : null,
      offset: new window.AMap.Pixel(-13, -13),
    })
    markers.value.push(marker)
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
  const points = routePoints.value.map((item) => [item.position.lng, item.position.lat])
  if (points.length < 2) return

  const requestId = Date.now()
  routeRequestId.value = requestId
  isDrawingRoute.value = true

  try {
    const segments = await Promise.all(
      points.slice(0, -1).map((point, index) =>
        tripApi.calculateRoute(`${point[0]},${point[1]}`, `${points[index + 1][0]},${points[index + 1][1]}`, 'driving').catch(() => null)
      )
    )

    if (routeRequestId.value !== requestId || !mapInstance.value) return

    let totalDistance = 0
    let totalDuration = 0
    const overlays = [...markers.value]

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
        strokeColor: '#2563eb',
        strokeWeight: 5,
        strokeOpacity: 0.95,
        lineJoin: 'round',
        lineCap: 'round',
        showDir: true,
        map: mapInstance.value,
      })
      polylines.value.push(polyline)
      overlays.push(polyline)
    })

    routeStats.value = {
      distance: totalDistance,
      duration: totalDuration,
      segments: polylines.value.length,
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
