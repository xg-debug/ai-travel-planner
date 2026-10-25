<template>
  <div class="page-stack trace-page">
    <a-card :bordered="false" class="trace-header">
      <div class="trace-header__row">
        <div>
          <h1>Agent 运行轨迹</h1>
          <p>查看每次规划的模型调用、地图工具、耗时与结果摘要。每次失败重试会单独记录。</p>
        </div>
        <a-button :loading="loading" @click="fetchRuns">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </div>
      <div class="trace-filters">
        <a-input-search v-model:value="search" allow-clear placeholder="搜索城市或任务 ID" @search="resetAndFetch" />
        <a-select v-model:value="statusFilter" :options="statusOptions" @change="resetAndFetch" />
      </div>
    </a-card>

    <a-card :bordered="false" class="trace-list">
      <a-table :data-source="runs" :columns="columns" :loading="loading" :pagination="false" row-key="id" :scroll="{ x: 900 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'trip'">
            <strong>{{ record.city || '未知城市' }} · {{ record.days }} 天</strong>
            <small>{{ sourceLabel(record.source) }} · 第 {{ record.attempt }} 次执行</small>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
            <small v-if="record.errorCode" class="trace-error">{{ record.errorCode }}</small>
          </template>
          <template v-else-if="column.key === 'calls'">
            <span>模型 {{ record.modelCalls }} 次</span>
            <small>工具 {{ record.toolCalls }} 次</small>
          </template>
          <template v-else-if="column.key === 'durationMs'">{{ formatDuration(record.durationMs) }}</template>
          <template v-else-if="column.key === 'createdAt'">{{ formatTime(record.createdAt) }}</template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" @click="openRun(record.id)">查看轨迹</a-button>
          </template>
        </template>
      </a-table>
      <div class="trace-pagination">
        <span>共 {{ total }} 次运行</span>
        <a-pagination v-model:current="page" :page-size="pageSize" :total="total" :show-size-changer="false" @change="fetchRuns" />
      </div>
    </a-card>

    <a-drawer :open="Boolean(detailId)" width="min(760px, 100vw)" title="Agent 轨迹详情" @close="closeDetail">
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <div class="trace-detail-head">
            <div><strong>{{ detail.city }} · {{ detail.days }} 天</strong><small>{{ formatTime(detail.createdAt) }} · {{ sourceLabel(detail.source) }}</small></div>
            <a-tag :color="statusColor(detail.status)">{{ statusLabel(detail.status) }}</a-tag>
          </div>
          <div class="trace-stats">
            <div><span>总耗时</span><strong>{{ formatDuration(detail.durationMs) }}</strong></div>
            <div><span>模型调用</span><strong>{{ detail.modelCalls }}</strong></div>
            <div><span>工具调用</span><strong>{{ detail.toolCalls }}</strong></div>
          </div>
          <a-alert v-if="detail.errorCode" type="error" show-icon :message="`失败原因：${detail.errorCode}`" class="trace-alert" />
          <div v-if="detail.resultSummary" class="trace-result">
            <h3>运行结果</h3>
            <pre>{{ formatJson(detail.resultSummary) }}</pre>
          </div>
          <h3 class="trace-events-title">事件时间线 · {{ detail.events.length }} 条</h3>
          <a-empty v-if="!detail.events.length" description="暂无轨迹事件" />
          <a-timeline v-else>
            <a-timeline-item v-for="event in detail.events" :key="event.id" :color="eventColor(event.status)">
              <div class="trace-event">
                <div class="trace-event__top">
                  <strong>{{ eventLabel(event.kind, event.name) }}</strong>
                  <span>{{ formatTime(event.createdAt) }}</span>
                </div>
                <div class="trace-event__meta">
                  <a-tag :color="eventColor(event.status)">{{ statusLabel(event.status) }}</a-tag>
                  <span v-if="event.provider">{{ event.provider }}<template v-if="event.model"> / {{ event.model }}</template></span>
                  <span v-if="event.endpoint">{{ event.endpoint }}</span>
                  <span v-if="event.durationMs !== null && event.durationMs !== undefined">{{ formatDuration(event.durationMs) }}</span>
                </div>
                <div v-if="event.errorCode" class="trace-error">{{ event.errorCode }}</div>
                <details v-if="event.inputSummary || event.outputSummary" class="trace-event__details">
                  <summary>输入与结果摘要</summary>
                  <div v-if="event.inputSummary"><b>输入</b><pre>{{ formatJson(event.inputSummary) }}</pre></div>
                  <div v-if="event.outputSummary"><b>结果</b><pre>{{ formatJson(event.outputSummary) }}</pre></div>
                </details>
              </div>
            </a-timeline-item>
          </a-timeline>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { adminApi } from '@/services/api'
import type { AgentRun, AgentRunDetail } from '@/types/admin'

