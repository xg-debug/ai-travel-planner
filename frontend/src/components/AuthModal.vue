<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
    @click.self="$emit('close')"
  >
    <div class="w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
      <div class="grid md:grid-cols-[320px_1fr] min-h-[560px]">
        <aside class="bg-slate-900 text-slate-100 p-8">
          <h2 class="text-2xl font-semibold tracking-tight">TravelAI Console</h2>
          <p class="text-sm text-slate-300 mt-3 leading-6">
            企业级旅行规划工作台。登录后可管理行程、查看地图并导出计划。
          </p>
          <div class="mt-10 space-y-4 text-sm text-slate-300">
            <div class="flex items-start gap-3">
              <span class="mt-0.5 h-2 w-2 rounded-full bg-blue-400"></span>
              <p>账号体系：注册、登录、忘记密码</p>
            </div>
            <div class="flex items-start gap-3">
              <span class="mt-0.5 h-2 w-2 rounded-full bg-blue-400"></span>
              <p>登录态管理：支持记住我</p>
            </div>
            <div class="flex items-start gap-3">
              <span class="mt-0.5 h-2 w-2 rounded-full bg-blue-400"></span>
              <p>安全控制：JWT + 密码重置令牌</p>
            </div>
          </div>
        </aside>

        <section class="p-8">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h3 class="text-xl font-semibold text-slate-900">
                {{ titleMap[activeMode] }}
              </h3>
              <p class="text-sm text-slate-500 mt-1">{{ subtitleMap[activeMode] }}</p>
            </div>
            <button
              type="button"
              class="h-9 w-9 inline-flex items-center justify-center rounded-lg hover:bg-slate-100"
              @click="$emit('close')"
            >
              <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div v-if="activeMode === 'login' || activeMode === 'register'" class="mb-6">
            <div class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
              <button
                type="button"
                class="px-4 py-2 text-sm rounded-md transition-colors"
                :class="activeMode === 'login' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'"
                @click="switchMode('login')"
              >
                登录
              </button>
              <button
                type="button"
                class="px-4 py-2 text-sm rounded-md transition-colors"
                :class="activeMode === 'register' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'"
                @click="switchMode('register')"
              >
                注册
              </button>
            </div>
          </div>

          <form class="space-y-4" @submit.prevent="handleSubmit">
            <div v-if="activeMode === 'register'">
              <label class="block text-sm font-medium text-slate-700 mb-2">姓名（可选）</label>
              <input
                v-model="form.name"
                type="text"
                placeholder="不填将默认使用邮箱前缀"
                class="w-full h-11 px-3 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">邮箱</label>
              <input
                v-model="form.email"
                type="email"
                required
                placeholder="you@company.com"
                class="w-full h-11 px-3 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500"
              />
            </div>

            <div v-if="activeMode !== 'forgot'">
              <label class="block text-sm font-medium text-slate-700 mb-2">
                {{ activeMode === 'reset' ? '新密码' : '密码' }}
              </label>
              <input
                v-model="form.password"
                type="password"
                :minlength="activeMode === 'login' ? 1 : 6"
                required
                :placeholder="activeMode === 'login' ? '请输入密码' : '至少 6 位字符'"
                class="w-full h-11 px-3 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500"
              />
            </div>

            <div v-if="activeMode === 'reset'">
              <label class="block text-sm font-medium text-slate-700 mb-2">重置令牌</label>
              <input
                v-model="form.resetToken"
                type="text"
                required
                placeholder="请输入重置令牌"
                class="w-full h-11 px-3 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500"
              />
            </div>

            <div v-if="activeMode === 'login'" class="flex items-center justify-between pt-1">
              <label class="inline-flex items-center gap-2 text-sm text-slate-600">
                <input v-model="form.rememberMe" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
                记住我
              </label>
              <button type="button" class="text-sm text-blue-600 hover:text-blue-700" @click="switchMode('forgot')">
                忘记密码？
              </button>
            </div>

            <div v-if="authStore.error" class="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">
              {{ authStore.error }}
            </div>

            <div v-if="notice" class="p-3 rounded-lg border border-emerald-200 bg-emerald-50 text-sm text-emerald-700">
              {{ notice }}
            </div>

            <button
              type="submit"
              :disabled="authStore.isLoading"
              class="w-full h-11 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <span v-if="authStore.isLoading">处理中...</span>
              <span v-else>{{ submitText }}</span>
            </button>
          </form>

          <div class="pt-5 mt-5 border-t border-slate-100 text-sm text-slate-600">
            <template v-if="activeMode === 'forgot'">
              <button type="button" class="text-blue-600 hover:text-blue-700" @click="switchMode('reset')">
                我已经拿到令牌，去重置密码
              </button>
              <span class="mx-2">·</span>
              <button type="button" class="text-blue-600 hover:text-blue-700" @click="switchMode('login')">
                返回登录
              </button>
            </template>
            <template v-else-if="activeMode === 'reset'">
              <button type="button" class="text-blue-600 hover:text-blue-700" @click="switchMode('login')">
                返回登录
              </button>
            </template>
            <template v-else>
              <span>{{ activeMode === 'login' ? '没有账号？' : '已有账号？' }}</span>
              <button
                type="button"
                class="ml-1 text-blue-600 hover:text-blue-700"
                @click="switchMode(activeMode === 'login' ? 'register' : 'login')"
              >
                {{ activeMode === 'login' ? '立即注册' : '立即登录' }}
              </button>
            </template>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/authStore'

