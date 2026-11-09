import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { BacktestRow, Prediction, Race, Stage } from '@/api'
import {
  Countdown,
  GuideLine,
  IssueStamp,
  Load,
  Notice,
  ProbabilityDial,
  SectionTitle,
  StageToggle,
} from '@/components/core'
import { PredictionTable } from '@/components/PredictionTable'
import { useApi, type Loadable } from '@/hooks'
import { formatLocal, pct, STAGE_LABEL } from '@/format'

function preferredStage(stages: Stage[]): Stage | null {
  return stages.includes('t2') ? 't2' : (stages[0] ?? null)
}

function ReplayStats() {
  const bt = useApi<{ t2?: BacktestRow[] }>('/backtest/2026')
  const rows = bt.state === 'ready' ? (bt.data.t2 ?? []) : []
  const stats: [string, string][] = rows.length
    ? [
        [String(rows.length), '2026 races replayed'],
        [String(rows.filter((r) => r.pole_won).length), 'won from pole'],
        [String(rows.filter((r) => r.predicted === r.actual).length), 'winners we called'],
      ]
    : []
  return (
    <dl className="grid grid-cols-3 gap-4 md:block md:space-y-4">
      {stats.map(([v, l]) => (
        <div key={l}>
          <dt className="sr-only">{l}</dt>
          <dd>
            <span className="narrow block text-4xl leading-none font-extrabold tabular">{v}</span>
            <span className="label">{l}</span>
          </dd>
        </div>
      ))}
      {rows.length > 0 && (
        <Link to="/track-record" className="label col-span-3 inline-block underline underline-offset-4 hover:text-night">
          See every race →
        </Link>
      )}
    </dl>
  )
}

function Hero({ race, prediction, stage }: { race: Race; prediction: Loadable<Prediction>; stage: Stage | null }) {
  const name = race.race_name.replace(' Grand Prix', '')
  const top = prediction.state === 'ready' ? prediction.data.predictions[0] : null
  return (
    <section className="text-center">
      <p className="label">
        Round {race.round} · {race.locality}, {race.country}
      </p>
      <h1 className="wide mt-3 text-[clamp(2.6rem,9vw,6.5rem)] leading-[0.92] font-extrabold tracking-tight uppercase">
        {name}
        <span className="block">
          <span className="mark">Grand Prix</span>
        </span>
      </h1>

      <div className="mx-auto mt-6 flex max-w-4xl items-center gap-4">
        <GuideLine className="flex-1" />
        <span className="label whitespace-nowrap">Lights out {formatLocal(race.race_start_utc)}</span>
        <GuideLine className="flex-1" />
      </div>

      <a
        href="#prediction"
        className="brackets mt-7 inline-block px-5 py-2.5 font-mono text-[0.72rem] tracking-[0.12em] uppercase"
      >
        {top ? 'See the full prediction' : 'How the prediction works'}
      </a>

      <div className="mt-12 grid items-center gap-10 text-left md:grid-cols-[1fr_320px_1fr]">
        <ReplayStats />
        <div className="order-first md:order-none">
        <ProbabilityDial
          probability={top ? top.p_win : null}
          title={top ? (top.code ?? top.driver_id) : 'TBA'}
          subtitle={top ? (top.name ?? top.driver_id) : 'After final practice'}
          detail={top ? `${pct(top.p_win)} to win` : undefined}
          caption={stage ? STAGE_LABEL[stage] : 'Not issued'}
        />
        </div>
        <div className="md:justify-self-end md:text-right">
          <Countdown iso={race.race_start_utc} />
        </div>
      </div>
    </section>
  )
}

export default function NextRace() {
  const race = useApi<Race>('/races/next')
  const stages = race.state === 'ready' ? race.data.prediction_stages : []
  const [stage, setStage] = useState<Stage | null>(null)
  useEffect(() => setStage(preferredStage(stages)), [stages.join(',')]) // eslint-disable-line react-hooks/exhaustive-deps
  const path =
    race.state === 'ready' && stage ? `/races/${race.data.season}/${race.data.round}/predictions?stage=${stage}` : null
  const prediction = useApi<Prediction>(path)

  return (
    <Load
      value={race}
      missing={<Notice>The 2026 season is over. See the track record for how the predictions did.</Notice>}
    >
      {(r) => (
        <div className="space-y-16">
          <Hero race={r} prediction={path ? prediction : { state: 'missing' }} stage={stage} />

          <section id="prediction" className="scroll-mt-24">
            <SectionTitle eyebrow="Who wins?">The prediction</SectionTitle>
            {!stage ? (
              <Notice>
                <p className="mb-2 font-semibold text-night">No prediction published for this race yet.</p>
                <p>
                  The first one (before qualifying) is issued after final practice, ahead of qualifying on{' '}
                  <strong className="text-night">{formatLocal(r.quali_utc)}</strong>. The second adds the starting grid
                  and is issued before lights out. Both are committed to the public repository before the race.
                </p>
              </Notice>
            ) : (
              <div className="rounded-xl border border-rule bg-paper/60 p-4 sm:p-6">
                <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
                  <StageToggle stage={stage} available={stages} onChange={setStage} />
                  {prediction.state === 'ready' && <IssueStamp prediction={prediction.data} />}
                </div>
                <Load value={prediction}>
                  {(p) => (
                    <>
                      <PredictionTable prediction={p} />
                      <p className="mt-4 font-mono text-[0.68rem] text-earth">
                        Model: {p.model.kind} · trained on {p.train_races} races up to {p.train_until}. Win
                        probabilities add up to 100% per race; podium probabilities to 300%.
                      </p>
                      {p.warnings.map((w) => (
                        <p key={w} className="mt-1 font-mono text-[0.68rem] text-earth">
                          Note: {w}
                        </p>
                      ))}
                    </>
                  )}
                </Load>
              </div>
            )}
          </section>
        </div>
      )}
    </Load>
  )
}
