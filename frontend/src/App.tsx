import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide'
import { Morph } from '@/components/Morph'
import NextRace from './pages/NextRace'
import TrackRecord from './pages/TrackRecord'
import Season from './pages/Season'
import Model from './pages/Model'

const NAV = [
  { to: '/', label: 'Next race' },
  { to: '/track-record', label: 'Track record' },
  { to: '/season', label: '2026 season' },
  { to: '/model', label: 'How it works' },
]

function NavItems({ onPick }: { onPick?: () => void }) {
  return (
    <>
      {NAV.map((n) => (
        <li key={n.to}>
          <NavLink
            to={n.to}
            end={n.to === '/'}
            onClick={onPick}
            className={({ isActive }) =>
              `block rounded-full px-3 py-1.5 transition-colors duration-[320ms] ease-[cubic-bezier(.22,1,.36,1)] ${
                isActive ? 'bg-night text-stone' : 'text-night hover:bg-paper'
              }`
            }
          >
            {n.label}
          </NavLink>
        </li>
      ))}
    </>
  )
}

export default function App() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => setOpen(false), [pathname])

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-rule bg-stone/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <NavLink to="/" className="wide text-base font-extrabold tracking-tight uppercase">
            Podium<span className="mx-0.5 rounded-sm bg-sun px-1">/</span>Predictor
          </NavLink>
          <nav aria-label="Main" className="hidden md:block">
            <ul className="flex gap-1 font-mono text-[0.7rem] tracking-[0.08em] uppercase">
              <NavItems />
            </ul>
          </nav>
          <button
            className="rounded-full border border-night p-2 md:hidden"
            aria-expanded={open}
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            <Morph icon={open ? X : Menu} />
          </button>
        </div>
        {open && (
          <nav id="mobile-nav" aria-label="Main" className="border-t border-rule px-4 py-3 md:hidden">
            <ul className="flex flex-col gap-1 font-mono text-[0.75rem] tracking-[0.08em] uppercase">
              <NavItems onPick={() => setOpen(false)} />
            </ul>
          </nav>
        )}
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">
        <Routes>
          <Route path="/" element={<NextRace />} />
          <Route path="/track-record" element={<TrackRecord />} />
          <Route path="/season" element={<Season />} />
          <Route path="/model" element={<Model />} />
          <Route path="*" element={<p className="text-earth">Page not found.</p>} />
        </Routes>
      </main>

      <footer className="relative mt-10 border-t border-rule">
        <div aria-hidden className="dots absolute inset-x-0 bottom-full h-16" />
        <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-2 px-4 py-5 font-mono text-[0.68rem] text-earth">
          <span>Data: Jolpica-F1 (results since 2014) · OpenF1 (sessions since 2023)</span>
          <a className="underline underline-offset-2 hover:text-night" href="https://github.com/edulon2000/f1-podium-predictor">
            Source on GitHub
          </a>
          <span>Unofficial project, not associated with Formula 1.</span>
        </div>
      </footer>
    </div>
  )
}
