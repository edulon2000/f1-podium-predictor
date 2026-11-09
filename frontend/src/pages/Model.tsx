import type { EvalRow, Evaluation, Stage } from '@/api'
import { Load, SectionTitle } from '@/components/core'
import { useApi } from '@/hooks'
import { pct, STAGE_LABEL } from '@/format'
import { EXPLAIN, Tip } from '@/components/Tip'

const MODEL_LABEL: Record<string, string> = {
  logreg: 'Logistic regression',
  lgbm: 'Gradient boosting (LightGBM)',
  rank: 'Ranking model (LightGBM)',
  'B1 pole wins': 'Pole-sitter wins',
  'B1p P(win | grid)': 'Pole-sitter, calibrated by grid slot',
  'B2 leader wins': 'Championship leader wins',
  'B2p P(win | standings)': 'Leader, calibrated by standings',
}
const label = (m: string) => MODEL_LABEL[m] ?? m
const rowLabel = (r: EvalRow) =>
  r.role === 'chosen' ? `${label(r.model)} — current` : r.role === 'best base' ? `${label(r.model)} — previous version` : label(r.model)
const isBaseline = (m: string) => m.startsWith('B')
// All-or-nothing baselines (100% on one driver): log-loss is not meaningful for them.
const isDeterministic = (m: string) => isBaseline(m) && !m.startsWith('B1p') && !m.startsWith('B2p')

