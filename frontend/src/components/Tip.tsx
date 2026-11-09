import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

/**
 * Plain-language explanation next to a label. Opens on hover, keyboard focus or tap, closes on
 * Escape / outside tap. The text is linked with aria-describedby so screen readers read it.
 */
export function Tip({ text, children, align = 'left' }: { text: string; children?: ReactNode; align?: 'left' | 'right' }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onDown = (e: PointerEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open])

  return (
    <span
      ref={ref}
      className="relative inline-flex items-center gap-1"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children}
      <button
        type="button"
        aria-describedby={id}
        aria-label="What does this mean?"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex size-[15px] shrink-0 items-center justify-center rounded-full border border-current font-mono text-[9px] leading-none normal-case opacity-60 transition-opacity duration-[320ms] hover:opacity-100 focus-visible:opacity-100"
      >
        ?
      </button>
      <span
        role="tooltip"
        id={id}
        className={`pointer-events-none absolute top-full z-30 mt-2 w-64 rounded-md bg-night px-3 py-2 text-left font-sans text-[12.5px] leading-snug font-normal tracking-normal text-stone normal-case shadow-lg transition-[opacity,transform] duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] ${
          align === 'right' ? 'right-0' : 'left-0'
        } ${open ? 'translate-y-0 opacity-100' : '-translate-y-1 opacity-0'}`}
      >
        {text}
      </span>
    </span>
  )
}

/** One source of truth for the explanations shown in tooltips and in the glossary. */
export const EXPLAIN = {
  chanceWin:
    'How likely the model thinks this driver is to win. All drivers add up to 100%. 30% means: in races like this one, this driver wins about 3 times in 10.',
  chancePodium:
    'How likely the driver is to finish in the top three. All drivers add up to 300%, because there are three places on the podium.',
  rank: 'Order of the drivers from the most to the least likely to win.',
  started: 'Where the driver started the race. Pole means first on the grid.',
  favourite: 'The driver the model gave the highest chance of winning.',
  winner: 'Who actually won the race.',
  chanceGivenToWinner:
    'The chance the model had given to the driver who actually won. High is good: even when the favourite loses, a good forecast still gives the real winner a decent chance.',
  podiumGuessed: 'Of the three drivers the model expected on the podium, how many really finished there.',
  pickedWinner: 'Share of races where the model’s favourite won.',
  winnerTop3: 'Share of races where the winner was one of the three drivers the model rated most likely to win.',
  confidenceScore:
    'Log-loss: measures how much chance the model gave to the real winner, on average. Lower is better. 0.69 ≈ 50% to the winner, 1.2 ≈ 30%, 2.3 ≈ 10%.',
  holdout:
    'Races the model was not tuned on. Each one was predicted using only earlier races, so this is a fair test.',
  backtest:
    'A replay: each past race predicted again with a model trained only on the races before it. Not published in advance.',
  stage:
    'Before qualifying uses form, standings and practice. After qualifying also knows the starting grid, which makes it much more accurate.',
  baseline: 'A simple rule the model has to beat, like “the driver on pole wins”.',
} as const
