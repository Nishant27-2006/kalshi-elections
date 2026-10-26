import type { ReactNode } from 'react'

/** The unwritten module, rendered as a first-class state rather than an error.
 *  For the next nine days this is the most common thing on screen, so it is
 *  designed rather than apologised for. */
export function Pending({
  file,
  note,
  cmd,
}: {
  file: string
  note: string
  cmd?: string
}) {
  return (
    <div className="pending">
      <span className="pending-tag">Not written yet</span>
      <span className="pending-file">{file}</span>
      <p className="pending-note">{note}</p>
      {cmd ? <code className="pending-cmd">{cmd}</code> : null}
    </div>
  )
}

export function Panel({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="chartbox">
      <div className="chart-cap">{caption}</div>
      {children}
    </div>
  )
}

export function Stat({
  label,
  value,
  sign = false,
}: {
  label: string
  value: number | null | undefined
  sign?: boolean
}) {
  const has = value !== null && value !== undefined && Number.isFinite(value)
  const cls = !has || !sign ? '' : value! >= 0 ? 'up' : 'down'
  return (
    <div className="stat">
      <span className="stat-l">{label}</span>
      <span className={`stat-v ${cls}`}>{has ? fmt(value!) : '--'}</span>
    </div>
  )
}

export function fmt(x: number, dp = 4): string {
  if (!Number.isFinite(x)) return '--'
  if (Math.abs(x) >= 1e6) return x.toExponential(2)
  return x.toFixed(dp)
}

const W = 640
const H = 200
const PAD = { l: 46, r: 10, t: 10, b: 22 }

interface Frame {
  x: (v: number) => number
  y: (v: number) => number
  xs: [number, number]
  ys: [number, number]
}

function frame(xs: number[], ys: number[]): Frame {
  const x0 = Math.min(...xs)
  const x1 = Math.max(...xs)
  const y0 = Math.min(0, ...ys)
  const y1 = Math.max(...ys)
  const sx = x1 === x0 ? 1 : x1 - x0
  const sy = y1 === y0 ? 1 : y1 - y0
  return {
    x: (v) => PAD.l + ((v - x0) / sx) * (W - PAD.l - PAD.r),
    y: (v) => H - PAD.b - ((v - y0) / sy) * (H - PAD.t - PAD.b),
    xs: [x0, x1],
    ys: [y0, y1],
  }
}

function Axes({ f }: { f: Frame }) {
  const yTicks = [f.ys[0], (f.ys[0] + f.ys[1]) / 2, f.ys[1]]
  const xTicks = [f.xs[0], (f.xs[0] + f.xs[1]) / 2, f.xs[1]]
  return (
    <g>
      {yTicks.map((t, i) => (
        <g key={`y${i}`}>
          <line className="gridline" x1={PAD.l} x2={W - PAD.r} y1={f.y(t)} y2={f.y(t)} />
          <text className="tick" x={PAD.l - 6} y={f.y(t) + 3} textAnchor="end">
            {Math.abs(t) < 1 ? t.toFixed(3) : t.toFixed(0)}
          </text>
        </g>
      ))}
      {xTicks.map((t, i) => (
        <text
          key={`x${i}`}
          className="tick"
          x={f.x(t)}
          y={H - 7}
          textAnchor={i === 0 ? 'start' : i === 2 ? 'end' : 'middle'}
        >
          {t >= 1000 ? (t / 1000).toFixed(1) + 'k' : t.toFixed(t < 10 ? 2 : 0)}
        </text>
      ))}
      <line className="axis" x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} />
      <line className="axis" x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={H - PAD.b} />
    </g>
  )
}

/** An empty frame with axes but no series: the chart exists before the data
 *  does, so you can see the shape of what you have not built. */
export function EmptyChart({ hint }: { hint: string }) {
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={hint}>
      <rect
        x={PAD.l}
        y={PAD.t}
        width={W - PAD.l - PAD.r}
        height={H - PAD.t - PAD.b}
        fill="none"
        stroke="#2a2a2a"
      />
      <line className="axis" x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} />
      <line className="axis" x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={H - PAD.b} />
      <text className="tick" x={W / 2} y={H / 2} textAnchor="middle" fill="var(--bb-amber-dim)">
        {hint}
      </text>
    </svg>
  )
}

export function LineChart({ xs, ys, label }: { xs: number[]; ys: number[]; label: string }) {
  if (xs.length < 2) return <EmptyChart hint={label} />
  const f = frame(xs, ys)
  const d = xs.map((x, i) => `${i ? 'L' : 'M'}${f.x(x).toFixed(2)},${f.y(ys[i]).toFixed(2)}`).join(' ')
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <Axes f={f} />
      <path className="series-cdf" d={d} />
    </svg>
  )
}

/** Bars, signed. Negative bars take the red series because a negative
 *  bucket mass is a monotonicity violation, not a small positive number. */
export function BarChart({
  xs,
  ys,
  label,
}: {
  xs: number[]
  ys: number[]
  label: string
}) {
  if (xs.length < 1) return <EmptyChart hint={label} />
  const f = frame(xs, ys)
  const bw = Math.max(1, (W - PAD.l - PAD.r) / Math.max(xs.length, 1) - 1)
  const zero = f.y(0)
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <Axes f={f} />
      {xs.map((x, i) => {
        const v = ys[i]
        const top = v >= 0 ? f.y(v) : zero
        const h = Math.max(0.5, Math.abs(f.y(v) - zero))
        return (
          <rect
            key={i}
            className={v >= 0 ? 'series-pdf' : 'series-neg'}
            x={f.x(x) - bw / 2}
            y={top}
            width={bw}
            height={h}
          />
        )
      })}
    </svg>
  )
}
