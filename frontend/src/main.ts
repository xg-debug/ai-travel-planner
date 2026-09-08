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
      meta: { title: '随心游 - AI 智能旅行规划' }
    },
    {
      path: '/trip/:id',
      name: 'trip',
      component: TripDetailsView,
      meta: { title: '行程详情 - 随心游' }
    },
    {
      path: '/map',
      name: 'map',
      component: MapView,
      meta: { title: '旅行地图 - 随心游' }
    },
    {
      path: '/history',
      name: 'history',
      component: HistoryView,
      meta: { title: '我的行程 - 随心游', requiresAuth: true }
    }
  ]
})

// Update document title on route change
router.beforeEach((to, _from, next) => {
  document.title = to.meta.title as string || '随心游'
  if (to.meta.requiresAuth) {
    const authRaw = localStorage.getItem('cybertravel_auth') || sessionStorage.getItem('cybertravel_auth')
    if (!authRaw) {
      next('/')
      return
    }
  }
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
