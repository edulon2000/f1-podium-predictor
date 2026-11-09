// Types mirror the FastAPI response models (src/f1pred/api/app.py).

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

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (res.status === 404) throw new NotFound(path)
  if (!res.ok) throw new Error(`${res.status} on ${path}`)
  return res.json() as Promise<T>
}
