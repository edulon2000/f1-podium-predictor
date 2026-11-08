import { NavLink, Route, Routes } from 'react-router-dom'
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

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-rule bg-sheet">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <NavLink to="/" className="font-display text-xl font-extrabold tracking-wide uppercase">
            Podium<span className="text-purple">/</span>Predictor
          </NavLink>
          <nav aria-label="Main">
            <ul className="flex flex-wrap gap-1 font-mono text-[0.72rem] tracking-[0.08em] uppercase">
              {NAV.map((n) => (
                <li key={n.to}>
                  <NavLink
                    to={n.to}
                    end={n.to === '/'}
                    className={({ isActive }) =>
                      `block rounded px-2.5 py-1.5 ${isActive ? 'bg-ink text-sheet' : 'text-muted hover:text-ink'}`
                    }
                  >
                    {n.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <Routes>
          <Route path="/" element={<NextRace />} />
          <Route path="/track-record" element={<TrackRecord />} />
          <Route path="/season" element={<Season />} />
          <Route path="/model" element={<Model />} />
          <Route path="*" element={<p className="text-muted">Page not found.</p>} />
        </Routes>
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-5xl flex-wrap justify-between gap-2 px-4 py-5 font-mono text-[0.7rem] text-muted">
          <span>Data: Jolpica-F1 (results since 2014) · OpenF1 (sessions since 2023)</span>
          <span>Unofficial project, not associated with Formula 1.</span>
        </div>
      </footer>
    </div>
  )
}
