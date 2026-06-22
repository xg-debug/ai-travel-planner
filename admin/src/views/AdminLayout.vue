<template>
  <a-layout class="admin-shell">
    <a-layout-sider
      v-model:collapsed="collapsed"
      breakpoint="lg"
      class="admin-sider"
      collapsible
      :trigger="null"
      :width="248"
    >
      <div class="sider-brand">
        <div class="brand-mark">AI</div>
        <div v-if="!collapsed">
          <strong>AI Travel</strong>
          <span>管理后台</span>
        </div>
      </div>

      <a-menu
        mode="inline"
        class="admin-menu"
        :selected-keys="[selectedKey]"
        :items="menuItems"
        @click="handleMenuClick"
      />

      <div class="sider-bottom">
        <a-button
          class="sider-collapse-button"
          type="text"
          :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="collapsed = !collapsed"
        >
          <template #icon>
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </template>
          <span v-if="!collapsed">收起</span>
        </a-button>

        <div class="sider-account" :class="{ 'sider-account--collapsed': collapsed }">
          <div class="sider-user">
            <a-avatar :size="collapsed ? 36 : 42">{{ authStore.userName.slice(0, 1) }}</a-avatar>
            <div v-if="!collapsed" class="sider-user__meta">
              <strong>{{ authStore.userName }}</strong>
              <span>{{ roleLabel }}</span>
            </div>
          </div>
          <a-button
            class="sider-logout-button"
            :block="!collapsed"
            danger
            type="text"
            @click="confirmLogout"
          >
            <template #icon>
              <LogoutOutlined />
            </template>
            <span v-if="!collapsed">退出登录</span>
          </a-button>
        </div>
      </div>
    </a-layout-sider>

    <a-layout>
      <a-layout-content class="admin-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Modal } from 'ant-design-vue'
import type { ItemType } from 'ant-design-vue'
import {
  DashboardOutlined,
  LineChartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  TeamOutlined
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/authStore'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const collapsed = ref(false)

const roleMap = {
  user: '普通用户',
  admin: '管理员',
  super_admin: '超级管理员'
}

const selectedKey = computed(() => String(route.name || 'overview'))
const roleLabel = computed(() => roleMap[authStore.user?.role || 'user'])

const menuItems = computed<ItemType[]>(() => {
  const items: ItemType[] = [
    {
      key: 'overview',
      icon: () => h(DashboardOutlined),
      label: '数据监控'
    },
    {
      key: 'trends',
      icon: () => h(LineChartOutlined),
      label: '平台趋势'
    },
    {
      key: 'runtime',
      icon: () => h(RobotOutlined),
      label: '运行状态'
    }
  ]

  if (authStore.canManageUsers) {
    items.push({
      key: 'users',
      icon: () => h(TeamOutlined),
      label: '用户账号'
    })
  }

  return items
})

const handleMenuClick = ({ key }: { key: string }) => {
  router.push({ name: key })
}

const confirmLogout = () => {
  Modal.confirm({
    title: '退出登录',
    content: '确认退出当前后台账号？',
    okText: '退出',
    cancelText: '取消',
    onOk: () => {
      authStore.logout()
      router.replace('/login')
    }
  })
}
</script>
