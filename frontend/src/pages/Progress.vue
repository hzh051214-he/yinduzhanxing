<template>
  <div class="min-h-screen bg-stone-50 flex flex-col items-center justify-center px-6 py-16">

    <!-- 星盘加载动画 -->
    <div class="relative w-40 h-40 mb-10">
      <!-- 外环旋转 -->
      <div class="absolute inset-0 rounded-full border-2 border-amber-200 animate-spin"
           style="animation-duration: 8s;" />
      <!-- 中环反转 -->
      <div class="absolute inset-4 rounded-full border-2 border-stone-300 animate-spin"
           style="animation-duration: 5s; animation-direction: reverse;" />
      <!-- 中心符号 -->
      <div class="absolute inset-0 flex items-center justify-center text-3xl text-amber-600 font-serif">
        ✦
      </div>
    </div>

    <!-- 标题 -->
    <h1 class="font-serif text-2xl text-stone-700 mb-1 text-center">
      {{ titleText }}
    </h1>
    <p class="text-stone-400 text-sm mb-10 text-center">{{ subtitleText }}</p>

    <!-- 进度条 -->
    <div class="w-full max-w-md mb-8">
      <div class="flex justify-between text-xs text-stone-400 mb-1.5">
        <span>{{ store.status === 'done' ? '完成' : '计算中' }}</span>
        <span>{{ store.progress }}%</span>
      </div>
      <div class="h-1.5 rounded-full bg-stone-200 overflow-hidden">
        <div
          class="h-full bg-amber-600 rounded-full transition-all duration-700"
          :style="{ width: store.progress + '%' }"
        />
      </div>
    </div>

    <!-- 步骤列表 -->
    <div class="w-full max-w-md space-y-2.5">
      <div
        v-for="step in store.steps"
        :key="step.key"
        class="flex items-center gap-3 text-sm transition-all duration-300"
        :class="{
          'text-stone-800 font-medium': step.active,
          'text-stone-400':            !step.done && !step.active,
          'text-stone-500':             step.done,
        }"
      >
        <!-- 状态图标 -->
        <span class="w-5 h-5 flex-shrink-0 flex items-center justify-center text-base">
          <span v-if="step.done"   class="text-green-500">✓</span>
          <span v-else-if="step.active" class="animate-spin inline-block text-amber-600">⟳</span>
          <span v-else class="text-stone-300">○</span>
        </span>
        {{ step.label }}
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="store.status === 'failed'"
         class="mt-8 w-full max-w-md rounded-xl bg-red-50 border border-red-200 p-4 text-center">
      <p class="text-red-700 font-medium mb-1">计算失败</p>
      <p class="text-red-500 text-sm mb-3">{{ store.errorMsg || '未知错误，请重试' }}</p>
      <button
        @click="goHome"
        class="text-sm underline text-red-600 hover:text-red-800"
      >返回重新输入</button>
    </div>

    <!-- 完成后提示 -->
    <div v-if="store.status === 'done'"
         class="mt-8 text-center">
      <p class="text-stone-500 text-sm mb-4">报告已生成，正在跳转…</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useReadingStore } from '@/stores/reading'
import { useReadingWebSocket } from '@/composables/useReadingWebSocket'

const route  = useRoute()
const router = useRouter()
const store  = useReadingStore()

const readingId = route.params.readingId as string

const titleText = computed(() => {
  const map: Record<string, string> = {
    pending:     '准备开始…',
    calculating: '天文计算中',
    formatting:  '数据结构化',
    analyzing:   'AI 深度解读中',
    pdf:         '生成 PDF 报告',
    done:        '分析完成 ✓',
    failed:      '计算失败',
  }
  return map[store.status] ?? '处理中…'
})

const subtitleText = computed(() =>
  store.status === 'done'
    ? '全部流程完成，正在打开报告'
    : store.status === 'analyzing'
    ? 'AI 正在逐颗行星深度解读，通常需要 3-6 分钟'
    : '排盘计算通常需要 60-90 秒，请稍候'
)

// 连接 WebSocket
useReadingWebSocket(readingId, (data) => {
  store.updateFromWs(data as { status: string; progress: number; report_id?: string; error_msg?: string })
})

// 轮询保底（WebSocket 失败时兜底）
// 每 4 秒查一次状态，直到完成或失败
import { onUnmounted } from 'vue'
import axios from 'axios'

let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  pollTimer = setInterval(async () => {
    if (['done', 'failed'].includes(store.status)) {
      if (pollTimer) clearInterval(pollTimer)
      return
    }
    try {
      const res = await axios.get(`/api/readings/${readingId}/status`)
      store.updateFromWs(res.data)
    } catch { /* 静默 */ }
  }, 4000)
}

onMounted(() => startPolling())
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

// 完成后自动跳转
watch(() => store.status, (val) => {
  if (val === 'done' && store.reportId) {
    setTimeout(() => router.push(`/report/${store.reportId}`), 800)
  }
})

function goHome() {
  store.reset()
  router.push('/')
}
</script>
