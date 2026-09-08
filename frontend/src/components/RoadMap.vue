<template>
  <div class="road-map-frame">
    <div ref="container" class="road-map" aria-label="旅行路线真实地图" />
    <button class="fit-route" type="button" @click="fitRoute">查看全程</button>
    <div v-if="tileError" class="tile-error" role="alert">部分地图未能加载 <button @click="retryTiles">重试</button></div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import gcoord from 'gcoord'

type Position = { latitude: number; longitude: number }
type MapDay = { dayIndex: number; color: string; points: Array<Position & { id: string; title: string; order: number }>; paths: Position[][] }
const props = defineProps<{ days: MapDay[]; selectedId: string }>()
const emit = defineEmits<{ select: [id: string] }>()
const container = ref<HTMLElement>()
const tileError = ref(false)
let map: L.Map | undefined
let overlays: L.FeatureGroup
let tiles: L.TileLayer
let resizeObserver: ResizeObserver | undefined
const markers = new Map<string, L.Marker>()

// The API and mini-program keep GCJ-02. OSM uses WGS-84; convert every
// marker and route vertex together, only at the browser rendering boundary.
const latLng = (p: Position): L.LatLngTuple => {
  const [lng, lat] = gcoord.transform([p.longitude, p.latitude], gcoord.GCJ02, gcoord.WGS84)
  return [lat, lng]
}
const fitRoute = () => {
  if (!map || !overlays.getLayers().length) return
  const bounds = overlays.getBounds()
  if (bounds.isValid()) map.fitBounds(bounds, { paddingTopLeft: [35, 115], paddingBottomRight: [35, 85], maxZoom: 16 })
}
const selectMarker = () => {
  markers.forEach((marker, id) => {
    marker.getElement()?.classList.toggle('is-selected', id === props.selectedId)
    marker.setZIndexOffset(id === props.selectedId ? 1000 : 0)
  })
}
const renderRoutes = () => {
  if (!map) return
  overlays.clearLayers()
  markers.clear()
  for (const day of props.days) {
    // Only server-supplied road geometry is rendered. Never connect stops
    // to invent a path when the routing service has no geometry.
    const lines = day.paths.filter(p => p.length >= 2).map(path => path.map(latLng))
    if (lines.length) {
      // Separate parts stay separate. Draw all outlines underneath all strokes
      // so overlapping step endpoints do not cut white gaps into the route.
      L.polyline(lines, { color: '#fff', weight: 9, opacity: .95, smoothFactor: 0, interactive: false }).addTo(overlays)
      L.polyline(lines, { color: day.color, weight: 5, opacity: .95, smoothFactor: 0, interactive: false }).addTo(overlays)
    }
    for (const point of day.points) {
      const dot = document.createElement('span')
      dot.textContent = String(point.order)
      dot.style.backgroundColor = day.color
      const title = document.createElement('span')
      title.textContent = `第 ${day.dayIndex + 1} 天 · ${point.order}. ${point.title}`
      const marker = L.marker(latLng(point), {
        icon: L.divIcon({ html: dot, className: 'road-stop', iconSize: [32, 32], iconAnchor: [16, 16] }),
        title: title.textContent, keyboard: true,
      }).bindTooltip(title, { direction: 'top', offset: [0, -15] }).on('click', () => emit('select', point.id)).addTo(overlays)
      markers.set(point.id, marker)
    }
  }
  selectMarker()
  fitRoute()
}
const retryTiles = () => { tileError.value = false; tiles?.redraw() }
onMounted(() => {
  if (!container.value) return
  map = L.map(container.value, { zoomControl: false, scrollWheelZoom: true }).setView([30.25, 120.15], 12)
  L.control.zoom({ position: 'bottomright', zoomInTitle: '放大地图', zoomOutTitle: '缩小地图' }).addTo(map)
  L.control.scale({ position: 'bottomleft', imperial: false }).addTo(map)
  tiles = L.tileLayer(import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: import.meta.env.VITE_MAP_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).on('tileerror', () => { tileError.value = true }).addTo(map)
  overlays = L.featureGroup().addTo(map)
  resizeObserver = new ResizeObserver(() => { map?.invalidateSize() })
  resizeObserver.observe(container.value)
  renderRoutes()
})
watch(() => props.days, renderRoutes, { deep: true })
watch(() => props.selectedId, () => {
  selectMarker()
  const marker = markers.get(props.selectedId)
  if (marker && map && !map.getBounds().contains(marker.getLatLng())) map.panTo(marker.getLatLng())
})
onBeforeUnmount(() => { resizeObserver?.disconnect(); map?.remove(); map = undefined; markers.clear() })
</script>

<style scoped>
.road-map-frame{position:relative;height:100%;min-height:640px}.road-map{position:absolute;inset:0;z-index:0;background:#e5e7eb}.fit-route{position:absolute;z-index:500;left:18px;bottom:45px;padding:10px 14px;background:white;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 2px 8px #0002;font-weight:600;cursor:pointer}.tile-error{position:absolute;z-index:500;bottom:80px;left:18px;padding:8px;background:#fff7ed;color:#9a3412;border-radius:8px}.tile-error button{margin-left:8px;text-decoration:underline}.road-map :deep(.road-stop){border:3px solid white;border-radius:50%;box-shadow:0 2px 8px #0005}.road-map :deep(.road-stop span){display:grid;place-items:center;width:100%;height:100%;border-radius:50%;color:white;font-size:13px;font-weight:800}.road-map :deep(.road-stop.is-selected){outline:3px solid #111827;outline-offset:2px}.road-map :deep(.leaflet-control-attribution){font-size:10px}.road-map :deep(.leaflet-tooltip){font-size:12px;white-space:normal;max-width:240px}@media(max-width:640px){.road-map-frame{min-height:65vh}}
</style>
