# Features and baselines

> **Status (2026-11-08):** implemented in `src/f1pred/features.py` (column lists `T1_FEATURES`,
> `T2_FEATURES`) and evaluated in [reports/EVALUATION.md](../reports/EVALUATION.md). Not built yet:
> #13 weather forecast. Practice pace (#11) uses OpenF1 from 2023 on.

Target, per race: P(driver wins) and P(driver finishes on the podium), for every driver on the
entry list. Prediction is made at two moments, which define two feature sets:

- **T1 — before qualifying** (Thursday/Friday, after practice): predicts without the grid.
- **T2 — after qualifying** (Saturday night): adds grid and qualifying pace.

Every feature for race *(season, round)* must be computed only from rounds `< round` of the same
season and from earlier seasons, plus the T1/T2 information of that weekend. In code: group by
driver/constructor, sort by `(season, round)`, then `shift(1)` before any rolling window.
See the leakage tags in [DATA_MAP.md](DATA_MAP.md).

## T1 — available before qualifying

| # | Feature | Source | Notes |
|---|---|---|---|
| 1 | Driver championship position, points, gap to leader, wins (after round r-1) | `driver_standings` | Must join on `round = r-1`. For round 1, use previous season's final standings, flagged with `is_round_1` |
| 2 | Constructor championship position, points, gap to leader | `constructor_standings` | Same `r-1` join |
| 3 | Driver form: EWMA finish position, points/race, podium rate over the last 3/5 races | `results` | `shift(1)`; DNFs as position 20 + separate DNF rate |
| 4 | Constructor form: best car finish EWMA, combined points/race this season | `results` | Captures car competitiveness, which matters most under new rules |
| 5 | Qualifying form: mean qualifying position this season, Q3 rate, teammate head-to-head | `qualifying` | A strong proxy for raw car pace |
| 6 | Reliability: driver and constructor DNF rate (mechanical `status` only) | `results.status` | Needs a status → {mechanical, accident, other} mapping |
| 7 | Circuit history: driver/team mean finish at this `circuit_id`, past wins there | `results` + `races` | Sparse: Las Vegas only since 2023, Qatar since 2021, Abu Dhabi since 2009 |
| 8 | Circuit character: historical pole-to-win rate and grid↔finish correlation at the circuit | `results` | Use as an interaction with grid at T2. Street vs permanent comes from OpenF1 `circuit_type` |
| 9 | Regulation era (`2014–21`, `2022–25`, `2026`), rounds since rule change | `races.season` | Also used as **sample weights** (e.g. 2026 ×3, 2022–25 ×1.5, older ×1, to be tuned) |
| 10 | Sprint weekend flag; sprint result when the sprint runs before GP qualifying (2023+ format) | `races`, `sprint_results` | In 2021–22 the sprint set the grid, so it counts as T2 |
| 11 | Practice pace: best FP lap gap to fastest (%), long-run pace from stints | OpenF1 `laps`/`stints` | 2023+ only → feature is missing for older rows (model must tolerate NaN) |
| 12 | Driver experience: races started, age at race date | `results`, `drivers` | Weak, but cheap |
| 13 | Weather forecast: rain probability, track temperature | External forecast API (not in Phase 1) | Only actual weather exists historically (OpenF1 2023+), so forecast vs actual differ; Phase 3 |

## T2 — available after qualifying (all of T1, plus)

| # | Feature | Source | Notes |
|---|---|---|---|
| 14 | Grid position, front row, pit-lane start (`grid = 0`) | `results.grid` | **Availability lag**: Jolpica publishes grid with the race result (null for Brazil 2026 hours after the race). At prediction time take it from OpenF1 `starting_grid` (quali `session_key`) |
| 15 | Qualifying position, gap to pole in % (best of Q1/Q2/Q3), reached Q3 | `qualifying` | Gap in % normalises across circuits |
| 16 | Grid penalty = grid − qualifying position | `results` + `qualifying` | Penalties often also signal new PU parts (a reliability risk) |
| 17 | Teammate qualifying gap (%) | `qualifying` | Isolates driver from car |
| 18 | Interaction: grid × circuit pole-win rate (#8) | derived | P1 at Monaco ≠ P1 at Monza |
| 19 | Sprint result in the 2021–22 format (it set the grid) | `sprint_results` | |

## Never features (post-race → leakage)

`results.position`, `position_text`, `points`, `status`, `laps`, `time_millis`, all `fastest_lap_*`;
standings of the same round; anything aggregated over the full season (for example "final
constructor ranking"). Full list in DATA_MAP.md.

## Baselines

Both are evaluated walk-forward on every race in 2014–2026, reported per era and for 2026 alone.

**B1 — "Pole wins"** (T2)
- Winner = driver with `grid == 1`. If grid isn't published, use `qualifying.position == 1`.
- Podium = grid positions 1–2–3, in that order.
- Reference value: 13 of the 19 races in 2026 so far with known grid (68%) were won from pole.

**B2 — "Championship leader wins"** (T1)
- Winner = leader of `driver_standings` after round r-1. Round 1 uses the previous season's
  champion, which is a weak choice in 2026 because of the rule change, so it's reported separately.
- Podium = standings positions 1–2–3.

## Metrics

- **Winner top-1 accuracy**: directly comparable to both baselines.
- **Podium hit rate**: mean of |predicted top-3 ∩ actual top-3| / 3. Also report the exact-order rate.
- **Log-loss / Brier score** on P(win), with probabilities normalised to sum to 1 within each race.
  This rewards being confident when it's justified, which top-1 accuracy ignores.
- **Calibration plot** of P(win).

## Model sketch for Phase 2 (for discussion)

- One row per driver per race, binary targets `win` and `podium`. Gradient boosting
  (LightGBM/XGBoost) with per-race softmax normalisation, or a ranking objective (LambdaRank)
  grouped by race.
- Walk-forward validation: train on everything before race r, predict r. Never use random K-fold.
- For Las Vegas, Qatar and Abu Dhabi: freeze and commit the T1 prediction on Friday and the T2
  prediction on Saturday, before each race, with a timestamp. That makes the out-of-sample record
  verifiable on the portfolio.
