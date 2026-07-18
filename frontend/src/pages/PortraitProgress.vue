<template>
  <div class="min-h-screen bg-stone-50 flex flex-col items-center justify-center px-6 py-16">

    <!-- 进度动画 -->
    <div class="relative w-32 h-32 mb-10">
      <div class="absolute inset-0 rounded-full border-2 border-rose-200 animate-spin"
           style="animation-duration: 8s;" />
      <div class="absolute inset-4 rounded-full border-2 border-stone-200 animate-spin"
           style="animation-duration: 5s; animation-direction: reverse;" />
      <div class="absolute inset-0 flex items-center justify-center text-3xl">💫</div>
    </div>

    <h1 class="font-serif text-2xl text-stone-700 mb-2 text-center">{{ titleText }}</h1>
    <p class="text-stone-400 text-sm mb-10 text-center max-w-xs">{{ subtitleText }}</p>

    <!-- 进度条 -->
    <div class="w-full max-w-sm mb-10">
      <div class="flex justify-between text-xs text-stone-400 mb-1.5">
        <span>{{ stepLabel }}</span>
        <span>{{ progress }}%</span>
      </div>
      <div class="h-1.5 rounded-full bg-stone-200 overflow-hidden">
        <div class="h-full bg-rose-500 rounded-full transition-all duration-700"
             :style="{ width: progress + '%' }" />
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-if="status === 'failed'"
         class="w-full max-w-sm rounded-xl bg-red-50 border border-red-200 p-4 text-center">
      <p class="text-red-700 font-medium mb-1">生成失败</p>
      <p class="text-red-500 text-sm mb-3">{{ errorMsg || '未知错误，请重试' }}</p>
      <button @click="$router.push('/portrait')"
        class="text-sm underline text-red-600 hover:text-red-800">返回重新输入</button>
    </div>

    <!-- 完成提示 -->
    <div v-if="status === 'done'" class="text-stone-500 text-sm">
      画像已生成，正在跳转…
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route  = useRoute()
const router = useRouter()
const portraitId = route.params.portraitId as string

const status   = ref('pending')
const progress = ref(0)
const errorMsg = ref('')
const isTerminal = ref(false)

const STEP_LABELS: Record<string, string> = {
  pending:    '等待开始…',
  calculating:'天文计算中',
  analyzing:  'AI 解读气质…',
  generating: 'DALL-E 生成画像…',
  done:       '完成 ✓',
  failed:     '失败',
}

const titleText = computed(() => {
  const map: Record<string, string> = {
    pending:    '准备开始…',
    calculating:'星盘计算中',
    analyzing:  'AI 正在感知你的正缘气质',
    generating: '绘制正缘画像',
    done:       '画像已生成 ✨',
    failed:     '生成失败',
  }
  return map[status.value] ?? '处理中…'
})

const subtitleText = computed(() =>
  status.value === 'generating'
    ? 'DALL-E 3 正在把气质描述转化为图像，约需 20 秒'
    : status.value === 'analyzing'
    ? 'AI 正在逐层解读 7宫结构与 DK 指示星…'
    : '正在计算星盘数据，约需 30-60 秒'
)

const stepLabel = computed(() => STEP_LABELS[status.value] ?? '处理中')

// ── WebSocket ─────────────────────────────────────────────────
let ws: WebSocket | null = null
let retries = 0
const MAX_RETRIES = 5

function connect() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${protocol}://${location.host}/api/portrait/${portraitId}/ws`)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      status.value   = data.status   ?? status.value
      progress.value = data.progress ?? progress.value
      if (data.error_msg) errorMsg.value = data.error_msg
      if (data.status === 'done' || data.status === 'failed') {
        isTerminal.value = true
        ws?.close()
      }
    } catch { /* ignore */ }
  }

  ws.onclose = () => {
    if (isTerminal.value || retries >= MAX_RETRIES) return
    retries++
    setTimeout(connect, 1500 * retries)
  }

  ws.onerror = () => ws?.close()
}

// ── 轮询保底 ──────────────────────────────────────────────────
let pollTimer: ReturnType<typeof setInterval> | null = null

async function poll() {
  if (isTerminal.value) {
    if (pollTimer) clearInterval(pollTimer)
    return
  }
  try {
    const res = await axios.get(`/api/portrait/${portraitId}/status`)
    status.value   = res.data.status   ?? status.value
    progress.value = res.data.progress ?? progress.value
    if (res.data.error_msg) errorMsg.value = res.data.error_msg
    if (res.data.status === 'done' || res.data.status === 'failed') {
      isTerminal.value = true
      if (pollTimer) clearInterval(pollTimer)
    }
  } catch { /* silent */ }
}

onMounted(() => {
  connect()
  pollTimer = setInterval(poll, 4000)
})

onUnmounted(() => {
  isTerminal.value = true
  ws?.close()
  if (pollTimer) clearInterval(pollTimer)
})

// ── 完成后跳转 ────────────────────────────────────────────────
watch(status, (val) => {
  if (val === 'done') {
    setTimeout(() => router.push(`/portrait/${portraitId}/result`), 800)
  }
})
</script>
