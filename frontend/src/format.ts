// Approximate team colours, used only as a thin identification stripe.
export const TEAM_COLOURS: Record<string, string> = {
  mercedes: '#27c4b4',
  ferrari: '#d40f1f',
  red_bull: '#2b3f8f',
  mclaren: '#f28c18',
  aston_martin: '#1b6b4f',
  alpine: '#2a8be0',
  williams: '#1e5bc6',
  rb: '#6c8ff0',
  haas: '#9aa0a6',
  sauber: '#3ba845',
  audi: '#8a8f94',
  cadillac: '#c6a64a',
}

export const teamColour = (id: string) => TEAM_COLOURS[id] ?? '#9aa0a6'

export const pct = (p: number, digits = 1) => `${(p * 100).toFixed(digits)}%`

export function formatLocal(iso?: string | null, opts?: Intl.DateTimeFormatOptions) {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    ...opts,
  }).format(new Date(iso))
}

export function formatUtc(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

export function countdownParts(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000))
  return {
    days: Math.floor(s / 86400),
    hours: Math.floor((s % 86400) / 3600),
    minutes: Math.floor((s % 3600) / 60),
    seconds: s % 60,
  }
}

export const STAGE_LABEL = {
  t1: 'Before qualifying',
  t2: 'After qualifying',
} as const

export function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`
}

/** "Pole", "2nd", "Pit lane"… for a starting position. */
export function startedText(grid?: number | null) {
  if (grid === null || grid === undefined) return 'Unknown'
  if (grid === 0) return 'Pit lane'
  return grid === 1 ? 'Pole' : ordinal(grid)
}

export const surname = (name?: string | null, family?: string | null) =>
  family ?? (name ? name.split(' ').slice(-1)[0] : '')
