<template>
  <div class="fixed inset-0 z-40 overflow-hidden bg-[#f3f4f6]">
    <div class="absolute inset-0 bg-[radial-gradient(circle_at_top,#ffffff_0%,#f3f4f6_58%,#e9edf3_100%)]"></div>

    <div class="absolute inset-0 p-5 md:p-7">
      <div class="relative h-full overflow-hidden rounded-[28px] border border-white/70 bg-white/70 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-sm">
        <div ref="mapElement" class="absolute inset-0"></div>

        <div class="pointer-events-none absolute inset-x-0 top-0 z-10 h-28 bg-gradient-to-b from-white/82 via-white/48 to-transparent"></div>

        <div v-if="mapError" class="absolute left-1/2 top-5 z-30 -translate-x-1/2 rounded-2xl border border-red-200 bg-red-50/95 px-4 py-3 text-sm text-red-700 shadow-lg">
          {{ mapError }}
        </div>

        <div class="absolute left-5 top-5 z-20">
          <button
            @click="router.back()"
            class="flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/92 px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-white"
          >
            <span class="text-base leading-none">←</span>
            <span>返回行程</span>
          </button>
        </div>

        <div class="absolute right-5 top-5 z-20 flex items-start gap-3">
          <div class="rounded-2xl border border-slate-200/80 bg-white/92 px-4 py-3 shadow-sm backdrop-blur">
            <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Route Overview</div>
            <div class="mt-1 text-base font-semibold text-slate-900">{{ tripTitle }}</div>
            <div class="mt-2 text-[13px] text-slate-500">{{ routeSummary || fallbackSummary }}</div>
          </div>

          <div class="flex flex-col gap-3">
            <button
              @click="toggleMapStyle"
              class="rounded-2xl border border-slate-200/80 bg-white/92 p-3 text-slate-700 shadow-sm transition hover:bg-white"
              :title="currentBaseLayer === 'standard' ? '切换为卫星图' : '切换为标准图'"
            >
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 6.75 12 3l9 3.75m-18 0V17.25L12 21m-9-13.5L12 11.25m9-3.75V17.25L12 21m0-9.75V21" />
              </svg>
            </button>

            <button
              @click="resetView"
              class="rounded-2xl border border-slate-200/80 bg-white/92 p-3 text-slate-700 shadow-sm transition hover:bg-white"
              title="重置视图"
            >
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 4v5h5M20 20v-5h-5M19 9a7 7 0 0 0-12.03-2.97L4 9m16 6-2.97 2.97A7 7 0 0 1 5 15" />
              </svg>
            </button>

            <button
              @click="toggleMarkers"
              class="rounded-2xl border border-slate-200/80 bg-white/92 p-3 text-slate-700 shadow-sm transition hover:bg-white"
              :class="showMarkers ? 'ring-2 ring-blue-300/60' : ''"
              title="显示或隐藏点位"
            >
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 21s-6-4.35-6-10a6 6 0 1 1 12 0c0 5.65-6 10-6 10Z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 13.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
              </svg>
            </button>
          </div>
        </div>

        <div v-if="isDrawingRoute" class="absolute left-1/2 top-24 z-20 -translate-x-1/2 rounded-full border border-slate-200 bg-white/92 px-4 py-2 text-sm font-medium text-slate-700 shadow-sm">
          正在绘制路线总览...
        </div>

        <div v-if="routeDays.length" class="absolute bottom-5 left-5 z-20 w-[300px] max-w-[calc(100vw-2.5rem)] rounded-[24px] border border-slate-200/80 bg-white/92 p-4 shadow-[0_16px_42px_rgba(15,23,42,0.14)] backdrop-blur">
          <div class="mb-4">
            <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Trip Route</div>
            <div class="mt-1 text-[1.55rem] font-semibold leading-none text-slate-900">行程路线</div>
          </div>

          <div class="space-y-3.5">
            <div v-for="day in routeDays" :key="`legend-${day.dayIndex}`" class="flex items-start gap-3">
              <span class="mt-[9px] block h-1.5 w-9 rounded-full" :style="{ backgroundColor: day.color }"></span>
              <div class="min-w-0">
                <div class="text-[15px] font-semibold leading-6 text-slate-900">Day {{ day.dayIndex + 1 }}: {{ day.legendTitle }}</div>
                <div class="mt-1 text-[12px] leading-5 text-slate-500">
                  {{ day.points[0]?.name }}
                  <span v-if="day.points.length > 1"> → {{ day.points[day.points.length - 1]?.name }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="absolute bottom-5 right-5 z-20 rounded-2xl border border-slate-200/80 bg-white/92 px-4 py-3 text-sm text-slate-600 shadow-sm backdrop-blur">
          <div>地图中心 {{ coordinates.lat.toFixed(3) }}, {{ coordinates.lng.toFixed(3) }}</div>
          <div class="mt-1">缩放级别 {{ zoomLevel.toFixed(1) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTripStore } from '@/stores/tripStore'
import { tripApi } from '@/services/api'

const DEFAULT_CENTER = { lat: 31.2304, lng: 121.4737 }
const DAY_COLORS = ['#4169e1', '#ff6a3d', '#38c86a', '#8b5cf6', '#f43f7d', '#0ea5a8']

const router = useRouter()
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
let mapInitWatchdog = 0

const tripTitle = computed(() => tripStore.currentTrip?.destination || '旅行总览')
const fallbackSummary = computed(() => {
  if (!routeDays.value.length) return '暂无可绘制路线'
  return `共 ${routeDays.value.length} 天 · ${routePoints.value.length} 个定位点`
})

const getAMapEnvSummary = () => {
  const amapKey = import.meta.env.VITE_AMAP_KEY || import.meta.env.VITE_AMAP_API_KEY
  return {
    hasKey: Boolean(amapKey && !String(amapKey).includes('YOUR_AMAP_KEY')),
  }
}

const formatAMapError = (error) => {
  const raw = String(error?.message || error || '').trim()
  const { hasKey } = getAMapEnvSummary()

  if (!hasKey) return '地图暂不可用，请完善地图配置。'
  if (raw.includes('USERKEY_PLAT_NOMATCH')) return '地图暂不可用，请检查地图 Key 和域名配置。'
  if (raw.includes('INVALID_USER_KEY') || raw.includes('INVALID_PARAMS')) return '地图配置无效，请检查地图 Key。'
  if (raw.includes('INVALID_USER_SCODE') || raw.includes('securityJsCode') || raw.includes('SECURITY')) {
    return '地图配置校验失败，请检查 Key、域名白名单或安全码。'
  }
  if (raw.includes('高德地图脚本加载失败')) return '地图加载失败，请稍后再试。'
  if (raw.includes('未配置前端地图 Key')) return '地图暂不可用，请完善地图配置。'
  return '地图加载失败，请稍后再试。'
}

const validPosition = (value) => {
  if (!value) return false
  const lat = Number(value.lat)
  const lng = Number(value.lng)
  return Number.isFinite(lat) && Number.isFinite(lng) && lat >= 3 && lat <= 54 && lng >= 73 && lng <= 136
}

const DAY_STOPWORDS = ['早餐', '午餐', '晚餐', '夜宵', '小吃', '咖啡', '本地特色', '开启行程', '酒店', '民宿', '客栈']

const cleanLegendText = (value) =>
  String(value || '')
    .replace(/[（(]第\d+天[）)]/g, '')
    .replace(/\s+/g, ' ')
    .trim()

const isStopwordTitle = (value) => {
  const text = cleanLegendText(value)
  if (!text) return true
  return DAY_STOPWORDS.some((keyword) => text.includes(keyword))
}

const buildLegendTitle = (day, dayIndex, points) => {
  const destination = String(tripStore.currentTrip?.destination || '').trim()
  const summary = cleanLegendText(day.summary)
  const theme = cleanLegendText(day.theme)
  const notes = cleanLegendText(day.notes)
  const preferredText = [theme, summary, notes].find((item) => item && !isStopwordTitle(item))
  if (preferredText) return preferredText.slice(0, 18)

  const scenicPoint = points.find((point) => {
    const title = cleanLegendText(point.title)
    const name = cleanLegendText(point.name)
    return point.type !== 'food' && !isStopwordTitle(title) && !isStopwordTitle(name)
  })

  if (scenicPoint) {
    const scenicName = cleanLegendText(scenicPoint.name || scenicPoint.title)
    if (scenicName) {
      if (destination && scenicName.includes(destination)) return scenicName
      if (destination && dayIndex === 0) return `${destination}市区游`
      return scenicName.slice(0, 18)
    }
  }

  const endPoint = points[points.length - 1]
  const endName = cleanLegendText(endPoint?.name || endPoint?.title || '')
  if (endName && !isStopwordTitle(endName)) {
    return endName.slice(0, 18)
  }

  return destination ? `${destination}路线 Day ${dayIndex + 1}` : `第 ${dayIndex + 1} 天`
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
        legendTitle: buildLegendTitle(day, dayIndex, points),
        points,
      }
    })
    .filter(Boolean)
})

