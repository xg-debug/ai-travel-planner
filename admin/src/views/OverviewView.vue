<template>
  <a-spin :spinning="loading">
    <div class="page-stack">
      <section class="overview-hero">
        <div>
          <a-typography-text>平台数据监控</a-typography-text>
          <h1>核心运营数据一屏掌握</h1>
          <p>聚合用户增长、行程生成、目的地热度与主题偏好，帮助管理员快速判断平台运行状态。</p>
        </div>
        <a-button type="primary" size="large" @click="fetchOverview">
          <template #icon>
            <ReloadOutlined />
          </template>
          刷新数据
        </a-button>
      </section>

      <a-row :gutter="[16, 16]">
        <a-col v-for="card in metricCards" :key="card.title" :xs="24" :sm="12" :xl="6">
          <a-card class="metric-card" :bordered="false">
            <div class="metric-card__head">
              <span>{{ card.title }}</span>
              <component :is="card.icon" />
            </div>
            <a-statistic :value="card.value" :suffix="card.suffix" />
            <p>{{ card.description }}</p>
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :xl="8">
          <a-card title="热门目的地" :bordered="false" class="clean-card">
            <a-list :data-source="overview?.topDestinations || []" size="small">
              <template #renderItem="{ item, index }">
                <a-list-item>
                  <div class="destination-row">
                    <span class="destination-rank">{{ index + 1 }}</span>
                    <div class="destination-main">
                      <strong>{{ item.name }}</strong>
                      <a-progress
                        :percent="rankPercent(item.count, overview?.topDestinations || [])"
                        :show-info="false"
                        size="small"
                      />
                    </div>
                    <span class="destination-count">{{ item.count }}</span>
                  </div>
                </a-list-item>
              </template>
              <template #empty>
                <a-empty description="暂无目的地数据" />
              </template>
            </a-list>
          </a-card>
        </a-col>

        <a-col :xs="24" :xl="8">
          <a-card title="热门行程主题" :bordered="false" class="clean-card">
            <div v-if="overview?.topThemes?.length" class="theme-grid">
              <div v-for="item in overview.topThemes" :key="item.name" class="theme-item">
                <span class="theme-icon">{{ themeMeta(item.name).icon }}</span>
                <div>
                  <strong>{{ themeMeta(item.name).label }}</strong>
                  <small>{{ item.count }} 次选择</small>
                </div>
              </div>
            </div>
            <a-empty v-else description="暂无主题数据" />
          </a-card>
        </a-col>

        <a-col :xs="24" :xl="8">
          <a-card title="最近生成行程" :bordered="false" class="clean-card">
            <a-list :data-source="overview?.recentTrips || []" size="small">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <span>{{ item.destination }}</span>
                    </template>
                    <template #description>
                      {{ item.user.name }} · {{ formatDateTime(item.createdAt) }}
                    </template>
                  </a-list-item-meta>
                  <a-tag>{{ item.status }}</a-tag>
                </a-list-item>
              </template>
              <template #empty>
                <a-empty description="暂无行程数据" />
              </template>
            </a-list>
          </a-card>
        </a-col>
      </a-row>

      <a-card title="用户行程生成排行" :bordered="false" class="clean-card">
        <a-table
          :columns="userColumns"
          :data-source="overview?.userTripCounts || []"
          :pagination="{ pageSize: 8 }"
          row-key="id"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'user'">
              <strong>{{ record.name }}</strong>
              <span class="muted-line">{{ record.email }}</span>
            </template>
            <template v-if="column.key === 'role'">
              <a-tag :color="roleColor(record.role)">{{ roleLabel(record.role) }}</a-tag>
            </template>
            <template v-if="column.key === 'lastLoginAt'">
              {{ formatDateTime(record.lastLoginAt) }}
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { computed, markRaw, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  FieldTimeOutlined,
  ReloadOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UsergroupAddOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { adminApi } from '@/services/api'
import type { AdminOverview, AdminRole, RankItem } from '@/types/admin'

const loading = ref(false)
const overview = ref<AdminOverview | null>(null)

const userColumns = [
  { title: '用户', key: 'user' },
  { title: '角色', key: 'role', width: 120 },
  { title: '行程生成数', dataIndex: 'tripCount', key: 'tripCount', width: 130 },
  { title: '最近登录', key: 'lastLoginAt', width: 180 }
]

const metricCards = computed(() => {
  const totals = overview.value?.totals
  return [
    {
      title: '总用户数',
      value: totals?.users || 0,
      suffix: '人',
      description: `今日注册 ${totals?.registrationsToday || 0}`,
      icon: markRaw(UsergroupAddOutlined)
    },
    {
      title: '今日登录',
      value: totals?.loginsToday || 0,
      suffix: '次',
      description: `今日活跃 ${totals?.activeToday || 0}`,
      icon: markRaw(FieldTimeOutlined)
    },
    {
      title: '总行程生成',
      value: totals?.trips || 0,
      suffix: '份',
      description: `今日生成 ${totals?.tripsToday || 0}`,
      icon: markRaw(ThunderboltOutlined)
    },
    {
      title: '管理员账号',
      value: totals?.admins || 0,
      suffix: '个',
      description: `超级管理员 ${totals?.superAdmins || 0}`,
      icon: markRaw(TeamOutlined)
    }
  ]
})

const fetchOverview = async () => {
  loading.value = true
  try {
    overview.value = await adminApi.getOverview()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载数据失败')
  } finally {
    loading.value = false
  }
}

const rankPercent = (value: number, items: RankItem[]) => {
  const max = Math.max(1, ...items.map((item) => item.count))
  return Math.round((value / max) * 100)
}

const themeMap: Record<string, { label: string; icon: string }> = {
  culture: { label: '文化历史', icon: '🏛️' },
  food: { label: '美食餐饮', icon: '🍽️' },
  nature: { label: '自然风光', icon: '🏞️' },
  shopping: { label: '购物逛街', icon: '🛍️' },
  adventure: { label: '冒险体验', icon: '🧗' },
  relaxation: { label: '休闲放松', icon: '🧘' },
  family: { label: '亲子活动', icon: '👨‍👩‍👧' },
  photography: { label: '摄影打卡', icon: '📸' },
  classic: { label: '经典必玩', icon: '📍' },
  history: { label: '历史古建', icon: '🏯' },
  local: { label: '小众探索', icon: '🧭' },
  photo: { label: '拍照出片', icon: '📸' },
  citywalk: { label: '城市漫步', icon: '🚶' },
  art: { label: '文艺展览', icon: '🎨' }
}

const themeMeta = (name: string) => {
  return themeMap[name] || { label: name, icon: '✨' }
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '-'
    : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const roleLabel = (role: AdminRole) => {
  const map: Record<AdminRole, string> = {
    user: '普通用户',
    admin: '管理员',
    super_admin: '超级管理员'
  }
  return map[role]
}

const roleColor = (role: AdminRole) => {
  if (role === 'super_admin') return 'gold'
  if (role === 'admin') return 'blue'
  return 'default'
}

onMounted(() => {
  fetchOverview()
  window.addEventListener('admin-refresh', fetchOverview)
})

onBeforeUnmount(() => {
  window.removeEventListener('admin-refresh', fetchOverview)
})
</script>
