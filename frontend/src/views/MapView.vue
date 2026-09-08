<template>
  <div class="map-page">
    <header class="map-header">
      <button class="back-button" type="button" @click="goBack">← <span>返回行程</span></button>
      <div class="map-heading">
        <span>TRIP ROUTE</span>
        <strong>{{ tripTitle }}</strong>
        <small>{{ routeSummary }}</small>
      </div>
      <button class="details-button" type="button" @click="openTripDetails">行程详情 <span>→</span></button>
    </header>

    <div class="map-controls">
      <label>交通方式 <select v-model="routeMode" :disabled="isLoadingRoutes">
        <option value="touring">按距离推荐</option><option value="walking">步行</option><option value="driving">驾车</option><option value="bicycling">骑行</option><option value="transit">公交 / 地铁</option>
      </select></label>
      <button :disabled="!routeDays.length || isLoadingRoutes" @click="loadMapRoutes">重新规划路线</button>
      <button :disabled="!routeDays.length || exporting" @click="exportMap">{{ exporting ? '正在生成…' : '导出到高德专属地图' }}</button>
      <a v-if="exportUrl" :href="exportUrl" target="_blank" rel="noopener noreferrer">打开高德专属地图 ↗</a>
      <span v-if="exportError" role="alert">{{ exportError }}</span>
    </div>
    <main class="map-layout">
      <section class="route-canvas-card">
        <div v-if="routeDays.length" class="day-tabs" aria-label="选择行程日期">
          <button type="button" :class="{ active: selectedDay === -1 }" @click="selectDay(-1)">全程</button>
          <button v-for="day in routeDays" :key="day.dayIndex" type="button" :class="{ active: selectedDay === day.dayIndex }" @click="selectDay(day.dayIndex)">
            DAY {{ day.dayIndex + 1 }}
          </button>
        </div>

        <div class="map-status" :class="routeStatusTone"><i /> {{ routeStatusText }}</div>

        <div v-if="!trip" class="empty-state">
          <span class="empty-state__mark">✦</span>
          <small>ROUTE NOT READY</small>
          <h1>先生成一份旅行计划</h1>
          <p>地图会根据每天的地点自动生成，并提供高德交通方案和逐段指引。</p>
          <button type="button" @click="router.push('/')">开始规划旅行</button>
        </div>

        <div v-else-if="!routePoints.length" class="empty-state">
          <span class="empty-state__mark">⌖</span>
          <small>LOCATION DATA MISSING</small>
          <h1>这份行程还没有可定位地点</h1>
          <p>重新生成行程或在行程详情中补充地点后，路线地图会自动出现。</p>
          <button type="button" @click="openTripDetails">返回行程详情</button>
        </div>

        <RoadMap v-else :days="mapDays" :selected-id="selectedPointId" @select="selectedPointId = $event" />

        <div v-if="routeWarning" class="route-warning">{{ routeWarning }}</div>
      </section>

      <aside class="route-panel">
        <section v-if="selectedPoint" class="place-card">
          <div class="place-card__eyebrow">SELECTED PLACE</div>
          <div class="place-card__title-row">
            <span :style="{ background: selectedPoint.color }">{{ selectedPoint.order }}</span>
            <div><strong>{{ selectedPoint.title }}</strong><small>DAY {{ selectedPoint.dayIndex + 1 }} · {{ selectedPoint.time || '时间待定' }}</small></div>
          </div>
          <p>{{ selectedPoint.description || selectedPoint.location || '已加入本次旅行路线。' }}</p>
          <p v-if="placeDetail" data-testid="poi-detail">{{ placeDetail.verified ? '已核对高德地点 · ' : '' }}{{ placeDetail.address }}<br v-if="placeDetail.opening_hours" />{{ placeDetail.opening_hours }}</p>
          <div class="place-tools">
            <button :disabled="!selectedPoint.poiId || loadingPlaces" @click="loadDetail">核对地点详情</button>
            <button :disabled="loadingPlaces" @click="loadNearby">{{ loadingPlaces ? '查询中…' : '找附近餐饮' }}</button>
          </div>
          <p v-if="placeError" role="alert">{{ placeError }}</p>
          <ul v-if="nearby.length" class="nearby-list"><li v-for="poi in nearby" :key="poi.id"><strong>{{ poi.name }}</strong><small>{{ poi.address }}</small></li></ul>
          <button type="button" @click="openInAMap(selectedPoint)">在高德地图中查看 <span>↗</span></button>
        </section>

        <section class="route-list-card">
          <div class="route-list-card__head">
            <div><small>ITINERARY</small><strong>路线顺序</strong></div><span>{{ visibleDays.length }} 天</span>
          </div>
          <div v-if="visibleDays.length" class="route-days">
            <article v-for="day in visibleDays" :key="`panel-${day.dayIndex}`" class="route-day">
              <button type="button" class="route-day__head" @click="selectDay(day.dayIndex)">
                <i :style="{ background: day.color }" /><span><small>DAY {{ day.dayIndex + 1 }}</small><strong>{{ day.legendTitle }}</strong></span><b>{{ formatDayDistance(day.dayIndex) }}</b>
              </button>
              <details v-if="routePlans[day.dayIndex]?.legs?.length" class="route-instructions">
                <summary>查看交通指引 · 约 {{ Math.round((routePlans[day.dayIndex]?.duration || 0) / 60) }} 分钟</summary>
                <div v-for="(leg, index) in routePlans[day.dayIndex]?.legs" :key="index">
                  <strong>{{ day.points[index]?.title }} → {{ day.points[index + 1]?.title }}</strong>
                  <small v-if="leg.ok">{{ modeLabel(leg.mode) }} · {{ Math.round((leg.duration || 0) / 60) }} 分钟</small>
                  <p v-if="leg.error">{{ leg.error }}</p><ol v-else><li v-for="(instruction, i) in leg.instructions" :key="i">{{ instruction }}</li></ol>
                </div>
              </details>
              <div class="route-stops">
                <button v-for="point in day.points" :key="`stop-${point.id}`" type="button" :class="{ active: selectedPoint?.id === point.id }" @click="selectedPointId = point.id">
                  <span>{{ point.order }}</span><div><strong>{{ point.title }}</strong><small>{{ point.time || point.location || '行程地点' }}</small></div>
                </button>
              </div>
            </article>
          </div>
          <div v-else class="route-list-empty">生成行程后，这里会显示每日路线。</div>
        </section>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import RoadMap from '@/components/RoadMap.vue'
