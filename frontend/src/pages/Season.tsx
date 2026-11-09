import type { Race } from '../api'
import { Load, SectionTitle } from '@/components/core'
import { useApi } from '../hooks'
import { formatLocal } from '../format'

export default function Season() {
  const races = useApi<Race[]>('/races?season=2026')
  return (
    <Load value={races}>
      {(rs) => {
        const done = rs.filter((r) => r.status === 'done' && r.winner)
        const fromPole = done.filter((r) => r.winner?.grid === 1).length
        const wins = new Map<string, { name: string; team: string; n: number }>()
        for (const r of done) {
          const w = r.winner!
          const cur = wins.get(w.driver_id) ?? { name: w.name ?? w.driver_id, team: w.team ?? '', n: 0 }
          wins.set(w.driver_id, { ...cur, n: cur.n + 1 })
        }
        const ranking = [...wins.values()].sort((a, b) => b.n - a.n)
        const max = ranking[0]?.n ?? 1
        return (
          <div className="grid gap-10 md:grid-cols-[1fr_280px]">
            <section>
              <SectionTitle eyebrow={`${done.length} of ${rs.length} rounds run`}>2026 calendar</SectionTitle>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[480px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-ink font-mono text-[0.68rem] tracking-[0.12em] text-muted uppercase">
                      <th className="py-2 text-left font-medium">Rd</th>
                      <th className="py-2 text-left font-medium">Grand Prix</th>
                      <th className="py-2 text-left font-medium">Winner</th>
                      <th className="py-2 text-right font-medium">From grid</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rs.map((r, i) => (
                      <tr key={r.round} className={`border-b border-rule ${i % 2 ? 'bg-stripe/60' : ''}`}>
                        <td className="py-2 font-mono tabular text-muted">{String(r.round).padStart(2, '0')}</td>
                        <td className="py-2">
                          {r.race_name.replace(' Grand Prix', '')}
                          {r.is_sprint_weekend && (
                            <span className="ml-2 font-mono text-[0.65rem] text-muted uppercase">sprint</span>
                          )}
                        </td>
                        <td className="py-2">
                          {r.winner ? (
                            <>
                              <span className="font-mono font-semibold">{r.winner.code}</span>{' '}
                              <span className="text-muted">{r.winner.team}</span>
                            </>
                          ) : (
                            <span className="font-mono text-[0.75rem] text-muted">{formatLocal(r.race_start_utc)}</span>
                          )}
                        </td>
                        <td
                          className={`py-2 text-right font-mono tabular ${r.winner?.grid === 1 ? 'text-purple' : ''}`}
                        >
                          {r.winner ? (r.winner.grid === 1 ? 'P1' : `P${r.winner.grid ?? '?'}`) : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <aside className="space-y-8">
              <div>
                <SectionTitle eyebrow="Pole-to-win">From pole</SectionTitle>
                <p className="font-display text-6xl font-extrabold text-purple tabular">
                  {fromPole}
                  <span className="text-3xl text-muted">/{done.length}</span>
                </p>
                <p className="text-sm text-muted">
                  races won from P1 in 2026, which is why "the pole-sitter wins" is the baseline the model has to
                  beat.
                </p>
              </div>
              <div>
                <SectionTitle eyebrow="Wins">Drivers</SectionTitle>
                <ul className="space-y-2">
                  {ranking.map((w) => (
                    <li key={w.name}>
                      <div className="flex justify-between text-sm">
                        <span>{w.name}</span>
                        <span className="font-mono tabular">{w.n}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-sm bg-stripe">
                        <div className="bar h-full rounded-sm bg-ink/70" style={{ width: `${(w.n / max) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </aside>
          </div>
        )
      }}
    </Load>
  )
}
