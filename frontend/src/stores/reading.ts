import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export interface ReadingForm {
  birth_date: string
  birth_time: string
  place: string
  lat?: number
  lon?: number
  tz_str?: string
  gender: '男' | '女'
  relationship: string
  name: string
  lang: 'cn' | 'en'
  time_precision_level: 1 | 2 | 3 | 4
  d60_consent: boolean | null
  modules: string
}

export interface ProgressStep {
  key: string
  label: string
  done: boolean
  active: boolean
}

export const PROGRESS_STEPS: ProgressStep[] = [
  { key: 'calculating', label: '天文坐标计算（Shadbala · Ashtakavarga · 分盘）', done: false, active: false },
  { key: 'formatting',  label: '数据结构化',                                     done: false, active: false },
  { key: 'analyzing',   label: 'AI 深度解读（行星 · 分盘 · 宫位 · 人生）',       done: false, active: false },
  { key: 'pdf',         label: '生成完整 PDF 报告',                              done: false, active: false },
  { key: 'done',        label: '完成',                                           done: false, active: false },
]

export const useReadingStore = defineStore('reading', () => {
  const form = ref<ReadingForm>({
    birth_date: '',
    birth_time: '',
    place: '',
    gender: '男',
    relationship: '单身',
    name: '',
    lang: 'cn',
    time_precision_level: 2,
    d60_consent: null,
    modules: 'core',
  })

  const readingId  = ref<string | null>(null)
  const reportId   = ref<string | null>(null)
  const status     = ref<string>('idle')
  const progress   = ref<number>(0)
  const errorMsg   = ref<string | null>(null)
  const steps      = ref<ProgressStep[]>(PROGRESS_STEPS.map(s => ({ ...s })))

  async function submitReading() {
    const res = await axios.post('/api/readings', form.value)
    readingId.value = res.data.reading_id
    status.value    = 'pending'
    progress.value  = 0
    errorMsg.value  = null
    steps.value     = PROGRESS_STEPS.map(s => ({ ...s }))
    return res.data.reading_id
  }

  function updateFromWs(data: { status: string; progress: number; report_id?: string; error_msg?: string }) {
    status.value   = data.status
    progress.value = data.progress ?? progress.value
    if (data.report_id) reportId.value = data.report_id
    if (data.error_msg) errorMsg.value = data.error_msg

    // 更新步骤状态
    const progressMap: Record<string, number> = {
      pending:     0,
      calculating: 0,
      formatting:  1,
      analyzing:   2,
      pdf:         3,
      done:        4,
      failed:      -1,
    }
    const stepIdx = progressMap[data.status] ?? 0
    steps.value.forEach((s, i) => {
      s.done   = i < stepIdx
      s.active = i === stepIdx
    })
  }

  function reset() {
    readingId.value = null
    reportId.value  = null
    status.value    = 'idle'
    progress.value  = 0
    errorMsg.value  = null
  }

  return { form, readingId, reportId, status, progress, errorMsg, steps, submitReading, updateFromWs, reset }
})
