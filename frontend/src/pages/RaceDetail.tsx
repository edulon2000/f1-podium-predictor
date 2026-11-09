import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight } from 'lucide'
import type { DriverDetail, Prediction, Race, RaceDetail as Detail, Reason, Stage } from '@/api'
import { GuideLine, Load, Notice, ResultMark, SectionTitle, StageToggle } from '@/components/core'
import { Morph } from '@/components/Morph'
import { PredictionTable } from '@/components/PredictionTable'
import { EXPLAIN, Tip } from '@/components/Tip'
import { useApi } from '@/hooks'
import { formatLocal, ordinal, pct, startedText, surname, teamColour } from '@/format'

const pWin = (d: DriverDetail, s: Stage) => (s === 't1' ? d.t1_p_win : d.t2_p_win) ?? 0
const pPod = (d: DriverDetail, s: Stage) => (s === 't1' ? d.t1_p_podium : d.t2_p_podium) ?? 0
const rankOf = (d: DriverDetail, s: Stage) => (s === 't1' ? d.t1_rank : d.t2_rank) ?? 99
const retired = (d: DriverDetail) => !!d.status && !d.status.startsWith('Finished')

// ---------------------------------------------------------------------------------------------

function WeatherChips({ w }: { w: Detail['weather'] }) {
  if (!w) return null
  const num = (v: unknown) => (typeof v === 'number' ? v : null)
  const rain = w.wet_race ?? w.rainfall_any
  const chips: { text: string; strong?: boolean }[] = []
  if (rain !== undefined && rain !== null) chips.push({ text: rain ? 'Rain during the race' : 'Dry race', strong: !!rain })
  const mm = num(w.actual_rain_mm)
  if (mm !== null && mm > 0) chips.push({ text: `${mm.toFixed(1)} mm of rain` })
  const air = num(w.actual_temp_c) ?? num(w.air_temp_mean)
  if (air !== null) chips.push({ text: `Air ${Math.round(air)}°C` })
  const track = num(w.track_temp_mean)
  if (track !== null) chips.push({ text: `Track ${Math.round(track)}°C` })
  const fc = num(w.fc_d1_rain_mm) ?? num(w.fc_live_rain_mm)
  if (fc !== null) chips.push({ text: `Forecast the day before: ${fc.toFixed(1)} mm` })
  if (!chips.length) return null
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {chips.map((c) => (
        <span
          key={c.text}
          className={`rounded-full px-3 py-1 font-mono text-[0.7rem] tracking-[0.06em] uppercase ${
            c.strong ? 'bg-night text-sun' : 'border border-rule bg-paper'
          }`}
        >
          {c.text}
        </span>
      ))}
      <Tip text="What the weather did during the race (measured), and what the forecast said the day before. Only the forecast is used to predict; the measured weather teaches the model how each driver copes with rain." />
    </div>
  )
}

function Summary({ drivers, stage }: { drivers: DriverDetail[]; stage: Stage }) {
  const fav = [...drivers].sort((a, b) => rankOf(a, stage) - rankOf(b, stage))[0]
  const winner = drivers.find((d) => d.finish === 1)
  const predictedPodium = [...drivers].sort((a, b) => pPod(b, stage) - pPod(a, stage)).slice(0, 3)
  const hits = predictedPodium.filter((d) => d.finish !== null && d.finish <= 3).length
  const cards: { label: string; tip: string; value: string; sub: string; ok?: boolean }[] = [
    { label: 'Our favourite', tip: EXPLAIN.favourite, value: surname(fav?.name, fav?.family_name), sub: `${pct(pWin(fav, stage))} to win · ${fav?.team}`, ok: fav?.driver_id === winner?.driver_id },
    { label: 'Winner', tip: EXPLAIN.winner, value: surname(winner?.name, winner?.family_name), sub: `started ${startedText(winner?.grid).toLowerCase()} · ${winner?.team}` },
    { label: 'Chance we gave the winner', tip: EXPLAIN.chanceGivenToWinner, value: winner ? pct(pWin(winner, stage)) : '—', sub: winner ? `ranked ${ordinal(rankOf(winner, stage))} of ${drivers.length}` : '' },
    { label: 'Podium guessed', tip: EXPLAIN.podiumGuessed, value: `${hits} of 3`, sub: predictedPodium.map((d) => surname(d.name, d.family_name)).join(', ') },
  ]
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="brackets bg-paper/60 p-4">
          <p className="label"><Tip text={c.tip}>{c.label}</Tip></p>
          <p className="narrow mt-1 flex items-center gap-2 text-4xl leading-none font-extrabold uppercase">
            {c.value}
            {c.ok !== undefined && <ResultMark ok={c.ok} />}
          </p>
          <p className="mt-1 text-[12.5px] text-earth">{c.sub}</p>
        </div>
      ))}
    </div>
  )
}

