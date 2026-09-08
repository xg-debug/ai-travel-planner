<template>
  <div class="planner-page">
    <TravelNav @auth="openAuthModal" />
    <AuthModal
      v-if="showAuthModal"
      :show="showAuthModal"
      :initial-mode="authMode"
      @close="showAuthModal = false"
      @success="handleAuthSuccess"
    />

    <main class="planner-main">
      <section class="hero">
        <div class="hero__copy">
          <span class="hero__eyebrow"><i /> AI 智能旅行规划</span>
          <h1>你只管出发，<br />路线交给我们。</h1>
          <p>基于真实地图、目的地天气和你的旅行偏好，生成每天走得顺、住得稳、预算看得懂的行程。</p>
          <div class="hero__capabilities">
            <span>真实地点</span>
            <span>天气适配</span>
            <span>路线优化</span>
            <span>预算估算</span>
          </div>
        </div>

        <div class="hero__preview" aria-label="规划能力概览">
          <div class="hero__preview-head">
            <span>PLANNING SIGNAL</span>
            <strong>实时研究</strong>
          </div>
          <div class="preview-route">
            <div class="preview-route__item">
              <span class="preview-route__point preview-route__point--start" />
              <div>
                <small>从</small>
                <strong>{{ departureCity.trim() || '你的城市' }}</strong>
              </div>
            </div>
            <span class="preview-route__line" />
            <div class="preview-route__item">
              <span class="preview-route__point preview-route__point--end" />
              <div>
                <small>到</small>
                <strong>{{ destination.trim() || '下一站' }}</strong>
              </div>
            </div>
          </div>
          <div class="preview-metrics">
            <div><strong>{{ days }}</strong><span>天行程</span></div>
            <div><strong>{{ travelers }}</strong><span>位旅行者</span></div>
            <div><strong>¥{{ totalBudget.toLocaleString() }}</strong><span>总预算</span></div>
          </div>
        </div>
      </section>

      <section class="planner-workspace">
        <aside class="brief-card">
          <div class="brief-card__head">
            <span>TRIP BRIEF</span>
            <strong>这趟旅行</strong>
          </div>

          <div class="brief-route">
            <div class="brief-route__item">
              <span class="brief-route__dot" />
              <div><small>出发城市</small><strong>{{ departureCity.trim() || '待填写' }}</strong></div>
            </div>
            <div class="brief-route__connector" />
            <div class="brief-route__item">
              <span class="brief-route__dot brief-route__dot--destination" />
              <div><small>目的地</small><strong>{{ destination.trim() || '待填写' }}</strong></div>
            </div>
          </div>

          <dl class="brief-facts">
            <div><dt>日期</dt><dd>{{ dateSummary }}</dd></div>
            <div><dt>同行</dt><dd>{{ travelers }} 人</dd></div>
            <div><dt>预算</dt><dd>¥{{ budgetPerPerson.toLocaleString() }}/人</dd></div>
            <div><dt>住宿</dt><dd>{{ accommodationLabel }}</dd></div>
          </dl>

          <div class="brief-card__note">
            <span>✦</span>
            <p>Agent 会先查地点、天气与住宿，再检查相邻地点的真实交通路线。</p>
          </div>

          <button
            v-if="tripStore.currentTrip"
            class="recent-trip"
            type="button"
            @click="openCurrentTrip"
          >
            <span><small>最近方案</small><strong>{{ tripStore.currentTrip.destination }}</strong></span>
            <b>→</b>
          </button>
        </aside>

        <div class="form-card">
          <div class="form-card__head">
            <div>
              <span>01 / 03</span>
              <h2>告诉我你的旅行需求</h2>
              <p>带 <b>*</b> 的信息会直接影响路线和预算。</p>
            </div>
            <span class="form-card__status">{{ canGenerate ? '可以开始规划' : '等待完整信息' }}</span>
          </div>

          <form @submit.prevent="generateTrip">
            <section class="form-section">
              <div class="form-section__title">
                <span>01</span>
                <div><h3>路线与日期</h3><p>先确定从哪里出发、去哪里以及往返时间。</p></div>
              </div>

              <div class="route-fields">
                <label class="field">
                  <span>出发城市 *</span>
                  <div class="field__control"><b>出</b><input v-model="departureCity" placeholder="例如：上海" /></div>
                </label>
                <button class="swap-cities" type="button" aria-label="交换出发地和目的地" @click="swapCities">⇄</button>
                <label class="field">
                  <span>目的地 *</span>
                  <div class="field__control field__control--spark"><b>✦</b><input v-model="destination" placeholder="例如：北京" /></div>
                </label>
              </div>

              <div class="date-fields">
                <label class="field">
                  <span>开始日期 *</span>
                  <input v-model="startDate" type="date" :min="today" />
                </label>
                <label class="field field--time">
                  <span>出发时间</span>
                  <input v-model="departureTime" type="time" />
                </label>
                <span class="date-fields__arrow">→</span>
                <label class="field">
                  <span>结束日期 *</span>
                  <input v-model="endDate" type="date" :min="startDate || today" />
                </label>
                <label class="field field--time">
                  <span>返程到达</span>
                  <input v-model="returnArrivalTime" type="time" />
                </label>
              </div>
            </section>

            <section class="form-section">
              <div class="form-section__title">
                <span>02</span>
                <div><h3>旅行尺度</h3><p>人数、预算与住宿标准会参与每一项费用判断。</p></div>
              </div>

              <div class="scale-grid">
                <div class="setting-box">
                  <span class="setting-box__label">出行人数</span>
                  <small>最多支持 20 人</small>
                  <div class="stepper">
                    <button type="button" @click="travelers = Math.max(1, travelers - 1)">−</button>
                    <strong>{{ travelers }} <i>人</i></strong>
                    <button type="button" @click="travelers = Math.min(20, travelers + 1)">＋</button>
                  </div>
                </div>

                <label class="setting-box">
                  <span class="setting-box__label">每人预算</span>
                  <small>当前总预算 ¥{{ totalBudget.toLocaleString() }}</small>
                  <div class="budget-input"><span>¥</span><input v-model.number="budgetPerPerson" type="number" min="100" step="100" /></div>
                </label>
              </div>

              <div class="stay-options">
                <button
                  v-for="option in accommodationOptions"
                  :key="option.id"
                  type="button"
                  :class="{ 'is-active': accommodationPreference === option.id }"
                  @click="accommodationPreference = option.id"
                >
                  <span>{{ option.label }}</span>
                  <small>{{ option.desc }}</small>
                </button>
              </div>
            </section>

            <section class="form-section">
              <div class="form-section__title form-section__title--with-note">
                <span>03</span>
                <div><h3>旅行偏好</h3><p>选择你愿意投入更多时间的体验。</p></div>
                <small>可多选</small>
              </div>

              <div class="interest-grid">
                <button
                  v-for="item in availableInterests"
                  :key="item.id"
                  type="button"
                  :class="{ 'is-active': interests.includes(item.id) }"
                  @click="toggleInterest(item.id)"
                >
                  <span>{{ item.icon }}</span>{{ item.label }}
                </button>
              </div>

              <label class="field requirements-field">
                <span>补充需求</span>
                <textarea
                  v-model="additionalRequirements"
                  rows="3"
                  placeholder="例如：带孩子、希望少走路、想安排一晚夜景、需要素食餐厅……"
                />
              </label>
            </section>

            <div v-if="isLoading" class="generation-panel">
              <div class="generation-panel__head">
                <span class="generation-panel__pulse" />
                <div><strong>Agent 正在规划 {{ destination || '本次旅行' }}</strong><p>{{ tripStore.streamingStatus || '正在理解你的旅行需求' }}</p></div>
              </div>
              <div class="generation-steps">
                <div v-for="step in tripStore.streamSteps" :key="step.key" :class="['generation-step', step.status]">
                  <span>{{ step.status === 'done' ? '✓' : step.status === 'active' ? '•' : '' }}</span>
                  <small>{{ step.label }}</small>
                </div>
              </div>
            </div>

            <div v-if="errorMessage" class="error-message">
              <div><strong>暂时没有生成成功</strong><p>{{ errorMessage }}</p></div>
              <button type="button" @click="errorMessage = ''">关闭</button>
            </div>

            <div class="submit-row">
              <div><strong>{{ destination.trim() || '等待目的地' }}</strong><span>{{ days }} 天 · {{ travelers }} 人 · ¥{{ totalBudget.toLocaleString() }}</span></div>
              <button type="submit" :disabled="!canGenerate || isLoading">
                <span>{{ isLoading ? '规划中…' : '开始智能规划' }}</span><b>→</b>
              </button>
            </div>
          </form>
        </div>
      </section>
    </main>

    <TravelFooter />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthModal from '@/components/AuthModal.vue'