function Results({ rows, stage }: { rows: EvalRow[]; stage: Stage }) {
  const sub = rows.filter((r) => r.stage === stage)
  const windows = [...new Set(sub.map((r) => r.window))]
  return (
    <div className="space-y-6">
      {windows.map((w) => {
        const ws = sub.filter((r) => r.window === w).sort((a, b) => a.logloss_win - b.logloss_win)
        const maxAcc = Math.max(...ws.map((r) => r.winner_acc), 0.01)
        return (
          <div key={w}>
            <p className="label mb-2">
              <Tip text={EXPLAIN.holdout}>{w.replace('holdout', 'Test on')} · {ws[0]?.races} races</Tip>
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] border-collapse">
                <thead>
                  <tr className="label border-b border-night">
                    <th className="py-2 text-left font-medium"><Tip text={EXPLAIN.baseline}>Method</Tip></th>
                    <th className="w-[30%] py-2 text-left font-medium"><Tip text={EXPLAIN.pickedWinner}>Picked the winner</Tip></th>
                    <th className="py-2 text-right font-medium"><Tip text={EXPLAIN.winnerTop3} align="right">Winner in our top 3</Tip></th>
                    <th className="py-2 text-right font-medium"><Tip text={EXPLAIN.podiumGuessed} align="right">Podium places guessed</Tip></th>
                    <th className="py-2 text-right font-medium"><Tip text={EXPLAIN.confidenceScore} align="right">Confidence score</Tip></th>
                  </tr>
                </thead>
                <tbody>
                  {ws.map((r) => {
                    const base = isBaseline(r.model)
                    return (
                      <tr key={`${r.role ?? ''}-${r.model}`} className={`border-b border-rule transition-colors duration-[320ms] hover:bg-sun ${base ? '' : 'bg-sun/30'}`}>
                        <td className={`py-2.5 ${base ? 'text-earth' : 'narrow text-2xl font-extrabold uppercase'}`}>{rowLabel(r)}</td>
                        <td className="py-2">
                          <div className="flex items-center gap-3">
                            <div className="h-2 w-full rounded-full bg-paper">
                              <div
                                className={`bar h-full rounded-full ${base ? 'bg-dash' : 'bg-night'}`}
                                style={{ width: `${(r.winner_acc / maxAcc) * 100}%` }}
                              />
                            </div>
                            <span className="w-12 text-right font-mono tabular">{pct(r.winner_acc, 0)}</span>
                          </div>
                        </td>
                        <td className="py-2 text-right font-mono tabular">{r.winner_top3 === undefined ? '—' : pct(r.winner_top3, 0)}</td>
                        <td className="py-2 text-right font-mono tabular">{pct(r.podium_hit, 0)}</td>
                        <td className="py-2 text-right font-mono tabular">
                          {isDeterministic(r.model) ? <span className="text-earth">{r.logloss_win.toFixed(2)}*</span> : r.logloss_win.toFixed(2)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
      <p className="font-mono text-[0.68rem] text-earth">
        * All-or-nothing baselines put 100% on one driver, so their log-loss explodes whenever they miss. The calibrated
        versions (win rate by grid slot or by standings position, learned from earlier races) are the fair comparison.
      </p>
    </div>
  )
}

const STEPS = [
  ['Data', 'Every race since 2014 from Jolpica-F1 (results, grid, qualifying, standings) and practice laps, tyres and the starting grid from OpenF1 since 2023.'],
  ['Features', 'Championship position before the race, recent form of driver and team, qualifying pace, reliability, history at the circuit and, after qualifying, the grid. Anything that depends on a race result only enters the following races.'],
  ['Leakage tests', "Automated tests scramble a race's result and check its own features don't move, and that features built before a race match those built after it."],
  ['Validation', 'Walk-forward: each race is predicted by a model trained only on earlier races. Settings were chosen on 2023–24, then checked once on 2025–26.'],
  ['2026 weighting', 'The 2026 cars follow new rules, so how much races from the current rules era weigh in training is tuned. It helped after qualifying (×3) but not before it (×1).'],
  ['Publishing', 'Predictions are generated and committed to the public repository before the start, then scored against the result.'],
]

export default function Model() {
  const ev = useApi<Evaluation>('/evaluation')
  return (
    <div className="space-y-16">
      <section>
        <SectionTitle eyebrow="Method">How the predictions <span className="mark">are made</span></SectionTitle>
        <dl className="grid gap-x-10 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map(([t, d]) => (
            <div key={t} className="brackets p-4">
              <dt className="wide text-base font-extrabold uppercase">{t}</dt>
              <dd className="mt-1 text-sm text-earth">{d}</dd>
            </div>
          ))}
        </dl>
      </section>
      <Load value={ev} missing={<p className="text-sm text-earth">Evaluation not published yet.</p>}>
        {(e) => (
          <>
            {(['t2', 't1'] as Stage[]).map((s) => (
              <section key={s}>
                <SectionTitle eyebrow={`Chosen: ${label(e.chosen[s].kind)}`}>
                  {STAGE_LABEL[s]}: model vs simple rules
                </SectionTitle>
                <Results rows={e.holdout} stage={s} />
              </section>
            ))}
          </>
        )}
      </Load>
      <Glossary />
    </div>
  )
}

const GLOSSARY: [string, string][] = [
  ['Chance to win', EXPLAIN.chanceWin],
  ['Chance of a podium', EXPLAIN.chancePodium],
  ['Our favourite', EXPLAIN.favourite],
  ['Chance we gave the winner', EXPLAIN.chanceGivenToWinner],
  ['Podium places guessed', EXPLAIN.podiumGuessed],
  ['Before / after qualifying', EXPLAIN.stage],
  ['Confidence score (log-loss)', EXPLAIN.confidenceScore],
  ['Baseline', EXPLAIN.baseline + ' “Calibrated” versions use how often each grid slot (or standings position) won in the past instead of betting everything on one driver.'],
  ['Test races', EXPLAIN.holdout],
  ['Replay', EXPLAIN.backtest],
  ['Pole', 'First place on the starting grid, earned by setting the fastest lap in qualifying.'],
  ['Qualifying', 'The session the day before the race that decides the starting order.'],
  ['Practice', 'Free sessions before qualifying where teams test their cars; we use the lap times to estimate race pace.'],
  ['Sprint', 'A short extra race on Saturday at some events, with fewer points.'],
]

function Glossary() {
  return (
    <section id="glossary" className="scroll-mt-24">
      <SectionTitle eyebrow="Plain-language definitions">Glossary</SectionTitle>
      <dl className="grid gap-x-10 gap-y-5 sm:grid-cols-2">
        {GLOSSARY.map(([term, def]) => (
          <div key={term} className="border-t border-rule pt-3">
            <dt className="font-semibold">{term}</dt>
            <dd className="mt-0.5 text-sm text-earth">{def}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
