import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './theme.css'
import {
  getAlphas,
  getBacktest,
  getDensity,
  getEvents,
  getExchange,
  getHealth,
  getLadder,
  getPerps,
  getProgress,
  getPuts,
  getUniverse,
  openLiveSocket,
} from './api'
import type {
  AlphaRow,
  BacktestResponse,
  DensityResponse,
  EventRow,
  ExchangeStatus,
  Health,
  MarketRow,
  Perp,
  Progress,
  PutsResponse,
} from './api'
import { BarChart, EmptyChart, LineChart, Panel, Pending, fmt } from './components'

const PANELS = [
  { key: 'UNIV', label: 'UNIVERSE' },
  { key: 'PERP', label: 'PERPS' },
  { key: 'LADR', label: 'LADDER' },
  { key: 'DENS', label: 'DENSITY' },
  { key: 'PUTS', label: 'PUTS' },
  { key: 'ALPH', label: 'ALPHA' },
  { key: 'DRIL', label: 'DRILL' },
] as const
type PanelKey = (typeof PANELS)[number]['key']

const num = (x: number | null | undefined, dp = 2): string =>
  x === null || x === undefined || !Number.isFinite(x)
    ? '--'
    : x.toLocaleString(undefined, {
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
      })

const signCls = (x: number | null | undefined): string =>
  x === null || x === undefined || !Number.isFinite(x) ? '' : x >= 0 ? 'up' : 'down'

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

