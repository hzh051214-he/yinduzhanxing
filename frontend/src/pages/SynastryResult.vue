<template>
  <div class="min-h-screen bg-stone-50">
    <header class="border-b border-stone-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <button @click="$router.push('/synastry')" class="text-stone-400 hover:text-stone-700 text-sm flex items-center gap-1">← 重新分析</button>
        <span class="font-serif text-stone-700">
          {{ p1Name && p2Name ? `${p1Name} × ${p2Name}` : '合盘分析' }}
        </span>
        <div class="w-20" />
      </div>
    </header>

    <div v-if="loading" class="flex items-center justify-center min-h-[60vh] text-stone-400">
      <span class="animate-spin text-2xl mr-3">⟳</span> 加载报告中…
    </div>
    <div v-else-if="error" class="flex items-center justify-center min-h-[60vh] text-red-500 text-sm p-8 text-center">{{ error }}</div>

    <main v-else class="max-w-5xl mx-auto px-6 py-8">

      <!-- 总分仪表盘 -->
      <div class="bg-white rounded-2xl border border-stone-100 shadow-sm p-6 mb-6 flex flex-col sm:flex-row items-center gap-6">
        <!-- 环形得分 -->
        <div class="flex-shrink-0 relative w-28 h-28">
          <svg viewBox="0 0 100 100" class="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#e7e5e4" stroke-width="10" />
            <circle cx="50" cy="50" r="40" fill="none"
              :stroke="scoreColor" stroke-width="10"
              stroke-linecap="round"
              :stroke-dasharray="`${scorePercent * 2.51} 251`" />
          </svg>
          <div class="absolute inset-0 flex flex-col items-center justify-center">
            <span class="text-2xl font-bold" :style="{ color: scoreColor }">{{ totalScore }}</span>
            <span class="text-xs text-stone-400">/36</span>
          </div>
        </div>

        <!-- 信息 -->
        <div class="flex-1 text-center sm:text-left">
          <p class="text-xs text-stone-400 mb-1">Ashtakoota 匹配得分</p>
          <p class="text-2xl font-serif text-stone-800 mb-1">{{ grade }}</p>
          <p class="text-sm text-stone-500">{{ gradeDesc }}</p>

          <!-- Dosha 警告 -->
          <div v-if="doshaWarnings.length" class="mt-3 space-y-1">
            <div v-for="w in doshaWarnings" :key="w"
              class="inline-flex items-center gap-1 bg-red-50 border border-red-200 rounded-lg px-3 py-1 text-xs text-red-700 mr-2">
              ⚠️ {{ w }}
            </div>
          </div>
        </div>
      </div>

      <!-- 左右布局：目录 + 报告 -->
      <div class="flex gap-6">
        <!-- 左侧目录 -->
        <aside class="hidden lg:flex flex-col w-48 flex-shrink-0">
          <p class="text-xs font-medium text-stone-400 uppercase tracking-wider mb-2 px-3">目录</p>
          <button v-for="sec in sections" :key="sec.id"
            @click="scrollToSection(sec.id)"
            :class="['text-left text-sm rounded-md px-3 py-1.5 transition-colors truncate w-full mb-0.5',
              activeSection === sec.id ? 'text-indigo-700 bg-indigo-50 font-medium' : 'text-stone-500 hover:text-indigo-700 hover:bg-indigo-50']">
            <span class="text-stone-400 mr-1.5 text-xs">{{ sec.num }}</span>{{ sec.title }}
          </button>
        </aside>

        <!-- 右侧报告 iframe -->
        <div class="flex-1 min-w-0">
          <div v-if="!htmlContent" class="text-stone-400 text-center py-20">报告加载中…</div>
          <iframe v-else ref="iframeRef" :srcdoc="htmlContent" sandbox="allow-same-origin allow-scripts"
            class="w-full border-0 rounded-xl" style="height: 75vh" @load="onIframeLoad" />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route      = useRoute()
const synastryId = route.params.synastryId as string

const loading     = ref(true)
const error       = ref('')
const htmlContent = ref('')
const p1Name      = ref('')
const p2Name      = ref('')
const totalScore  = ref(0)
const grade       = ref('')
const iframeRef   = ref<HTMLIFrameElement | null>(null)
const activeSection = ref('')

interface Section { id: string; num: string; title: string }
const sections = ref<Section[]>([])

// 得分颜色
const scorePercent = computed(() => (totalScore.value / 36) * 100)
const scoreColor = computed(() => {
  const p = scorePercent.value
  if (p >= 75) return '#4f46e5'   // 高分 indigo
  if (p >= 55) return '#d97706'   // 中分 amber
  return '#dc2626'                 // 低分 red
})

const gradeDesc = computed(() => {
  const s = totalScore.value
  if (s >= 28) return '星盘层面高度相容，各维度匹配均衡'
  if (s >= 21) return '整体良好，有小部分需要磨合的地方'
  if (s >= 18) return '基本匹配，关键指标需要关注'
  return '匹配度偏低，需要认真参考 AI 分析'
})

// 从报告中提取 Dosha 警告（简单检测）
const doshaWarnings = ref<string[]>([])

onMounted(async () => {
  try {
    const res = await axios.get(`/api/synastry/${synastryId}/status`)
    if (res.data.status !== 'done') {
      error.value = '报告尚未完成，请返回进度页等待'
      return
    }
    p1Name.value     = res.data.p1_name     || ''
    p2Name.value     = res.data.p2_name     || ''
    totalScore.value = res.data.total_score || 0
    grade.value      = res.data.grade       || ''

    // 加载 HTML 报告
    const htmlRes = await axios.get(`/api/synastry/${synastryId}/html`, { responseType: 'text' })
    htmlContent.value = htmlRes.data

    // 简单检测 Dosha
    const text = htmlRes.data
    if (/Naadi Dosha|Naadi.*0\s*分/.test(text))  doshaWarnings.value.push('Naadi Dosha')
    if (/Bhakut Dosha|Bhakut.*0\s*分/.test(text)) doshaWarnings.value.push('Bhakut Dosha')
    if (/Gana Dosha|Gana.*0\s*分/.test(text))     doshaWarnings.value.push('Gana Dosha')

  } catch {
    error.value = '加载失败，请刷新重试'
  } finally {
    loading.value = false
  }
})

function onIframeLoad() {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return
  const sectionEls = Array.from(doc.querySelectorAll<HTMLElement>('div.section[id^="sec-"]'))
  sections.value = sectionEls.map((el) => ({
    id:    el.id,
    num:   el.querySelector('.section-number')?.textContent?.replace('Section ', '') ?? '',
    title: el.querySelector('h2')?.textContent?.trim() ?? el.id,
  }))
  iframeRef.value?.contentWindow?.addEventListener('scroll', onIframeScroll, { passive: true })
}

function onIframeScroll() {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return
  const scrollY = iframeRef.value?.contentWindow?.scrollY ?? 0
  let current = ''
  for (const sec of sections.value) {
    const el = doc.getElementById(sec.id)
    if (el && el.offsetTop <= scrollY + 120) current = sec.id
  }
  activeSection.value = current
}

function scrollToSection(id: string) {
  const el = iframeRef.value?.contentDocument?.getElementById(id)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  activeSection.value = id
}

onUnmounted(() => {
  iframeRef.value?.contentWindow?.removeEventListener('scroll', onIframeScroll)
})
</script>