import TravelFooter from '@/components/TravelFooter.vue'
import TravelNav from '@/components/TravelNav.vue'
import { useTripStore } from '@/stores/tripStore'
import type { TripRequest } from '@/types/trip'

const router = useRouter()
const tripStore = useTripStore()

const isoDate = (date: Date) => date.toISOString().split('T')[0]
const today = isoDate(new Date())
const defaultEnd = new Date()
defaultEnd.setDate(defaultEnd.getDate() + 2)

const departureCity = ref('')
const destination = ref('')
const startDate = ref(today)
const endDate = ref(isoDate(defaultEnd))
const departureTime = ref('08:00')
const returnArrivalTime = ref('20:00')
const travelers = ref(2)
const budgetPerPerson = ref(3500)
const accommodationPreference = ref<'budget' | 'mid-range' | 'luxury'>('mid-range')
const interests = ref<string[]>(['classic', 'food', 'history'])
const additionalRequirements = ref('')
const errorMessage = ref('')
const showAuthModal = ref(false)
const authMode = ref<'login' | 'register'>('login')

const accommodationOptions = [
  { id: 'budget', label: '经济', desc: '优先性价比与公共交通' },
  { id: 'mid-range', label: '中档', desc: '舒适度和预算平衡' },
  { id: 'luxury', label: '高档', desc: '位置与品质体验优先' }
] as const

