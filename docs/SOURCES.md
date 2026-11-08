# Data sources

Observed on **2026-11-08** (day of the Brazilian GP, round 20 of 23). Everything below comes from
real calls; the raw probe output is in `data/raw/samples/source_probe.json`
(regenerate with `uv run python scripts/probe_sources.py`).

| | Jolpica-F1 | OpenF1 | FastF1 |
|---|---|---|---|
| What | Ergast-compatible results archive | Live/recent timing API | Python lib over F1 live-timing feed (+ Ergast) |
| Coverage | 1950 → today | **2023 → today** (2022 returns "No results found") | 2018 → today (documented) |
| Granularity | One row per driver per session | Per lap / per stint / per sample | Per lap, per sample (telemetry) |
| Auth | None | None for historical data | **Now needs an F1 account — see below** |
| Limits | Documented 4 req/s burst, 500 req/h — **429s observed from ~1.6 req/s**, so the client runs at 1 req/s | Not hit at ~2 req/s | — |
| Used in Phase 1 | ✅ Main source (ingested) | 🔍 Probed only | ❌ Blocked |

## Jolpica-F1 — `https://api.jolpi.ca/ergast/f1/`

Successor to the retired Ergast API, same URL scheme and JSON shape (`MRData` envelope).

- **Pagination**: `limit` (max 100) + `offset`; `total` counts *rows* (e.g. result lines), not
  races, so one race can be split across pages. `Jolpica.season_races` merges them and checks the
  final row count against `total`.
- **Endpoints used**: `{season}` (calendar + session times), `{season}/results`,
  `{season}/qualifying`, `{season}/sprint`, `{season}/{round}/driverStandings`,
  `{season}/{round}/constructorStandings`.
- **Not ingested yet (available)**: `laps` (per-lap times, from 1996), `pitstops` (from 2011),
  `status`. Candidates for Phase 2 if we need pit-stop or race-pace features over 2014–2022.
- **Session keys in the calendar vary by era**: `SprintShootout` (2023) vs `SprintQualifying`
  (2024+); 2021–22 sprint weekends have `FirstPractice`/`SecondPractice` and no `ThirdPractice`.
- **Freshness**: the latest race shows up within hours but **incomplete** — for Brazil 2026
  (raced today) `grid` is `null` for all 22 drivers and `FastestLap` is missing. The ingestion
  flags this in `ingest_report.json` and re-fetches the current season after a TTL.
- **Quirk**: 2026 round 16 is named "Bahrain Grand Prix in Malaysia" — kept as returned.

## OpenF1 — `https://api.openf1.org/v1/`

Flat JSON arrays, filterable by any field (`session_key`, `driver_number`, `date>`…). Keys:
`meeting_key` (a GP weekend) and `session_key` (one session). Drivers are identified by
**`driver_number`**, not by Ergast's `driverId` → a mapping table will be needed to join.

Endpoints confirmed working for Brazil 2026 (race `session_key=11412`, quali `11408`):

| Endpoint | Grain | Useful columns |
|---|---|---|
| `meetings`, `sessions` | weekend / session | `circuit_key`, `date_start`, `session_type`, `gmt_offset` |
| `drivers` | driver × session | `driver_number`, `name_acronym`, `team_name` |
| `session_result` | driver × session | `position`, `gap_to_leader`, `duration`, `dnf/dns/dsq`, `points` |
| `starting_grid` | driver | `position`, `lap_duration` — **keyed by the qualifying session_key** (404 with the race key) |
| `laps` | driver × lap | `lap_duration`, sector times, speed traps, `is_pit_out_lap` |
| `stints` | driver × stint | `compound`, `lap_start/lap_end`, `tyre_age_at_start` |
| `pit` | stop | `pit_duration`, `stop_duration`, `lane_duration` |
| `weather` | ~1/min | air/track temp, humidity, `rainfall`, wind |
| `race_control` | message | flags, SC/VSC, penalties |
| `position`, `intervals`, `overtakes` | event stream | in-race dynamics |
| `championship_drivers/teams` | driver/team × session | `points_start`, `points_current` |
| `car_data`, `location` | ~4 Hz samples | telemetry (huge — always filter by driver + time window) |

**Why it matters**: OpenF1's `starting_grid` (via quali key) already has the Brazil 2026 grid that
Jolpica hasn't published yet, and it gives practice-session pace (FP1–FP3 laps/stints) — the
main "before qualifying" signal for the Las Vegas/Qatar/Abu Dhabi predictions. Limitation: only
2023+, so it can't feed features over the whole 2014–2026 history.

## FastF1 (v3.9.2) — ❌ blocked without an F1 account

`session.load()` fails for every session tested (2019, 2024, 2025, 2026). The underlying
F1 live-timing feed now answers **HTTP 401** (`livetiming.formula1.com/static/2024/Index.json`),
and FastF1 logs: *"No F1 account credentials available. Set the environment variables
F1_USERNAME and F1_PASSWORD."* Only the event schedule loads.

Options (your call — not done in Phase 1):
1. Set `F1_USERNAME`/`F1_PASSWORD` yourself (an F1 account; check whether F1 TV is required) and
   re-run the probe. FastF1 would then give laps, tyres, weather and telemetry back to 2018.
2. Use OpenF1 instead for the same kind of data, accepting the 2023+ limit.
3. Use Jolpica `laps`/`pitstops` for long-history pace features (no tyres/weather).

Recommendation: **2 + 3** for Phase 2 — no credentials in the pipeline, and 2023–2026 covers
the current regulation era plus its predecessor, which is what the model should weight anyway.
