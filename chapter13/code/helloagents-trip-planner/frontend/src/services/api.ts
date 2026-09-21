import axios from 'axios'
import type {
  AttractionPhotoResponse,
  RunAcceptance,
  RunEvent,
  RunEventType,
  RunStatusResponse,
  TripFormData
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    return Promise.reject(error)
  }
)

export async function generateTripPlan(formData: TripFormData): Promise<RunAcceptance> {
  try {
    const response = await apiClient.post<RunAcceptance>('/api/trip/plan', formData)
    return response.data
  } catch (error: unknown) {
    console.error('受理旅行计划失败:', error)
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || error.message || '受理旅行计划失败')
    }
    throw new Error('受理旅行计划失败')
  }
}

export async function getRunStatus(runId: string): Promise<RunStatusResponse> {
  const response = await apiClient.get<RunStatusResponse>(`/api/trip/runs/${encodeURIComponent(runId)}`)
  return response.data
}

export function subscribeRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (event: Event) => void
): () => void {
  const source = new EventSource(
    `${API_BASE_URL}/api/trip/runs/${encodeURIComponent(runId)}/events`
  )
  // 服务端在重连时全量重放历史事件：用不可变信封身份（run_id + timestamp + type）
  // 在同一订阅内去重，避免 replay 重复触发 UI 副作用。
  // 同一工具的多次独立调用因 timestamp 不同而保留，不会被误判为重复。
  const seenEnvelopes = new Set<string>()
  const eventTypes: RunEventType[] = [
    'run_started', 'step_started', 'tool_call', 'tool_result', 'validation_error', 'run_completed'
  ]
  const listeners = eventTypes.map((eventType) => {
    const listener = (event: Event) => {
      try {
        const runEvent = JSON.parse((event as MessageEvent<string>).data) as RunEvent
        const envelopeId = `${runEvent.run_id}:${runEvent.timestamp}:${runEvent.type}`
        if (seenEnvelopes.has(envelopeId)) {
          return
        }
        seenEnvelopes.add(envelopeId)
        onEvent(runEvent)
      } catch (error: unknown) {
        console.error(`解析 ${eventType} SSE 事件失败:`, error)
      }
    }
    source.addEventListener(eventType, listener)
    return { eventType, listener }
  })
  source.onerror = (event) => onError?.(event)
  return () => {
    listeners.forEach(({ eventType, listener }) => {
      source.removeEventListener(eventType, listener)
    })
    source.close()
    // 订阅关闭即重置去重缓存；新的订阅（新 run）持有全新的空缓存
    seenEnvelopes.clear()
  }
}

export async function healthCheck(): Promise<unknown> {
  const response = await apiClient.get('/health')
  return response.data
}

/** 获取景点图片（复用同一 axios 客户端）。后端未命中/失败也返回 HTTP 200，
 *  以顶层 photo_url/is_placeholder/warnings 表达语义，此处只做类型化透传。 */
export async function getAttractionPhoto(name: string): Promise<AttractionPhotoResponse> {
  const response = await apiClient.get<AttractionPhotoResponse>('/api/poi/photo', {
    params: { name }
  })
  return response.data
}

export default apiClient


