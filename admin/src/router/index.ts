import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '@/views/AdminLayout.vue'
import RuntimeStatusView from '@/views/RuntimeStatusView.vue'
import LoginView from '@/views/LoginView.vue'
import OverviewView from '@/views/OverviewView.vue'
import TrendView from '@/views/TrendView.vue'
import UsersView from '@/views/UsersView.vue'
import { useAuthStore } from '@/stores/authStore'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: '后台登录 - AI 旅行规划管理后台' }
    },
    {
      path: '/',
      component: AdminLayout,
      redirect: '/overview',
      meta: { requiresAuth: true },
      children: [
        {
          path: 'overview',
          name: 'overview',
          component: OverviewView,
          meta: { title: '数据监控 - AI 旅行规划管理后台' }
        },
        {
          path: 'trends',
          name: 'trends',
          component: TrendView,
          meta: { title: '平台趋势 - AI 旅行规划管理后台' }
        },
        {
          path: 'runtime',
          name: 'runtime',
          component: RuntimeStatusView,
          meta: { title: '运行状态 - AI 旅行规划管理后台' }
        },
        {
          path: 'users',
          name: 'users',
          component: UsersView,
          meta: { title: '用户账号 - AI 旅行规划管理后台', requiresSuperAdmin: true }
        }
      ]
    }
  ]
})

router.beforeEach(async (to) => {
  document.title = (to.meta.title as string) || 'AI 旅行规划管理后台'

  const authStore = useAuthStore()
  if (!to.meta.requiresAuth) {
    if (to.name === 'login' && authStore.isAuthenticated) {
      return '/overview'
    }
    return true
  }

  if (!authStore.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  try {
    await authStore.ensureProfile()
  } catch {
    authStore.logout()
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresSuperAdmin && !authStore.isSuperAdmin) {
    return '/overview'
  }

  return true
})

export default router
