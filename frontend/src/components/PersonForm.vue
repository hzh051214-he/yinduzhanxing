<template>
  <div class="space-y-4">
    <!-- 姓名 -->
    <div>
      <label class="block text-sm font-medium text-stone-600 mb-1">姓名（可选）</label>
      <input v-model="form.name" type="text" placeholder="如：李明"
        :class="inputClass" />
    </div>

    <!-- 日期 + 时间 -->
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="block text-sm font-medium text-stone-600 mb-1">出生日期 <span class="text-red-400">*</span></label>
        <input v-model="form.birth_date" type="date" required :class="inputClass" />
      </div>
      <div>
        <label class="block text-sm font-medium text-stone-600 mb-1">出生时间 <span class="text-red-400">*</span></label>
        <input v-model="form.birth_time" type="time" required :class="inputClass" />
      </div>
    </div>

    <!-- 地点 -->
    <div>
      <label class="block text-sm font-medium text-stone-600 mb-1">出生地点 <span class="text-red-400">*</span></label>
      <CitySearch v-model="form.place" @select="onCitySelect" />
    </div>

    <!-- 性别 -->
    <div>
      <label class="block text-sm font-medium text-stone-600 mb-1.5">性别 <span class="text-red-400">*</span></label>
      <div class="flex gap-4">
        <label v-for="g in ['男', '女']" :key="g" class="flex items-center gap-2 cursor-pointer">
          <input v-model="form.gender" type="radio" :value="g"
            :class="`w-4 h-4 accent-${accent}-600`" />
          <span class="text-stone-700 text-sm">{{ g }}</span>
        </label>
      </div>
    </div>

    <!-- 时间精度 -->
    <div>
      <label class="block text-sm font-medium text-stone-600 mb-1">时间精度</label>
      <select v-model="form.time_precision_level"
        class="w-full rounded-lg border border-stone-200 px-3 py-2 text-stone-800 text-sm
               focus:outline-none focus:ring-2 bg-white transition"
        :class="`focus:ring-${accent}-400`">
        <option :value="1">精确到分钟</option>
        <option :value="2">±5 分钟以内</option>
        <option :value="3">±15 分钟或更大</option>
        <option :value="4">不确定</option>
      </select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CitySearch from './CitySearch.vue'

interface PersonForm {
  name: string
  birth_date: string
  birth_time: string
  place: string
  lat?: number
  lon?: number
  tz_str?: string
  gender: '男' | '女'
  time_precision_level: 1 | 2 | 3 | 4
}

const props = defineProps<{
  modelValue: PersonForm
  accent?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: PersonForm): void
}>()

const form = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const accent = computed(() => props.accent || 'amber')

const inputClass = computed(() =>
  `w-full rounded-lg border border-stone-200 px-3 py-2.5 text-stone-800 text-sm placeholder-stone-300
   focus:outline-none focus:ring-2 focus:ring-${accent.value}-400 focus:border-transparent transition`
)

function onCitySelect(city: { lat: number; lon: number; tz_str: string }) {
  emit('update:modelValue', {
    ...props.modelValue,
    lat:    city.lat,
    lon:    city.lon,
    tz_str: city.tz_str,
  })
}
</script>
