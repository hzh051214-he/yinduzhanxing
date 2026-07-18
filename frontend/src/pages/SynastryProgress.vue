<template>
  <div class="min-h-screen bg-stone-50 flex flex-col items-center justify-center px-6 py-16">
    <div class="relative w-32 h-32 mb-10">
      <div class="absolute inset-0 rounded-full border-2 border-indigo-200 animate-spin" style="animation-duration:8s" />
      <div class="absolute inset-4 rounded-full border-2 border-stone-200 animate-spin" style="animation-duration:5s;animation-direction:reverse" />
      <div class="absolute inset-0 flex items-center justify-center text-3xl">🔮</div>
    </div>

    <h1 class="font-serif text-2xl text-stone-700 mb-2 text-center">{{ titleText }}</h1>
    <p class="text-stone-400 text-sm mb-10 text-center max-w-xs">{{ subtitleText }}</p>

    <div class="w-full max-w-sm mb-10">
      <div class="flex justify-between text-xs text-stone-400 mb-1.5">
        <span>{{ STEP_LABELS[status] ?? '处理中' }}</span>
        <span>{{ progress }}%</span>
      </div>
      <div class="h-1.5 rounded-full bg-stone-200 overflow-hidden">
        <div class="h-full bg-indigo-500 rounded-full transition-all duration-700" :style="{ width: progress + '%' }" />
      </div>
    </div>

    <div v-if="status === 'failed'" class="w-full max-w-sm rounded-xl bg-red-50 border border-red-200 p-4 text-center">
      <p class="text-red-700 font-medium mb-1">分析失败</p>
      <p class="text-red-500 text-sm mb-3">{{ errorMsg || '未知错误，请重试' }}</p>
      <button @click="$router.push('/synastry')" class="text-sm underline text-red-600">返回重新输入</button>
    </div>
    <div v-if="status === 'done'" class="text-stone-500 text-sm">报告已生成，正在跳转…</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route      = useRoute()
const router     = useRouter()
const synastryId = route.params.synastryId as string

const status     = ref('pending')
const progress   = ref(0)
const errorMsg   = ref('')
const isTerminal = ref(false)
const resultData = ref<any>(null)

const STEP_LABELS: Record<string, string> = {
  pending:    '等待开始…',
  calculating:'双盘天文计算',
  analyzing:  'AI 解读中…',
  pdf:        '生成报告',
  done:       '完成 ✓',
  failed:     '失败',
}

const titleText = computed(() => ({
  pending: '准备开始…', calculating: '双盘计算中',
  analyzing: 'AI 正在解读匹配度', pdf: '打包报告中',
  done: '分析完成 ✨', failed: '分析失败',
}[status.value] ?? '处理中…'))

const subtitleText = computed(() =>
  status.value === 'analyzing' ? 'AI 正在对 Ashtakoota 和 Jaimini 结果进行解读，约需 60 秒'
  : status.value === 'calculating' ? '正在分别计算双方星盘，约需 30 秒'
  : '合盘分析通常需要 1-2 分钟'
)

let ws: WebSocket | null = null
let retries = 0

function connect() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${protocol}://${location.host}/api/synastry/${synastryId}/ws`)
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      status.value   = data.status   ?? status.value
      progress.value = data.progress ?? progress.value
      if (data.error_msg) errorMsg.value = data.error_msg
      if (data.report_id) resultData.value = data
      if (['done', 'failed'].includes(data.status)) { isTerminal.value = true; ws?.close() }
    } catch { /* ignore */ }
  }
  ws.onclose = () => {
    if (isTerminal.value || retries >= 5) return
    retries++
    setTimeout(connect, 1500 * retries)
  }
  ws.onerror = () => ws?.close()
}

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  connect()
  pollTimer = setInterval(async () => {
    if (isTerminal.value) { clearInterval(pollTimer!); return }
    try {
      const res = await axios.get(`/api/synastry/${synastryId}/status`)
      status.value   = res.data.status   ?? status.value
      progress.value = res.data.progress ?? progress.value
      if (res.data.error_msg) errorMsg.value = res.data.error_msg
      if (res.data.report_id) resultData.value = res.data
      if (['done', 'failed'].includes(res.data.status)) { isTerminal.value = true; clearInterval(pollTimer!) }
    } catch { /* silent */ }
  }, 4000)
})

onUnmounted(() => { isTerminal.value = true; ws?.close(); if (pollTimer) clearInterval(pollTimer) })

watch(status, (val) => {
  if (val === 'done') {
    setTimeout(() => router.push(`/synastry/${synastryId}/result`), 800)
  }
})
</script>
