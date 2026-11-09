import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide'
import type { DriverPrediction, Prediction } from '@/api'
import { pct, STAGE_LABEL, startedText, surname, teamColour } from '@/format'
import { FocusField } from './microkit/focus-input'
import { Morph } from './Morph'
import { EXPLAIN, Tip } from './Tip'

type SortKey = 'p_win' | 'p_podium'

// Defined outside the table so it is not re-created on each render (that would remount
// the morphing icon and skip its animation).
function SortButton({ active, desc, onClick, children }: { active: boolean; desc: boolean; onClick: () => void; children: string }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 uppercase ${active ? 'text-night' : 'text-earth hover:text-night'}`}
      aria-label={`Sort by ${children}`}
    >
      {children}
      <span className={active ? 'opacity-100' : 'opacity-0'}>
        <Morph icon={desc ? ArrowDown : ArrowUp} size={12} strokeWidth={2.25} />
      </span>
    </button>
  )
}

/** Large condensed rows; the model's pick is marked in sun. Filterable and sortable. */
export function PredictionTable({ prediction }: { prediction: Prediction }) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<SortKey>('p_win')
  const [desc, setDesc] = useState(true)
  const pick = prediction.predictions[0]?.driver_id
  const maxWin = Math.max(...prediction.predictions.map((p) => p.p_win))
  const showGrid = prediction.stage === 't2'

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    const filtered = prediction.predictions.filter(
      (p) => !q || [p.name, p.code, p.team, p.driver_id].some((v) => v?.toLowerCase().includes(q)),
    )
    return [...filtered].sort((a, b) => (desc ? b[sort] - a[sort] : a[sort] - b[sort]))
  }, [prediction, query, sort, desc])

  const rank = new Map(prediction.predictions.map((p, i) => [p.driver_id, i + 1]))
  const sortBy = (k: SortKey) => () => (sort === k ? setDesc(!desc) : (setSort(k), setDesc(true)))

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <FocusField label="Find a driver" value={query} onChange={setQuery} placeholder="Name or team" />
        <p className="label">
          {rows.length} of {prediction.predictions.length} drivers
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse">
          <caption className="sr-only">
            {prediction.race_name}, {STAGE_LABEL[prediction.stage]}: probability of winning and of a podium per driver
          </caption>
          <thead>
            <tr className="label border-b border-night">
              <th className="py-2 pr-2 text-left font-medium"><Tip text={EXPLAIN.rank}>Rank</Tip></th>
              <th className="py-2 pr-3 text-left font-medium">Driver</th>
              {showGrid && <th className="py-2 pr-3 text-right font-medium"><Tip text={EXPLAIN.started}>Starts</Tip></th>}
              <th className="w-[36%] py-2 pr-3 text-left font-medium">
                <Tip text={EXPLAIN.chanceWin}>
                  <SortButton active={sort === 'p_win'} desc={desc} onClick={sortBy('p_win')}>Chance to win</SortButton>
                </Tip>
              </th>
              <th className="py-2 text-right font-medium">
                <Tip text={EXPLAIN.chancePodium} align="right">
                  <SortButton active={sort === 'p_podium'} desc={desc} onClick={sortBy('p_podium')}>Chance of podium</SortButton>
                </Tip>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p: DriverPrediction, i) => {
              const isPick = p.driver_id === pick
              return (
                <tr
                  key={p.driver_id}
                  className={`group border-b border-rule transition-colors duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] hover:bg-sun ${
                    isPick ? 'bg-sun/45' : ''
                  }`}
                >
                  <td className="py-2.5 pr-2 font-mono text-sm tabular text-earth">
                    {String(rank.get(p.driver_id)).padStart(2, '0')}
                  </td>
                  <td className="py-2.5 pr-3">
                    <div className="flex items-center gap-3">
                      <span className="h-7 w-1 rounded-sm" style={{ background: teamColour(p.constructor_id) }} />
                      <span className="flex flex-col">
                        <span className="narrow text-2xl leading-none font-extrabold uppercase sm:text-3xl">
                          {surname(p.name, p.family_name)}
                        </span>
                        <span className="text-[12px] text-earth group-hover:text-night">
                          {p.name} · {p.team}
                        </span>
                      </span>
                    </div>
                  </td>
                  {showGrid && <td className="py-2.5 pr-3 text-right font-mono text-sm">{startedText(p.grid)}</td>}
                  <td className="py-2.5 pr-3">
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-full rounded-full bg-paper group-hover:bg-stone/70" aria-hidden>
                        <div
                          className={`bar h-full rounded-full ${isPick ? 'bg-night' : 'bg-night/55'}`}
                          style={{ width: `${(p.p_win / maxWin) * 100}%`, animationDelay: `${i * 30}ms` }}
                        />
                      </div>
                      <span className={`w-14 text-right font-mono tabular ${isPick ? 'font-semibold' : ''}`}>{pct(p.p_win)}</span>
                    </div>
                  </td>
                  <td className="py-2.5 text-right font-mono tabular">
                    <span className="inline-flex items-center gap-2">
                      <span className="hidden h-2 w-12 rounded-full bg-paper sm:inline-block" aria-hidden>
                        <span className="bar block h-full rounded-full bg-sand" style={{ width: `${p.p_podium * 100}%` }} />
                      </span>
                      {pct(p.p_podium, 0)}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {rows.length === 0 && <p className="py-6 text-sm text-earth">No driver matches “{query}”. Clear the filter to see all.</p>}
      </div>
    </div>
  )
}
