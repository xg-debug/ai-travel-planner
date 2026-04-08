<template>
  <div class="space-y-2">
    <label v-if="label" class="block text-sm font-medium text-gray-700">
      <span v-if="required" class="text-red-500">*</span>
      {{ label }}
    </label>
    
    <div class="relative">
      <!-- 图标 -->
      <div v-if="icon" class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
        <component :is="icon" class="w-5 h-5" />
      </div>
      
      <!-- 输入框 -->
      <input
        :value="modelValue"
        @input="onInput"
        :type="type"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :class="[
          'w-full px-4 py-3 bg-white border rounded-lg text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 transition-all duration-300',
          icon ? 'pl-10' : 'pl-4',
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
  type?: string
  placeholder?: string
  required?: boolean
  disabled?: boolean
  error?: string
  helpText?: string
  icon?: any
}

withDefaults(defineProps<Props>(), {
  type: 'text',
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
