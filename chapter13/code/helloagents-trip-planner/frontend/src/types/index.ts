// 类型定义

export interface Location {
  longitude: number
  latitude: number
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  ticket_price?: number
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  name: string
  address?: string
  location?: Location
  description?: string
  estimated_cost?: number
}

export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
}

export interface TripFormData {
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

export type RunStatus = 'pending' | 'running' | 'success' | 'degraded' | 'failed'

// 终态三态：只有成功 / 降级 / 失败可以终结一次运行，pending/running 均非终态
export type TerminalRunStatus = 'success' | 'degraded' | 'failed'

export interface RunAcceptance {
  run_id: string
  status: RunStatus
  message: string
}

export interface RunStatusResponse {
  run_id: string
  status: RunStatus
  request: TripFormData
  warnings: string[]
  result?: TripPlan
  error?: string
  created_at: string
  updated_at: string
}

// run_completed 终态载荷：与后端 _publish_terminal 契约严格一致。
// warnings 必然存在（成功时为空数组）；result 仅 success/degraded 存在、failed 缺失；
// error 仅 failed 存在、其余缺失。
export interface RunCompletedPayload {
  status: TerminalRunStatus
  warnings: string[]
  result?: TripPlan | null
  error?: string | null
}

// 落 sessionStorage 的完整终态信封：run_id + 终态 + warnings + result + error 一次存齐，
// 结果页据此三态如实渲染，不再只存裸 TripPlan。
export interface TripRunResult {
  run_id: string
  status: TerminalRunStatus
  warnings: string[]
  result: TripPlan | null
  error: string | null
}

export interface AttractionPhotoData {
  name: string
  photo_url: string | null
}

// GET /api/poi/photo 顶层契约：photo_url / is_placeholder / warnings 均为顶层字段
export interface AttractionPhotoResponse {
  name: string
  success: boolean
  message: string
  photo_url: string | null
  is_placeholder: boolean
  warnings: string[]
  data: AttractionPhotoData | null
}

export type RunEventType =
  | 'run_started'
  | 'step_started'
  | 'tool_call'
  | 'tool_result'
  | 'validation_error'
  | 'run_completed'

export interface RunEvent {
  run_id: string
  type: RunEventType
  data: Record<string, unknown>
  timestamp: string
}

