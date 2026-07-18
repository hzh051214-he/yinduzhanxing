<template>
  <div class="min-h-screen bg-stone-50">
    <!-- 顶部导航 -->
    <header class="border-b border-stone-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
      <div class="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
        <span class="font-serif text-lg text-stone-700 tracking-wider">✦ 吠陀占星</span>
        <nav class="hidden sm:flex gap-6 text-sm text-stone-500">
          <a href="#about" class="hover:text-stone-800 transition-colors">关于</a>
          <a href="#faq"   class="hover:text-stone-800 transition-colors">常见问题</a>
        </nav>
      </div>
    </header>

    <!-- 英雄区 -->
    <section class="max-w-4xl mx-auto px-6 pt-16 pb-12 text-center">
      <p class="text-xs tracking-[0.25em] uppercase text-amber-700 mb-4">DATA-DRIVEN VEDIC ASTROLOGY</p>
      <h1 class="font-serif text-4xl sm:text-5xl text-stone-800 mb-4 leading-tight">
        数据驱动的<br class="sm:hidden">吠陀占星
      </h1>
      <p class="text-stone-500 text-base sm:text-lg max-w-xl mx-auto leading-relaxed">
        基于 KN Rao 体系 · Swiss Ephemeris 精确计算<br>
        每项结论均有量化行星指标支撑
      </p>
    </section>

    <!-- 表单卡片 -->
    <section class="max-w-2xl mx-auto px-6 pb-20">
      <div class="bg-white rounded-2xl shadow-sm border border-stone-100 p-8">
        <h2 class="font-serif text-xl text-stone-700 mb-6">输入出生信息</h2>

        <form @submit.prevent="handleSubmit" class="space-y-5">

          <!-- 姓名（可选） -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-1.5">姓名（可选，用于报告封面）</label>
            <input
              v-model="store.form.name"
              type="text"
              placeholder="如：李明"
              class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800 placeholder-stone-300
                     focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent transition"
            />
          </div>

          <!-- 出生日期 + 时间 -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-stone-600 mb-1.5">出生日期 <span class="text-red-400">*</span></label>
              <input
                v-model="store.form.birth_date"
                type="date"
                required
                class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800
                       focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent transition"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-stone-600 mb-1.5">出生时间 <span class="text-red-400">*</span></label>
              <input
                v-model="store.form.birth_time"
                type="time"
                required
                class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800
                       focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent transition"
              />
            </div>
          </div>

          <!-- 时间精度 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-1.5">
              时间精度
              <span class="ml-1 text-xs text-stone-400 font-normal">（影响 D60 业力盘的可信度）</span>
            </label>
            <select
              v-model="store.form.time_precision_level"
              class="w-full rounded-lg border border-stone-200 px-4 py-2.5 text-stone-800
                     focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent transition bg-white"
            >
              <option :value="1">精确到分钟（来自出生证明 / 医院记录）</option>
              <option :value="2">±5 分钟以内（可靠的家人记忆）</option>
              <option :value="3">±15 分钟或更大误差（大概时间段）</option>
              <option :value="4">不确定（只知道上午 / 下午）</option>
            </select>
          </div>

          <!-- 出生地点 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-1.5">出生地点 <span class="text-red-400">*</span></label>
            <CitySearch v-model="store.form.place" @select="onCitySelect" />
          </div>

          <!-- 性别 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-2">性别 <span class="text-red-400">*</span></label>
            <div class="flex gap-4">
              <label v-for="g in ['男', '女']" :key="g" class="flex items-center gap-2 cursor-pointer">
                <input
                  v-model="store.form.gender"
                  type="radio"
                  :value="g"
                  class="accent-amber-600 w-4 h-4"
                />
                <span class="text-stone-700">{{ g }}</span>
              </label>
            </div>
          </div>

          <!-- D60 知情同意（时间精度 1 或 2 时显示） -->
          <div
            v-if="store.form.time_precision_level <= 2"
            class="rounded-lg bg-amber-50 border border-amber-200 p-4"
          >
            <p class="text-sm text-amber-800 mb-2 font-medium">D60 业力盘（前世业力分析）</p>
            <p class="text-xs text-amber-700 mb-3 leading-relaxed">
              D60 盘揭示灵魂深层模式，对出生时间精度极度敏感（每 0.5° ≈ 1-2 分钟）。
              分析此盘前需要您的知情同意。
            </p>
            <label class="flex items-start gap-2 cursor-pointer">
              <input
                v-model="store.form.d60_consent"
                type="checkbox"
                :true-value="true"
                :false-value="null"
                class="mt-0.5 accent-amber-600 w-4 h-4 flex-shrink-0"
              />
              <span class="text-sm text-amber-800">我了解 D60 的敏感性，同意在报告中包含业力盘分析</span>
            </label>
          </div>

          <!-- 报告语言 -->
          <div>
            <label class="block text-sm font-medium text-stone-600 mb-1.5">报告语言</label>
            <div class="flex gap-4">
              <label v-for="[val, label] in [['cn', '中文'], ['en', 'English']]" :key="val"
                     class="flex items-center gap-2 cursor-pointer">
                <input
                  v-model="store.form.lang"
                  type="radio"
                  :value="val"
                  class="accent-amber-600 w-4 h-4"
                />
                <span class="text-stone-700 text-sm">{{ label }}</span>
              </label>
            </div>
          </div>

          <!-- 提交 -->
          <button
            type="submit"
            :disabled="submitting"
            class="w-full mt-2 py-3 rounded-xl bg-amber-700 hover:bg-amber-800 text-white font-medium
                   transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <span v-if="submitting" class="animate-spin text-lg">⟳</span>
            {{ submitting ? '提交中…' : '开始星盘分析' }}
          </button>
        </form>

        <p v-if="errorMsg" class="mt-4 text-sm text-red-600 text-center">{{ errorMsg }}</p>
      </div>

      <!-- 功能入口 -->
      <div class="mt-4 flex flex-col sm:flex-row gap-3 justify-center">
        <button @click="router.push('/portrait')"
          class="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-rose-200
                 bg-rose-50 text-rose-700 text-sm font-medium hover:bg-rose-100 transition-colors">
          💫 正缘气质画像
        </button>
        <button @click="router.push('/synastry')"
          class="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-indigo-200
                 bg-indigo-50 text-indigo-700 text-sm font-medium hover:bg-indigo-100 transition-colors">
          🔮 合盘分析
        </button>
      </div>
      <p class="mt-1.5 text-xs text-stone-400 text-center">基于吠陀占星引擎 · AI 深度解读</p>
    </section>

    <!-- 特色说明 -->
    <section id="about" class="max-w-4xl mx-auto px-6 pb-20">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div v-for="f in features" :key="f.title"
             class="rounded-xl border border-stone-100 bg-white p-6">
          <div class="text-2xl mb-3">{{ f.icon }}</div>
          <h3 class="font-medium text-stone-700 mb-1">{{ f.title }}</h3>
          <p class="text-sm text-stone-500 leading-relaxed">{{ f.desc }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useReadingStore } from '@/stores/reading'
