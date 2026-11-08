import type { ReactNode } from 'react'
import type { DriverPrediction, Prediction } from './api'
import type { Loadable } from './hooks'
import { formatUtc, pct, STAGE_LABEL, teamColour } from './format'

export function SectionTitle({ eyebrow, children }: { eyebrow?: string; children: ReactNode }) {
  return (
    <div className="mb-4">
      {eyebrow && (
        <p className="font-mono text-[0.7rem] tracking-[0.14em] text-muted uppercase">{eyebrow}</p>
      )}
      <h2 className="font-display text-3xl font-bold tracking-tight uppercase">{children}</h2>
    </div>
  )
}

export function Notice({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'error' }) {
  return (
    <div
      className={`rounded-md border border-dashed px-4 py-5 text-sm ${
        tone === 'error' ? 'border-amber text-amber' : 'border-rule text-muted'
      }`}
    >
      {children}
    </div>
  )
}

/** Render loading / missing / error states, or the content when ready. */
export function Load<T>({
  value,
  missing,
  children,
}: {
  value: Loadable<T>
  missing?: ReactNode
  children: (data: T) => ReactNode
}) {
  if (value.state === 'loading') return <p className="font-mono text-sm text-muted">Loading…</p>
  if (value.state === 'missing') return <>{missing ?? <Notice>No data published yet.</Notice>}</>
  if (value.state === 'error')
    return <Notice tone="error">Could not load data ({value.message}). Refresh to retry.</Notice>
  return <>{children(value.data)}</>
}

/** The signature element: the prediction as an issued timing document. */
export function IssueStamp({ prediction }: { prediction: Prediction }) {
  const issued = new Date(prediction.generated_at)
  const start = new Date(prediction.race_start_utc + (prediction.race_start_utc.endsWith('Z') || prediction.race_start_utc.includes('+') ? '' : 'Z'))
  const lead = start.getTime() - issued.getTime()
  const before = lead > 0
  const hours = Math.floor(Math.abs(lead) / 3_600_000)
  return (
    <div className={`stamp inline-block ${before ? 'text-purple' : 'text-amber'}`}>
      <div className="font-semibold">{before ? 'Issued before lights out' : 'Issued after the start'}</div>
      <div>{formatUtc(prediction.generated_at)}</div>
      <div>{before ? `${hours} h before the start` : 'not a valid forecast'}</div>
    </div>
  )
}

function Bar({ value, max, strong, delay }: { value: number; max: number; strong: boolean; delay: number }) {
  const width = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="h-2.5 w-full rounded-sm bg-stripe" aria-hidden>
      <div
        className={`bar h-full rounded-sm ${strong ? 'bg-purple' : 'bg-ink/70'}`}
        style={{ width: `${width}%`, animationDelay: `${delay}ms` }}
      />
    </div>
  )
}

/** Timing-tower style list: position, team stripe, code, name, P(win) bar, P(podium). */
export function TimingTower({ prediction, limit }: { prediction: Prediction; limit?: number }) {
  const rows = prediction.predictions.slice(0, limit)
  const maxWin = Math.max(...prediction.predictions.map((p) => p.p_win))
  const showGrid = prediction.stage === 't2'
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] border-collapse text-sm">
        <caption className="sr-only">
          {prediction.race_name} — {STAGE_LABEL[prediction.stage]}: probability of winning and of a podium per driver
        </caption>
        <thead>
          <tr className="border-b border-ink font-mono text-[0.68rem] tracking-[0.12em] text-muted uppercase">
            <th className="py-2 pr-2 text-left font-medium">Pos</th>
            <th className="py-2 pr-3 text-left font-medium">Driver</th>
            {showGrid && <th className="py-2 pr-3 text-right font-medium">Grid</th>}
            <th className="w-[40%] py-2 pr-3 text-left font-medium">P(win)</th>
            <th className="py-2 text-right font-medium">P(podium)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p: DriverPrediction, i) => (
            <tr key={p.driver_id} className={`border-b border-rule ${i % 2 ? 'bg-stripe/60' : ''}`}>
              <td className="py-2 pr-2 font-mono tabular text-muted">{String(i + 1).padStart(2, '0')}</td>
              <td className="py-2 pr-3">
                <div className="flex items-center gap-2.5">
                  <span className="h-5 w-1 rounded-sm" style={{ background: teamColour(p.constructor_id) }} />
                  <span className={`font-mono font-semibold ${i === 0 ? 'text-purple' : ''}`}>{p.code ?? p.driver_id}</span>
                  <span className="hidden text-muted sm:inline">{p.name}</span>
                </div>
              </td>
              {showGrid && <td className="py-2 pr-3 text-right font-mono tabular">{p.grid ?? '—'}</td>}
              <td className="py-2 pr-3">
                <div className="flex items-center gap-3">
                  <Bar value={p.p_win} max={maxWin} strong={i === 0} delay={i * 35} />
                  <span className={`w-14 text-right font-mono tabular ${i === 0 ? 'font-semibold text-purple' : ''}`}>
                    {pct(p.p_win)}
                  </span>
                </div>
              </td>
              <td className="py-2 text-right font-mono tabular">{pct(p.p_podium, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Check({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="font-mono font-semibold text-green" aria-label="correct">✓</span>
  ) : (
    <span className="font-mono text-muted" aria-label="wrong">✗</span>
  )
}
