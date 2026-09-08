<template>
  <div class="space-y-2">
    <label v-if="label" class="block text-sm font-medium text-gray-700">
      <span v-if="required" class="text-red-500">*</span>
      {{ label }}
    </label>
    
    <div class="relative">
      <!-- 日历图标 -->
      <div class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      
      <!-- 日期输入框 -->
      <input
        :value="modelValue"
        @input="onInput"
        type="date"
        :min="minDate"
        :max="maxDate"
        :required="required"
        :disabled="disabled"
        :class="[
          'w-full pl-10 pr-4 py-3 bg-white border rounded-lg text-gray-900 focus:outline-none focus:ring-2 transition-all duration-300',
          error ? 'border-red-300 focus:border-red-500 focus:ring-red-200' : 'border-gray-300 focus:border-blue-500 focus:ring-blue-200',
          disabled ? 'bg-gray-50 cursor-not-allowed' : ''
        ]"
      />
      
      <!-- 错误信息 -->
      <div v-if="error" class="mt-1 text-sm text-red-600">
        {{ error }}
      </div>
      
      <!-- 帮助文本 -->
      <div v-if="helpText" class="mt-1 text-sm text-gray-500">
        {{ helpText }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

interface Props {
  modelValue: string
  label?: string
  minDate?: string
  maxDate?: string
  required?: boolean
  disabled?: boolean
  error?: string
  helpText?: string
}

withDefaults(defineProps<Props>(), {
  required: false,
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const onInput = (event: Event) => {
  const target = event.target as HTMLInputElement | null
  emit('update:modelValue', target?.value ?? '')
}
</script>