import CitySearch from '@/components/CitySearch.vue'

const store     = useReadingStore()
const router    = useRouter()
const submitting = ref(false)
const errorMsg   = ref('')

const features = [
  {
    icon: '⚖️',
    title: '盲审机制',
    desc:  '行星审计（P1-P12）在不读取您个人经历的前提下独立推导，结论可独立验证。',
  },
  {
    icon: '📊',
    title: '量化指标',
    desc:  '每项结论有 Shadbala 力量值、SAV 资源分数、D9 兑现率等数据支撑。',
  },
  {
    icon: '🔮',
    title: '三层大运',
    desc:  'Vimsottari × Chara × Narayana 三套系统交叉扫描，锁定高概率时机窗口。',
  },
]

function onCitySelect(city: { lat: number; lon: number; tz_str: string }) {
  store.form.lat    = city.lat
  store.form.lon    = city.lon
  store.form.tz_str = city.tz_str
}

async function handleSubmit() {
  if (!store.form.birth_date || !store.form.birth_time || !store.form.place) {
    errorMsg.value = '请填写出生日期、时间和地点'
    return
  }
  submitting.value = true
  errorMsg.value   = ''
  try {
    const id = await store.submitReading()
    router.push(`/reading/${id}`)
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    errorMsg.value = msg || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
