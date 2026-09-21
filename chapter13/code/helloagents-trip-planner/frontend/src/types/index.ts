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

export interface RunAcceptance {
  run_id: string
  status: RunStatus
  message: string
}

export interface RunStatusResponse {
  run_id: string
  status: RunStatus
  request: TripFormData
  result?: TripPlan
  error?: string
  created_at: string
  updated_at: string
}

export interface RunCompletedPayload {
  status: RunStatus
  warnings?: string[]
  error?: string
  result?: TripPlan
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

