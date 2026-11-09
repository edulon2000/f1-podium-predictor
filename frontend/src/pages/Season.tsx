import { useNavigate } from 'react-router-dom'
import type { Race } from '@/api'
import { Load, SectionTitle } from '@/components/core'
import { useApi } from '@/hooks'
import { formatLocal, startedText, surname, teamColour } from '@/format'
import { EXPLAIN, Tip } from '@/components/Tip'

export default function Season() {
  const races = useApi<Race[]>('/races?season=2026')
  const navigate = useNavigate()
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
          <div className="grid gap-12 lg:grid-cols-[1fr_300px]">
            <section>
              <SectionTitle eyebrow={`${done.length} of ${rs.length} rounds run`}>2026 calendar</SectionTitle>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] border-collapse">
                  <thead>
                    <tr className="label border-b border-night">
                      <th className="py-2 text-left font-medium">Round</th>
                      <th className="py-2 text-left font-medium">Grand Prix</th>
                      <th className="py-2 text-left font-medium">Winner</th>
                      <th className="py-2 text-right font-medium"><Tip text={EXPLAIN.started} align="right">Winner started</Tip></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rs.map((r) => {
                      const pole = r.winner?.grid === 1
                      const linkable = r.status === 'done' || r.prediction_stages.length > 0
                      const go = () => linkable && navigate(`/race/${r.season}/${r.round}`)
                      return (
                        <tr
                          key={r.round}
                          tabIndex={linkable ? 0 : -1}
                          onClick={go}
                          onKeyDown={(e) => e.key === 'Enter' && go()}
                          className={`group border-b border-rule transition-colors duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] hover:bg-sun focus-visible:bg-sun ${
                            r.status === 'upcoming' ? 'text-earth' : ''
                          } ${linkable ? 'cursor-pointer' : ''}`}
                        >
                          <td className="py-2 font-mono text-sm tabular text-earth">{r.round}</td>
                          <td className="narrow py-2 text-2xl font-extrabold uppercase sm:text-3xl">
                            {r.race_name.replace(' Grand Prix', '')}
                            {r.is_sprint_weekend && <span className="label ml-2 align-middle">sprint</span>}
                          </td>
                          <td className="py-2">
                            {r.winner ? (
                              <span className="inline-flex items-center gap-2">
                                <span className="h-5 w-1 rounded-sm" style={{ background: teamColour(teamId(r.winner.team)) }} />
                                <span className="font-semibold">{surname(r.winner.name, null)}</span>
                                <span className="hidden text-sm text-earth sm:inline">{r.winner.team}</span>
                              </span>
                            ) : (
                              <span className="font-mono text-[0.75rem]">{formatLocal(r.race_start_utc)}</span>
                            )}
                          </td>
                          <td className="py-2 text-right font-mono tabular">
                            {r.winner &&
                              (pole ? (
                                <span className="rounded bg-sun px-1.5 py-0.5 group-hover:bg-night group-hover:text-sun">Pole</span>
                              ) : (
                                startedText(r.winner.grid)
                              ))}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </section>
            <aside className="space-y-10">
              <div>
                <p className="label"><Tip text="Races won by the driver who started first.">Won from pole</Tip></p>
                <p className="narrow text-[7rem] leading-[0.85] font-extrabold tabular">
                  {fromPole}
                  <span className="text-5xl text-earth">/{done.length}</span>
                </p>
                <p className="mt-2 text-sm text-earth">
                  races won from pole in 2026, which is why “the pole-sitter wins” is the baseline the model has to beat.
                </p>
              </div>
              <div>
                <p className="label mb-3">Wins by driver</p>
                <ul className="space-y-3">
                  {ranking.map((w) => (
                    <li key={w.name}>
                      <div className="flex items-baseline justify-between">
                        <span className="text-sm">{w.name}</span>
                        <span className="narrow text-2xl font-extrabold tabular">{w.n}</span>
                      </div>
                      <div className="mt-1 h-2 rounded-full bg-paper">
                        <div className="bar h-full rounded-full bg-sand" style={{ width: `${(w.n / max) * 100}%` }} />
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

// Winner objects carry the team name; map the common ones back to an id for the colour stripe.
function teamId(team?: string) {
  const t = (team ?? '').toLowerCase()
  if (t.includes('red bull')) return 'red_bull'
  if (t.includes('mercedes')) return 'mercedes'
  if (t.includes('ferrari')) return 'ferrari'
  if (t.includes('mclaren')) return 'mclaren'
  return t.replace(/\s+/g, '_')
}