import { useRouter } from 'vue-router'
import { tripApi, type MapRoutePlan, type MapRoutePoint, type MapPoi } from '@/services/api'
import { useTripStore } from '@/stores/tripStore'

type RoutePoint = { id: string; poiId: string; dayIndex: number; order: number; title: string; location: string; time: string; description: string; position: { lat: number; lng: number } }
type RouteDay = { dayIndex: number; date: string; color: string; legendTitle: string; points: RoutePoint[] }

const DAY_COLORS = ['#2563EB', '#7B4FF6', '#0F766E', '#F97316', '#DB2777', '#0891B2', '#111827']
const router = useRouter()
const tripStore = useTripStore()
const selectedDay = ref(-1)
const selectedPointId = ref('')
const routePlans = ref<Record<number, MapRoutePlan>>({})
const isLoadingRoutes = ref(false)
const routeError = ref('')
const routeMode = ref('touring')
const exporting = ref(false)
const exportUrl = ref('')
const exportError = ref('')
const nearby = ref<MapPoi[]>([])
const placeDetail = ref<MapPoi | null>(null)
const loadingPlaces = ref(false)
const placeError = ref('')
let placeRequest = 0
let routeRequest = 0
const modeLabel = (mode?: string) => ({ walking: '步行', driving: '驾车', bicycling: '骑行', transit: '公交 / 地铁' }[mode || ''] || '交通')

const trip = computed(() => tripStore.currentTrip)
const tripTitle = computed(() => trip.value?.destination ? `${trip.value.destination}旅行地图` : '旅行路线地图')
const isValidPosition = (position: any) => {
  const lat = Number(position?.lat)
  const lng = Number(position?.lng)
  return Number.isFinite(lat) && Number.isFinite(lng) && lat >= 3 && lat <= 54 && lng >= 73 && lng <= 136
}
const cleanLabel = (value: unknown) => String(value || '').replace(/[（(]第\d+天[）)]/g, '').trim()

