<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">
        {{ label || '选择兴趣偏好' }}
      </label>
      <p v-if="description" class="text-sm text-gray-500 mb-4">
        {{ description }}
      </p>
    </div>
    
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      <button
        v-for="interest in interests"
        :key="interest.id"
        @click="toggleInterest(interest.id)"
        type="button"
        :class="[
          'flex items-center justify-center space-x-2 px-4 py-3 rounded-lg border transition-all duration-300',
          selectedInterests.includes(interest.id)
            ? 'border-blue-500 bg-blue-50 text-blue-700'
            : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50'
        ]"
      >
        <span class="text-lg">{{ interest.icon }}</span>
        <span class="text-sm font-medium">{{ interest.label }}</span>
      </button>
    </div>
    
    <!-- 已选兴趣显示 -->
    <div v-if="selectedInterests.length > 0" class="mt-4">
      <div class="text-sm text-gray-600 mb-2">已选择：</div>
      <div class="flex flex-wrap gap-2">
        <div
          v-for="interestId in selectedInterests"
          :key="interestId"
          class="inline-flex items-center space-x-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm"
        >
          <span>{{ getInterestIcon(interestId) }}</span>
          <span>{{ getInterestLabel(interestId) }}</span>
          <button
            @click="removeInterest(interestId)"
            type="button"
            class="ml-1 text-blue-500 hover:text-blue-700"
          >
            ×
          </button>
        </div>
      </div>
    </div>
    
    <!-- 错误信息 -->
    <div v-if="error" class="mt-2 text-sm text-red-600">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits, computed } from 'vue'

interface Interest {
  id: string
  label: string
  icon: string
}

interface Props {
  modelValue: string[]
  interests: Interest[]
  label?: string
  description?: string
  error?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const selectedInterests = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const toggleInterest = (interestId: string) => {
  const index = selectedInterests.value.indexOf(interestId)
  if (index === -1) {
    selectedInterests.value = [...selectedInterests.value, interestId]
  } else {
    selectedInterests.value = selectedInterests.value.filter(id => id !== interestId)
  }
}

const removeInterest = (interestId: string) => {
  selectedInterests.value = selectedInterests.value.filter(id => id !== interestId)
}

const getInterestIcon = (interestId: string) => {
  const interest = props.interests.find(i => i.id === interestId)
  return interest?.icon || ''
}

const getInterestLabel = (interestId: string) => {
  const interest = props.interests.find(i => i.id === interestId)
  return interest?.label || interestId
}
</script>