export default function App() {
  const [panel, setPanel] = useState<PanelKey>('UNIV')
  const [health, setHealth] = useState<Health | null>(null)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [exch, setExch] = useState<ExchangeStatus | null>(null)
  const [markets, setMarkets] = useState<MarketRow[]>([])
  const [perps, setPerps] = useState<Perp[]>([])
  const [events, setEvents] = useState<EventRow[]>([])
  const [sel, setSel] = useState<string | null>(null)
  const [cmd, setCmd] = useState('')
  const [clock, setClock] = useState(() => new Date())
  const [connected, setConnected] = useState(false)
  const [down, setDown] = useState<string | null>(null)
  const cmdRef = useRef<HTMLInputElement>(null)

  const slow = useCallback(() => {
    getHealth()
      .then((h) => {
        setHealth(h)
        setDown(null)
      })
      .catch((e) => setDown(String(e)))
    getProgress().then(setProgress).catch(() => {})
    getExchange().then(setExch).catch(() => {})
    getEvents()
      .then((r) => {
        setEvents(r.events)
        setSel((s) => s ?? r.events[0]?.event_ticker ?? null)
      })
      .catch(() => {})
    getUniverse(400).then((r) => setMarkets(r.markets)).catch(() => {})
    getPerps().then((r) => setPerps(r.perps)).catch(() => {})
  }, [])

  useEffect(() => {
    slow()
    const close = openLiveSocket((f) => {
      setConnected(true)
      if (f.perps?.length) setPerps(f.perps)
      if (f.markets?.length) setMarkets(f.markets)
    })
    const slowId = window.setInterval(slow, 30_000)
    const clockId = window.setInterval(() => setClock(new Date()), 1000)
    return () => {
      close()
      window.clearInterval(slowId)
      window.clearInterval(clockId)
    }
  }, [slow])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) {
        if (e.key === 'Escape') e.target.blur()
        return
      }
      if (e.key === '/') {
        e.preventDefault()
        cmdRef.current?.focus()
        return
      }
      const i = Number(e.key)
      if (i >= 1 && i <= PANELS.length) setPanel(PANELS[i - 1].key)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const spot = useMemo(() => {
    const by = Object.fromEntries(perps.map((p) => [p.ticker, p.spot]))
    return { btc: by['KXBTCPERP'] ?? null, eth: by['KXETHPERP'] ?? null }
  }, [perps])

  const recorderFresh = useMemo(
    () => (health?.last_ts ? Date.now() / 1000 - health.last_ts < 900 : false),
    [health],
  )

  const runCommand = () => {
    const q = cmd.trim().toUpperCase()
    if (!q) return
    const hit = events.find((e) => e.event_ticker.toUpperCase().includes(q))
    if (hit) {
      setSel(hit.event_ticker)
      if (panel === 'UNIV' || panel === 'PERP') setPanel('LADR')
    }
    setCmd('')
    cmdRef.current?.blur()
  }

  return (
    <div className="shell">
      <div className="cmdline">
        <span className="cmd-prompt">KALSHI EQR&gt;</span>
        <input
          ref={cmdRef}
          className="cmd-input"
          value={cmd}
          placeholder="type an event ticker, e.g. KXBTCD — press / to focus"
          onChange={(e) => setCmd(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') runCommand()
          }}
          aria-label="Command line"
        />
        <button className="cmd-go" onClick={runCommand}>
          &lt;GO&gt;
        </button>
        <span className="cmd-hint">1-7 panels</span>
      </div>

      <div className="head">
        <div className="hcell">
          <span className="hlabel">EXCH</span>
          {/* Not-yet-known is NOT the same as closed. Printing CLOSED before
              the first response lands would be the terminal asserting
              something it has not been told. */}
          <span
            className={`hval ${
              exch == null ? 'dim' : exch.reachable === false ? 'down'
                : exch.trading_active ? 'up' : 'warn'
            }`}
          >
            {exch == null
              ? '...'
              : exch.reachable === false
                ? 'UNREACHABLE'
                : exch.trading_active
                  ? 'TRADING'
                  : 'CLOSED'}
          </span>
        </div>
        <div className="hcell">
          <span className="hlabel">BTC</span>
          <span className="hval">{spot.btc ? num(spot.btc, 0) : '--'}</span>
        </div>
        <div className="hcell">
          <span className="hlabel">ETH</span>
          <span className="hval">{spot.eth ? num(spot.eth, 2) : '--'}</span>
        </div>
        <div className="hcell">
          <span className="hlabel">PERPS</span>
          <span className="hval">{perps.length}</span>
        </div>
        <div className="hcell">
          <span className="hlabel">MKTS</span>
          <span className="hval">{markets.length}</span>
        </div>
        <div className="hcell">
          <span className="hlabel">LADDERS</span>
          <span className="hval">{events.length}</span>
        </div>
        <div className="hcell">
          <span className="hlabel">ROWS</span>
          <span className="hval">{health?.panel_rows?.toLocaleString() ?? '--'}</span>
        </div>
        <div className="hcell hspacer" />
        <div className="hcell">
          <span className="hlabel">MODULES</span>
          <span className={`hval ${progress?.complete ? 'up' : 'warn'}`}>
            {progress ? `${progress.complete}/${progress.total}` : '--'}
          </span>
        </div>
        <div className="hcell">
          <span className="hval">{clock.toLocaleTimeString([], { hour12: false })}</span>
        </div>
      </div>

      <nav className="rail" aria-label="Drill progress">
        <div className="rail-hd">YOUR LADDER</div>
        {(progress?.modules ?? []).map((m) => (
          <div key={m.module} className={`rung ${m.done ? 'done' : ''}`}>
            <span className="rung-led" />
            <span className="rung-txt">
              <span className="rung-day">{m.day.toUpperCase()}</span>
              <br />
              <span className="rung-mod">{RAIL_LABEL[m.module] ?? m.module}</span>
            </span>
          </div>
        ))}
      </nav>

      <main className="main">
        {down ? (
          <div className="panel-body">
            <Pending
              file="research service unreachable"
              note={`The terminal cannot reach localhost:8000. Start it and every panel fills in. (${down})`}
              cmd="python -m uvicorn server.app:app --port 8000"
            />
          </div>
        ) : panel === 'UNIV' ? (
          <UniversePanel markets={markets} />
        ) : panel === 'PERP' ? (
          <PerpsPanel perps={perps} />
        ) : panel === 'LADR' ? (
          <LadderPanel events={events} sel={sel} onSel={setSel} />
        ) : panel === 'DENS' ? (
          <DensityPanel events={events} sel={sel} onSel={setSel} />
        ) : panel === 'PUTS' ? (
          <PutsPanel events={events} sel={sel} onSel={setSel} />
        ) : panel === 'ALPH' ? (
          <AlphaPanel />
        ) : (
          <DrillPanel progress={progress} />
        )}
      </main>

      <div className="fkeys">
        {PANELS.map((p, i) => (
          <button
            key={p.key}
            className="fkey"
            aria-selected={panel === p.key}
            onClick={() => setPanel(p.key)}
          >
            <span className="fkey-n">F{i + 1}</span>
            {p.label}
          </button>
        ))}
        <div className="fstatus">
          <span className={`led ${connected ? '' : 'stale'}`} />
          <span>{connected ? 'LIVE 2s' : 'RECONNECTING'}</span>
          <span className={`led ${recorderFresh ? '' : 'warn'}`} />
          <span>REC {health?.sweeps ?? '--'}</span>
        </div>
      </div>
    </div>
  )
}