type AuthMode = 'login' | 'register' | 'forgot' | 'reset'

interface Props {
  show: boolean
  initialMode?: 'login' | 'register'
}

interface Emits {
  (e: 'close'): void
  (e: 'success'): void
}

const props = withDefaults(defineProps<Props>(), {
  initialMode: 'login'
})

const emit = defineEmits<Emits>()
const authStore = useAuthStore()

const activeMode = ref<AuthMode>(props.initialMode === 'register' ? 'register' : 'login')
const notice = ref('')

const titleMap: Record<AuthMode, string> = {
  login: '登录账户',
  register: '创建账户',
  forgot: '找回密码',
  reset: '重置密码'
}

const subtitleMap: Record<AuthMode, string> = {
  login: '使用企业账户进入系统',
  register: '填写信息并完成注册',
  forgot: '输入邮箱获取密码重置链接',
  reset: '输入令牌并设置新密码'
}

const form = reactive({
  name: '',
  email: '',
  password: '',
  rememberMe: true,
  resetToken: ''
})

const submitText = computed(() => {
  if (activeMode.value === 'login') return '登录'
  if (activeMode.value === 'register') return '注册'
  if (activeMode.value === 'forgot') return '发送重置邮件'
  return '更新密码'
})

const resetForm = () => {
  form.name = ''
  form.email = ''
  form.password = ''
  form.rememberMe = true
  form.resetToken = ''
  notice.value = ''
  authStore.error = null
}

const switchMode = (mode: AuthMode) => {
  activeMode.value = mode
  notice.value = ''
  authStore.error = null
}

const handleSubmit = async () => {
  try {
    if (activeMode.value === 'login') {
      await authStore.login(form.email, form.password, form.rememberMe)
      emit('success')
      emit('close')
      resetForm()
      return
    }

    if (activeMode.value === 'register') {
      await authStore.register(form.email, form.password, form.name, form.rememberMe)
      emit('success')
      emit('close')
      resetForm()
      return
    }

    if (activeMode.value === 'forgot') {
      const res = await authStore.forgotPassword(form.email)
      notice.value = res.reset_token
        ? `重置请求已受理。调试令牌：${res.reset_token}`
        : res.message
      if (res.reset_token) {
        form.resetToken = res.reset_token
        switchMode('reset')
      }
      return
    }

    await authStore.resetPassword(form.resetToken, form.password)
    notice.value = '密码已重置，请使用新密码登录。'
    switchMode('login')
    form.password = ''
    form.resetToken = ''
  } catch (error) {
    console.error('Auth submit failed', error)
  }
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    resetForm()
    activeMode.value = props.initialMode === 'register' ? 'register' : 'login'
  }
)
</script>
