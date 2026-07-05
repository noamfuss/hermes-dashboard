const API_BASE = '/api';

export type DailyRow = {
  day: string
  model: string
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  total_tokens: number
  estimated_cost_usd: number
  actual_cost_usd: number
  session_count: number
}

export type Summary = {
  total_sessions: number
  total_input_tokens: number
  total_output_tokens: number
  total_cache_read_tokens: number
  total_cache_write_tokens: number
  total_tokens: number
  total_estimated_cost: number
  total_actual_cost: number
  model_count: number
}

export type SessionRow = {
  id: string
  model: string
  title: string | null
  started_at: number
  ended_at: number | null
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  estimated_cost_usd: number | null
  actual_cost_usd: number | null
  cost_status: string
  cost_source: string
  billing_provider: string | null
  message_count: number | null
  tool_call_count: number | null
  source: string
}

export type SessionsResponse = {
  total: number
  limit: number
  offset: number
  sessions: SessionRow[]
}

export type Filters = {
  days: number
  startDate?: string
  endDate?: string
  model?: string
}

export async function fetchSummary(filters: Filters): Promise<Summary> {
  const params = new URLSearchParams()
  params.set('days', String(filters.days))
  if (filters.startDate) params.set('start_date', filters.startDate)
  if (filters.endDate) params.set('end_date', filters.endDate)
  if (filters.model) params.set('model', filters.model)
  const res = await fetch(`${API_BASE}/stats/summary?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchDaily(filters: Filters): Promise<DailyRow[]> {
  const params = new URLSearchParams()
  params.set('days', String(filters.days))
  if (filters.startDate) params.set('start_date', filters.startDate)
  if (filters.endDate) params.set('end_date', filters.endDate)
  if (filters.model) params.set('model', filters.model)
  const res = await fetch(`${API_BASE}/stats/daily?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchModels(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/stats/models`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchSessions(filters: Filters, limit = 50, offset = 0): Promise<SessionsResponse> {
  const params = new URLSearchParams()
  params.set('days', String(filters.days))
  if (filters.startDate) params.set('start_date', filters.startDate)
  if (filters.endDate) params.set('end_date', filters.endDate)
  if (filters.model) params.set('model', filters.model)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const res = await fetch(`${API_BASE}/stats/sessions?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
