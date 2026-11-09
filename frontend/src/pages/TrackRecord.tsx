import { useState } from 'react'
import type { BacktestRow, DriverInfo, Race, ScoreRow, Stage } from '../api'
import { Check, Load, Notice, SectionTitle } from '@/components/core'
import { useApi } from '../hooks'
import { pct, STAGE_LABEL } from '../format'

type Drivers = Record<string, DriverInfo>
const code = (d: Drivers, id: string | null) => (id ? d[id]?.code ?? id : '—')

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
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-ink font-mono text-[0.68rem] tracking-[0.12em] text-muted uppercase">
                <th className="py-2 text-left font-medium">Race</th>
                <th className="py-2 text-left font-medium">Stage</th>
                <th className="py-2 text-left font-medium">Picked</th>
                <th className="py-2 text-left font-medium">Winner</th>
                <th className="py-2 text-right font-medium">P(winner)</th>
                <th className="py-2 text-right font-medium">Podium</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.race}-${r.stage}`} className="border-b border-rule">
                  <td className="py-2 font-mono">{r.race}</td>
                  <td className="py-2 text-muted">{STAGE_LABEL[r.stage]}</td>
                  <td className="py-2 font-mono">
                    {code(drivers, r.predicted)} <Check ok={r.winner_correct} />
                  </td>
                  <td className="py-2 font-mono">{code(drivers, r.actual)}</td>
                  <td className="py-2 text-right font-mono tabular">{pct(r.p_actual_winner)}</td>
                  <td className="py-2 text-right font-mono tabular">{Math.round(r.podium_hit * 3)}/3</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      }
    </Load>
  )
}

function Backtest({ drivers, races }: { drivers: Drivers; races: Race[] }) {
  const [stage, setStage] = useState<Stage>('t2')
  const bt = useApi<Partial<Record<Stage, BacktestRow[]>>>('/backtest/2026')
  const names = Object.fromEntries(races.map((r) => [r.round, r.race_name.replace(' Grand Prix', '')]))
  return (
    <Load value={bt}>
      {(data) => {
        const rows = data[stage] ?? []
        const hits = rows.filter((r) => r.predicted === r.actual).length
        const pole = rows.filter((r) => r.pole_won).length
        return (
          <div className="rounded-lg border border-rule bg-sheet p-4 sm:p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div role="tablist" aria-label="Prediction stage" className="flex gap-1">
                {(['t1', 't2'] as Stage[]).map((s) => (
                  <button
                    key={s}
                    role="tab"
                    aria-selected={stage === s}
                    onClick={() => setStage(s)}
                    className={`rounded px-3 py-1.5 font-mono text-[0.72rem] tracking-[0.08em] uppercase ${
                      stage === s ? 'bg-ink text-sheet' : 'border border-rule text-muted hover:text-ink'
                    }`}
                  >
                    {STAGE_LABEL[s]}
                  </button>
                ))}
              </div>
              <p className="font-mono text-sm">
                Model <strong className="text-purple">{hits}</strong>/{rows.length} · Pole-sitter{' '}
                <strong>{pole}</strong>/{rows.length}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-ink font-mono text-[0.68rem] tracking-[0.12em] text-muted uppercase">
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
                    return (
                      <tr key={r.round} className={`border-b border-rule ${i % 2 ? 'bg-stripe/60' : ''}`}>
                        <td className="py-2 font-mono tabular text-muted">{String(r.round).padStart(2, '0')}</td>
                        <td className="py-2">{names[r.round] ?? `Round ${r.round}`}</td>
                        <td className="py-2 font-mono">
                          {code(drivers, r.predicted)}{' '}
                          <span className="text-muted">{pct(r.p_predicted, 0)}</span>{' '}
                          <Check ok={r.predicted === r.actual} />
                        </td>
                        <td className="py-2 font-mono">{code(drivers, r.actual)}</td>
                        <td className="py-2 text-right font-mono tabular">
                          {r.p_actual === null ? '—' : pct(r.p_actual)}
                        </td>
                        <td className="py-2 text-right font-mono tabular">{podium}/3</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
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
    <div className="space-y-10">
      <section>
        <SectionTitle eyebrow="Published before the race, scored after">Live predictions</SectionTitle>
        <Load value={drivers}>{(d) => <LiveRecord drivers={d} />}</Load>
      </section>
      <section>
        <SectionTitle eyebrow="Replay: each race predicted from earlier races only">2026 backtest</SectionTitle>
        <p className="mb-4 max-w-2xl text-sm text-muted">
          These were not published in advance. Each race was re-run with a model trained only on the races before it, so
          no result leaks into its own forecast. Live predictions above are the ones that count.
        </p>
        <Load value={drivers}>
          {(d) => <Load value={races}>{(rs) => <Backtest drivers={d} races={rs} />}</Load>}
        </Load>
      </section>
    </div>
  )
}