const routeDays = computed<RouteDay[]>(() => (trip.value?.days || []).map((day: any, dayIndex: number) => {
  const points = (day.activities || []).filter((activity: any) => isValidPosition(activity.coordinates)).map((activity: any, index: number) => ({
    id: String(activity.id || `route-${dayIndex}-${index}`), poiId: String(activity.source_id || activity.poi_id || ""), dayIndex, order: index + 1,
    title: cleanLabel(activity.location || activity.title) || `第 ${index + 1} 站`,
    location: cleanLabel(activity.location || ''), time: String(activity.time || ''), description: String(activity.description || activity.notes || ''),
    position: { lat: Number(activity.coordinates.lat), lng: Number(activity.coordinates.lng) }
  }))
  if (!points.length) return null
  return { dayIndex, date: String(day.date || ''), color: DAY_COLORS[dayIndex % DAY_COLORS.length], legendTitle: cleanLabel(day.theme || day.notes || points[0]?.title) || `第 ${dayIndex + 1} 天`, points }
}).filter(Boolean) as RouteDay[])

const visibleDays = computed(() => selectedDay.value < 0 ? routeDays.value : routeDays.value.filter((day) => day.dayIndex === selectedDay.value))
const routePoints = computed(() => routeDays.value.flatMap((day) => day.points))
const selectedPoint = computed(() => {
  const all = routePoints.value.map((point) => ({ ...point, color: DAY_COLORS[point.dayIndex % DAY_COLORS.length] }))
  return all.find((point) => point.id === selectedPointId.value) || all[0] || null
})
const isRealRoute = (plan?: MapRoutePlan) => {
  if (!plan) return false
  const providers = String(plan.provider || '').split(',').filter(Boolean)
  if (providers.length && providers.every((provider) => ['fallback', 'none', 'unavailable'].includes(provider))) return false
  return (plan.polyline || []).length >= 2 || (plan.legs || []).some((leg) => (leg.polyline || []).length >= 2 || !!leg.polylines?.length)
}
const routeGroupsForDay = (day: RouteDay): MapRoutePoint[][] => {
  const plan = routePlans.value[day.dayIndex]
  if (isRealRoute(plan)) {
    const legs = (plan?.legs || []).flatMap((leg) => leg.polylines?.length ? leg.polylines : [leg.polyline || []]).filter((line) => line.length >= 2)
    if (legs.length) return legs
    if ((plan?.polyline || []).length >= 2) return [plan.polyline]
  }
  return []
}
const mapDays = computed(() => visibleDays.value.map(day => ({
  dayIndex: day.dayIndex, color: day.color,
  points: day.points.map(point => ({ id: point.id, title: point.title, order: point.order, latitude: point.position.lat, longitude: point.position.lng })),
  paths: routeGroupsForDay(day)
})))

