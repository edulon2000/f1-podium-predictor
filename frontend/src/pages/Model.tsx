import type { EvalRow, Evaluation, Stage } from '../api'
import { Load, SectionTitle } from '../components'
import { useApi } from '../hooks'
import { pct, STAGE_LABEL } from '../format'

const MODEL_LABEL: Record<string, string> = {
  logreg: 'Logistic regression',
  lgbm: 'Gradient boosting (LightGBM)',
  'B1 pole wins': 'Pole-sitter wins',
  'B1p P(win | grid)': 'Pole-sitter, calibrated by grid slot',
  'B2 leader wins': 'Championship leader wins',
  'B2p P(win | standings)': 'Leader, calibrated by standings',
}
const label = (m: string) => MODEL_LABEL[m] ?? m
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
            <p className="mb-2 font-mono text-[0.7rem] tracking-[0.12em] text-muted uppercase">
              {w} · {ws[0]?.races} races
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-ink font-mono text-[0.68rem] tracking-[0.12em] text-muted uppercase">
                    <th className="py-2 text-left font-medium">Predictor</th>
                    <th className="w-[35%] py-2 text-left font-medium">Winner picked</th>
                    <th className="py-2 text-right font-medium">Podium</th>
                    <th className="py-2 text-right font-medium" title="−log P(actual winner); lower is better">
                      Log-loss
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ws.map((r) => {
                    const base = isBaseline(r.model)
                    return (
                      <tr key={r.model} className="border-b border-rule">
                        <td className={`py-2 ${base ? 'text-muted' : 'font-semibold'}`}>{label(r.model)}</td>
                        <td className="py-2">
                          <div className="flex items-center gap-3">
                            <div className="h-2.5 w-full rounded-sm bg-stripe">
                              <div
                                className={`bar h-full rounded-sm ${base ? 'bg-muted/50' : 'bg-purple'}`}
                                style={{ width: `${(r.winner_acc / maxAcc) * 100}%` }}
                              />
                            </div>
                            <span className="w-12 text-right font-mono tabular">{pct(r.winner_acc, 0)}</span>
                          </div>
                        </td>
                        <td className="py-2 text-right font-mono tabular">{pct(r.podium_hit, 0)}</td>
                        <td className="py-2 text-right font-mono tabular">
                          {isDeterministic(r.model) ? <span className="text-muted">{r.logloss_win.toFixed(2)}*</span> : r.logloss_win.toFixed(2)}
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
      <p className="font-mono text-[0.7rem] text-muted">
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
    <div className="space-y-10">
      <section>
        <SectionTitle eyebrow="Method">How the predictions are made</SectionTitle>
        <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
          {STEPS.map(([t, d]) => (
            <div key={t} className="border-t border-rule pt-3">
              <dt className="font-display text-lg font-bold uppercase">{t}</dt>
              <dd className="text-sm text-muted">{d}</dd>
            </div>
          ))}
        </dl>
      </section>
      <Load value={ev} missing={<p className="text-sm text-muted">Evaluation not published yet.</p>}>
        {(e) => (
          <>
            {(['t2', 't1'] as Stage[]).map((s) => (
              <section key={s}>
                <SectionTitle eyebrow={`Chosen: ${label(e.chosen[s].kind)}`}>
                  {STAGE_LABEL[s]} vs baselines
                </SectionTitle>
                <Results rows={e.holdout} stage={s} />
              </section>
            ))}
          </>
        )}
      </Load>
    </div>
  )
}
