# Data map

Tables written by `uv run f1pred-ingest` to `data/processed/*.parquet` (source: Jolpica-F1).
The row counts and gaps below come from the run summarised in `data/processed/ingest_report.json`.

## Leakage tags

Every column gets one tag, from the point of view of **predicting race (season, round)**:

| Tag | Meaning | Can be a feature? |
|---|---|---|
| `KEY` | Identifier / join key | Used for joins (circuit and team IDs can also be categorical features) |
| `PRE-QUALI` | Known before qualifying (calendar, profile, history) | ✅ T1 and T2 |
| `PRE-RACE` | Known after qualifying, before lights out | ✅ T2 only |
| `POST-RACE` | Only known once the race has run | ❌ Same round: leakage. ✅ Previous rounds (lagged) |

**The general rule:** any `POST-RACE` value from round *r* turns into `PRE-QUALI` information
for round *r+1* onwards. Every lagged feature has to be built with
`groupby(...).shift(1)` after sorting by `(season, round)`.

## Join keys

```
races (season, round) ──┬── results            (season, round, driver_id)
   │ circuit_id          ├── qualifying         (season, round, driver_id)
   ▼                     ├── sprint_results     (season, round, driver_id)
circuits                 ├── driver_standings   (season, round, driver_id)   ← AFTER the round
                         └── constructor_standings (season, round, constructor_id) ← AFTER the round
drivers (driver_id)   constructors (constructor_id)
```

- `season` + `round` identify a GP. `round` is the official race number within the season.
- `driver_id` and `constructor_id` are Ergast slugs (`max_verstappen`, `red_bull`). They stay the
  same across seasons for the same driver. Constructor IDs change when a team rebrands, e.g.
  `alphatauri` → `rb`, `alfa` → `sauber`. Mapping teams across rebrands is Phase 2 work.
- **Standings trap:** `driver_standings` at `(s, r)` is the table **after** race r. To predict
  race r, join standings on `round = r - 1`.
- OpenF1, if it's used later, identifies drivers by `driver_number` and sessions by
  `session_key`/`meeting_key`. Joining it needs a `(season, driver_number) → driver_id` map,
  built from `results.number`.

## Tables

### `races`: one row per scheduled GP (season, round)

| Column | Type | Tag | Notes |
|---|---|---|---|
| season, round | int | KEY | |
| race_name | str | PRE-QUALI | |
| circuit_id | str | KEY / PRE-QUALI | → `circuits` |
| race_date | str (YYYY-MM-DD) | PRE-QUALI | |
| race_start_utc | timestamp UTC | PRE-QUALI | Scheduled start time |
| fp1_utc, fp2_utc, fp3_utc | timestamp UTC | PRE-QUALI | Null when that session doesn't exist (sprint weekends have FP1 only from 2023) |
| quali_utc | timestamp UTC | PRE-QUALI | |
| sprint_quali_utc, sprint_utc | timestamp UTC | PRE-QUALI | SprintShootout (2023) and SprintQualifying (2024+) are merged into `sprint_quali_utc` |
| is_sprint_weekend | bool | PRE-QUALI | |
| url | str | KEY | Wikipedia link |

### `results`: one row per driver per GP (season, round, driver_id)

| Column | Type | Tag | Notes |
|---|---|---|---|
| season, round, driver_id, constructor_id | | KEY | |
| number | int | PRE-QUALI | Car number for that race |
| grid | int | **PRE-RACE** | 0 = pit-lane start. The *value* is known after qualifying, but Jolpica **publishes it with the race result**. See gaps |
| position | int | **POST-RACE** | Classification order. Always filled, including for DNFs |
| position_text | str | POST-RACE | Number, or R=retired, D=disqualified, W=withdrawn, N=not classified, E=excluded, F=failed to qualify |
| points | float | POST-RACE | |
| laps | int | POST-RACE | |
| status | str | POST-RACE | "Finished", "+1 Lap", "Lapped", "Engine", "Accident"… The values vary by era (2026 uses "Lapped") |
| time_millis | int | POST-RACE | Null for drivers who didn't finish on the lead lap |
| fastest_lap_rank, fastest_lap_lap, fastest_lap_time_s, fastest_lap_avg_kph | | POST-RACE | Missing for some rounds, see gaps |

