import { useMemo, useState } from 'react'
import type { BacktestRow, DriverInfo, Race, ScoreRow, Stage } from '@/api'
import { Load, Notice, ResultMark, SectionTitle, StageToggle } from '@/components/core'
import { FocusField } from '@/components/microkit/focus-input'
import { useApi } from '@/hooks'
import { pct, STAGE_LABEL } from '@/format'

type Drivers = Record<string, DriverInfo>
const code = (d: Drivers, id: string | null) => (id ? (d[id]?.code ?? id) : '—')
const name = (d: Drivers, id: string | null) => (id ? (d[id]?.name ?? id) : '')

function LiveRecord({ drivers }: { drivers: Drivers }) {
  const board = useApi<ScoreRow[]>('/scoreboard')
  return (
    <Load value={board}>
      {(rows) =>
        rows.length === 0 ? (
          <Notice>
            No live prediction has been scored yet. The first ones are for the Las Vegas Grand Prix: issued before
            qualifying and before the start, then scored here after the chequered flag.
          </Notice>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse">
              <thead>
                <tr className="label border-b border-night">
                  <th className="py-2 text-left font-medium">Race</th>
                  <th className="py-2 text-left font-medium">Stage</th>
                  <th className="py-2 text-left font-medium">Picked</th>
                  <th className="py-2 text-left font-medium">Winner</th>
                  <th className="py-2 text-right font-medium">P(winner)</th>
                  <th className="py-2 text-right font-medium">Podium</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.race}-${r.stage}`} className="border-b border-rule transition-colors duration-[320ms] hover:bg-sun">
                    <td className="narrow py-2.5 text-2xl font-extrabold">{r.race}</td>
                    <td className="py-2.5 text-sm text-earth">{STAGE_LABEL[r.stage]}</td>
                    <td className="py-2.5 font-mono">
                      {code(drivers, r.predicted)} <ResultMark ok={r.winner_correct} delay={i * 60} />
                    </td>
                    <td className="py-2.5 font-mono">{code(drivers, r.actual)}</td>
                    <td className="py-2.5 text-right font-mono tabular">{pct(r.p_actual_winner)}</td>
                    <td className="py-2.5 text-right font-mono tabular">{Math.round(r.podium_hit * 3)}/3</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
    </Load>
  )
}

function Backtest({ drivers, races }: { drivers: Drivers; races: Race[] }) {
  const [stage, setStage] = useState<Stage>('t2')
  const [query, setQuery] = useState('')
  const bt = useApi<Partial<Record<Stage, BacktestRow[]>>>('/backtest/2026')
  const names = useMemo(() => Object.fromEntries(races.map((r) => [r.round, r.race_name.replace(' Grand Prix', '')])), [races])

  return (
    <Load value={bt}>
      {(data) => {
        const all = data[stage] ?? []
        const q = query.trim().toLowerCase()
        const rows = all.filter(
          (r) =>
            !q ||
            [names[r.round], r.predicted, r.actual, name(drivers, r.predicted), name(drivers, r.actual), code(drivers, r.actual)]
              .some((v) => v?.toLowerCase().includes(q)),
        )
        const hits = all.filter((r) => r.predicted === r.actual).length
        const pole = all.filter((r) => r.pole_won).length
        return (
          <div>
            <div className="mb-6 grid gap-6 sm:grid-cols-3">
              {[
                [`${hits}/${all.length}`, 'Winners called by the model'],
                [`${pole}/${all.length}`, 'Won by the pole-sitter'],
                [
                  `${all.reduce((s, r) => s + r.predicted_podium.filter((d) => r.actual_podium.includes(d)).length, 0)}/${all.length * 3}`,
                  'Podium places called',
                ],
              ].map(([v, l], i) => (
                <div key={l} className="border-t border-night pt-2">
                  <div className={`narrow text-5xl leading-none font-extrabold tabular ${i === 0 ? '' : 'text-earth'}`}>{v}</div>
                  <div className="label mt-1">{l}</div>
                </div>
              ))}
            </div>

            <div className="mb-3 flex flex-wrap items-end justify-between gap-4">
              <StageToggle stage={stage} available={['t1', 't2']} onChange={setStage} />
              <FocusField label="Filter races" value={query} onChange={setQuery} placeholder="Grand Prix or driver" />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px] border-collapse">
                <thead>
                  <tr className="label border-b border-night">
                    <th className="py-2 text-left font-medium">Rd</th>
                    <th className="py-2 text-left font-medium">Grand Prix</th>
                    <th className="py-2 text-left font-medium">Picked</th>
                    <th className="py-2 text-left font-medium">Winner</th>
                    <th className="py-2 text-right font-medium">P(winner)</th>
                    <th className="py-2 text-right font-medium">Podium</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const podium = r.predicted_podium.filter((d) => r.actual_podium.includes(d)).length
                    const ok = r.predicted === r.actual
                    return (
                      <tr
                        key={`${stage}-${r.round}`}
                        className="group border-b border-rule transition-colors duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] hover:bg-sun"
                      >
                        <td className="py-2 font-mono text-sm tabular text-earth">{String(r.round).padStart(2, '0')}</td>
                        <td className="narrow py-2 text-2xl font-extrabold uppercase sm:text-3xl">{names[r.round] ?? `Round ${r.round}`}</td>
                        <td className="py-2 font-mono">
                          <span className="inline-flex items-center gap-2">
                            {code(drivers, r.predicted)}
                            <span className="text-earth">{pct(r.p_predicted, 0)}</span>
                            <ResultMark ok={ok} delay={i * 40} />
                          </span>
                        </td>
                        <td className="py-2 font-mono font-semibold">{code(drivers, r.actual)}</td>
                        <td className="py-2 text-right font-mono tabular">{r.p_actual === null ? '—' : pct(r.p_actual)}</td>
                        <td className="py-2 text-right font-mono tabular">{podium}/3</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {rows.length === 0 && <p className="py-6 text-sm text-earth">No race matches “{query}”. Clear the filter to see all.</p>}
            </div>
          </div>
        )
      }}
    </Load>
  )
}

export default function TrackRecord() {
  const drivers = useApi<Drivers>('/drivers')
  const races = useApi<Race[]>('/races?season=2026')
  return (
    <div className="space-y-16">
      <section>
        <SectionTitle eyebrow="Published before the race, scored after">
          <span className="mark">Live</span> predictions
        </SectionTitle>
        <Load value={drivers}>{(d) => <LiveRecord drivers={d} />}</Load>
      </section>
      <section>
        <SectionTitle eyebrow="Replay: each race predicted from earlier races only">2026 backtest</SectionTitle>
        <p className="mb-6 max-w-2xl text-sm text-earth">
          These were not published in advance. Each race was re-run with a model trained only on the races before it, so
          no result leaks into its own forecast. The live predictions above are the ones that count.
        </p>
        <Load value={drivers}>{(d) => <Load value={races}>{(rs) => <Backtest drivers={d} races={rs} />}</Load>}</Load>
      </section>
    </div>
  )
}
