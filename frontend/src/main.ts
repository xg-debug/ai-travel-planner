import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

// Import styles
import './styles/main.css'

// Import components
import TripPlannerView from './views/TripPlannerView.vue'
import TripDetailsView from './views/TripDetailsView.vue'
import MapView from './views/MapView.vue'
import HistoryView from './views/HistoryView.vue'

// Create Pinia store
const pinia = createPinia()

// Create router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: TripPlannerView,
      meta: { title: '智能旅行规划器 - AI Travel Planner' }
    },
    {
      path: '/trip/:id',
      name: 'trip',
      component: TripDetailsView,
      meta: { title: '行程详情' }
    },
    {
      path: '/map',
      name: 'map',
      component: MapView,
      meta: { title: '3D地图' }
    },
    {
      path: '/history',
      name: 'history',
      component: HistoryView,
      meta: { title: '旅行历史' }
    }
  ]
})

// Update document title on route change
router.beforeEach((to, _from, next) => {
  document.title = to.meta.title as string || '智能旅行规划器'
  next()
})

// Create and mount app
const app = createApp(App)
app.use(pinia)
app.use(router)
app.mount('#app')

// Add global error handler
app.config.errorHandler = (err, _instance, info) => {
  console.error('Vue error:', err, info)
  // In production, send to error tracking service
}
