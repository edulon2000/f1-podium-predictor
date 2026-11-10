import { useEffect, useState, type ReactNode } from 'react'
import { Check as CheckIcon, CircleDashed, Flag, Timer, X } from 'lucide'
import type { Prediction, Stage } from '@/api'
import type { Loadable } from '@/hooks'
import { useNow } from '@/hooks'
import { countdownParts, formatUtc, STAGE_LABEL } from '@/format'
import { Morph } from './Morph'
import { track } from '@/analytics'

export function SectionTitle({ eyebrow, children }: { eyebrow?: string; children: ReactNode }) {
  return (
    <div className="mb-5">
      {eyebrow && <p className="label">{eyebrow}</p>}
      <h2 className="wide text-2xl font-extrabold tracking-tight uppercase sm:text-3xl">{children}</h2>
    </div>
  )
}

export function Notice({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'error' }) {
  return (
    <div
      className={`rounded-lg border border-dashed px-4 py-5 text-sm ${
        tone === 'error' ? 'border-earth text-earth' : 'border-dash text-earth'
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
  if (value.state === 'loading') return <p className="label">Loading…</p>
  if (value.state === 'missing') return <>{missing ?? <Notice>No data published yet.</Notice>}</>
  if (value.state === 'error')
    return <Notice tone="error">Could not load data ({value.message}). Refresh the page to retry.</Notice>
  return <>{children(value.data)}</>
}

/** Dashed technical guide with square end nodes (decorative). */
export function GuideLine({ className = '' }: { className?: string }) {
  return (
    <div aria-hidden className={`flex items-center ${className}`}>
      <span className="size-1.5 bg-night" />
      <span className="h-px flex-1 border-t border-dashed border-dash" />
      <span className="size-1.5 bg-night" />
    </div>
  )
}

/** Result mark that resolves from "pending" into ✓ / ✗ when it mounts. */
export function ResultMark({ ok, delay = 0 }: { ok: boolean; delay?: number }) {
  const [settled, setSettled] = useState(false)
  useEffect(() => {
    const id = setTimeout(() => setSettled(true), 200 + delay)
    return () => clearTimeout(id)
  }, [delay])
  return (
    <span className={`inline-flex align-middle ${settled ? (ok ? 'text-teal' : 'text-dash') : 'text-dash'}`}>
      <Morph icon={settled ? (ok ? CheckIcon : X) : CircleDashed} size={16} strokeWidth={2.25} label={ok ? 'correct' : 'wrong'} />
    </span>
  )
}

/** T1 / T2 switch; the icon morphs between a stopwatch (before quali) and a flag (after). */
export function StageToggle({
  stage,
  available,
  onChange,
}: {
  stage: Stage
  available: Stage[]
  onChange: (s: Stage) => void
}) {
  return (
    <div role="tablist" aria-label="Prediction stage" className="inline-flex rounded-full border border-night p-1">
      {(['t1', 't2'] as Stage[]).map((s) => {
        const active = stage === s
        return (
          <button
            key={s}
            role="tab"
            aria-selected={active}
            disabled={!available.includes(s)}
            onClick={() => {
              onChange(s)
              track('stage-toggle', { stage: s })
            }}
            className={`flex items-center gap-2 rounded-full px-3.5 py-1.5 font-mono text-[0.7rem] tracking-[0.08em] uppercase transition-colors duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] disabled:cursor-not-allowed disabled:opacity-35 ${
              active ? 'bg-night text-stone' : 'text-night hover:bg-paper'
            }`}
          >
            {active && <Morph icon={s === 't1' ? Timer : Flag} size={14} />}
            {STAGE_LABEL[s]}
          </button>
        )
      })}
    </div>
  )
}

/**
 * The signature element: a semicircular dial whose sun segments light up in proportion to the
 * favourite's win probability. Empty (all dim) until a prediction is published.
 */
export function ProbabilityDial({
  probability,
  title,
  subtitle,
  detail,
  caption,
}: {
  probability: number | null
  title: string
  subtitle: string
  detail?: string
  caption: string
}) {
  const n = 17
  const lit = probability === null ? 0 : Math.max(1, Math.round(probability * n))
  const cx = 120
  const cy = 118
  return (
    <figure className="rounded-xl bg-sun p-2.5 shadow-[0_18px_40px_-20px_rgba(12,16,24,0.45)]">
      <div className="rounded-lg bg-night px-4 pt-3 pb-4 text-stone">
        <div className="mb-1 flex items-center justify-between">
          <span className="font-mono text-[0.62rem] tracking-[0.14em] text-stone/70 uppercase">Chance to win</span>
          <span className="rounded-full bg-sun px-2 py-0.5 font-mono text-[0.62rem] tracking-[0.1em] text-night uppercase">
            {caption}
          </span>
        </div>
        <svg viewBox="0 0 240 132" className="w-full" role="img" aria-label={probability === null ? 'No prediction yet' : `${Math.round(probability * 100)}% chance to win`}>
          {Array.from({ length: n }, (_, i) => {
            const a = Math.PI - (i / (n - 1)) * Math.PI
            const x = cx + Math.cos(a) * 92
            const y = cy - Math.sin(a) * 92
            const deg = 90 - (a * 180) / Math.PI
            const on = i < lit
            return (
              <rect
                key={i}
                x={x - 6}
                y={y - 15}
                width={12}
                height={30}
                rx={5}
                transform={`rotate(${deg} ${x} ${y})`}
                className={on ? 'seg fill-sun' : 'fill-night-2'}
                style={on ? { animationDelay: `${i * 45}ms` } : undefined}
              />
            )
          })}
          {Array.from({ length: 24 }, (_, i) => {
            const a = Math.PI - (i / 23) * Math.PI
            return <circle key={i} cx={cx + Math.cos(a) * 66} cy={cy - Math.sin(a) * 66} r={1.2} className="fill-stone/30" />
          })}
        </svg>
        <figcaption className="mx-auto -mt-[4.6rem] max-w-[150px] text-center">
          <div className="narrow text-4xl leading-none font-extrabold tracking-tight uppercase">{title}</div>
          <div className="mt-1 truncate font-mono text-[0.62rem] tracking-[0.08em] text-stone/75 uppercase">{subtitle}</div>
          {detail && <div className="narrow mt-0.5 text-xl leading-none font-bold text-sun tabular">{detail}</div>}
        </figcaption>
      </div>
    </figure>
  )
}

/** Big countdown in the instrument style: DD:HH:MM:SS. */
export function Countdown({ iso }: { iso?: string }) {
  const now = useNow()
  if (!iso) return null
  const ms = new Date(iso).getTime() - now
  if (ms <= 0) return <p className="label">Race under way or finished</p>
  const c = countdownParts(ms)
  const parts = [c.days, c.hours, c.minutes, c.seconds].map((v) => String(v).padStart(2, '0'))
  return (
    <div aria-label="Time until lights out">
      <div className="narrow text-5xl leading-none font-extrabold tabular sm:text-6xl">{parts.join(':')}</div>
      <div className="label mt-1">days · hrs · min · sec to lights out</div>
    </div>
  )
}

/** Stamp showing how long before the start a prediction was issued. */
export function IssueStamp({ prediction }: { prediction: Prediction }) {
  const issued = new Date(prediction.generated_at)
  const startIso = prediction.race_start_utc
  const start = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(startIso) ? startIso : `${startIso}Z`)
  const lead = start.getTime() - issued.getTime()
  const before = lead > 0
  return (
    <div
      className={`inline-block -rotate-2 rounded border-2 px-2.5 py-1.5 font-mono text-[0.66rem] leading-tight tracking-[0.08em] uppercase ${
        before ? 'border-night text-night' : 'border-earth text-earth'
      }`}
    >
      <div className="font-semibold">{before ? 'Issued before lights out' : 'Issued after the start'}</div>
      <div>{formatUtc(prediction.generated_at)}</div>
      <div>{before ? `${Math.floor(lead / 3_600_000)} h before the start` : 'not a valid forecast'}</div>
    </div>
  )
}
