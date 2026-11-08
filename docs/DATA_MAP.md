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

## Gaps found

_Filled in from `ingest_report.json` once the full run finishes._
