<template>
  <div class="relative">
    <input
      v-model="query"
      type="text"
      :placeholder="placeholder"
      autocomplete="off"
      class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800 placeholder-stone-300
             focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent transition"
      @input="onInput"
      @blur="onBlur"
      @keydown.down.prevent="moveDown"
      @keydown.up.prevent="moveUp"
      @keydown.enter.prevent="selectActive"
      @keydown.escape="close"
    />
    <!-- 下拉候选 -->
    <ul
      v-if="open && results.length"
      class="absolute z-20 mt-1 w-full rounded-lg border border-stone-200 bg-white shadow-lg overflow-hidden"
    >
      <li
        v-for="(city, i) in results"
        :key="i"
        class="px-4 py-2.5 text-sm cursor-pointer transition-colors"
        :class="i === activeIdx ? 'bg-amber-50 text-amber-800' : 'text-stone-700 hover:bg-stone-50'"
        @mousedown.prevent="selectCity(city)"
      >
        {{ city.name }}
        <span class="text-xs text-stone-400 ml-1">{{ city.tz_str }}</span>
      </li>
    </ul>
    <!-- 无结果提示 -->
    <p
      v-else-if="open && searched && !results.length"
      class="absolute z-20 mt-1 w-full rounded-lg border border-stone-200 bg-white shadow-lg px-4 py-3
             text-sm text-stone-400"
    >
      未找到"{{ query }}"，请尝试更精确的城市名
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'

interface CityResult {
  name: string
  lat: number
  lon: number
  tz_str: string
}

const props = defineProps<{
  modelValue: string
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
  (e: 'select', city: CityResult): void
}>()

const query     = ref(props.modelValue)
const results   = ref<CityResult[]>([])
const open      = ref(false)
const searched  = ref(false)
const activeIdx = ref(-1)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(() => props.modelValue, (v) => { if (v !== query.value) query.value = v })

function onInput() {
  emit('update:modelValue', query.value)
  searched.value  = false
  activeIdx.value = -1

  if (debounceTimer) clearTimeout(debounceTimer)
  if (!query.value.trim()) { results.value = []; open.value = false; return }

  debounceTimer = setTimeout(async () => {
    try {
      const res = await axios.get('/api/cities/search', { params: { q: query.value } })
      results.value  = res.data.results ?? []
      searched.value = true
      open.value     = true
    } catch { /* 网络错误时静默 */ }
  }, 250)
}

function onBlur() {
  setTimeout(() => { open.value = false }, 150)
}

function close() { open.value = false }

function moveDown() {
  if (!open.value) return
  activeIdx.value = Math.min(activeIdx.value + 1, results.value.length - 1)
}
function moveUp() {
  if (!open.value) return
  activeIdx.value = Math.max(activeIdx.value - 1, 0)
}
function selectActive() {
  if (activeIdx.value >= 0 && results.value[activeIdx.value]) {
    selectCity(results.value[activeIdx.value])
  }
}

function selectCity(city: CityResult) {
  query.value = city.name
  emit('update:modelValue', city.name)
  emit('select', city)
  open.value  = false
}
</script>
