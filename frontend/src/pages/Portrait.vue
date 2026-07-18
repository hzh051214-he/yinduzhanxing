<template>
  <div class="min-h-screen bg-stone-50">
    <!-- 顶部导航 -->
    <header class="border-b border-stone-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
      <div class="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
        <button @click="$router.push('/')" class="text-stone-400 hover:text-stone-700 text-sm flex items-center gap-1">
          ← 返回
        </button>
        <span class="font-serif text-lg text-stone-700 tracking-wider">✦ 真爱画像</span>
        <div class="w-16" />
      </div>
    </header>

    <!-- 说明区 -->
    <section class="max-w-2xl mx-auto px-6 pt-12 pb-8 text-center">
      <div class="text-4xl mb-4">💫</div>
      <h1 class="font-serif text-3xl text-stone-800 mb-3">正缘气质画像</h1>
      <p class="text-stone-500 text-sm leading-relaxed max-w-lg mx-auto">
        基于吠陀占星 7宫结构推导正缘的外貌气质倾向，并调用 AI 绘图生成画像。<br>
        <span class="text-amber-700">这是气质方向推断，不是精准长相预测。</span>
      </p>
    </section>

    <!-- 表单 -->
    <section class="max-w-xl mx-auto px-6 pb-20">
      <div class="bg-white rounded-2xl shadow-sm border border-stone-100 p-8">
        <form @submit.prevent="handleSubmit" class="space-y-5">

          <!-- 姓名 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-1.5">姓名（可选）</label>
            <input v-model="form.name" type="text" placeholder="如：李明"
              class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800 placeholder-stone-300
                     focus:outline-none focus:ring-2 focus:ring-amber-400 transition" />
          </div>

          <!-- 出生日期 + 时间 -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-stone-600 mb-1.5">出生日期 <span class="text-red-400">*</span></label>
              <input v-model="form.birth_date" type="date" required
                class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800
                       focus:outline-none focus:ring-2 focus:ring-amber-400 transition" />
            </div>
            <div>
              <label class="block text-sm font-medium text-stone-600 mb-1.5">出生时间 <span class="text-red-400">*</span></label>
              <input v-model="form.birth_time" type="time" required
                class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800
                       focus:outline-none focus:ring-2 focus:ring-amber-400 transition" />
            </div>
          </div>

          <!-- 出生地点 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-1.5">出生地点 <span class="text-red-400">*</span></label>
            <CitySearch v-model="form.place" @select="onCitySelect" />
          </div>

          <!-- 性别 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-2">性别 <span class="text-red-400">*</span></label>
            <div class="flex gap-4">
              <label v-for="g in ['男', '女']" :key="g" class="flex items-center gap-2 cursor-pointer">
                <input v-model="form.gender" type="radio" :value="g" class="accent-amber-600 w-4 h-4" />
                <span class="text-stone-700">{{ g }}</span>
              </label>
            </div>
          </div>

          <!-- 时间精度 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-1.5">时间精度</label>
            <select v-model="form.time_precision_level"
              class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800
                     focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white transition">
              <option :value="1">精确到分钟（出生证明）</option>
              <option :value="2">±5 分钟以内</option>
              <option :value="3">±15 分钟或更大误差</option>
              <option :value="4">不确定</option>
            </select>
          </div>

          <!-- 提交 -->
          <button type="submit" :disabled="submitting"
            class="w-full mt-2 py-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-medium
                   transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
            <span v-if="submitting" class="animate-spin text-lg">⟳</span>
            {{ submitting ? '生成中…' : '✨ 生成真爱画像' }}
          </button>
        </form>

        <p v-if="errorMsg" class="mt-4 text-sm text-red-600 text-center">{{ errorMsg }}</p>
      </div>

      <!-- 说明卡片 -->
      <div class="mt-6 rounded-xl border border-amber-100 bg-amber-50 p-5 text-sm text-amber-800 space-y-1.5">
        <p class="font-medium">📌 关于这个功能</p>
        <p>· 基于吠陀占星 7宫结构、DK（配偶指示星）、D9 Venus 三层推导</p>
        <p>· 需要 OpenAI API Key 才能生成图片，否则只输出文字描述</p>
        <p>· 画像是「感觉方向校准」，不是精准预测</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import CitySearch from '@/components/CitySearch.vue'

const router     = useRouter()
const submitting = ref(false)
const errorMsg   = ref('')

const form = ref({
  name:                '',
  birth_date:          '',
  birth_time:          '',
  place:               '',
  lat:                 undefined as number | undefined,
  lon:                 undefined as number | undefined,
  tz_str:              undefined as string | undefined,
  gender:              '男' as '男' | '女',
  time_precision_level: 2 as 1 | 2 | 3 | 4,
  d60_consent:         null as boolean | null,
})

function onCitySelect(city: { lat: number; lon: number; tz_str: string }) {
  form.value.lat    = city.lat
  form.value.lon    = city.lon
  form.value.tz_str = city.tz_str
}

async function handleSubmit() {
  if (!form.value.birth_date || !form.value.birth_time || !form.value.place) {
    errorMsg.value = '请填写出生日期、时间和地点'
    return
  }
  submitting.value = true
  errorMsg.value   = ''
  try {
    const res = await axios.post('/api/portrait', form.value)
    router.push(`/portrait/${res.data.portrait_id}`)
  } catch (e: any) {
    const msg = e?.response?.data?.detail
    errorMsg.value = msg || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
