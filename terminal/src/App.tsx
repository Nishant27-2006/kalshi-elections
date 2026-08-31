import { useCallback, useEffect, useMemo, useState } from 'react'
import './theme.css'
import {
  getAlphas,
  getBacktest,
  getDensity,
  getEvents,
  getHealth,
  getLadder,
  getProgress,
  getUniverse,
  openQuoteSocket,
} from './api'
import type {
  AlphaRow,
  BacktestResponse,
  DensityResponse,
  EventRow,
  Health,
  MarketRow,
  Progress,
} from './api'
import { BarChart, EmptyChart, LineChart, Panel, Pending, Stat, fmt } from './components'

const TABS = ['Universe', 'Ladder', 'Density', 'Alpha', 'Drill'] as const
type Tab = (typeof TABS)[number]

export default function App() {
  const [tab, setTab] = useState<Tab>('Universe')
  const [health, setHealth] = useState<Health | null>(null)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [markets, setMarkets] = useState<MarketRow[]>([])
  const [events, setEvents] = useState<EventRow[]>([])
  const [sel, setSel] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const refresh = useCallback(() => {
    getHealth().then(setHealth).catch((e) => setErr(String(e)))
    getProgress().then(setProgress).catch(() => {})
    getEvents()
      .then((r) => {
        setEvents(r.events)
        setSel((s) => s ?? (r.events[0]?.event_ticker ?? null))
      })
      .catch(() => {})
    getUniverse(400).then((r) => setMarkets(r.markets)).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
    const close = openQuoteSocket(setMarkets)
    const id = window.setInterval(refresh, 30_000)
    return () => {
      close()
      window.clearInterval(id)
    }
  }, [refresh])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const i = Number(e.key)
      if (i >= 1 && i <= TABS.length) setTab(TABS[i - 1])
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const alive = useMemo(() => {
    if (!health?.last_ts) return false
    return Date.now() / 1000 - health.last_ts < 900
  }, [health])

  return (
    <div className="shell">
      <header className="head">
        <span className="wordmark">Kalshi EQR</span>
        <span className="head-stat">
          Markets<b>{markets.length}</b>
        </span>
        <span className="head-stat">
          Ladders<b>{events.length}</b>
        </span>
        <span className="head-stat">
          Sweeps<b>{health?.sweeps ?? '--'}</b>
        </span>
        <span className="head-stat">
          Rows<b>{health?.panel_rows?.toLocaleString() ?? '--'}</b>
        </span>
        <span className="head-spacer" />
        <span className="head-stat">
          Modules<b>
            {progress ? `${progress.complete}/${progress.total}` : '--'}
          </b>
        </span>
      </header>

      <DrillRail progress={progress} />

      <main className="main">
        <div className="tabs" role="tablist">
          {TABS.map((t, i) => (
            <button
              key={t}
              className="tab"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
            >
              <span className="tab-key">{i + 1}</span>
              {t}
            </button>
          ))}
        </div>

        <div className="pane" role="tabpanel">
          {err ? (
            <Pending
              file="server not reachable"
              note={`The terminal could not reach the research service at localhost:8000. Start it and this panel fills in. (${err})`}
              cmd="python -m uvicorn server.app:app --port 8000"
            />
          ) : tab === 'Universe' ? (
            <UniversePane markets={markets} />
          ) : tab === 'Ladder' ? (
            <LadderPane events={events} sel={sel} onSel={setSel} />
          ) : tab === 'Density' ? (
            <DensityPane events={events} sel={sel} onSel={setSel} />
          ) : tab === 'Alpha' ? (
            <AlphaPane />
          ) : (
            <DrillPane progress={progress} />
          )}
        </div>
      </main>

      <footer className="foot">
        <span className={`pulse ${alive ? '' : 'dead'}`} />
        <span>{alive ? 'Recorder live' : 'Recorder stale'}</span>
        <span>
          Last sweep {health?.last_ts ? new Date(health.last_ts * 1000).toLocaleTimeString() : '--'}
        </span>
        <span className="head-spacer" />
        <span>Press 1-5 to switch panels</span>
      </footer>
    </div>
  )
}

/* ------------------------------------------------------------------ rail */

const RAIL_LABEL: Record<string, string> = {
  'eqr.gbm': 'gbm.py',
  'eqr.surface': 'surface.py',
  'eqr.greeks': 'greeks.py',
  'eqr.density': 'density.py',
  'eqr.universe': 'universe.py',
  'eqr.evaluate': 'evaluate.py',
  'eqr.costs': 'costs.py',
  'eqr.neutralize': 'neutralize.py',
}

function DrillRail({ progress }: { progress: Progress | null }) {
  return (
    <nav className="rail" aria-label="Drill progress">
      <div className="rail-title">Your ladder</div>
      {(progress?.modules ?? []).map((m) => (
        <div key={m.module} className={`rung ${m.done ? 'done' : ''}`}>
          <div className="rung-mark" />
          <div className="rung-body">
            <div className="rung-day">{m.day}</div>
            <div className="rung-mod">{RAIL_LABEL[m.module] ?? m.module}</div>
          </div>
        </div>
      ))}
      {!progress ? <div className="rail-title">waiting for server</div> : null}
    </nav>
  )
}

