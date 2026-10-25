<template>
  <a-spin :spinning="loading">
    <div class="page-stack">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :lg="8">
          <a-card class="runtime-card" :bordered="false">
            <template #title>
              <span><RobotOutlined /> 大模型</span>
            </template>
            <a-badge :status="status?.health.llmConfigured ? 'success' : 'error'" />
            <h3>{{ status?.llm.providerLabel || '-' }}</h3>
            <p>{{ status?.llm.model || '未设置模型' }}</p>
          </a-card>
        </a-col>
        <a-col :xs="24" :lg="8">
          <a-card class="runtime-card" :bordered="false">
            <template #title>
              <span><EnvironmentOutlined /> 地图服务</span>
            </template>
            <a-badge :status="status?.health.mapConfigured ? 'success' : 'error'" />
            <h3>{{ status?.map.providerLabel || '-' }}</h3>
            <p>{{ status?.health.mapConfigured ? 'API Key 已配置' : 'API Key 未配置' }}</p>
          </a-card>
        </a-col>
        <a-col :xs="24" :lg="8">
          <a-card class="runtime-card" :bordered="false">
            <template #title>
              <span><SafetyCertificateOutlined /> 运行状态</span>
            </template>
            <a-badge :status="status?.health.warnings.length ? 'warning' : 'success'" />
            <h3>{{ status?.health.warnings.length ? '需要处理' : '运行就绪' }}</h3>
            <p>{{ status?.health.warnings.join('；') || '核心供应商配置完整' }}</p>
          </a-card>
        </a-col>
      </a-row>

      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :xl="12">
          <a-card title="大模型配置" :bordered="false">
            <a-form layout="vertical" :model="llmForm" @finish="saveLlm">
              <a-form-item label="供应商" name="provider" :rules="[{ required: true, message: '请选择供应商' }]">
                <a-select v-model:value="llmForm.provider" size="large" :options="llmOptions" />
              </a-form-item>
              <a-form-item label="模型名称" name="model" >
                <a-select
                  v-if="isDeepseekProvider"
                  v-model:value="llmForm.model"
                  size="large"
                  :options="deepseekModelOptions"
                />
                <a-input
                  v-else
                  v-model:value="llmForm.model"
                  size="large"
                  placeholder="例如 gpt-4o-mini"
                />
              </a-form-item>
              <a-form-item label="API Key" name="apiKey" extra="已配置时留空可保留原 Key。">
                <a-input-password
                  v-model:value="llmForm.apiKey"
                  size="large"
                  :placeholder="llmKeyPlaceholder"
                />
              </a-form-item>
              <a-button type="primary" html-type="submit" :loading="savingLlm">
                <template #icon>
                  <SaveOutlined />
                </template>
                保存模型配置
              </a-button>
            </a-form>
          </a-card>
        </a-col>

        <a-col :xs="24" :xl="12">
          <a-card title="地图配置" :bordered="false">
            <a-form layout="vertical" :model="mapForm" @finish="saveMap">
              <a-form-item label="供应商" name="provider" :rules="[{ required: true, message: '请选择供应商' }]">
                <a-select v-model:value="mapForm.provider" size="large" :options="mapOptions" />
              </a-form-item>
              <a-form-item label="API Key" name="apiKey">
                <a-input-password
                  v-model:value="mapForm.apiKey"
                  size="large"
                  :placeholder="mapKeyPlaceholder"
                />
              </a-form-item>
              <a-alert
                class="settings-alert"
                type="info"
                show-icon
                message="腾讯位置服务用于 POI 与路线；天气、周边与专属地图使用高德 MCP。"
              />
              <a-button type="primary" html-type="submit" :loading="savingMap">
                <template #icon>
                  <SaveOutlined />
                </template>
                保存地图配置
              </a-button>
            </a-form>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  EnvironmentOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SaveOutlined
} from '@ant-design/icons-vue'
import { adminApi } from '@/services/api'
import type { RuntimeStatus } from '@/types/admin'

const loading = ref(false)
const savingLlm = ref(false)
const savingMap = ref(false)
const status = ref<RuntimeStatus | null>(null)

const llmForm = reactive({
  provider: '',
  model: '',
  apiKey: ''
})

const mapForm = reactive({
  provider: '',
  apiKey: ''
})

const llmOptions = computed(() =>
  (status.value?.llm.providers || []).map((item) => ({
    label: `${item.label}${item.hasKey ? ' · 已配置' : ' · 未配置'}`,
    value: item.id
  }))
)

const mapOptions = computed(() =>
  (status.value?.map.providers || []).map((item) => ({
    label: `${item.label}${item.hasKey ? ' · 已配置' : ' · 未配置'}`,
    value: item.id
  }))
)

const selectedLlmProvider = computed(() =>
  status.value?.llm.providers.find((item) => item.id === llmForm.provider)
)

const selectedMapProvider = computed(() =>
  status.value?.map.providers.find((item) => item.id === mapForm.provider)
)

const isDeepseekProvider = computed(() => llmForm.provider === 'deepseek')

const deepseekModelOptions = computed(() =>
  (selectedLlmProvider.value?.models || []).map((model) => ({ label: model, value: model }))
)

const llmKeyPlaceholder = computed(() =>
  selectedLlmProvider.value?.maskedKey ? `已配置：${selectedLlmProvider.value.maskedKey}` : '粘贴新的 API Key'
)

const mapKeyPlaceholder = computed(() =>
  selectedMapProvider.value?.maskedKey ? `已配置：${selectedMapProvider.value.maskedKey}` : '粘贴新的 API Key'
)

const syncForms = () => {
  if (!status.value) return
  llmForm.provider = status.value.llm.provider
  llmForm.model = status.value.llm.model
  llmForm.apiKey = ''
  mapForm.provider = status.value.map.provider
  mapForm.apiKey = ''
}

watch(() => llmForm.provider, (provider) => {
  const saved = status.value?.llm.providers.find(item => item.id === provider)
  llmForm.model = saved?.model || saved?.defaultModel || ''
  llmForm.apiKey = ''
}, { flush: 'sync' })

const fetchStatus = async () => {
  loading.value = true
  try {
    status.value = await adminApi.getRuntimeStatus()
    syncForms()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载 运行状态失败')
  } finally {
    loading.value = false
  }
}

const saveLlm = async () => {
  savingLlm.value = true
  try {
    await adminApi.updateSettings({
      llm: {
        provider: llmForm.provider,
        model: llmForm.model,
        api_key: llmForm.apiKey
      }
    })
    message.success('模型配置已保存')
    await fetchStatus()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    savingLlm.value = false
  }
}

const saveMap = async () => {
  savingMap.value = true
  try {
    await adminApi.updateSettings({
      map: {
        provider: mapForm.provider,
        api_key: mapForm.apiKey
      }
    })
    message.success('地图配置已保存')
    await fetchStatus()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    savingMap.value = false
  }
}

onMounted(() => {
  fetchStatus()
  window.addEventListener('admin-refresh', fetchStatus)
})

onBeforeUnmount(() => {
  window.removeEventListener('admin-refresh', fetchStatus)
})
</script>