const availableInterests = [
  { id: 'classic', label: '经典必玩', icon: '📍' },
  { id: 'food', label: '吃吃喝喝', icon: '🍽️' },
  { id: 'local', label: '小众探索', icon: '🧭' },
  { id: 'photo', label: '拍照出片', icon: '📸' },
  { id: 'shopping', label: '逛街购物', icon: '🛍️' },
  { id: 'citywalk', label: '城市漫步', icon: '🚶' },
  { id: 'nature', label: '自然风光', icon: '🏞️' },
  { id: 'art', label: '文艺展览', icon: '🎨' },
  { id: 'history', label: '历史古建', icon: '🏛️' }
]

const days = computed(() => {
  const start = new Date(startDate.value)
  const end = new Date(endDate.value)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0
  return Math.max(0, Math.floor((end.getTime() - start.getTime()) / 86400000) + 1)
})
const totalBudget = computed(() => Math.max(0, Number(budgetPerPerson.value || 0)) * travelers.value)
const accommodationLabel = computed(() => accommodationOptions.find(item => item.id === accommodationPreference.value)?.label || '中档')
const dateSummary = computed(() => startDate.value && endDate.value ? `${startDate.value.slice(5)} — ${endDate.value.slice(5)}` : '待填写')
const isLoading = computed(() => tripStore.isLoading)
const canGenerate = computed(() => Boolean(
  departureCity.value.trim()
  && destination.value.trim()
  && startDate.value
  && endDate.value
  && days.value > 0
  && days.value <= 7
  && totalBudget.value > 0
))

const swapCities = () => {
  const previous = departureCity.value
  departureCity.value = destination.value
  destination.value = previous
}

const toggleInterest = (id: string) => {
  interests.value = interests.value.includes(id)
    ? interests.value.filter(item => item !== id)
    : [...interests.value, id]
}