/** Interactive slope chart: left = our forecast (or the grid), right = how they finished. */
function SlopeChart({ drivers, stage }: { drivers: DriverDetail[]; stage: Stage }) {
  const [left, setLeft] = useState<'forecast' | 'grid'>('forecast')
  const [hover, setHover] = useState<string | null>(null)
  const [pinned, setPinned] = useState<string | null>(null)
  const active = hover ?? pinned
  const leftOrder = [...drivers].sort((a, b) =>
    left === 'forecast' ? rankOf(a, stage) - rankOf(b, stage) : (a.grid || 99) - (b.grid || 99),
  )
  const rightOrder = [...drivers].sort((a, b) => (a.finish ?? 99) - (b.finish ?? 99))
  const row = 26
  const top = 34
  const H = top + drivers.length * row + 8
  const W = 680
  const xl = 236
  const xr = W - 236
  const yL = new Map(leftOrder.map((d, i) => [d.driver_id, top + i * row + row / 2]))
  const yR = new Map(rightOrder.map((d, i) => [d.driver_id, top + i * row + row / 2]))
  const winner = rightOrder[0]?.driver_id
  const fav = [...drivers].sort((a, b) => rankOf(a, stage) - rankOf(b, stage))[0]?.driver_id

  const bind = (id: string) => ({
    onMouseEnter: () => setHover(id),
    onMouseLeave: () => setHover(null),
    onClick: () => setPinned((p) => (p === id ? null : id)),
    style: { cursor: 'pointer' },
  })

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Left column" className="inline-flex rounded-full border border-night p-1">
          {(['forecast', 'grid'] as const).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={left === k}
              onClick={() => setLeft(k)}
              className={`rounded-full px-3.5 py-1.5 font-mono text-[0.7rem] tracking-[0.08em] uppercase transition-colors duration-[320ms] ${
                left === k ? 'bg-night text-stone' : 'hover:bg-paper'
              }`}
            >
              {k === 'forecast' ? 'Our forecast' : 'Starting grid'}
            </button>
          ))}
        </div>
        <p className="text-[12.5px] text-earth">Hover or tap a driver to follow their line. Tap again to release.</p>
      </div>
      <div className="overflow-x-auto rounded-xl border border-rule bg-paper/60 p-2">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[560px]" role="img" aria-label="Forecast or grid order on the left, finishing order on the right">
          <text x={xl - 8} y={18} textAnchor="end" className="fill-earth font-mono text-[10px] tracking-widest uppercase">
            {left === 'forecast' ? 'Most likely to win' : 'Starting grid'}
          </text>
          <text x={xr + 8} y={18} className="fill-earth font-mono text-[10px] tracking-widest uppercase">
            How they finished
          </text>
          {drivers.map((d) => {
            const on = active === d.driver_id
            const dim = active !== null && !on
            const isWinner = d.driver_id === winner
            const isFav = d.driver_id === fav
            const stroke = isWinner ? 'var(--color-sun)' : isFav ? 'var(--color-night)' : 'var(--color-dash)'
            return (
              <path
                key={d.driver_id}
                d={`M${xl} ${yL.get(d.driver_id)} C ${W / 2} ${yL.get(d.driver_id)}, ${W / 2} ${yR.get(d.driver_id)}, ${xr} ${yR.get(d.driver_id)}`}
                fill="none"
                stroke={on ? 'var(--color-night)' : stroke}
                strokeWidth={on ? 3 : isWinner || isFav ? 2.4 : 1.2}
                opacity={dim ? 0.12 : 1}
                {...bind(d.driver_id)}
                style={{ cursor: 'pointer', transition: 'opacity 320ms cubic-bezier(.22,1,.36,1), stroke-width 320ms' }}
              />
            )
          })}
          {leftOrder.map((d, i) => {
            const y = yL.get(d.driver_id)!
            const dim = active !== null && active !== d.driver_id
            const meta = left === 'forecast' ? pct(pWin(d, stage)) : startedText(d.grid)
            return (
              <g key={`l-${d.driver_id}`} opacity={dim ? 0.3 : 1} {...bind(d.driver_id)}>
                <rect x={0} y={y - row / 2 + 2} width={xl - 4} height={row - 4} rx={4} className={active === d.driver_id ? 'fill-sun' : 'fill-transparent'} />
                <text x={10} y={y + 4} className="fill-earth font-mono text-[11px]">{String(i + 1).padStart(2, '0')}</text>
                <rect x={34} y={y - 7} width={3} height={14} rx={1} fill={teamColour(d.constructor_id)} />
                <text x={44} y={y + 4} className="fill-night text-[13px] font-semibold">{surname(d.name, d.family_name)}</text>
                <text x={xl - 10} y={y + 4} textAnchor="end" className="fill-earth font-mono text-[11px]">{meta}</text>
              </g>
            )
          })}
          {rightOrder.map((d) => {
            const y = yR.get(d.driver_id)!
            const dim = active !== null && active !== d.driver_id
            return (
              <g key={`r-${d.driver_id}`} opacity={dim ? 0.3 : 1} {...bind(d.driver_id)}>
                <rect x={xr + 4} y={y - row / 2 + 2} width={W - xr - 4} height={row - 4} rx={4} className={active === d.driver_id ? 'fill-sun' : 'fill-transparent'} />
                <text x={xr + 12} y={y + 4} className="fill-night font-mono text-[11px] font-semibold">
                  {d.finish ? ordinal(d.finish) : '—'}
                </text>
                <text x={xr + 52} y={y + 4} className="fill-night text-[13px]">{surname(d.name, d.family_name)}</text>
                {retired(d) && (
                  <text x={W - 8} y={y + 4} textAnchor="end" className="fill-earth font-mono text-[10px] uppercase">
                    {d.status?.startsWith('Retired') ? 'retired' : d.status?.toLowerCase()}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap gap-4 text-[12px] text-earth">
        <span className="inline-flex items-center gap-1.5"><span className="h-1 w-5 rounded bg-sun" /> winner</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-1 w-5 rounded bg-night" /> our favourite</span>
      </div>
    </div>
  )
}

function ReasonBars({ title, reasons, scale }: { title: string; reasons: Reason[]; scale: number }) {
  return (
    <div>
      <p className="wide mb-3 text-base font-extrabold uppercase">{title}</p>
      <ul className="space-y-2.5">
        {reasons.map((r, i) => {
          const w = Math.min(100, (Math.abs(r.effect) / scale) * 100)
          const up = r.effect > 0
          return (
            <li key={r.feature}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>{r.label}</span>
                <span className={`font-mono text-[11px] uppercase ${up ? 'text-night' : 'text-earth'}`}>
                  {up ? 'raised the chance' : 'lowered the chance'}
                </span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-paper">
                <div
                  className={`bar h-full rounded-full ${up ? 'bg-night' : 'bg-sand'}`}
                  style={{ width: `${w}%`, animationDelay: `${i * 60}ms` }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Reasons({ detail, stage }: { detail: Detail; stage: Stage }) {
  const s = detail.stages[stage]
  if (!s) return null
  const by = new Map(detail.drivers.map((d) => [d.driver_id, d]))
  const fav = by.get(s.favourite)
  const winner = detail.drivers.find((d) => d.finish === 1)
  const all = [...s.favourite_reasons, ...(s.winner_reasons ?? [])]
  const scale = Math.max(...all.map((r) => Math.abs(r.effect)), 0.01)
  return (
    <div className="grid gap-10 md:grid-cols-2">
      <ReasonBars title={`Why the model backed ${surname(fav?.name, fav?.family_name)}`} reasons={s.favourite_reasons} scale={scale} />
      {s.winner_reasons && winner ? (
        <ReasonBars title={`What it saw in the winner, ${surname(winner.name, winner.family_name)}`} reasons={s.winner_reasons} scale={scale} />
      ) : (
        <Notice>The favourite won, so the reasons on the left are also the winner’s.</Notice>
      )}
    </div>
  )
}

function ForecastShift({ drivers }: { drivers: DriverDetail[] }) {
  const rows = [...drivers].sort((a, b) => (b.t2_p_win ?? 0) - (a.t2_p_win ?? 0)).slice(0, 8)
  const max = Math.max(...rows.flatMap((d) => [d.t1_p_win ?? 0, d.t2_p_win ?? 0]), 0.01)
  return (
    <ul className="space-y-3">
      {rows.map((d) => {
        const a = ((d.t1_p_win ?? 0) / max) * 100
        const b = ((d.t2_p_win ?? 0) / max) * 100
        const lo = Math.min(a, b)
        return (
          <li key={d.driver_id} className="grid grid-cols-[120px_1fr_110px] items-center gap-3 text-sm sm:grid-cols-[160px_1fr_120px]">
            <span className="truncate font-semibold">{surname(d.name, d.family_name)}</span>
            <span className="relative h-3">
              <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-rule" />
              <span className="absolute top-1/2 h-1 -translate-y-1/2 rounded bg-night/30" style={{ left: `${lo}%`, width: `${Math.abs(b - a)}%` }} />
              <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-night bg-stone" style={{ left: `${a}%` }} title="Before qualifying" />
              <span className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sun ring-2 ring-night" style={{ left: `${b}%` }} title="After qualifying" />
            </span>
            <span className="text-right font-mono text-[12px] tabular">
              {pct(d.t1_p_win ?? 0, 0)} → <strong>{pct(d.t2_p_win ?? 0, 0)}</strong>
            </span>
          </li>
        )
      })}
      <li className="flex gap-4 pt-1 text-[12px] text-earth">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full border-2 border-night" /> before qualifying</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-sun ring-2 ring-night" /> after qualifying</span>
      </li>
    </ul>
  )
}

function PracticePace({ drivers }: { drivers: DriverDetail[] }) {
  const rows = drivers.filter((d) => d.practice_longrun_gap_pct !== null).sort((a, b) => a.practice_longrun_gap_pct! - b.practice_longrun_gap_pct!).slice(0, 10)
  if (!rows.length) return <Notice>No practice data for this race (available from 2023).</Notice>
  const max = Math.max(...rows.map((d) => d.practice_longrun_gap_pct!), 0.1)
  return (
    <ul className="space-y-2">
      {rows.map((d, i) => (
        <li key={d.driver_id} className="grid grid-cols-[120px_1fr_120px] items-center gap-3 text-sm sm:grid-cols-[160px_1fr_140px]">
          <span className="truncate">{surname(d.name, d.family_name)}</span>
          <span className="h-2 rounded-full bg-paper">
            <span className={`bar block h-full rounded-full ${i === 0 ? 'bg-sun' : 'bg-night/50'}`} style={{ width: `${Math.max(3, (1 - d.practice_longrun_gap_pct! / (max * 1.15)) * 100)}%` }} />
          </span>
          <span className="text-right font-mono text-[12px]">
            {i === 0 ? 'fastest' : `+${d.practice_longrun_gap_pct!.toFixed(2)}% slower`}
          </span>
        </li>
      ))}
    </ul>
  )
}

function FullTable({ drivers }: { drivers: DriverDetail[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="label border-b border-night">
            <th className="py-2 text-left font-medium">Finished</th>
            <th className="py-2 text-left font-medium">Driver</th>
            <th className="py-2 text-left font-medium"><Tip text={EXPLAIN.started}>Started</Tip></th>
            <th className="py-2 text-left font-medium">Result</th>
            <th className="py-2 text-right font-medium"><Tip text={EXPLAIN.stage}>Chance to win, before quali</Tip></th>
            <th className="py-2 text-right font-medium">After quali</th>
            <th className="py-2 text-right font-medium"><Tip text={EXPLAIN.chancePodium} align="right">Chance of podium</Tip></th>
          </tr>
        </thead>
        <tbody>
          {drivers.map((d) => (
            <tr key={d.driver_id} className="border-b border-rule transition-colors duration-[320ms] hover:bg-sun">
              <td className="py-2 font-mono">{d.finish ? ordinal(d.finish) : '—'}</td>
              <td className="py-2">
                <span className="inline-flex items-center gap-2">
                  <span className="h-5 w-1 rounded-sm" style={{ background: teamColour(d.constructor_id) }} />
                  <span className="font-semibold">{d.name}</span>
                  <span className="text-earth">{d.team}</span>
                </span>
              </td>
              <td className="py-2">{startedText(d.grid)}</td>
              <td className="py-2 text-earth">{d.status}</td>
              <td className="py-2 text-right font-mono tabular">{pct(d.t1_p_win ?? 0)}</td>
              <td className="py-2 text-right font-mono tabular font-semibold">{pct(d.t2_p_win ?? 0)}</td>
              <td className="py-2 text-right font-mono tabular">{pct(d.t2_p_podium ?? 0, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Neighbours({ races, current }: { races: Race[]; current: number }) {
  const linkable = races.filter((r) => r.status === 'done' || r.prediction_stages.length)
  const i = linkable.findIndex((r) => r.round === current)
  const prev = i > 0 ? linkable[i - 1] : null
  const next = i >= 0 && i < linkable.length - 1 ? linkable[i + 1] : null
  const cls = 'group inline-flex items-center gap-2 rounded-full border border-night px-4 py-2 font-mono text-[0.72rem] tracking-[0.08em] uppercase transition-colors duration-[320ms] hover:bg-night hover:text-stone'
  return (
    <nav aria-label="Other races" className="flex flex-wrap justify-between gap-3">
      {prev ? (
        <Link to={`/race/${prev.season}/${prev.round}`} className={cls}>
          <Morph icon={ArrowLeft} size={14} /> {prev.race_name.replace(' Grand Prix', '')}
        </Link>
      ) : <span />}
      {next && (
        <Link to={`/race/${next.season}/${next.round}`} className={cls}>
          {next.race_name.replace(' Grand Prix', '')} <Morph icon={ArrowRight} size={14} />
        </Link>
      )}
    </nav>
  )
}

function LiveOnly({ detail }: { detail: Detail }) {
  const stage: Stage = detail.live.t2 ? 't2' : 't1'
  const live = detail.live[stage]!
  const prediction: Prediction = {
    season: detail.season, round: detail.round, race_name: detail.race_name, stage,
    generated_at: live.generated_at, race_start_utc: detail.race_start_utc ?? '', model: { kind: '' },
    train_races: 0, train_until: '', warnings: [], predictions: live.predictions,
  }
  return <PredictionTable prediction={prediction} />
}

export default function RaceDetailPage() {
  const { season = '2026', round = '1' } = useParams()
  const detail = useApi<Detail>(`/races/${season}/${round}/detail`)
  const races = useApi<Race[]>(`/races?season=${season}`)
  const [stage, setStage] = useState<Stage>('t2')
  const winner = useMemo(() => (detail.state === 'ready' ? detail.data.drivers.find((d) => d.finish === 1) : undefined), [detail])

  return (
    <Load
      value={detail}
      missing={<Notice>There is no detail page for this race yet. Details appear once a prediction is published or the race is run.</Notice>}
    >
      {(d) => (
        <article className="space-y-14">
          <header className="text-center">
            <p className="label">
              Round {d.round} · {d.locality}, {d.country} · {formatLocal(d.race_start_utc)}
            </p>
            <h1 className="wide mt-3 text-[clamp(2.2rem,7vw,5rem)] leading-[0.92] font-extrabold tracking-tight uppercase">
              {d.race_name.replace(' Grand Prix', '')}
              <span className="block"><span className="mark">Grand Prix</span></span>
            </h1>
            <div className="mx-auto mt-5 flex max-w-3xl items-center gap-4">
              <GuideLine className="flex-1" />
              <span className="label whitespace-nowrap">
                {d.kind === 'backtest' ? (
                  <Tip text={EXPLAIN.backtest}>Replay — not published in advance</Tip>
                ) : (
                  'Live prediction'
                )}
              </span>
              <GuideLine className="flex-1" />
            </div>
            <div className="mt-5"><WeatherChips w={d.weather} /></div>
          </header>

          {d.status === 'upcoming' ? (
            <section>
              <SectionTitle eyebrow="Published before the race">Our prediction</SectionTitle>
              <LiveOnly detail={d} />
            </section>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Tip text={EXPLAIN.stage}>
                  <StageToggle stage={stage} available={['t1', 't2']} onChange={setStage} />
                </Tip>
                {winner && <p className="text-sm text-earth">Winner: <strong className="text-night">{winner.name}</strong>, started {startedText(winner.grid).toLowerCase()}</p>}
              </div>

              <Summary drivers={d.drivers} stage={stage} />

              <section>
                <SectionTitle eyebrow="Forecast against reality">Who we expected vs who finished</SectionTitle>
                <SlopeChart drivers={d.drivers} stage={stage} />
              </section>

              <section>
                <SectionTitle eyebrow="What weighed most in the forecast">The model’s reasons</SectionTitle>
                <Reasons detail={d} stage={stage} />
              </section>

              <section className="grid gap-12 lg:grid-cols-2">
                <div>
                  <SectionTitle eyebrow="Before → after qualifying">How the grid changed the odds</SectionTitle>
                  <ForecastShift drivers={d.drivers} />
                </div>
                <div>
                  <SectionTitle eyebrow="Long runs in practice, lower is better">Race pace in practice</SectionTitle>
                  <PracticePace drivers={d.drivers} />
                </div>
              </section>

              <section>
                <SectionTitle eyebrow="Every driver">Full result and forecast</SectionTitle>
                <FullTable drivers={d.drivers} />
              </section>
            </>
          )}

          <Load value={races}>{(rs) => <Neighbours races={rs} current={d.round} />}</Load>
        </article>
      )}
    </Load>
  )
}
