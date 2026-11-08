import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { BacktestRow, Prediction, Race, Stage } from '../api'
import { IssueStamp, Load, Notice, SectionTitle, TimingTower } from '../components'
import { useApi, useNow } from '../hooks'
import { countdownParts, formatLocal, STAGE_LABEL } from '../format'

function Countdown({ iso }: { iso?: string }) {
  const now = useNow()
  if (!iso) return null
  const ms = new Date(iso).getTime() - now
  if (ms <= 0) return <p className="font-mono text-sm text-muted">Race under way or finished.</p>
  const c = countdownParts(ms)
  const cells: [number, string][] = [
    [c.days, 'days'],
    [c.hours, 'hrs'],
    [c.minutes, 'min'],
    [c.seconds, 'sec'],
  ]
  return (
    <div className="flex gap-4" aria-label="Time until lights out">
      {cells.map(([v, l]) => (
        <div key={l} className="text-center">
          <div className="font-display text-4xl font-bold tabular">{String(v).padStart(2, '0')}</div>
          <div className="font-mono text-[0.65rem] tracking-[0.14em] text-muted uppercase">{l}</div>
        </div>
      ))}
    </div>
  )
}

function PredictionPanel({ race }: { race: Race }) {
  const stages = race.prediction_stages
  const [stage, setStage] = useState<Stage | null>(stages.includes('t2') ? 't2' : stages[0] ?? null)
  useEffect(() => {
    setStage(stages.includes('t2') ? 't2' : stages[0] ?? null)
  }, [race.round, stages])
  const pred = useApi<Prediction>(stage ? `/races/${race.season}/${race.round}/predictions?stage=${stage}` : null)

  if (!stage) {
    return (
      <Notice>
        <p className="mb-2 font-semibold text-ink">No prediction published for this race yet.</p>
        <p>
          The first one (before qualifying) is issued after final practice, ahead of qualifying on{' '}
          <strong className="text-ink">{formatLocal(race.quali_utc)}</strong>. The second one adds the starting grid and
          is issued before lights out.
        </p>
      </Notice>
    )
  }

  return (
    <div className="rounded-lg border border-rule bg-sheet p-4 sm:p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div role="tablist" aria-label="Prediction stage" className="flex gap-1">
          {(['t1', 't2'] as Stage[]).map((s) => (
            <button
              key={s}
              role="tab"
              aria-selected={stage === s}
              disabled={!stages.includes(s)}
              onClick={() => setStage(s)}
              className={`rounded px-3 py-1.5 font-mono text-[0.72rem] tracking-[0.08em] uppercase disabled:cursor-not-allowed disabled:opacity-40 ${
                stage === s ? 'bg-ink text-sheet' : 'border border-rule text-muted hover:text-ink'
              }`}
            >
              {STAGE_LABEL[s]}
            </button>
          ))}
        </div>
        {pred.state === 'ready' && <IssueStamp prediction={pred.data} />}
      </div>
      <Load value={pred}>
        {(p) => (
          <>
            <TimingTower prediction={p} />
            <p className="mt-4 font-mono text-[0.7rem] text-muted">
              Model: {p.model.kind} · trained on {p.train_races} races up to {p.train_until}. Win probabilities add up
              to 100% per race; podium probabilities add up to 300%.
            </p>
            {p.warnings.map((w) => (
              <p key={w} className="mt-1 font-mono text-[0.7rem] text-amber">
                Note: {w}
              </p>
            ))}
          </>
        )}
      </Load>
    </div>
  )
}

function BacktestTeaser() {
  const bt = useApi<{ t2?: BacktestRow[] }>('/backtest/2026')
  if (bt.state !== 'ready' || !bt.data.t2?.length) return null
  const rows = bt.data.t2
  const model = rows.filter((r) => r.predicted === r.actual).length
  const pole = rows.filter((r) => r.pole_won).length
  return (
    <p className="text-sm text-muted">
      Replayed over the {rows.length} races of 2026 so far (each one predicted only from earlier races), the model picked
      the winner <strong className="text-ink">{model} times</strong>; simply backing the pole-sitter would have been right{' '}
      <strong className="text-ink">{pole} times</strong>.{' '}
      <Link to="/track-record" className="text-purple underline underline-offset-2">
        See every race
      </Link>
      .
    </p>
  )
}

export default function NextRace() {
  const race = useApi<Race>('/races/next')
  return (
    <Load
      value={race}
      missing={<Notice>The 2026 season is over — see the track record for how the predictions did.</Notice>}
    >
      {(r) => (
        <div className="space-y-8">
          <section className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <p className="font-mono text-[0.72rem] tracking-[0.14em] text-muted uppercase">
                Round {r.round} · {r.locality}, {r.country}
              </p>
              <h1 className="font-display text-6xl leading-[0.9] font-extrabold tracking-tight uppercase sm:text-7xl">
                {r.race_name.replace(' Grand Prix', '')}
                <span className="block text-2xl font-semibold tracking-normal text-muted sm:text-3xl">Grand Prix</span>
              </h1>
              <p className="mt-3 font-mono text-sm text-muted">Lights out {formatLocal(r.race_start_utc)} (your time)</p>
            </div>
            <Countdown iso={r.race_start_utc} />
          </section>

          <section>
            <SectionTitle eyebrow="Who wins?">Prediction</SectionTitle>
            <PredictionPanel race={r} />
          </section>

          <BacktestTeaser />
        </div>
      )}
    </Load>
  )
}