const generateTrip = async () => {
  errorMessage.value = ''
  if (!canGenerate.value) {
    errorMessage.value = days.value > 7 ? '当前最多支持 7 天游。' : '请完整填写出发城市、目的地、日期和预算。'
    return
  }

  const payload: TripRequest = {
    departureCity: departureCity.value.trim(),
    destination: destination.value.trim(),
    startDate: startDate.value,
    endDate: endDate.value,
    departureTime: departureTime.value,
    returnArrivalTime: returnArrivalTime.value,
    days: days.value,
    travelers: travelers.value,
    interests: interests.value,
    budget: totalBudget.value,
    accommodationPreference: accommodationPreference.value,
    additionalRequirements: additionalRequirements.value.trim(),
    preferences: {
      pace: 'moderate',
      accommodation: accommodationPreference.value,
      food: 'mixed',
      transportation: 'mixed'
    }
  }

  try {
    const trip = await tripStore.createTrip(payload)
    await router.push(`/trip/${trip.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生成行程失败，请稍后重试。'
  }
}

const openAuthModal = (mode: 'login' | 'register') => {
  authMode.value = mode
  showAuthModal.value = true
}

const handleAuthSuccess = () => {
  showAuthModal.value = false
  errorMessage.value = ''
}

const openCurrentTrip = () => {
  if (tripStore.currentTrip) router.push(`/trip/${tripStore.currentTrip.id}`)
}
</script>

<style scoped>
.planner-page { min-height: 100vh; color: #111827; background: #f6f7f9; }
.planner-main { width: min(1180px, calc(100% - 40px)); margin: 0 auto; padding: 66px 0 88px; }
.hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(330px, .65fr); align-items: end; gap: 72px; margin-bottom: 54px; }
.hero__eyebrow { display: inline-flex; align-items: center; gap: 9px; color: #6d5bd0; font-size: 12px; font-weight: 900; letter-spacing: .12em; }
.hero__eyebrow i { width: 8px; height: 8px; border-radius: 50%; background: #7b4ff6; box-shadow: 0 0 0 6px rgba(123,79,246,.1); }
.hero h1 { margin: 22px 0 20px; font-size: clamp(48px, 6vw, 76px); font-weight: 950; line-height: 1.04; letter-spacing: -.055em; }
.hero__copy > p { max-width: 680px; margin: 0; color: #667085; font-size: 17px; line-height: 1.8; }
.hero__capabilities { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 28px; }
.hero__capabilities span { padding: 9px 14px; border: 1px solid #e0e5ec; border-radius: 999px; color: #475467; background: rgba(255,255,255,.72); font-size: 12px; font-weight: 750; }
.hero__preview { padding: 26px; border: 1px solid #e1e6ed; border-radius: 28px; background: #fff; box-shadow: 0 20px 50px rgba(17,24,39,.07); }
.hero__preview-head { display: flex; align-items: center; justify-content: space-between; padding-bottom: 18px; border-bottom: 1px solid #edf0f4; }
.hero__preview-head span { color: #98a2b3; font-size: 10px; font-weight: 900; letter-spacing: .16em; }
.hero__preview-head strong { color: #0f766e; font-size: 12px; }
.preview-route { padding: 22px 0; }
.preview-route__item { display: grid; grid-template-columns: 16px minmax(0,1fr); gap: 12px; }
.preview-route__point { position: relative; z-index: 1; width: 12px; height: 12px; margin-top: 5px; border: 3px solid #dbeafe; border-radius: 50%; background: #2563eb; }
.preview-route__point--end { border-color: #ede9fe; border-radius: 50% 50% 50% 3px; background: #7b4ff6; transform: rotate(-45deg); }
.preview-route__line { display: block; width: 1px; height: 26px; margin: 3px 0 3px 5px; border-left: 1px dashed #cbd5e1; }
.preview-route small,.preview-route strong { display: block; }
.preview-route small { color: #98a2b3; font-size: 11px; }
.preview-route strong { margin-top: 2px; font-size: 16px; }
.preview-metrics { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; }
.preview-metrics div { padding: 12px 8px; border-radius: 15px; background: #f5f7fa; text-align: center; }
.preview-metrics strong,.preview-metrics span { display: block; }
.preview-metrics strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.preview-metrics span { margin-top: 3px; color: #98a2b3; font-size: 9px; }

.planner-workspace { display: grid; grid-template-columns: 300px minmax(0,1fr); align-items: start; gap: 24px; }
.brief-card { position: sticky; top: 96px; padding: 26px; border: 1px solid #e1e6ed; border-radius: 26px; background: #fff; box-shadow: 0 12px 34px rgba(17,24,39,.045); }
.brief-card__head span,.brief-card__head strong { display: block; }
.brief-card__head span { color: #98a2b3; font-size: 10px; font-weight: 900; letter-spacing: .15em; }
.brief-card__head strong { margin-top: 8px; font-size: 25px; font-weight: 950; }
.brief-route { margin: 26px 0; padding: 20px; border-radius: 20px; background: #f6f7f9; }
.brief-route__item { display: grid; grid-template-columns: 14px minmax(0,1fr); align-items: center; gap: 12px; }
.brief-route__item small,.brief-route__item strong { display: block; }
.brief-route__item small { color: #98a2b3; font-size: 10px; }
.brief-route__item strong { margin-top: 2px; overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.brief-route__dot { width: 11px; height: 11px; border: 3px solid #dbeafe; border-radius: 50%; background: #2563eb; }
.brief-route__dot--destination { border-color: #ede9fe; background: #7b4ff6; }
.brief-route__connector { height: 22px; margin-left: 5px; border-left: 1px dashed #cbd5e1; }
.brief-facts { margin: 0; }
.brief-facts div { display: flex; justify-content: space-between; gap: 18px; padding: 13px 0; border-bottom: 1px solid #edf0f4; font-size: 12px; }
.brief-facts dt { color: #98a2b3; }
.brief-facts dd { margin: 0; color: #344054; font-weight: 800; text-align: right; }
.brief-card__note { display: flex; gap: 11px; margin-top: 20px; padding: 15px; border-radius: 16px; color: #5b6472; background: #eef4ff; font-size: 11px; line-height: 1.55; }
.brief-card__note span { color: #7b4ff6; }
.brief-card__note p { margin: 0; }
.recent-trip { width: 100%; display: flex; align-items: center; justify-content: space-between; margin-top: 14px; padding: 15px; border: 1px solid #e1e6ed; border-radius: 16px; background: #fff; text-align: left; cursor: pointer; }
.recent-trip small,.recent-trip strong { display: block; }
.recent-trip small { color: #98a2b3; font-size: 9px; }
.recent-trip strong { margin-top: 3px; font-size: 13px; }

.form-card { overflow: hidden; border: 1px solid #e1e6ed; border-radius: 28px; background: #fff; box-shadow: 0 18px 48px rgba(17,24,39,.055); }
.form-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; padding: 30px 34px; color: #fff; background: #111827; }
.form-card__head span { color: #a5b4fc; font-size: 10px; font-weight: 900; letter-spacing: .12em; }
.form-card__head h2 { margin: 8px 0 5px; font-size: 25px; font-weight: 900; }
.form-card__head p { margin: 0; color: #aeb8c8; font-size: 12px; }
.form-card__head p b { color: #fb7185; }
.form-card__head .form-card__status { flex-shrink: 0; padding: 8px 12px; border: 1px solid rgba(255,255,255,.15); border-radius: 999px; color: #dbeafe; background: rgba(255,255,255,.07); letter-spacing: 0; }
.form-section { padding: 32px 34px; border-bottom: 1px solid #edf0f4; }
.form-section__title { display: grid; grid-template-columns: 38px minmax(0,1fr); gap: 12px; margin-bottom: 24px; }
.form-section__title > span { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 12px; color: #fff; background: #111827; font-size: 11px; font-weight: 900; }
.form-section__title h3,.form-section__title p { margin: 0; }
.form-section__title h3 { font-size: 17px; font-weight: 900; }
.form-section__title p { margin-top: 4px; color: #98a2b3; font-size: 11px; }
.form-section__title--with-note { grid-template-columns: 38px minmax(0,1fr) auto; }
.form-section__title--with-note > small { color: #98a2b3; font-size: 10px; }
.field { display: grid; gap: 8px; min-width: 0; }
.field > span,.setting-box__label { color: #475467; font-size: 11px; font-weight: 800; }
.field input,.field textarea { box-sizing: border-box; width: 100%; min-height: 46px; padding: 0 14px; border: 1px solid #dce2e9; border-radius: 14px; outline: 0; color: #111827; background: #fff; font-size: 13px; transition: .2s ease; }
.field textarea { min-height: 92px; padding-top: 13px; line-height: 1.55; resize: vertical; }
.field input:focus,.field textarea:focus { border-color: #2563eb; box-shadow: 0 0 0 4px rgba(37,99,235,.09); }
.field__control { display: flex; align-items: center; min-height: 52px; padding: 0 14px; border: 1px solid #dce2e9; border-radius: 16px; }
.field__control:focus-within { border-color: #2563eb; box-shadow: 0 0 0 4px rgba(37,99,235,.09); }
.field__control b { flex: 0 0 auto; color: #2563eb; font-size: 18px; }
.field__control--spark b { color: #7b4ff6; }
.field__control input { min-height: 48px; border: 0; box-shadow: none!important; }
.route-fields { display: grid; grid-template-columns: minmax(0,1fr) 42px minmax(0,1fr); align-items: end; gap: 12px; }
.swap-cities { width: 40px; height: 40px; margin-bottom: 6px; border: 1px solid #dce2e9; border-radius: 50%; color: #475467; background: #f6f7f9; cursor: pointer; }
.date-fields { display: grid; grid-template-columns: minmax(0,1fr) 112px 28px minmax(0,1fr) 112px; align-items: end; gap: 10px; margin-top: 20px; }
.date-fields__arrow { padding-bottom: 14px; color: #98a2b3; text-align: center; }
.scale-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 14px; }
.setting-box { display: block; padding: 18px; border: 1px solid #dce2e9; border-radius: 18px; }
.setting-box small { display: block; margin-top: 4px; color: #98a2b3; font-size: 10px; }
.stepper { display: flex; align-items: center; justify-content: space-between; margin-top: 18px; }
.stepper button { width: 36px; height: 36px; border: 0; border-radius: 50%; color: #111827; background: #f0f2f5; font-size: 17px; cursor: pointer; }
.stepper strong { font-size: 22px; }
.stepper i { color: #667085; font-size: 11px; font-style: normal; }
.budget-input { display: flex; align-items: center; margin-top: 15px; color: #111827; font-size: 18px; font-weight: 900; }
.budget-input input { width: 100%; min-width: 0; border: 0; outline: 0; text-align: right; font-size: 22px; font-weight: 900; }
.stay-options { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; margin-top: 14px; }
.stay-options button { min-height: 72px; padding: 12px; border: 1px solid #dce2e9; border-radius: 16px; color: #344054; background: #fff; cursor: pointer; }
.stay-options span,.stay-options small { display: block; }
.stay-options span { font-size: 13px; font-weight: 900; }
.stay-options small { margin-top: 5px; color: #98a2b3; font-size: 9px; }
.stay-options button.is-active { border-color: #111827; color: #fff; background: #111827; }
.stay-options button.is-active small { color: #cbd5e1; }
.interest-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 9px; }
.interest-grid button { min-height: 46px; padding: 0 10px; border: 1px solid #dce2e9; border-radius: 999px; color: #475467; background: #fff; font-size: 11px; font-weight: 800; cursor: pointer; }
.interest-grid button span { margin-right: 5px; }
.interest-grid button.is-active { border-color: #111827; color: #fff; background: #111827; }
.requirements-field { margin-top: 22px; }
.generation-panel { margin: 24px 34px 0; padding: 20px; border: 1px solid #bfdbfe; border-radius: 20px; background: #eff6ff; }
.generation-panel__head { display: flex; align-items: center; gap: 14px; }
.generation-panel__pulse { width: 12px; height: 12px; border: 3px solid #bfdbfe; border-radius: 50%; background: #2563eb; box-shadow: 0 0 0 6px rgba(37,99,235,.1); }
.generation-panel__head strong,.generation-panel__head p { display: block; margin: 0; }
.generation-panel__head strong { color: #1e3a8a; font-size: 13px; }
.generation-panel__head p { margin-top: 3px; color: #3b82f6; font-size: 10px; }
.generation-steps { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 7px; margin-top: 16px; }
.generation-step { display: flex; align-items: center; gap: 6px; min-width: 0; padding: 8px; border-radius: 10px; color: #7c8ba1; background: rgba(255,255,255,.62); }
.generation-step span { width: 15px; font-size: 12px; text-align: center; }
.generation-step small { overflow: hidden; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.generation-step.active { color: #1d4ed8; background: #dbeafe; }
.generation-step.done { color: #047857; background: #ecfdf5; }
.error-message { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin: 24px 34px 0; padding: 16px 18px; border: 1px solid #fecaca; border-radius: 16px; color: #991b1b; background: #fef2f2; }
.error-message strong,.error-message p { display: block; margin: 0; }
.error-message p { margin-top: 4px; font-size: 11px; }
.error-message button { border: 0; color: #b91c1c; background: transparent; font-size: 11px; cursor: pointer; }
.submit-row { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 26px 34px; }
.submit-row > div strong,.submit-row > div span { display: block; }
.submit-row > div strong { font-size: 14px; }
.submit-row > div span { margin-top: 4px; color: #98a2b3; font-size: 10px; }
.submit-row > button { min-width: 250px; min-height: 52px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; border: 0; border-radius: 16px; color: #fff; background: #111827; font-size: 13px; font-weight: 900; cursor: pointer; box-shadow: 0 10px 22px rgba(17,24,39,.16); }
.submit-row > button:disabled { color: #98a2b3; background: #e4e7ec; box-shadow: none; cursor: not-allowed; }

@media (max-width: 980px) {
  .planner-main { width: min(100% - 32px, 760px); padding-top: 44px; }
  .hero { grid-template-columns: 1fr; gap: 30px; }
  .hero h1 { font-size: clamp(46px, 10vw, 68px); }
  .hero__preview { max-width: 520px; }
  .planner-workspace { grid-template-columns: 1fr; }
  .brief-card { position: static; }
}
@media (max-width: 680px) {
  .planner-main { width: min(100% - 24px, 520px); padding: 38px 0 92px; }
  .hero { margin-bottom: 34px; }
  .hero h1 { margin-top: 18px; font-size: 46px; }
  .hero__copy > p { font-size: 14px; }
  .hero__preview { padding: 20px; border-radius: 22px; }
  .planner-workspace { gap: 16px; }
  .brief-card { display: none; }
  .form-card { border-radius: 22px; }
  .form-card__head,.form-section { padding: 24px 20px; }
  .form-card__status { display: none; }
  .route-fields,.scale-grid { grid-template-columns: 1fr; }
  .swap-cities { margin: -4px auto; transform: rotate(90deg); }
  .date-fields { grid-template-columns: 1fr 108px; }
  .date-fields__arrow { display: none; }
  .stay-options,.interest-grid { grid-template-columns: repeat(3,minmax(0,1fr)); }
  .generation-panel,.error-message { margin-right: 20px; margin-left: 20px; }
  .generation-steps { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .submit-row { align-items: stretch; flex-direction: column; padding: 22px 20px; }
  .submit-row > button { width: 100%; min-width: 0; }
}
@media (max-width: 420px) {
  .hero h1 { font-size: 40px; }
  .hero__capabilities span { padding: 8px 11px; }
  .form-section__title p { display: none; }
  .stay-options { grid-template-columns: 1fr; }
  .interest-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
</style>