const runs = ref<AgentRun[]>([])
const detail = ref<AgentRunDetail | null>(null)
const detailId = ref('')
const loading = ref(false)
const detailLoading = ref(false)
const search = ref('')
const statusFilter = ref('all')
const page = ref(1)
const pageSize = 15
const total = ref(0)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const columns = [
  { title: '行程 / 来源', key: 'trip', width: 210 },
  { title: '状态', key: 'status', width: 150 },
  { title: '调用次数', key: 'calls', width: 120 },
  { title: '耗时', key: 'durationMs', width: 105 },
  { title: '开始时间', key: 'createdAt', width: 180 },
  { title: '', key: 'action', width: 110 }
]

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已中断', value: 'interrupted' }
]

const statusLabel = (value: string) => ({ running: '运行中', completed: '已完成', failed: '失败', interrupted: '已中断', skipped: '跳过', progress: '进行中', started: '已开始' } as Record<string, string>)[value] || value
const statusColor = (value: string) => ({ running: 'blue', completed: 'green', failed: 'red', interrupted: 'orange' } as Record<string, string>)[value] || 'default'
const eventColor = (value: string) => value === 'failed' ? 'red' : value === 'completed' ? 'green' : 'blue'
const sourceLabel = (value: string) => ({ job: '异步任务', sync: '同步接口', stream: '流式接口' } as Record<string, string>)[value] || value
const eventLabel = (kind: string, name: string) => `${({ model: '模型', tool: '工具', phase: '阶段', decision: '决策', checkpoint: '检查点', result: '结果' } as Record<string, string>)[kind] || kind} · ${name}`
const formatDuration = (value?: number | null) => value === null || value === undefined ? '—' : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s`
const formatTime = (value?: string | null) => value ? new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleString('zh-CN', { hour12: false }) : '—'
const formatJson = (value: unknown) => JSON.stringify(value, null, 2)

const fetchRuns = async () => {
  loading.value = true
  try {
    const response = await adminApi.listAgentRuns({ page: page.value, page_size: pageSize, status: statusFilter.value === 'all' ? undefined : statusFilter.value, search: search.value.trim() || undefined })
    runs.value = response.items
    total.value = response.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载 Agent 轨迹失败')
  } finally {
    loading.value = false
  }
}

const resetAndFetch = () => { page.value = 1; fetchRuns() }
const openRun = async (runId: string) => {
  detailId.value = runId
  detailLoading.value = true
  try {
    detail.value = await adminApi.getAgentRun(runId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载轨迹详情失败')
  } finally {
    detailLoading.value = false
  }
}
const closeDetail = () => { detailId.value = ''; detail.value = null }

onMounted(() => {
  fetchRuns()
  refreshTimer = setInterval(() => {
    if (runs.value.some((run) => run.status === 'running')) {
      fetchRuns()
      if (detailId.value && detail.value?.status === 'running') openRun(detailId.value)
    }
  }, 15000)
})
onBeforeUnmount(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<style scoped>
.trace-page { display: grid; gap: 18px; }
.trace-header__row, .trace-pagination, .trace-detail-head, .trace-event__top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.trace-header h1 { margin: 0 0 6px; font-size: 22px; font-weight: 750; color: #172033; }
.trace-header p { margin: 0; color: #64748b; }
.trace-filters { display: flex; gap: 12px; margin-top: 22px; max-width: 560px; }
.trace-filters :deep(.ant-input-search) { flex: 1; }
.trace-filters :deep(.ant-select) { width: 145px; }
.trace-list strong, .trace-list small, .trace-detail-head small, .trace-event__meta span { display: block; }
.trace-list small, .trace-detail-head small { margin-top: 4px; color: #738197; font-size: 12px; }
.trace-pagination { align-items: center; margin-top: 18px; color: #738197; }
.trace-error { color: #b42318 !important; }
.trace-detail-head { margin-bottom: 18px; }
.trace-detail-head strong { font-size: 18px; }
.trace-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 18px; }
.trace-stats > div { padding: 14px; border-radius: 10px; background: #f4f7fb; }
.trace-stats span { display: block; color: #69788d; font-size: 12px; }
.trace-stats strong { display: block; margin-top: 5px; color: #172033; font-size: 18px; }
.trace-alert { margin-bottom: 16px; }
.trace-result h3, .trace-events-title { margin: 22px 0 12px; font-size: 15px; font-weight: 700; }
.trace-event { padding-bottom: 14px; }
.trace-event__top strong { color: #172033; }
.trace-event__top span, .trace-event__meta { color: #738197; font-size: 12px; }
.trace-event__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; margin-top: 8px; }
.trace-event__details { margin-top: 10px; color: #45566e; }
.trace-event__details summary { cursor: pointer; }
pre { overflow-x: auto; padding: 12px; border-radius: 8px; background: #f5f7fa; color: #344054; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 600px) { .trace-header__row, .trace-pagination { flex-direction: column; } .trace-filters { flex-direction: column; }.trace-filters :deep(.ant-select) { width: 100%; } }
</style>
