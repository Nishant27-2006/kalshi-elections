const BASE = 'http://localhost:8000'

export interface MarketRow {
  ts: number
  series: string
  ticker: string
  event_ticker: string
  yes_bid_c: number
  yes_ask_c: number
  spread_c: number
  oi: number
  v24: number
}

export interface Health {
  ok: boolean
  panel_rows: number
  sweeps: number
  first_ts: number | null
  last_ts: number | null
  panel_path: string
}

export interface EventRow {
  event_ticker: string
  rungs: number
  v24: number
  series: string | null
}

export type Moments = Partial<
  Record<'mean' | 'var' | 'stdev' | 'skew' | 'kurtosis' | 'mass', number>
>

export interface DensityResponse {
  event_ticker: string
  strikes: number[]
  p_ge: number[]
  pdf: [number, number][]
  moments: Moments
  negative_buckets: [number, number][]
  diagnostics?: {
    rungs: number
    wide_books: number
    upward_steps: number
    upward_steps_tight: number
  }
  pending?: string
}

export interface AlphaRow {
  module: string
  name: string
}

export interface BacktestResponse {
  alpha: string
  n_rebalances: number
  mean_ic: number | null
  t_stat: number | null
  ics: { ts: number; ic: number }[]
  pending?: string
  error?: string
}

export interface ProgressModule {
  day: string
  module: string
  fn: string
  done: boolean
}

export interface Progress {
  modules: ProgressModule[]
  complete: number
  total: number
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return (await r.json()) as T
}

export const getHealth = () => get<Health>('/api/health')
export const getProgress = () => get<Progress>('/api/progress')
export const getEvents = () => get<{ count: number; events: EventRow[] }>('/api/events')
export const getAlphas = () => get<{ alphas: AlphaRow[] }>('/api/alphas')

export const getUniverse = (limit = 400) =>
  get<{ count: number; markets: MarketRow[] }>(`/api/universe?limit=${limit}`)

export const getLadder = (ev: string) =>
  get<{ event_ticker: string; rungs: MarketRow[] }>(
    `/api/ladder/${encodeURIComponent(ev)}`,
  )

export const getDensity = (ev: string) =>
  get<DensityResponse>(`/api/density/${encodeURIComponent(ev)}`)

export const getBacktest = (mod: string) =>
  get<BacktestResponse>(`/api/backtest/${encodeURIComponent(mod)}`)

/** Live quotes. Returns a closer; a torn frame is skipped, not fatal. */
export function openQuoteSocket(onRows: (rows: MarketRow[]) => void): () => void {
  const ws = new WebSocket(`${BASE.replace('http', 'ws')}/ws/quotes`)
  ws.onmessage = (e) => {
    try {
      onRows(JSON.parse(e.data as string).markets as MarketRow[])
    } catch {
      /* ignore */
    }
  }
  return () => ws.close()
}
