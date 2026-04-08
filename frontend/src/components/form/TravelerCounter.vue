<template>
  <div class="space-y-3">
    <label v-if="label" class="block text-sm font-medium text-gray-700">
      {{ label }}
    </label>
    
    <div class="flex items-center justify-between">
      <!-- 减少按钮 -->
      <button
        @click="decrement"
        type="button"
        :disabled="modelValue <= min"
        :class="[
          'w-10 h-10 flex items-center justify-center rounded-full border transition-colors duration-300',
          modelValue <= min
            ? 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
            : 'border-gray-300 bg-white text-gray-700 hover:border-blue-500 hover:text-blue-600 hover:bg-blue-50'
        ]"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
        </svg>
      </button>
      
      <!-- 显示人数 -->
      <div class="text-center">
        <div class="text-3xl font-bold text-gray-900">{{ modelValue }}</div>
        <div class="text-sm text-gray-500 mt-1">人</div>
      </div>
      
      <!-- 增加按钮 -->
      <button
        @click="increment"
        type="button"
        :disabled="modelValue >= max"
        :class="[
          'w-10 h-10 flex items-center justify-center rounded-full border transition-colors duration-300',
          modelValue >= max
            ? 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
            : 'border-gray-300 bg-white text-gray-700 hover:border-blue-500 hover:text-blue-600 hover:bg-blue-50'
        ]"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
      </button>
    </div>
    
    <!-- 人数描述 -->
    <div class="text-center">
      <div class="text-sm text-gray-600">
        <span v-if="modelValue === 1">独自旅行</span>
        <span v-else-if="modelValue === 2">双人旅行</span>
        <span v-else-if="modelValue <= 4">{{ modelValue }}人小团体</span>
        <span v-else>{{ modelValue }}人团体旅行</span>
      </div>
    </div>
    
    <!-- 错误信息 -->
    <div v-if="error" class="mt-2 text-sm text-red-600">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

interface Props {
  modelValue: number
  label?: string
  min?: number
  max?: number
  error?: string
}

const props = withDefaults(defineProps<Props>(), {
  min: 1,
  max: 10
})

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const increment = () => {
  if (props.modelValue < props.max) {
    emit('update:modelValue', props.modelValue + 1)
  }
}

const decrement = () => {
  if (props.modelValue > props.min) {
    emit('update:modelValue', props.modelValue - 1)
  }
}
</script>