// Types mirror the exported JSON (src/f1pred/export.py) and the FastAPI models (src/f1pred/api/app.py).

export type Stage = 't1' | 't2'

export interface Winner {
  driver_id: string
  name?: string
  code?: string
  team?: string
  grid?: number | null
}

export interface Race {
  season: number
  round: number
  race_name: string
  circuit_id: string
  circuit_name?: string
  locality?: string
  country?: string
  race_start_utc?: string
  quali_utc?: string
  fp1_utc?: string
  is_sprint_weekend: boolean
  status: 'done' | 'upcoming'
  winner?: Winner | null
  pole_driver_id?: string | null
  prediction_stages: Stage[]
}

export interface DriverPrediction {
  driver_id: string
  constructor_id: string
  name?: string
  family_name?: string
  code?: string
  team?: string
  p_win: number
  p_podium: number
  grid?: number | null
}

export interface Prediction {
  season: number
  round: number
  race_name: string
  stage: Stage
  generated_at: string
  race_start_utc: string
  model: { kind: string; params?: Record<string, unknown>; same_era_weight?: number }
  train_races: number
  train_until: string
  warnings: string[]
  predictions: DriverPrediction[]
}

export interface ScoreRow {
  race: string
  season: number
  round: number
  stage: Stage
  predicted: string
  actual: string
  p_actual_winner: number
  winner_correct: boolean
  podium_hit: number
  pole_won: boolean
}

export interface BacktestRow {
  season: number
  round: number
  predicted: string
  p_predicted: number
  actual: string | null
  p_actual: number | null
  predicted_podium: string[]
  top3?: string[]
  actual_podium: string[]
  pole_won: boolean
}

export interface EvalRow {
  stage: Stage
  window: string
  model: string
  winner_acc: number
  winner_top3?: number
  role?: 'chosen' | 'best base' | 'baseline'
  feature_set?: string
  podium_hit: number
  logloss_win: number
  brier_win: number
  races: number
  same_era_weight?: number
}

export interface Evaluation {
  chosen: Record<Stage, { kind: string; params: Record<string, unknown>; same_era_weight: number }>
  holdout: EvalRow[]
}

export interface DriverInfo {
  driver_id: string
  name: string
  family_name: string
  code: string | null
  number: number | null
}

export interface Reason {
  feature: string
  label: string
  effect: number
}

export interface StageDetail {
  model: { kind: string; params?: Record<string, unknown>; same_era_weight?: number }
  train_races: number
  favourite: string
  favourite_reasons: Reason[]
  winner_reasons: Reason[] | null
}

export interface DriverDetail {
  driver_id: string
  name: string
  family_name: string
  code: string | null
  constructor_id: string
  team: string
  grid: number | null
  finish: number | null
  status: string | null
  points: number | null
  quali_position: number | null
  quali_gap_pct: number | null
  practice_best_gap_pct: number | null
  practice_longrun_gap_pct: number | null
  t1_p_win?: number | null
  t1_p_podium?: number | null
  t1_rank?: number
  t2_p_win?: number | null
  t2_p_podium?: number | null
  t2_rank?: number
}

export interface RaceDetail {
  season: number
  round: number
  race_name: string
  circuit_name: string | null
  locality: string | null
  country: string | null
  race_start_utc: string | null
  is_sprint_weekend: boolean
  weather: Record<string, number | boolean | string | null> | null
  status: 'done' | 'upcoming'
  kind: 'backtest' | 'live'
  drivers: DriverDetail[]
  stages: Partial<Record<Stage, StageDetail>>
  live: Partial<Record<Stage, { generated_at: string; predictions: DriverPrediction[] }>>
}

export class NotFound extends Error {}

/**
 * The site is static: the exported JSON (site_data/) is published under /data next to the
 * front. These routes keep the old API paths so pages did not have to change.
 */
const pad2 = (n: string) => n.padStart(2, '0')
const ROUTES: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^\/races\?season=(\d+)$/, (m) => `races_${m[1]}.json`],
  [/^\/races\/(\d+)\/(\d+)\/predictions\?stage=(t[12])$/, (m) => `predictions/${m[1]}_R${pad2(m[2])}_${m[3]}.json`],
  [/^\/races\/(\d+)\/(\d+)\/detail$/, (m) => `races/${m[1]}_R${pad2(m[2])}.json`],
  [/^\/backtest\/(\d+)$/, (m) => `backtest_${m[1]}.json`],
  [/^\/(scoreboard|evaluation|drivers|meta)$/, (m) => `${m[1]}.json`],
]

export function dataFile(path: string): string {
  for (const [re, file] of ROUTES) {
    const m = path.match(re)
    if (m) return `/data/${file(m)}`
  }
  throw new NotFound(path)
}

async function getFile<T>(path: string): Promise<T> {
  const url = dataFile(path)
  const res = await fetch(url, { cache: 'no-cache' })
  // A static host answers a missing file with the SPA's index.html (200, text/html): treat as 404.
  const isJson = (res.headers.get('content-type') ?? '').includes('json')
  if (res.status === 404 || (res.ok && !isJson)) throw new NotFound(path)
  if (!res.ok) throw new Error(`${res.status} on ${url}`)
  return res.json() as Promise<T>
}

export async function get<T>(path: string): Promise<T> {
  if (path === '/races/next') {
    const next = (await getFile<Race[]>('/races?season=2026')).find((r) => r.status === 'upcoming')
    if (!next) throw new NotFound(path)
    return next as T
  }
  return getFile<T>(path)
}