const totalDistance = computed(() => visibleDays.value.reduce((sum, day) => sum + Number(routePlans.value[day.dayIndex]?.distance || 0), 0))
const routeSummary = computed(() => {
  if (!trip.value) return '生成行程后查看地点与高德交通指引'
  if (!routePoints.value.length) return '当前行程暂无可定位地点'
  const distance = totalDistance.value > 0 ? ` · 约 ${(totalDistance.value / 1000).toFixed(1)} km` : ''
  return `${visibleDays.value.length} 天 · ${visibleDays.value.reduce((sum, day) => sum + day.points.length, 0)} 个地点${distance}`
})
const routeWarning = computed(() => {
  if (routeError.value) return '路线查询失败，仅显示地点。请重试或在高德地图中查看导航。'
  const failedDays = visibleDays.value.filter(day => routePlans.value[day.dayIndex]?.partial)
  if (!isLoadingRoutes.value && failedDays.length) return `DAY ${failedDays.map(day => day.dayIndex + 1).join('、')} 部分路线查询失败，请切换交通方式或稍后重试。`
  const fallbackDays = visibleDays.value.filter((day) => day.points.length >= 2 && !isRealRoute(routePlans.value[day.dayIndex]))
  return !isLoadingRoutes.value && fallbackDays.length ? `DAY ${fallbackDays.map((day) => day.dayIndex + 1).join('、')} 暂未取得道路折线，仅显示地点；可在高德地图中查看导航。` : ''
})
const routeStatusText = computed(() => {
  if (!trip.value) return '等待生成行程'
  if (!routePoints.value.length) return '缺少地点坐标'
  if (isLoadingRoutes.value) return '正在计算真实道路路线'
  if (routeError.value) return '路线暂不可用'
  if (!visibleDays.value.some(day => routePlans.value[day.dayIndex]?.legs?.some(leg => leg.ok))) return '地点图已就绪，路线待确认'
  return visibleDays.value.some((day) => isRealRoute(routePlans.value[day.dayIndex])) ? '真实道路路线已就绪' : '地点已定位，道路路线待获取'
})
const routeStatusTone = computed(() => isLoadingRoutes.value ? 'loading' : routeError.value ? 'warning' : 'ready')
const formatDayDistance = (dayIndex: number) => { const distance = Number(routePlans.value[dayIndex]?.distance || 0); return distance > 0 ? `${(distance / 1000).toFixed(1)} km` : '路线待确认' }

const loadMapRoutes = async () => {
  const requestId = ++routeRequest
  if (!routeDays.value.length) { routePlans.value = {}; isLoadingRoutes.value = false; return }
  isLoadingRoutes.value = true; routeError.value = ''; routePlans.value = {}
  try {
    const response = await tripApi.planMapRoutes({ mode: routeMode.value, city: trip.value?.destination, segments: routeDays.value.map((day) => ({ dayIndex: day.dayIndex, points: day.points.map((point) => ({ latitude: point.position.lat, longitude: point.position.lng, title: point.title })) })) })
    if (requestId !== routeRequest) return
    routePlans.value = Object.fromEntries((response.segments || []).map((plan) => [plan.dayIndex, plan]))
  } catch (error) {
    if (requestId !== routeRequest) return
    routeError.value = error instanceof Error ? error.message : '路线规划失败'; routePlans.value = {}
  } finally { if (requestId === routeRequest) isLoadingRoutes.value = false }
}
const loadNearby = async () => {
  const point = selectedPoint.value
  if (!point) return
  const id = ++placeRequest
  loadingPlaces.value = true; placeError.value = ''
  try {
    const result = await tripApi.nearbyPlaces({ latitude: point.position.lat, longitude: point.position.lng })
    if (id !== placeRequest) return
    nearby.value = result.pois
    if (!result.pois.length) placeError.value = '周边 1.5 公里内暂无餐饮结果。'
  } catch (error) { if (id === placeRequest) placeError.value = error instanceof Error ? error.message : '查询失败，请重试' }
  finally { if (id === placeRequest) loadingPlaces.value = false }
}
const loadDetail = async () => {
  if (!selectedPoint.value?.poiId) return
  const id = ++placeRequest
  loadingPlaces.value = true; placeError.value = ''
  try {
    const result = await tripApi.poiDetail(selectedPoint.value.poiId)
    if (id === placeRequest) placeDetail.value = result
  } catch (error) { if (id === placeRequest) placeError.value = error instanceof Error ? error.message : '查询失败，请重试' }
  finally { if (id === placeRequest) loadingPlaces.value = false }
}
const exportMap = async () => {
  exporting.value = true; exportError.value = ''; exportUrl.value = ''
  try {
    const result = await tripApi.exportMap({ title: tripTitle.value, segments: routeDays.value.map(day => ({
      dayIndex: day.dayIndex, title: `第 ${day.dayIndex + 1} 天 · ${day.legendTitle}`,
      points: day.points.map(p => ({ latitude: p.position.lat, longitude: p.position.lng, title: p.title, poiId: p.poiId }))
    })) })
    exportUrl.value = result.url
  } catch (error) { exportError.value = error instanceof Error ? error.message : '导出失败，请重试' }
  finally { exporting.value = false }
}
watch(() => selectedPoint.value?.id, () => { ++placeRequest; nearby.value = []; placeDetail.value = null; placeError.value = ''; loadingPlaces.value = false })
watch(routeMode, loadMapRoutes)

