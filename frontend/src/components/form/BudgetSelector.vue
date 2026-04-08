<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">
        {{ label || '预算选择' }}
      </label>
      <p v-if="description" class="text-sm text-gray-500 mb-4">
        {{ description }}
      </p>
    </div>
    
    <!-- 预算范围显示 -->
    <div class="mb-6">
      <div class="flex justify-between items-center mb-2">
        <span class="text-sm text-gray-600">预算范围</span>
        <span class="text-lg font-bold text-blue-600">
          ¥{{ formatCurrency(modelValue) }}
        </span>
      </div>
      
      <!-- 滑块 -->
      <input
        type="range"
        :value="modelValue"
        @input="onInput"
        :min="min"
        :max="max"
        :step="step"
        class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-600 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-lg"
      />
      
      <!-- 刻度标签 -->
      <div class="flex justify-between mt-2">
        <span class="text-xs text-gray-500">¥{{ formatCurrency(min) }}</span>
        <span class="text-xs text-gray-500">¥{{ formatCurrency(max) }}</span>
      </div>
    </div>
    
    <!-- 预算级别选项 -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <button
        v-for="level in budgetLevels"
        :key="level.id"
        @click="$emit('update:modelValue', level.value)"
        type="button"
        :class="[
          'flex flex-col items-center justify-center p-4 rounded-lg border transition-all duration-300',
          modelValue >= level.min && modelValue <= level.max
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
        ]"
      >
        <span class="text-lg mb-1">{{ level.icon }}</span>
        <span class="text-sm font-medium text-gray-700 mb-1">{{ level.label }}</span>
        <span class="text-xs text-gray-500">¥{{ formatCurrency(level.min) }} - ¥{{ formatCurrency(level.max) }}</span>
      </button>
    </div>
    
    <!-- 错误信息 -->
    <div v-if="error" class="mt-2 text-sm text-red-600">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits, computed } from 'vue'

interface BudgetLevel {
  id: string
  label: string
  icon: string
  min: number
  max: number
  value: number
}

interface Props {
  modelValue: number
  label?: string
  description?: string
  min?: number
  max?: number
  step?: number
  error?: string
}

withDefaults(defineProps<Props>(), {
  min: 1000,
  max: 20000,
  step: 500
})

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const budgetLevels = computed<BudgetLevel[]>(() => [
  {
    id: 'economy',
    label: '经济型',
    icon: '💰',
    min: 1000,
    max: 3000,
    value: 2000
  },
  {
    id: 'standard',
    label: '标准型',
    icon: '💵',
    min: 3000,
    max: 8000,
    value: 5000
  },
  {
    id: 'luxury',
    label: '豪华型',
    icon: '💎',
    min: 8000,
    max: 20000,
    value: 12000
  }
])

const formatCurrency = (value: number) => {
  return value.toLocaleString('zh-CN')
}

const onInput = (event: Event) => {
  const target = event.target as HTMLInputElement | null
  emit('update:modelValue', Number.parseInt(target?.value || '0', 10))
}
</script>