### `qualifying`: one row per driver per GP (season, round, driver_id)

| Column | Type | Tag | Notes |
|---|---|---|---|
| season, round, driver_id, constructor_id, number | | KEY | |
| position | int | **PRE-RACE** | Qualifying classification, before grid penalties |
| q1_s, q2_s, q3_s | float (s) | **PRE-RACE** | Null when knocked out earlier or no time was set |

The 2021–22 sprint weekends ran qualifying on Friday, and it set the *sprint* grid. The GP grid
then came from the sprint result.

### `sprint_results`: one row per driver per sprint (2021+)

Same columns as `results`. The tag depends on the weekend format, and the generic way to decide
it is to compare `races.sprint_utc` with `races.quali_utc`:

- **2021–22:** the sprint ran after qualifying and set the GP grid → `PRE-RACE`.
- **2023:** GP qualifying on Friday, sprint on Saturday → `PRE-RACE`.
- **2024 onwards:** sprint on Saturday morning, GP qualifying in the afternoon → **`PRE-QUALI`**.

### `driver_standings`: one row per driver after each round (season, round, driver_id)

| Column | Type | Tag | Notes |
|---|---|---|---|
| season, round, driver_id | | KEY | Standings **after** that round |
| constructor_id | str | KEY | The driver's latest team as of that round |
| position | int | POST-RACE (r) → PRE-QUALI (r+1) | Can be null for unclassified drivers |
| position_text | str | same | |
| points | float | same | Includes sprint points |
| wins | int | same | |

### `constructor_standings`: one row per team after each round

Columns are `season, round, constructor_id, position, position_text, points, wins`, with the
same tags as `driver_standings`.

### Lookup tables (snapshots as of today)

| Table | Columns | Tag | Caveat |
|---|---|---|---|
| `drivers` | driver_id, code, permanent_number, given_name, family_name, date_of_birth, nationality | KEY / PRE-QUALI | `permanent_number` is the *current* number. Norris carries #1 in 2026 as champion. For historical rows, use `results.number` |
| `constructors` | constructor_id, name, nationality | KEY / PRE-QUALI | Latest name and nationality |
| `circuits` | circuit_id, circuit_name, locality, country, lat, long | KEY / PRE-QUALI | |

## OpenF1 tables (2023+, `f1pred-ingest-openf1`)

| Table | Rows | Grain | Tag | Notes |
|---|---|---|---|---|
| of1_sessions | 450 | session | KEY | `meeting_key`/`session_key` mapped to `(season, round)`; testing dropped |
| of1_laps | 100,349 | driver × practice lap | PRE-QUALI | FP1–FP3 only; pit-out laps flagged |
| of1_stints | 18,265 | driver × practice stint | PRE-QUALI | compound, lap range, tyre age (see gap 12) |
| of1_grid | 1,835 | driver × race | **PRE-RACE** | official starting grid, published right after qualifying — used when Jolpica's `grid` is still null |
| of1_weather | 90 | race | POST-RACE | actual race weather (a forecast would be needed to use it as a feature) |

## What was collected (run of 2026-11-08, 590 API requests)

| Table | Rows | Coverage |
|---|---|---|
| races | 275 | 2014–2026, including the 3 remaining 2026 rounds (Las Vegas R21, Qatar R22, Abu Dhabi R23) |
| results | 5,545 | 270 races. Every completed round from 2014 to 2026 R20 (Brazil) |
| qualifying | 5,524 | Same 270 races |
| sprint_results | 612 | 30 sprints: 3 each in 2021–22, 6 each in 2023–26. Matches every `is_sprint_weekend` |
| driver_standings | 5,820 | After each of the 270 rounds |
| constructor_standings | 2,779 | After each of the 270 rounds |
| drivers / constructors / circuits | 65 / 22 / 33 | |