const selectDay = (dayIndex: number) => { selectedDay.value = dayIndex; const first = (dayIndex < 0 ? routePoints.value : routeDays.value.find((day) => day.dayIndex === dayIndex)?.points || [])[0]; if (first) selectedPointId.value = first.id }
const openTripDetails = () => trip.value?.id ? router.push(`/trip/${trip.value.id}`) : router.push('/')
const goBack = () => window.history.length > 1 ? router.back() : openTripDetails()
const openInAMap = (point: RoutePoint) => { const name = encodeURIComponent(point.title); window.open(`https://uri.amap.com/marker?position=${point.position.lng},${point.position.lat}&name=${name}&coordinate=gaode&callnative=0`, '_blank', 'noopener,noreferrer') }

watch(() => routeDays.value.map((day) => `${day.dayIndex}:${day.points.map((point) => `${point.id}:${point.position.lng},${point.position.lat}`).join(',')}`).join('|'), () => { if (!selectedPointId.value && routePoints.value[0]) selectedPointId.value = routePoints.value[0].id; loadMapRoutes() }, { immediate: true })
</script>

<style scoped>
.map-controls{width:min(1400px,100%);margin:0 auto 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:13px}.map-controls select,.map-controls button,.place-tools button{border:1px solid #dfe4eb;border-radius:10px;padding:10px 12px;background:#fff;color:#344054}.map-controls a{color:#2563eb}.map-controls button:disabled,.place-tools button:disabled{opacity:.5;cursor:wait}.place-tools{display:flex;gap:8px;flex-wrap:wrap}.nearby-list{list-style:none;padding:0;font-size:12px}.nearby-list li{padding:10px 0;border-bottom:1px solid #edf0f4}.nearby-list small,.route-instructions small{display:block;margin-top:4px;color:#667085}.route-instructions{font-size:11px;line-height:1.65;padding:10px 0}.route-instructions summary{cursor:pointer;color:#2563eb}.route-instructions ol{padding-left:18px}.route-instructions strong{display:block;margin-top:10px}

.map-page{min-height:100vh;padding:22px;color:#111827;background:#eef1f5}.map-header{width:min(1400px,100%);min-height:70px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:22px;margin:0 auto 18px;padding:0 4px}.back-button,.details-button{width:fit-content;min-height:42px;padding:0 16px;border:1px solid #d9dee7;border-radius:999px;color:#344054;background:rgba(255,255,255,.84);font-size:12px;font-weight:800;cursor:pointer}.details-button{justify-self:end;color:#fff;border-color:#111827;background:#111827}.details-button span{margin-left:12px}.map-heading{text-align:center}.map-heading span,.map-heading strong,.map-heading small{display:block}.map-heading span{color:#7b4ff6;font-size:9px;font-weight:950;letter-spacing:.18em}.map-heading strong{margin-top:3px;font-size:20px;font-weight:950}.map-heading small{margin-top:3px;color:#7a8494;font-size:10px}.map-layout{width:min(1400px,100%);display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;margin:0 auto}.route-canvas-card{position:relative;min-height:calc(100vh - 132px);overflow:hidden;border:1px solid rgba(255,255,255,.9);border-radius:30px;background:#f8fafc;box-shadow:0 24px 70px rgba(15,23,42,.11)}.day-tabs{position:absolute;top:20px;left:20px;z-index:8;display:flex;flex-wrap:wrap;gap:6px;padding:5px;border:1px solid #e1e6ed;border-radius:999px;background:rgba(255,255,255,.92);box-shadow:0 8px 24px rgba(15,23,42,.08)}.day-tabs button{min-height:34px;padding:0 14px;border:0;border-radius:999px;color:#667085;background:transparent;font-size:10px;font-weight:900;cursor:pointer}.day-tabs button.active{color:#fff;background:#111827}.map-status{position:absolute;top:22px;right:22px;z-index:8;display:flex;align-items:center;gap:8px;padding:10px 13px;border:1px solid #dfe4eb;border-radius:999px;color:#475467;background:rgba(255,255,255,.92);font-size:10px;font-weight:850;box-shadow:0 8px 24px rgba(15,23,42,.07)}.map-status i{width:7px;height:7px;border-radius:50%;background:#0f766e}.map-status.loading i{background:#2563eb;animation:pulse 1s infinite}.map-status.warning i{background:#f97316}.route-stage{position:absolute;inset:0;overflow:hidden}.route-stage__background{position:absolute;inset:0;background:radial-gradient(circle at 18% 22%,rgba(37,99,235,.1),transparent 25%),radial-gradient(circle at 76% 70%,rgba(123,79,246,.1),transparent 27%),linear-gradient(145deg,#f8fafc,#edf1f6)}.route-svg{position:absolute;inset:0;width:100%;height:100%}.terrain-line{fill:none;stroke:#cbd5e1;stroke-width:1.2;stroke-dasharray:4 10;opacity:.58}.terrain-line--two{opacity:.42}.map-marker{--day-color:#2563eb;position:absolute;z-index:5;transform:translate(-50%,-50%);display:grid;grid-template-columns:32px auto;align-items:center;gap:7px;padding:4px 9px 4px 4px;border:2px solid #fff;border-radius:999px;color:#111827;background:rgba(255,255,255,.94);box-shadow:0 8px 22px rgba(15,23,42,.16);cursor:pointer;transition:.18s ease}.map-marker>span{width:30px;height:30px;display:grid;place-items:center;border-radius:50%;color:#fff;background:var(--day-color);font-size:11px;font-weight:950}.map-marker small{max-width:110px;overflow:hidden;font-size:10px;font-weight:850;text-overflow:ellipsis;white-space:nowrap}.map-marker:hover,.map-marker.active{z-index:7;transform:translate(-50%,-50%) scale(1.08);box-shadow:0 10px 30px rgba(15,23,42,.22)}.map-marker.active{outline:4px solid rgba(37,99,235,.12)}.map-scale{position:absolute;right:22px;bottom:22px;z-index:6;padding:10px 13px;border:1px solid #dfe4eb;border-radius:12px;color:#667085;background:rgba(255,255,255,.9);font-size:9px;font-weight:750}.map-scale span{width:34px;display:inline-block;margin-right:7px;border-top:2px solid #111827;vertical-align:middle}.route-warning{position:absolute;right:70px;bottom:112px;z-index:8;max-width:360px;padding:10px 13px;border:1px solid #fed7aa;border-radius:12px;color:#9a3412;background:rgba(255,247,237,.95);font-size:10px;line-height:1.45}.empty-state{position:absolute;inset:0;z-index:3;display:flex;align-items:center;justify-content:center;flex-direction:column;padding:40px;text-align:center}.empty-state__mark{width:58px;height:58px;display:grid;place-items:center;border-radius:20px;color:#fff;background:#111827;font-size:24px;box-shadow:0 12px 28px rgba(17,24,39,.16)}.empty-state>small{margin-top:22px;color:#7b4ff6;font-size:9px;font-weight:950;letter-spacing:.17em}.empty-state h1{margin:8px 0 10px;font-size:28px;font-weight:950;letter-spacing:-.035em}.empty-state p{max-width:440px;margin:0;color:#667085;font-size:12px;line-height:1.7}.empty-state button{min-height:44px;margin-top:20px;padding:0 20px;border:0;border-radius:14px;color:#fff;background:#111827;font-size:12px;font-weight:900;cursor:pointer}.route-panel{display:grid;align-content:start;gap:14px;min-width:0}.place-card,.route-list-card{border:1px solid #e1e6ed;border-radius:24px;background:#fff;box-shadow:0 12px 36px rgba(15,23,42,.07)}.place-card{padding:22px}.place-card__eyebrow,.route-list-card__head small{color:#98a2b3;font-size:8px;font-weight:950;letter-spacing:.16em}.place-card__title-row{display:flex;align-items:center;gap:12px;margin-top:16px}.place-card__title-row>span{width:38px;height:38px;display:grid;flex:0 0 38px;place-items:center;border-radius:50%;color:#fff;font-size:12px;font-weight:950}.place-card__title-row strong,.place-card__title-row small{display:block}.place-card__title-row strong{font-size:16px;font-weight:950}.place-card__title-row small{margin-top:4px;color:#98a2b3;font-size:9px;font-weight:750}.place-card p{display:-webkit-box;overflow:hidden;margin:16px 0;color:#667085;font-size:11px;line-height:1.7;-webkit-box-orient:vertical;-webkit-line-clamp:3}.place-card>button{width:100%;min-height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;border:1px solid #dfe4eb;border-radius:13px;color:#344054;background:#f8fafc;font-size:11px;font-weight:850;cursor:pointer}.route-list-card{overflow:hidden}.route-list-card__head{display:flex;align-items:center;justify-content:space-between;padding:20px 22px;border-bottom:1px solid #edf0f4}.route-list-card__head small,.route-list-card__head strong{display:block}.route-list-card__head strong{margin-top:4px;font-size:18px;font-weight:950}.route-list-card__head>span{padding:7px 10px;border-radius:999px;color:#475467;background:#f2f4f7;font-size:9px;font-weight:850}.route-days{max-height:calc(100vh - 380px);overflow-y:auto;padding:8px 18px 18px}.route-day{padding:13px 0}.route-day+.route-day{border-top:1px solid #edf0f4}.route-day__head{width:100%;display:grid;grid-template-columns:6px minmax(0,1fr) auto;align-items:center;gap:11px;padding:0;border:0;background:transparent;text-align:left;cursor:pointer}.route-day__head>i{width:5px;height:34px;border-radius:999px}.route-day__head small,.route-day__head strong{display:block}.route-day__head small{color:#98a2b3;font-size:8px;font-weight:900}.route-day__head strong{margin-top:3px;overflow:hidden;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.route-day__head b{color:#667085;font-size:9px}.route-stops{display:grid;gap:5px;margin:10px 0 0 17px;padding-left:12px;border-left:1px dashed #d8dee8}.route-stops button{display:grid;grid-template-columns:24px minmax(0,1fr);align-items:center;gap:9px;padding:7px;border:0;border-radius:10px;color:#475467;background:transparent;text-align:left;cursor:pointer}.route-stops button:hover,.route-stops button.active{color:#111827;background:#f4f6f8}.route-stops button>span{width:23px;height:23px;display:grid;place-items:center;border-radius:50%;color:#667085;background:#e9edf2;font-size:8px;font-weight:900}.route-stops strong,.route-stops small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.route-stops strong{font-size:10px}.route-stops small{margin-top:2px;color:#98a2b3;font-size:8px}.route-list-empty{padding:48px 22px;color:#98a2b3;font-size:11px;text-align:center}@keyframes pulse{50%{opacity:.35}}
@media(max-width:960px){.map-page{padding:14px}.map-layout{grid-template-columns:1fr}.route-canvas-card{min-height:68vh}.route-panel{grid-template-columns:minmax(0,1fr) minmax(0,1.3fr)}.route-days{max-height:360px}}
@media(max-width:640px){.map-page{padding:10px 10px 92px}.map-header{min-height:62px;grid-template-columns:auto 1fr auto;gap:8px;margin-bottom:10px}.back-button,.details-button{width:40px;height:40px;padding:0;display:grid;place-items:center;border-radius:50%}.back-button span,.details-button{font-size:0}.details-button span{margin:0;font-size:15px}.map-heading strong{font-size:15px}.map-heading small{max-width:210px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.route-canvas-card{min-height:68vh;border-radius:23px}.day-tabs{top:12px;right:12px;left:12px;overflow-x:auto;flex-wrap:nowrap}.day-tabs button{flex:0 0 auto}.map-status{top:67px;right:12px}.map-marker{grid-template-columns:28px;padding:3px}.map-marker>span{width:28px;height:28px}.map-marker small{display:none}.map-scale{right:12px;bottom:12px;max-width:210px}.route-warning{right:70px;bottom:112px;left:12px;max-width:none}.route-panel{grid-template-columns:1fr}.route-days{max-height:none}}
</style>
