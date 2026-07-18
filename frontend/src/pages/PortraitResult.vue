<template>
  <div class="min-h-screen bg-stone-50">
    <!-- 顶部 -->
    <header class="border-b border-stone-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <button @click="$router.push('/portrait')" class="text-stone-400 hover:text-stone-700 text-sm flex items-center gap-1">
          ← 重新生成
        </button>
        <span class="font-serif text-lg text-stone-700">✦ 正缘气质画像</span>
        <button @click="copyPrompt"
          class="text-xs px-3 py-1.5 rounded-lg border border-stone-200 text-stone-500 hover:text-stone-800 hover:border-stone-400 transition">
          {{ copied ? '✓ 已复制' : '复制绘图 Prompt' }}
        </button>
      </div>
    </header>

    <!-- 加载中 -->
    <div v-if="loading" class="flex items-center justify-center min-h-[60vh] text-stone-400">
      <span class="animate-spin text-2xl mr-3">⟳</span> 加载中…
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="flex items-center justify-center min-h-[60vh] text-red-500 text-sm">
      {{ error }}
    </div>

    <!-- 正文 -->
    <main v-else class="max-w-5xl mx-auto px-6 py-10">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">

        <!-- 左：图片 -->
        <div class="flex flex-col gap-4">
          <div class="relative rounded-2xl overflow-hidden bg-stone-100 aspect-square shadow-sm">
            <img v-if="imageUrl" :src="imageUrl" alt="正缘画像"
                 class="w-full h-full object-cover" />
            <div v-else class="w-full h-full flex flex-col items-center justify-center text-stone-400 gap-3">
              <span class="text-5xl">🎨</span>
              <p class="text-sm text-center px-6">
                {{ hasOpenAiKey ? '图片生成失败，请查看下方 Prompt 自行生成' : '未配置 OpenAI Key，请复制下方 Prompt 到 DALL-E 或 Midjourney' }}
              </p>
            </div>
          </div>

          <!-- 气质标签 -->
          <div v-if="hintsSummary" class="flex flex-wrap gap-2">
            <span class="px-3 py-1 rounded-full bg-rose-50 text-rose-700 text-xs border border-rose-100">
              7宫主：{{ hintsSummary.l7_sign }}
            </span>
            <span class="px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-xs border border-amber-100">
              气质底色：{{ hintsSummary.base_vibe }}
            </span>
            <span class="px-3 py-1 rounded-full bg-stone-100 text-stone-600 text-xs">
              D9 Venus：{{ hintsSummary.d9_venus_sign }}
            </span>
            <span v-if="hintsSummary.has_overseas"
              class="px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs border border-blue-100">
              🌏 有海外信号
            </span>
          </div>

          <!-- 绘图 Prompt -->
          <div v-if="imagePrompt" class="rounded-xl border border-stone-200 bg-white p-4">
            <p class="text-xs font-medium text-stone-400 mb-2 uppercase tracking-wider">AI 绘图 Prompt</p>
            <p class="text-xs text-stone-600 leading-relaxed break-all font-mono">{{ imagePrompt }}</p>
          </div>

          <!-- 免责声明 -->
          <p class="text-xs text-stone-400 leading-relaxed">
            ⚠️ 以上为气质方向推断，基于吠陀占星 7宫结构。不是精准长相预测，请把它当作「感觉方向校准」来用。
          </p>
        </div>

        <!-- 右：文字描述 -->
        <div class="bg-white rounded-2xl border border-stone-100 shadow-sm p-6 overflow-y-auto max-h-[80vh]">
          <div class="prose prose-stone prose-sm max-w-none" v-html="portraitHtml" />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

// 简单 markdown → html 转换（只处理 ## 标题和换行）
function simpleMarkdown(md: string): string {
  if (!md) return ''
  return md
    .replace(/^## (.+)$/gm, '<h3 class="text-base font-semibold text-stone-700 mt-5 mb-2">$1</h3>')
    .replace(/^### (.+)$/gm, '<h4 class="text-sm font-medium text-stone-600 mt-4 mb-1">$1</h4>')
    .replace(/^- (.+)$/gm, '<li class="text-stone-600 text-sm ml-4">$1</li>')
    .replace(/^> (.+)$/gm, '<blockquote class="border-l-2 border-amber-300 pl-3 text-xs text-stone-500 italic my-2">$1</blockquote>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/---/g, '<hr class="border-stone-100 my-4" />')
    .replace(/\n\n/g, '</p><p class="text-stone-600 text-sm leading-relaxed mb-3">')
    .replace(/^(?!<)(.+)$/gm, '<p class="text-stone-600 text-sm leading-relaxed mb-2">$1</p>')
    // 去掉代码块（Prompt 单独展示）
    .replace(/```[\s\S]*?```/g, '')
}

const route      = useRoute()
const portraitId = route.params.portraitId as string

const loading       = ref(true)
const error         = ref('')
const portraitText  = ref('')
const imagePrompt   = ref('')
const imageUrl      = ref('')
const hintsSummary  = ref<any>(null)
const hasOpenAiKey  = ref(false)
const copied        = ref(false)

const portraitHtml = computed(() => simpleMarkdown(portraitText.value))

onMounted(async () => {
  try {
    const res = await axios.get(`/api/portrait/${portraitId}/status`)
    if (res.data.status !== 'done') {
      error.value = '报告尚未完成，请返回进度页等待'
      return
    }
    portraitText.value = res.data.portrait_text || ''
    imagePrompt.value  = res.data.image_prompt  || ''
    imageUrl.value     = res.data.image_url     || ''

    // 尝试从 portrait_text 里提取 hints_summary（进度页轮询时已存入 result）
    // 或直接从 status 接口获取
    hintsSummary.value = res.data.hints_summary || null

    // 检查是否配置了 OpenAI key（从后端返回的 image_url 是否有值来判断）
    hasOpenAiKey.value = !!res.data.image_url
  } catch {
    error.value = '加载失败，请刷新重试'
  } finally {
    loading.value = false
  }
})

function copyPrompt() {
  if (!imagePrompt.value) return
  navigator.clipboard.writeText(imagePrompt.value).then(() => {
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  })
}
</script>
