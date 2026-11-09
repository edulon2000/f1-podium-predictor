import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide'
import type { BacktestRow, DriverInfo, Race, ScoreRow, Stage } from '@/api'
import { Load, Notice, ResultMark, SectionTitle, StageToggle } from '@/components/core'
import { FocusField } from '@/components/microkit/focus-input'
import { Morph } from '@/components/Morph'
import { EXPLAIN, Tip } from '@/components/Tip'
import { useApi } from '@/hooks'
import { pct, STAGE_LABEL } from '@/format'

type Drivers = Record<string, DriverInfo>
const fam = (d: Drivers, id: string | null) => (id ? (d[id]?.family_name ?? id) : '—')
const full = (d: Drivers, id: string | null) => (id ? (d[id]?.name ?? id) : '')

function Th({ children, tip, right, align }: { children: string; tip?: string; right?: boolean; align?: 'left' | 'right' }) {
  return (
    <th className={`py-2 font-medium ${right ? 'text-right' : 'text-left'}`}>
      {tip ? <Tip text={tip} align={align}>{children}</Tip> : children}
    </th>
  )
}

function LiveRecord({ drivers }: { drivers: Drivers }) {
  const board = useApi<ScoreRow[]>('/scoreboard')
  const navigate = useNavigate()
  return (
    <Load value={board}>
      {(rows) =>
        rows.length === 0 ? (
          <Notice>
            No live prediction has been scored yet. The first ones are for the Las Vegas Grand Prix: published before
            qualifying and before the start, then scored here after the chequered flag.
          </Notice>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse">
              <thead>
                <tr className="label border-b border-night">
                  <Th>Race</Th>
                  <Th tip={EXPLAIN.stage}>Published</Th>
                  <Th tip={EXPLAIN.favourite}>Our favourite</Th>
                  <Th tip={EXPLAIN.winner}>Winner</Th>
                  <Th tip={EXPLAIN.chanceGivenToWinner} right align="right">Chance we gave the winner</Th>
                  <Th tip={EXPLAIN.podiumGuessed} right align="right">Podium guessed</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={`${r.race}-${r.stage}`}
                    tabIndex={0}
                    onClick={() => navigate(`/race/${r.season}/${r.round}`)}
                    onKeyDown={(e) => e.key === 'Enter' && navigate(`/race/${r.season}/${r.round}`)}
                    className="cursor-pointer border-b border-rule transition-colors duration-[320ms] hover:bg-sun focus-visible:bg-sun"
                  >
                    <td className="narrow py-2.5 text-2xl font-extrabold">{r.race}</td>
                    <td className="py-2.5 text-sm text-earth">{STAGE_LABEL[r.stage]}</td>
                    <td className="py-2.5">
                      {fam(drivers, r.predicted)} <ResultMark ok={r.winner_correct} delay={i * 60} />
                    </td>
                    <td className="py-2.5 font-semibold">{fam(drivers, r.actual)}</td>
                    <td className="py-2.5 text-right font-mono tabular">{pct(r.p_actual_winner)}</td>
                    <td className="py-2.5 text-right font-mono tabular">{Math.round(r.podium_hit * 3)} of 3</td>
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
  const navigate = useNavigate()
  const bt = useApi<Partial<Record<Stage, BacktestRow[]>>>('/backtest/2026')
  const names = useMemo(() => Object.fromEntries(races.map((r) => [r.round, r.race_name.replace(' Grand Prix', '')])), [races])

  return (
    <Load value={bt}>
      {(data) => {
        const all = data[stage] ?? []
        const q = query.trim().toLowerCase()
        const rows = all.filter(
          (r) => !q || [names[r.round], full(drivers, r.predicted), full(drivers, r.actual)].some((v) => v?.toLowerCase().includes(q)),
        )
        const hits = all.filter((r) => r.predicted === r.actual).length
        const pole = all.filter((r) => r.pole_won).length
        const podium = all.reduce((s, r) => s + r.predicted_podium.filter((d) => r.actual_podium.includes(d)).length, 0)
        const top3 = all.filter((r) => r.actual && (r.top3 ?? r.predicted_podium).includes(r.actual)).length
        const stats: [string, string, string][] = [
          [`${hits} of ${all.length}`, 'Winners we called', EXPLAIN.pickedWinner],
          [`${top3} of ${all.length}`, 'Winner among our top 3', EXPLAIN.winnerTop3],
          [`${pole} of ${all.length}`, 'Won from pole', 'The simple rule we compare against: the driver starting first wins.'],
          [`${podium} of ${all.length * 3}`, 'Podium places we guessed', EXPLAIN.podiumGuessed],
        ]
        return (
          <div>
            <div className="mb-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {stats.map(([v, l, tip], i) => (
                <div key={l} className="border-t border-night pt-2">
                  <div className={`narrow text-5xl leading-none font-extrabold tabular ${i === 0 ? '' : 'text-earth'}`}>{v}</div>
                  <div className="label mt-1"><Tip text={tip}>{l}</Tip></div>
                </div>
              ))}
            </div>

            <div className="mb-3 flex flex-wrap items-end justify-between gap-4">
              <Tip text={EXPLAIN.stage}>
                <StageToggle stage={stage} available={['t1', 't2']} onChange={setStage} />
              </Tip>
              <FocusField label="Find a race or driver" value={query} onChange={setQuery} placeholder="e.g. Monaco or Norris" />
            </div>
            <p className="mb-2 text-[12.5px] text-earth">Click a race to see the full story: forecast vs result, the model’s reasons and every driver.</p>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse">
                <thead>
                  <tr className="label border-b border-night">
                    <Th>Round</Th>
                    <Th>Grand Prix</Th>
                    <Th tip={EXPLAIN.favourite}>Our favourite</Th>
                    <Th tip={EXPLAIN.winner}>Winner</Th>
                    <Th tip={EXPLAIN.chanceGivenToWinner} right align="right">Chance we gave the winner</Th>
                    <Th tip={EXPLAIN.podiumGuessed} right align="right">Podium guessed</Th>
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const podiumHits = r.predicted_podium.filter((d) => r.actual_podium.includes(d)).length
                    const ok = r.predicted === r.actual
                    const go = () => navigate(`/race/${r.season}/${r.round}`)
                    return (
                      <tr
                        key={`${stage}-${r.round}`}
                        tabIndex={0}
                        onClick={go}
                        onKeyDown={(e) => e.key === 'Enter' && go()}
                        className="group cursor-pointer border-b border-rule transition-colors duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] hover:bg-sun focus-visible:bg-sun"
                      >
                        <td className="py-2 font-mono text-sm tabular text-earth">{r.round}</td>
                        <td className="narrow py-2 text-2xl font-extrabold uppercase sm:text-3xl">{names[r.round] ?? `Round ${r.round}`}</td>
                        <td className="py-2">
                          <span className="inline-flex items-center gap-2">
                            <span className="font-semibold">{fam(drivers, r.predicted)}</span>
                            <span className="font-mono text-[12px] text-earth">{pct(r.p_predicted, 0)}</span>
                            <ResultMark ok={ok} delay={i * 40} />
                          </span>
                        </td>
                        <td className="py-2 font-semibold">{fam(drivers, r.actual)}</td>
                        <td className="py-2 text-right font-mono tabular">{r.p_actual === null ? '—' : pct(r.p_actual)}</td>
                        <td className="py-2 text-right font-mono tabular">{podiumHits} of 3</td>
                        <td className="py-2 text-right">
                          <Link
                            to={`/race/${r.season}/${r.round}`}
                            onClick={(e) => e.stopPropagation()}
                            aria-label={`Details of the ${names[r.round]} Grand Prix`}
                            className="inline-flex translate-x-0 opacity-40 transition-[opacity,transform] duration-[320ms] group-hover:translate-x-1 group-hover:opacity-100"
                          >
                            <Morph icon={ArrowRight} size={16} />
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {rows.length === 0 && <p className="py-6 text-sm text-earth">Nothing matches “{query}”. Clear the search to see every race.</p>}
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
        <SectionTitle eyebrow="Each race predicted again from earlier races only">2026 replay</SectionTitle>
        <p className="mb-6 max-w-2xl text-sm text-earth">
          <Tip text={EXPLAIN.backtest}>These were not published in advance.</Tip> Each race was re-run with a model trained
          only on the races before it, so no result leaks into its own forecast. The live predictions above are the ones that
          count.
        </p>
        <Load value={drivers}>{(d) => <Load value={races}>{(rs) => <Backtest drivers={d} races={rs} />}</Load>}</Load>
      </section>
    </div>
  )
}