**Consistency checks passed**
- No duplicate `(season, round, driver_id)` keys in any table.
- For every driver and season, the sum of race and sprint points equals the final standings
  points (0 mismatches). That covers the 2014 Abu Dhabi double points.

## Gaps found

| # | Gap | Where | Impact / handling |
|---|---|---|---|
| 1 | **`grid` is null for all 22 drivers** | 2026 R20 Brazil (raced the same day) | Jolpica publishes the grid late. The next run refreshes the current season after a 6 h TTL. For live predictions, take the grid from OpenF1 `starting_grid` (quali `session_key`) |
| 2 | No `FastestLap` data | 2026 R20 (not published yet); 2021 R12 Spa (real: no green-flag laps) | Post-race column anyway, so no feature impact |
| 3 | **22 result rows have no qualifying row** | 17 races. Examples: 2014 R19 (Red Bulls excluded from quali), 2026 R1 (Verstappen, Sainz, Stroll set no time → started P20–22), 2026 R14 (Bearman, Stroll) | Qualifying is not a full entry list. Treat "no quali row" as "no time set" and use `grid` for starting position |
| 4 | 1 qualifying row has no race result | 2025 R9, Stroll (withdrew after qualifying) | Exclude from training targets |
| 5 | **Duplicate qualifying positions with inconsistent times** (7 cases) | 2023 R10, 2024 R8/R15/R17, 2025 R7, 2026 R19. E.g. 2024 R15: Albon is listed P10 with no Q1 time but a Q3 time | Upstream data errors, probably penalties and disqualifications applied unevenly. In Phase 2, derive quali pace from times rather than trusting `position` alone |
| 6 | `status` vocabulary changes over time | "+1 Lap" (≤2025) vs "Lapped" (2026); 2026 also uses generic "Retired" | Needs a status → {finished, lapped, mechanical, accident, other} map before computing DNF rates |
| 7 | Constructor IDs split across rebrands | `toro_rosso`→`alphatauri`→`rb`; `force_india`→`racing_point`→`aston_martin`; `renault`→`alpine`; `sauber`→`alfa`→`sauber`→`audi`; `lotus_f1`; `manor`/`marussia` | Team-history features need a lineage map. New entrants in 2026: `audi`, `cadillac` (no history) |
| 8 | Naming quirk | 2026 R16 "Bahrain Grand Prix in Malaysia", `circuit_id = sepang` (a relocated race) | Kept as returned. Circuit-history features use `circuit_id`, so it counts as Sepang (last raced in 2017) |
| 9 | Race dates are UTC | Las Vegas `race_date = 2026-11-22`, which is the local Saturday night of Nov 21 | Use `race_start_utc` for ordering, and local time only for display |
| 10 | No 2014–2022 practice, tyre or weather data | Not in Jolpica. FastF1 now needs an F1 account (see SOURCES.md) | Practice-pace features only exist from 2023 (OpenF1) |
| 11 | Field size varies (18–22 cars) | 2014–15 had fewer than 20 cars in some races; 2026 has 22 (Cadillac) | Normalise position-based features by field size |
| 12 | **OpenF1 mixes F2/F3 tyre stints into F1 practice sessions** | 3 sessions, e.g. 2025 R11 FP3 returned stints for 38 car numbers | Only cars with laps in that session are kept; a car whose stint numbers clash (F1 and support car sharing a number) is dropped. Reported as `openf1_foreign_stints` |
| 13 | OpenF1's per-weekend driver list includes support-series drivers who reuse F1 numbers | e.g. an F2 driver with #1 at 2023 R11 | Drivers are matched by 3-letter code; the car number is only a fallback when a row has no code |
| 14 | Reserve drivers in FP1 have no race entry | 135 driver-weekends (2023–26) | Their laps are dropped (`openf1_unmapped_driver`); they never race, so no feature is lost |