/* -------------------------------------------------------------- universe */

function UniversePane({ markets }: { markets: MarketRow[] }) {
  return (
    <>
      <div className="pane-head">
        <span className="pane-title">Universe</span>
        <span className="pane-sub">
          combo shards excluded &middot; sorted by 24h volume &middot; live
        </span>
      </div>
      {markets.length === 0 ? (
        <p className="empty">No snapshots recorded yet. The recorder writes every 5 minutes.</p>
      ) : (
        <table className="grid">
          <thead>
            <tr>
              <th className="l">Ticker</th>
              <th className="l">Series</th>
              <th>Bid</th>
              <th>Ask</th>
              <th>Spread</th>
              <th>OI</th>
              <th>24h vol</th>
            </tr>
          </thead>
          <tbody>
            {markets.slice(0, 250).map((m) => (
              <tr key={m.ticker}>
                <td className="l k">{m.ticker}</td>
                <td className="l">{m.series}</td>
                <td>{m.yes_bid_c?.toFixed(0)}</td>
                <td>{m.yes_ask_c?.toFixed(0)}</td>
                <td className={m.spread_c > 5 ? 'neg' : ''}>{m.spread_c?.toFixed(0)}</td>
                <td>{m.oi?.toLocaleString()}</td>
                <td>{m.v24?.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

/* ---------------------------------------------------------------- ladder */

function EventList({
  events,
  sel,
  onSel,
}: {
  events: EventRow[]
  sel: string | null
  onSel: (s: string) => void
}) {
  return (
    <table className="grid">
      <thead>
        <tr>
          <th className="l">Event</th>
          <th>Rungs</th>
          <th>24h vol</th>
        </tr>
      </thead>
      <tbody>
        {events.slice(0, 60).map((e) => (
          <tr
            key={e.event_ticker}
            className={e.event_ticker === sel ? 'sel' : ''}
            onClick={() => onSel(e.event_ticker)}
          >
            <td className="l k">{e.event_ticker}</td>
            <td>{e.rungs}</td>
            <td>{Math.round(e.v24).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function LadderPane({
  events,
  sel,
  onSel,
}: {
  events: EventRow[]
  sel: string | null
  onSel: (s: string) => void
}) {
  const [rungs, setRungs] = useState<MarketRow[]>([])
  useEffect(() => {
    if (!sel) return
    getLadder(sel).then((r) => setRungs(r.rungs)).catch(() => setRungs([]))
  }, [sel])

  const mids = rungs.map((r) => (r.yes_bid_c + r.yes_ask_c) / 200)
  const idx = rungs.map((_, i) => i)

  return (
    <>
      <div className="pane-head">
        <span className="pane-title">Ladder</span>
        <span className="pane-sub">{sel ?? 'select an event'} &middot; each rung quotes P(X &ge; K)</span>
      </div>
      <div className="two-col">
        <EventList events={events} sel={sel} onSel={onSel} />
        <Panel caption="Survival curve — the exchange publishes 1 − CDF for free">
          <LineChart xs={idx} ys={mids} label="rung index vs mid" />
        </Panel>
      </div>
    </>
  )
}

/* --------------------------------------------------------------- density */

function DensityPane({
  events,
  sel,
  onSel,
}: {
  events: EventRow[]
  sel: string | null
  onSel: (s: string) => void
}) {
  const [d, setD] = useState<DensityResponse | null>(null)
  useEffect(() => {
    if (!sel) return
    getDensity(sel).then(setD).catch(() => setD(null))
  }, [sel])

  const pending = d?.pending
  const strikes = d?.pdf.map((p) => p[0]) ?? []
  const mass = d?.pdf.map((p) => p[1]) ?? []

  return (
    <>
      <div className="pane-head">
        <span className="pane-title">Risk-neutral density</span>
        <span className="pane-sub">{sel ?? '--'}</span>
      </div>

      {pending ? (
        <Pending
          file="eqr/density.py"
          note="One first difference of the survival curve gives the density. The ladder is already loaded and waiting — write pdf_from_cdf and this chart draws itself."
          cmd="python -m pytest tests/eqr/test_density.py -v"
        />
      ) : (
        <div className="stat-row">
          <Stat label="Mass captured" value={d?.moments.mass} />
          <Stat label="Mean" value={d?.moments.mean} />
          <Stat label="Std dev" value={d?.moments.stdev} />
          <Stat label="Skew" value={d?.moments.skew} sign />
          <Stat label="Kurtosis" value={d?.moments.kurtosis} />
          <div className="stat">
            <span className="stat-l">Negative buckets</span>
            <span className={`stat-v ${d?.negative_buckets.length ? 'neg' : ''}`}>
              {d?.negative_buckets.length ?? 0}
            </span>
          </div>
        </div>
      )}

      {d?.diagnostics ? (
        <div className="stat-row">
          <div className="stat">
            <span className="stat-l">Rungs</span>
            <span className="stat-v">{d.diagnostics.rungs}</span>
          </div>
          <div className="stat">
            <span className="stat-l">Wide books (&ge;10c)</span>
            <span className={`stat-v ${d.diagnostics.wide_books ? 'neg' : ''}`}>
              {d.diagnostics.wide_books}
            </span>
          </div>
          <div className="stat">
            <span className="stat-l">Upward steps</span>
            <span className={`stat-v ${d.diagnostics.upward_steps ? 'neg' : ''}`}>
              {d.diagnostics.upward_steps}
            </span>
          </div>
          <div className="stat">
            <span className="stat-l">Upward steps, &le;2c only</span>
            <span className={`stat-v ${d.diagnostics.upward_steps_tight ? 'neg' : 'pos'}`}>
              {d.diagnostics.upward_steps_tight}
            </span>
          </div>
        </div>
      ) : null}

      {d?.diagnostics && d.diagnostics.upward_steps > 0 ? (
        <p className="pane-sub" style={{ maxWidth: '80ch', marginBottom: 12 }}>
          A survival curve cannot rise, and this one does. The cause is wide
          one-sided books: a rung at bid 0 / ask 81 has an 81c spread, and its
          mid of 0.405 is the midpoint of a hole, not a probability. Drop to
          tight quotes only and the violations fall to the third figure above.
          Nothing here filters them for you — where a quote stops being a price
          is your call to make and defend.
        </p>
      ) : null}

      <div className="two-col" style={{ marginTop: 12 }}>
        <Panel caption="Survival P(X ≥ K) — recorded, not modelled">
          <LineChart xs={d?.strikes ?? []} ys={d?.p_ge ?? []} label="strike vs P(X ≥ K)" />
        </Panel>
        <Panel caption="Density — violet bars are negative mass, i.e. a violation">
          {pending ? (
            <EmptyChart hint="write pdf_from_cdf" />
          ) : (
            <BarChart xs={strikes} ys={mass} label="strike vs bucket mass" />
          )}
        </Panel>
      </div>

      <div style={{ marginTop: 12 }}>
        <EventList events={events} sel={sel} onSel={onSel} />
      </div>
    </>
  )
}

/* ----------------------------------------------------------------- alpha */

function AlphaPane() {
  const [alphas, setAlphas] = useState<AlphaRow[]>([])
  const [results, setResults] = useState<Record<string, BacktestResponse>>({})

  useEffect(() => {
    getAlphas()
      .then((r) => {
        setAlphas(r.alphas)
        r.alphas.forEach((a) =>
          getBacktest(a.module)
            .then((b) => setResults((s) => ({ ...s, [a.module]: b })))
            .catch(() => {}),
        )
      })
      .catch(() => {})
  }, [])

  const anyPending = alphas.some((a) => results[a.module]?.pending)

  return (
    <>
      <div className="pane-head">
        <span className="pane-title">Alpha</span>
        <span className="pane-sub">rank IC against forward return, 1h horizon</span>
      </div>

      {anyPending ? (
        <Pending
          file="eqr/panel.py, eqr/universe.py, eqr/evaluate.py, eqr/signals/alpha_*.py"
          note="Scoring needs a point-in-time panel, a universe screen, an IC, and a signal. The backtest endpoint is wired and will run the moment those exist — it reports which file it is waiting on rather than inventing a number."
          cmd="python -m pytest tests/eqr -v"
        />
      ) : null}

      <table className="grid" style={{ marginTop: 12 }}>
        <thead>
          <tr>
            <th className="l">Alpha</th>
            <th>Rebalances</th>
            <th>Mean IC</th>
            <th>t-stat</th>
            <th className="l">Status</th>
          </tr>
        </thead>
        <tbody>
          {alphas.map((a) => {
            const r = results[a.module]
            return (
              <tr key={a.module}>
                <td className="l k">{a.name}</td>
                <td>{r?.n_rebalances ?? '--'}</td>
                <td className={r?.mean_ic == null ? '' : r.mean_ic >= 0 ? 'pos' : 'neg'}>
                  {r?.mean_ic == null ? '--' : fmt(r.mean_ic)}
                </td>
                <td>{r?.t_stat == null ? '--' : fmt(r.t_stat, 2)}</td>
                <td className="l">{r?.pending ?? (r ? 'scored' : 'loading')}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </>
  )
}

/* ----------------------------------------------------------------- drill */

function DrillPane({ progress }: { progress: Progress | null }) {
  return (
    <>
      <div className="pane-head">
        <span className="pane-title">Drill</span>
        <span className="pane-sub">
          derive it by hand, then make the tests pass, then defend it
        </span>
      </div>
      <table className="grid">
        <thead>
          <tr>
            <th className="l">Day</th>
            <th className="l">Module</th>
            <th className="l">Gate function</th>
            <th className="l">State</th>
          </tr>
        </thead>
        <tbody>
          {(progress?.modules ?? []).map((m) => (
            <tr key={m.module}>
              <td className="l k">{m.day}</td>
              <td className="l">{RAIL_LABEL[m.module] ?? m.module}</td>
              <td className="l">{m.fn}</td>
              <td className={`l ${m.done ? 'pos' : ''}`}>{m.done ? 'written' : 'yours to write'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
