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

export interface Perp {
  ticker: string
  title: string | null
  bid: number | null
  ask: number | null
  mid: number | null
  contract_size: number
  spot: number | null
  spot_bid: number | null
  spot_ask: number | null
  open_interest: number | null
  volume_24h: number | null
  leverage_estimate: number | null
  status: string | null
}

export interface ExchangeStatus {
  reachable: boolean
  exchange_active?: boolean
  trading_active?: boolean
  transfers_active?: boolean
  estimated_resume?: string | null
  indices?: { name: string; trading_active: boolean }[]
  error?: string
}

export type Moments = Partial<
  Record<'mean' | 'var' | 'stdev' | 'skew' | 'kurtosis' | 'mass', number>
>

export interface LadderDiagnostics {
  rungs: number
  wide_books: number
  upward_steps: number
  upward_steps_tight: number
}

export interface DensityResponse {
  event_ticker: string
  strikes: number[]
  p_ge: number[]
  pdf: [number, number][]
  moments: Moments
  negative_buckets: [number, number][]
  diagnostics?: LadderDiagnostics
  pending?: string
}

export interface PutRow {
  strike: number
  p_ge: number
  digital_put: number | null
  vanilla_put: number | null
  vanilla_call: number | null
  put_strip: number | null
  parity_vs_perp: number | null
  construction_gap: number | null
}

export interface PutsResponse {
  event_ticker: string
  series: string
  forward: number | null
  ladder_mean: number | null
  mass?: number | null
  diagnostics?: LadderDiagnostics
  rows: PutRow[]
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

export interface LiveFrame {
  perps?: Perp[]
  forwards?: Record<string, number>
  trading_active?: boolean
  exchange_active?: boolean
  markets?: MarketRow[]
  source?: string
  error?: string
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
export const getExchange = () => get<ExchangeStatus>('/api/exchange')

export const getPerps = () =>
  get<{ reachable: boolean; perps: Perp[]; forwards: Record<string, number> }>(
    '/api/perps',
  )

export const getUniverse = (limit = 400) =>
  get<{ count: number; markets: MarketRow[] }>(`/api/universe?limit=${limit}`)

export const getLadder = (ev: string) =>
  get<{ event_ticker: string; rungs: MarketRow[] }>(
    `/api/ladder/${encodeURIComponent(ev)}`,
  )

export const getDensity = (ev: string) =>
  get<DensityResponse>(`/api/density/${encodeURIComponent(ev)}`)

export const getPuts = (ev: string) =>
  get<PutsResponse>(`/api/puts/${encodeURIComponent(ev)}`)

export const getBacktest = (mod: string) =>
  get<BacktestResponse>(`/api/backtest/${encodeURIComponent(mod)}`)

/** Real-time feed. Auto-reconnects; a torn frame is skipped, not fatal. */
export function openLiveSocket(onFrame: (f: LiveFrame) => void): () => void {
  let ws: WebSocket | null = null
  let timer: number | undefined
  let closed = false

  const connect = () => {
    if (closed) return
    ws = new WebSocket(`${BASE.replace('http', 'ws')}/ws/live`)
    ws.onmessage = (e) => {
      try {
        onFrame(JSON.parse(e.data as string) as LiveFrame)
      } catch {
        /* torn frame */
      }
    }
    ws.onclose = () => {
      if (!closed) timer = window.setTimeout(connect, 3000)
    }
    ws.onerror = () => ws?.close()
  }
  connect()

  return () => {
    closed = true
    if (timer) window.clearTimeout(timer)
    ws?.close()
  }
}
