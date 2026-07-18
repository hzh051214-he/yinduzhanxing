import { ref, onUnmounted } from 'vue'

/**
 * 管理与排盘进度的 WebSocket 连接。
 * 自动重连、自动断开（任务完成或组件卸载时）。
 */
export function useReadingWebSocket(
  readingId: string,
  onMessage: (data: Record<string, unknown>) => void,
) {
  const ws      = ref<WebSocket | null>(null)
  const retries = ref(0)
  const MAX_RETRIES = 5
  // 任务已终结（done/failed）时不再重连
  const isTerminal = ref(false)

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${location.host}/api/readings/${readingId}/ws`
    ws.value = new WebSocket(url)

    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
        if (data.status === 'done' || data.status === 'failed') {
          isTerminal.value = true   // 标记终结，阻止后续重连
          ws.value?.close()
        }
      } catch {
        // 忽略解析错误
      }
    }

    ws.value.onclose = () => {
      // 任务已终结或已达重试上限时不重连
      if (isTerminal.value || retries.value >= MAX_RETRIES) return
      retries.value++
      setTimeout(connect, 1500 * retries.value)
    }

    ws.value.onerror = () => {
      ws.value?.close()
    }
  }

  function disconnect() {
    isTerminal.value = true   // 阻止重连
    ws.value?.close()
  }

  connect()
  onUnmounted(disconnect)

  return { disconnect }
}
