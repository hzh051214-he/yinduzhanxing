<template>
  <div class="min-h-screen bg-stone-50">
    <header class="border-b border-stone-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <button @click="$router.push('/')" class="text-stone-400 hover:text-stone-700 text-sm flex items-center gap-1">← 返回</button>
        <span class="font-serif text-lg text-stone-700 tracking-wider">✦ 合盘分析</span>
        <div class="w-16" />
      </div>
    </header>

    <section class="max-w-3xl mx-auto px-6 pt-10 pb-6 text-center">
      <div class="text-4xl mb-3">🔮</div>
      <h1 class="font-serif text-3xl text-stone-800 mb-2">吠陀合盘分析</h1>
      <p class="text-stone-500 text-sm leading-relaxed">
        基于 Ashtakoota 八项匹配 + Jaimini 双盘交叉，满分 36 分<br>
        <span class="text-indigo-600">AI 对结果进行通俗解读，约需 1-2 分钟</span>
      </p>
    </section>

    <section class="max-w-4xl mx-auto px-6 pb-20">
      <form @submit.prevent="handleSubmit">
        <!-- 两栏表单 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <!-- 甲方 -->
          <div class="bg-white rounded-2xl shadow-sm border border-indigo-100 p-6">
            <div class="flex items-center gap-2 mb-5">
              <span class="w-7 h-7 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-medium">甲</span>
              <h2 class="font-serif text-lg text-stone-700">甲方出生信息</h2>
            </div>
            <PersonForm v-model="p1" accent="indigo" />
          </div>

          <!-- 乙方 -->
          <div class="bg-white rounded-2xl shadow-sm border border-rose-100 p-6">
            <div class="flex items-center gap-2 mb-5">
              <span class="w-7 h-7 rounded-full bg-rose-500 text-white text-xs flex items-center justify-center font-medium">乙</span>
              <h2 class="font-serif text-lg text-stone-700">乙方出生信息</h2>
            </div>
            <PersonForm v-model="p2" accent="rose" />
          </div>
        </div>

        <!-- 报告语言 -->
        <div class="bg-white rounded-xl border border-stone-100 px-6 py-4 mb-4 flex items-center gap-6">
          <span class="text-sm font-medium text-stone-600">报告语言</span>
          <label v-for="[val, label] in [['cn','中文'],['en','English']]" :key="val"
                 class="flex items-center gap-2 cursor-pointer">
            <input v-model="lang" type="radio" :value="val" class="accent-indigo-600 w-4 h-4" />
            <span class="text-stone-700 text-sm">{{ label }}</span>
          </label>
        </div>

        <p v-if="errorMsg" class="text-sm text-red-600 text-center mb-3">{{ errorMsg }}</p>

        <button type="submit" :disabled="submitting"
          class="w-full py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-base
                 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
          <span v-if="submitting" class="animate-spin">⟳</span>
          {{ submitting ? '提交中…' : '🔮 开始合盘分析' }}
        </button>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import PersonForm from '@/components/PersonForm.vue'

const router     = useRouter()
const submitting = ref(false)
const errorMsg   = ref('')
const lang       = ref('cn')

const defaultPerson = () => ({
  name: '', birth_date: '', birth_time: '', place: '',
  lat: undefined as number | undefined,
  lon: undefined as number | undefined,
  tz_str: undefined as string | undefined,
  gender: '男' as '男' | '女',
  time_precision_level: 2 as 1 | 2 | 3 | 4,
})

const p1 = ref(defaultPerson())
const p2 = ref(defaultPerson())

async function handleSubmit() {
  if (!p1.value.birth_date || !p1.value.birth_time || !p1.value.place) {
    errorMsg.value = '请填写甲方的出生日期、时间和地点'
    return
  }
  if (!p2.value.birth_date || !p2.value.birth_time || !p2.value.place) {
    errorMsg.value = '请填写乙方的出生日期、时间和地点'
    return
  }
  submitting.value = true
  errorMsg.value   = ''
  try {
    const res = await axios.post('/api/synastry', { p1: p1.value, p2: p2.value, lang: lang.value })
    router.push(`/synastry/${res.data.synastry_id}`)
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
