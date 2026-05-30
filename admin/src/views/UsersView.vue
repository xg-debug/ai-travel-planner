<template>
  <a-card :bordered="false" title="用户权限管理">
    <template #extra>
      <a-button @click="fetchUsers">
        <template #icon>
          <ReloadOutlined />
        </template>
        刷新
      </a-button>
    </template>

    <a-result
      v-if="!authStore.canManageUsers"
      status="403"
      title="需要超级管理员权限"
      sub-title="当前账号没有用户权限管理权限。"
    />

    <a-table
      v-else
      :columns="columns"
      :data-source="users"
      :loading="loading"
      :pagination="{ pageSize: 10 }"
      row-key="id"
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

        <template v-if="column.key === 'action'">
          <a-select
            v-if="canEdit(record)"
            :value="record.role"
            style="width: 128px"
            @change="(value: string) => updateRole(record.id, value)"
          >
            <a-select-option value="user">普通用户</a-select-option>
            <a-select-option value="admin">管理员</a-select-option>
          </a-select>
          <a-typography-text v-else type="secondary">不可修改</a-typography-text>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { adminApi } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import type { AdminRole, AdminUser } from '@/types/admin'

const authStore = useAuthStore()
const loading = ref(false)
const users = ref<AdminUser[]>([])

const columns = [
  { title: '用户', key: 'user' },
  { title: '角色', key: 'role', width: 130 },
  { title: '行程生成数', dataIndex: 'tripCount', key: 'tripCount', width: 130 },
  { title: '最近登录', key: 'lastLoginAt', width: 180 },
  { title: '权限处理', key: 'action', width: 150 }
]

const fetchUsers = async () => {
  if (!authStore.canManageUsers) return
  loading.value = true
  try {
    const payload = await adminApi.listUsers()
    users.value = payload.users
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载用户失败')
  } finally {
    loading.value = false
  }
}

const updateRole = async (userId: string, role: string) => {
  try {
    await adminApi.updateUserRole(userId, role as 'user' | 'admin')
    message.success('用户权限已更新')
    await fetchUsers()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '更新失败')
  }
}

const canEdit = (record: AdminUser) => {
  return record.id !== authStore.user?.id && record.role !== 'super_admin'
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

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '-'
    : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  fetchUsers()
  window.addEventListener('admin-refresh', fetchUsers)
})

onBeforeUnmount(() => {
  window.removeEventListener('admin-refresh', fetchUsers)
})
</script>
