<template>
  <div class="min-h-screen bg-stone-100 flex flex-col">
    <!-- 顶部工具栏 -->
    <header class="bg-white border-b border-stone-200 px-4 h-14 flex items-center gap-4 sticky top-0 z-10">
      <button
        @click="$router.push('/')"
        class="text-stone-400 hover:text-stone-700 transition-colors text-sm flex items-center gap-1"
      >
        ← 返回
      </button>
      <span class="flex-1 font-serif text-stone-700 truncate">星盘报告</span>
      <button
        @click="downloadPdf"
        :disabled="downloading"
        class="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-amber-700 hover:bg-amber-800
               text-white text-sm font-medium transition-colors disabled:opacity-50"
      >
        <span v-if="downloading" class="animate-spin">⟳</span>
        <span>{{ downloading ? '生成中…' : '⬇ 下载 PDF' }}</span>
      </button>
    </header>

    <div class="flex flex-1 overflow-hidden">
      <!-- 左侧章节导航 -->
      <aside
        v-if="sections.length > 0"
        class="hidden lg:flex flex-col w-56 bg-white border-r border-stone-200 overflow-y-auto p-4 gap-0.5 flex-shrink-0"
      >
        <p class="text-xs font-medium text-stone-400 uppercase tracking-wider mb-2">目录</p>
        <button
          v-for="sec in sections"
          :key="sec.id"
          @click="scrollToSection(sec.id)"
          :class="[
            'text-left text-sm rounded-md px-3 py-1.5 transition-colors truncate w-full',
            activeSection === sec.id
              ? 'text-amber-700 bg-amber-50 font-medium'
              : 'text-stone-500 hover:text-amber-700 hover:bg-amber-50'
          ]"
          :title="sec.title"
        >
          <span class="text-stone-400 mr-1.5 text-xs">{{ sec.num }}</span>{{ sec.title }}
        </button>
      </aside>

      <!-- 报告主体 -->
      <main class="flex-1 overflow-hidden flex flex-col">
        <div v-if="loading" class="flex-1 flex items-center justify-center text-stone-400">
          <span class="animate-spin text-2xl mr-3">⟳</span> 加载报告中…
        </div>
        <div v-else-if="error" class="flex-1 flex items-center justify-center text-red-500 text-sm p-8 text-center">
          {{ error }}
        </div>
        <iframe
          v-else
          ref="iframeRef"
          :srcdoc="htmlContent"
          class="flex-1 w-full border-0"
          sandbox="allow-same-origin allow-scripts"
          @load="onIframeLoad"
        />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route     = useRoute()
const reportId  = route.params.reportId as string

const htmlContent   = ref('')
const loading       = ref(true)
const error         = ref('')
const downloading   = ref(false)
const iframeRef     = ref<HTMLIFrameElement | null>(null)
const activeSection = ref('')

interface Section { id: string; num: string; title: string }
const sections = ref<Section[]>([])

// ── 加载报告 HTML ─────────────────────────────────────────────
onMounted(async () => {
  try {
    const res = await axios.get(`/api/reports/${reportId}/html`, { responseType: 'text' })
    htmlContent.value = res.data
  } catch {
    error.value = '报告加载失败，请刷新重试'
  } finally {
    loading.value = false
  }
})

// ── iframe 加载完成，提取目录 & 监听滚动 ──────────────────────
function onIframeLoad() {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return

  // 提取所有带 id="sec-XX" 的 section，构建目录
  const sectionEls = Array.from(doc.querySelectorAll<HTMLElement>('div.section[id^="sec-"]'))
  sections.value = sectionEls.map((el) => {
    const id      = el.id
    const numEl   = el.querySelector('.section-number')
    const titleEl = el.querySelector('h2')
    return {
      id,
      num:   numEl?.textContent?.replace('Section ', '') ?? '',
      title: titleEl?.textContent?.trim() ?? id,
    }
  })

  // 监听 iframe 内滚动，高亮当前章节
  const win = iframeRef.value?.contentWindow
  if (win) {
    win.addEventListener('scroll', onIframeScroll, { passive: true })
  }
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

// ── 点击目录项跳转 ────────────────────────────────────────────
function scrollToSection(id: string) {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return
  const el = doc.getElementById(id)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  activeSection.value = id
}

// ── 卸载时移除滚动监听 ────────────────────────────────────────
onUnmounted(() => {
  const win = iframeRef.value?.contentWindow
  if (win) win.removeEventListener('scroll', onIframeScroll)
})

// ── 下载 PDF ──────────────────────────────────────────────────
async function downloadPdf() {
  downloading.value = true
  try {
    const res = await axios.get(`/api/reports/${reportId}/pdf`, {
      responseType: 'blob',
      timeout: 120000,   // PDF 生成最多等 2 分钟
    })
    const url  = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href     = url
    link.download = 'vedic_astrology_report.pdf'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch (e: any) {
    const msg = e?.response?.data ? await e.response.data.text?.() : ''
    alert('PDF 下载失败：' + (msg || '请稍后重试'))
  } finally {
    downloading.value = false
  }
}
</script>