function Head({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="panel-hd">
      <span className="panel-ttl">{title}</span>
      {sub ? <span className="panel-sub">{sub}</span> : null}
    </div>
  )
}

/* -------------------------------------------------------------- universe */

function UniversePanel({ markets }: { markets: MarketRow[] }) {
  return (
    <>
      <Head title="UNIVERSE" sub="combo shards excluded · sorted by 24h volume · live" />
      <div className="panel-body">
        {markets.length === 0 ? (
          <p className="empty">No snapshots yet. The recorder writes every 5 minutes.</p>
        ) : (
          <table className="bb">
            <thead>
              <tr>
                <th className="l">TICKER</th>
                <th className="l">SERIES</th>
                <th>BID</th>
                <th>ASK</th>
                <th>SPRD</th>
                <th>OI</th>
                <th>VOL 24H</th>
              </tr>
            </thead>
            <tbody>
              {markets.slice(0, 250).map((m) => (
                <tr key={m.ticker}>
                  <td className="l key">{m.ticker}</td>
                  <td className="l dim">{m.series}</td>
                  <td>{m.yes_bid_c?.toFixed(0)}</td>
                  <td>{m.yes_ask_c?.toFixed(0)}</td>
                  <td className={m.spread_c >= 10 ? 'down' : ''}>{m.spread_c?.toFixed(0)}</td>
                  <td className="dim">{num(m.oi, 0)}</td>
                  <td>{num(m.v24, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ perps */

function PerpsPanel({ perps }: { perps: Perp[] }) {
  return (
    <>
      <Head
        title="PERPETUAL FUTURES"
        sub="spot = price / contract_size · this is the forward the ladders do not publish"
      />
      <div className="panel-body">
        <table className="bb">
          <thead>
            <tr>
              <th className="l">TICKER</th>
              <th>BID</th>
              <th>ASK</th>
              <th>CSIZE</th>
              <th>SPOT BID</th>
              <th>SPOT ASK</th>
              <th>SPOT MID</th>
              <th>OPEN INT</th>
              <th>VOL 24H</th>
              <th>LEV</th>
            </tr>
          </thead>
          <tbody>
            {perps.map((p) => (
              <tr key={p.ticker}>
                <td className="l key">{p.ticker}</td>
                <td>{num(p.bid, 4)}</td>
                <td>{num(p.ask, 4)}</td>
                <td className="dim">{num(p.contract_size, 4)}</td>
                <td className="dim">{p.spot_bid ? num(p.spot_bid, 2) : '--'}</td>
                <td className="dim">{p.spot_ask ? num(p.spot_ask, 2) : '--'}</td>
                <td className={p.spot ? 'amb' : 'dim'}>
                  {p.spot ? num(p.spot, 2) : 'NO MKT'}
                </td>
                <td className="dim">{num(p.open_interest, 0)}</td>
                <td>{num(p.volume_24h, 0)}</td>
                <td className="dim">{num(p.leverage_estimate, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/* ----------------------------------------------------------------- ladder */

function EventTable({
  events,
  sel,
  onSel,
}: {
  events: EventRow[]
  sel: string | null
  onSel: (s: string) => void
}) {
  return (
    <table className="bb">
      <thead>
        <tr>
          <th className="l">EVENT</th>
          <th>RUNGS</th>
          <th>VOL 24H</th>
        </tr>
      </thead>
      <tbody>
        {events.slice(0, 60).map((e) => (
          <tr
            key={e.event_ticker}
            className={e.event_ticker === sel ? 'sel' : ''}
            onClick={() => onSel(e.event_ticker)}
          >
            <td className="l key">{e.event_ticker}</td>
            <td>{e.rungs}</td>
            <td>{num(e.v24, 0)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function LadderPanel({
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
    getLadder(sel)
      .then((r) => setRungs(r.rungs))
      .catch(() => setRungs([]))
  }, [sel])
  const mids = rungs.map((r) => (r.yes_bid_c + r.yes_ask_c) / 200)
  return (
    <>
      <Head title="LADDER" sub={`${sel ?? 'select an event'} · each rung quotes P(X >= K)`} />
      <div className="panel-body two-col">
        <EventTable events={events} sel={sel} onSel={onSel} />
        <Panel caption="SURVIVAL CURVE — THE EXCHANGE PUBLISHES 1 - CDF FOR FREE">
          <LineChart xs={rungs.map((_, i) => i)} ys={mids} label="rung index vs mid" />
        </Panel>
      </div>
    </>
  )
}

/* ---------------------------------------------------------------- density */

function LadderDiag({ d }: { d?: DensityResponse['diagnostics'] }) {
  if (!d) return null
  return (
    <div className="stats">
      <div className="stat">
        <span className="stat-l">RUNGS</span>
        <span className="stat-v">{d.rungs}</span>
      </div>
      <div className="stat">
        <span className="stat-l">WIDE &ge;10C</span>
        <span className={`stat-v ${d.wide_books ? 'down' : ''}`}>{d.wide_books}</span>
      </div>
      <div className="stat">
        <span className="stat-l">UPWARD STEPS</span>
        <span className={`stat-v ${d.upward_steps ? 'down' : 'up'}`}>{d.upward_steps}</span>
      </div>
      <div className="stat">
        <span className="stat-l">UPWARD &le;2C</span>
        <span className={`stat-v ${d.upward_steps_tight ? 'warn' : 'up'}`}>
          {d.upward_steps_tight}
        </span>
      </div>
    </div>
  )
}

function DensityPanel({
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
  const strikes = d?.pdf.map((p) => p[0]) ?? []
  const mass = d?.pdf.map((p) => p[1]) ?? []
  return (
    <>
      <Head title="RISK-NEUTRAL DENSITY" sub={sel ?? '--'} />
      <div className="panel-body">
        <LadderDiag d={d?.diagnostics} />
        {d?.pending ? (
          <Pending
            file="eqr/density.py"
            note="One first difference of the survival curve gives the density. The ladder is loaded and waiting — write pdf_from_cdf and this chart draws itself."
            cmd="python -m pytest tests/eqr/test_density.py -v"
          />
        ) : (
          <div className="stats">
            <div className="stat">
              <span className="stat-l">MASS</span>
              <span className="stat-v">{fmt(d?.moments.mass ?? NaN)}</span>
            </div>
            <div className="stat">
              <span className="stat-l">MEAN</span>
              <span className="stat-v">{fmt(d?.moments.mean ?? NaN, 2)}</span>
            </div>
            <div className="stat">
              <span className="stat-l">STDEV</span>
              <span className="stat-v">{fmt(d?.moments.stdev ?? NaN, 2)}</span>
            </div>
            <div className="stat">
              <span className="stat-l">SKEW</span>
              <span className={`stat-v ${signCls(d?.moments.skew)}`}>
                {fmt(d?.moments.skew ?? NaN)}
              </span>
            </div>
            <div className="stat">
              <span className="stat-l">NEG BUCKETS</span>
              <span className={`stat-v ${d?.negative_buckets.length ? 'down' : 'up'}`}>
                {d?.negative_buckets.length ?? 0}
              </span>
            </div>
          </div>
        )}
        <div className="two-col" style={{ marginTop: 8 }}>
          <Panel caption="SURVIVAL P(X >= K) — RECORDED, NOT MODELLED">
            <LineChart xs={d?.strikes ?? []} ys={d?.p_ge ?? []} label="strike vs P(X >= K)" />
          </Panel>
          <Panel caption="DENSITY — RED BARS ARE NEGATIVE MASS, I.E. A VIOLATION">
            {d?.pending ? (
              <EmptyChart hint="write pdf_from_cdf" />
            ) : (
              <BarChart xs={strikes} ys={mass} label="strike vs bucket mass" />
            )}
          </Panel>
        </div>
        <div style={{ marginTop: 8 }}>
          <EventTable events={events} sel={sel} onSel={onSel} />
        </div>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------- puts */

function PutsPanel({
  events,
  sel,
  onSel,
}: {
  events: EventRow[]
  sel: string | null
  onSel: (s: string) => void
}) {
  const [p, setP] = useState<PutsResponse | null>(null)
  useEffect(() => {
    if (!sel) return
    getPuts(sel).then(setP).catch(() => setP(null))
  }, [sel])

  const basis =
    p?.forward != null && p?.ladder_mean != null ? p.ladder_mean - p.forward : null

  return (
    <>
      <Head
        title="SYNTHETIC PUTS"
        sub={`${sel ?? '--'} · digital put = the NO leg · vanilla put = E[(K-S)+] from the density`}
      />
      <div className="panel-body">
        <div className="stats">
          <div className="stat">
            <span className="stat-l">PERP FORWARD</span>
            <span className="stat-v amb">{p?.forward ? num(p.forward, 2) : 'NO PERP'}</span>
          </div>
          <div className="stat">
            <span className="stat-l">LADDER MEAN</span>
            <span className="stat-v">
              {p?.ladder_mean != null ? num(p.ladder_mean, 2) : '--'}
            </span>
          </div>
          <div className="stat">
            <span className="stat-l">BASIS (LADDER - PERP)</span>
            <span className={`stat-v ${signCls(basis)}`}>
              {basis != null ? num(basis, 2) : '--'}
            </span>
          </div>
          <div className="stat">
            <span className="stat-l">MASS</span>
            <span className="stat-v">{p?.mass != null ? fmt(p.mass, 3) : '--'}</span>
          </div>
        </div>

        {p?.pending ? (
          <Pending
            file={p.pending}
            note="Puts need the density first, then eqr/puts.py. Three things are called a put here and they are not the same: the digital put is the NO leg you can already buy, the vanilla put is E[(K-S)+] from the density, and the same vanilla put built again by integrating the digital strip. The last two must agree — that is the gate."
            cmd="python -m pytest tests/eqr/test_puts.py -v"
          />
        ) : (
          <table className="bb" style={{ maxWidth: 'none' }}>
            <thead>
              <tr>
                <th>STRIKE</th>
                <th>P(X&ge;K)</th>
                <th>DIGITAL PUT</th>
                <th>VANILLA PUT</th>
                <th>PUT (STRIP)</th>
                <th>GAP</th>
                <th>VANILLA CALL</th>
                <th>PARITY vs PERP</th>
              </tr>
            </thead>
            <tbody>
              {(p?.rows ?? []).map((r) => (
                <tr key={r.strike}>
                  <td className="key">{num(r.strike, 2)}</td>
                  <td className="dim">{fmt(r.p_ge, 3)}</td>
                  <td>{r.digital_put != null ? fmt(r.digital_put, 3) : '--'}</td>
                  <td className="amb">
                    {r.vanilla_put != null ? num(r.vanilla_put, 2) : '--'}
                  </td>
                  <td>{r.put_strip != null ? num(r.put_strip, 2) : '--'}</td>
                  <td className={signCls(r.construction_gap)}>
                    {r.construction_gap != null ? num(r.construction_gap, 3) : '--'}
                  </td>
                  <td>{r.vanilla_call != null ? num(r.vanilla_call, 2) : '--'}</td>
                  <td className={signCls(r.parity_vs_perp)}>
                    {r.parity_vs_perp != null ? num(r.parity_vs_perp, 2) : '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div style={{ marginTop: 8 }}>
          <EventTable events={events} sel={sel} onSel={onSel} />
        </div>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ alpha */

function AlphaPanel() {
  const [alphas, setAlphas] = useState<AlphaRow[]>([])
  const [res, setRes] = useState<Record<string, BacktestResponse>>({})
  useEffect(() => {
    getAlphas()
      .then((r) => {
        setAlphas(r.alphas)
        r.alphas.forEach((a) =>
          getBacktest(a.module)
            .then((b) => setRes((s) => ({ ...s, [a.module]: b })))
            .catch(() => {}),
        )
      })
      .catch(() => {})
  }, [])
  const pending = alphas.some((a) => res[a.module]?.pending)
  return (
    <>
      <Head title="ALPHA" sub="rank IC against forward return, 1h horizon" />
      <div className="panel-body">
        {pending ? (
          <Pending
            file="eqr/panel.py · eqr/universe.py · eqr/evaluate.py · eqr/signals/alpha_*.py"
            note="Scoring needs a point-in-time panel, a universe screen, an IC and a signal. The backtest endpoint is wired and runs the moment those exist — it names the file it waits on rather than inventing a number."
            cmd="python -m pytest tests/eqr -v"
          />
        ) : null}
        <table className="bb" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th className="l">ALPHA</th>
              <th>REBAL</th>
              <th>MEAN IC</th>
              <th>T-STAT</th>
              <th className="l">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {alphas.map((a) => {
              const r = res[a.module]
              return (
                <tr key={a.module}>
                  <td className="l key">{a.name}</td>
                  <td>{r?.n_rebalances ?? '--'}</td>
                  <td className={signCls(r?.mean_ic)}>
                    {r?.mean_ic != null ? fmt(r.mean_ic) : '--'}
                  </td>
                  <td>{r?.t_stat != null ? fmt(r.t_stat, 2) : '--'}</td>
                  <td className="l dim">{r?.pending ?? (r ? 'scored' : 'loading')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ drill */

function DrillPanel({ progress }: { progress: Progress | null }) {
  return (
    <>
      <Head title="DRILL" sub="derive it by hand, make the tests pass, then defend it" />
      <div className="panel-body">
        <table className="bb">
          <thead>
            <tr>
              <th className="l">DAY</th>
              <th className="l">MODULE</th>
              <th className="l">GATE FN</th>
              <th className="l">STATE</th>
            </tr>
          </thead>
          <tbody>
            {(progress?.modules ?? []).map((m) => (
              <tr key={m.module}>
                <td className="l key">{m.day.toUpperCase()}</td>
                <td className="l">{RAIL_LABEL[m.module] ?? m.module}</td>
                <td className="l dim">{m.fn}</td>
                <td className={`l ${m.done ? 'up' : 'warn'}`}>
                  {m.done ? 'WRITTEN' : 'YOURS TO WRITE'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