const routePoints = computed(() => routeDays.value.flatMap((day) => day.points))

const hasActivitiesButNoCoordinates = computed(() => {
  const trip = tripStore.currentTrip
  const totalActivities = (trip?.days || []).reduce((count, day) => count + ((day.activities || []).length || 0), 0)
  return totalActivities > 0 && routePoints.value.length === 0
})

const routeSummary = computed(() => {
  if (!routeStats.value.segments) return ''
  return `共 ${routeStats.value.days} 天 · ${routeStats.value.segments} 段路线 · 约 ${(routeStats.value.distance / 1000).toFixed(1)} km`
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

const createMarkerContent = (point) => `
  <div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
    <div style="width:40px;height:40px;border-radius:999px;background:#3b82f6;color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 25px rgba(59,130,246,.35);border:3px solid rgba(255,255,255,.96);">
      ${point.order}
    </div>
    <div style="margin-top:6px;max-width:160px;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,.96);color:#0f172a;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 4px 18px rgba(15,23,42,.12);">
      ${point.title}
    </div>
  </div>
`

const buildBaseLayers = () => {
  if (!window.AMap?.TileLayer) return { standard: [], satellite: [] }
  const standard = [
    new window.AMap.TileLayer({
      zIndex: 1,
      opacity: 1,
      zooms: [3, 20],
      detectRetina: true,
    }),
  ]
  const satellite = [
    new window.AMap.TileLayer.Satellite({
      zIndex: 1,
      opacity: 1,
      zooms: [3, 20],
      detectRetina: true,
    }),
    new window.AMap.TileLayer.RoadNet({
      zIndex: 2,
      opacity: 0.95,
      zooms: [3, 20],
      detectRetina: true,
    }),
  ]
  return { standard, satellite }
}

const applyBaseLayers = (kind = 'standard') => {
  if (!mapInstance.value) return
  const target = kind === 'satellite' ? satelliteLayers.value : standardLayers.value
  if (!target.length) return
  mapInstance.value.setLayers(target)
  if (kind === 'standard') {
    mapInstance.value.setMapStyle('amap://styles/whitesmoke')
  } else {
    mapInstance.value.setMapStyle('amap://styles/normal')
  }
  currentBaseLayer.value = kind
}

const renderMapScene = async () => {
  if (!mapReady.value || !mapInstance.value) return

  if (hasActivitiesButNoCoordinates.value) {
    mapError.value = '当前行程缺少可定位地点，地图暂时无法绘制路线。'
  } else if (mapError.value === '当前行程缺少可定位地点，地图暂时无法绘制路线。') {
    mapError.value = ''
  }

  renderMarkers()
  await drawRoute()
}

const renderMarkers = () => {
  if (!mapInstance.value) return
  clearMarkers()

  routeDays.value.forEach((day) => {
    day.points.forEach((point) => {
      const marker = new window.AMap.Marker({
        position: [point.position.lng, point.position.lat],
        title: point.name,
        content: createMarkerContent(point),
        map: showMarkers.value ? mapInstance.value : null,
        anchor: 'bottom-center',
        zIndex: 130,
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

const createPolyline = (path, color, zIndex) => {
  const outline = new window.AMap.Polyline({
    path,
    strokeColor: '#ffffff',
    strokeWeight: 11,
    strokeOpacity: 0.96,
    lineJoin: 'round',
    lineCap: 'round',
    zIndex,
    map: mapInstance.value,
  })

  const main = new window.AMap.Polyline({
    path,
    strokeColor: color,
    strokeWeight: 6,
    strokeOpacity: 0.96,
    lineJoin: 'round',
    lineCap: 'round',
    showDir: true,
    zIndex: zIndex + 1,
    map: mapInstance.value,
  })

  polylines.value.push(outline, main)
  return [outline, main]
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
          return { day, points, segments: [] }
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
    let segmentCount = 0

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
        const lines = createPolyline(path, day.color, 40 + day.dayIndex * 4)
        overlays.push(...lines)
        segmentCount += 1
      })
    })

    routeStats.value = {
      distance: totalDistance,
      duration: totalDuration,
      segments: segmentCount,
      days: routeDays.value.length,
    }

    if (overlays.length) {
      mapInstance.value.setFitView(overlays, false, [110, 110, 110, 210])
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
    mapReady.value = false
    await injectAMapScript()
    if (!mapElement.value) return

    if (mapInstance.value) {
      mapInstance.value.destroy()
      mapInstance.value = null
    }

    const first = routePoints.value[0]
    const center = first?.position || DEFAULT_CENTER
    const { standard, satellite } = buildBaseLayers()
    standardLayers.value = standard
    satelliteLayers.value = satellite

    mapInstance.value = new window.AMap.Map(mapElement.value, {
      center: [center.lng, center.lat],
      zoom: 11,
      resizeEnable: true,
      viewMode: '2D',
      pitchEnable: false,
      rotateEnable: false,
      zooms: [3, 20],
      jogEnable: false,
      animateEnable: true,
      expandZoomRange: true,
      showIndoorMap: false,
      features: ['bg', 'road', 'point'],
      layers: standardLayers.value,
    })

    applyBaseLayers('standard')

    window.AMap.plugin(['AMap.Scale'], () => {
      if (!mapInstance.value) return
      mapInstance.value.addControl(new window.AMap.Scale())
    })

    mapInstance.value.on('moveend', updateViewportState)
    mapInstance.value.on('zoomend', updateViewportState)
    mapInstance.value.on('error', (event) => {
      mapError.value = formatAMapError(event)
    })

    window.clearTimeout(mapInitWatchdog)
    mapInitWatchdog = window.setTimeout(() => {
      if (!mapReady.value) {
        mapError.value = formatAMapError('高德地图脚本已加载但地图未成功初始化，可能是 JS key 类型、域名白名单或 securityJsCode 配置不匹配。')
      }
    }, 4000)

    mapInstance.value.on('complete', async () => {
      if (!mapInstance.value) return
      window.clearTimeout(mapInitWatchdog)
      mapReady.value = true
      updateViewportState()
      await renderMapScene()
    })
  } catch (error) {
    mapError.value = formatAMapError(error)
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
  mapInstance.value.setZoomAndCenter(11, [DEFAULT_CENTER.lng, DEFAULT_CENTER.lat])
}

const toggleMarkers = () => {
  showMarkers.value = !showMarkers.value
  markers.value.forEach((marker) => marker.setMap(showMarkers.value ? mapInstance.value : null))
}

watch(
  routePoints,
  async () => {
    await renderMapScene()
  },
  { deep: true, immediate: true }
)

onMounted(() => {
  initMap()
})

onBeforeUnmount(() => {
  window.clearTimeout(mapInitWatchdog)
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
  background: #f3f4f6;
}

:global(.amap-layer canvas),
:global(.amap-layers canvas),
:global(.amap-maps canvas) {
  image-rendering: auto;
  transform: translateZ(0);
  backface-visibility: hidden;
}

:global(.amap-logo),
:global(.amap-copyright) {
  transform: translate3d(0, 0, 0);
}
</style>
