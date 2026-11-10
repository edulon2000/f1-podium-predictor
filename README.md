# f1-podium-predictor

Machine-learning model that predicts the winner (and podium) of Formula 1 Grands Prix.
First live tests: Las Vegas (2026-11-21), Qatar (2026-11-29), Abu Dhabi (2026-12-06).

The 2026 season runs under new power-unit and chassis regulations, so the weight of rows from
the same regulation era as the race being predicted is a tuned hyperparameter (on 2023–24,
where "same era" = 2022+). It helped after qualifying (×3) and not before it (×1).

## Status

- **Phase 1 — data** ✅ Jolpica 2014–2026 + OpenF1 2023–2026 in Parquet, with a data map.
- **Phase 2 — features + model** ✅ leakage-tested features, walk-forward evaluation against two
  baselines, prediction CLI. Full results: [reports/EVALUATION.md](reports/EVALUATION.md).
- **Phase 3 — showcase** ✅ React site (static on Render) + FastAPI/Docker, CI.
- **Live record** — predictions are committed to `predictions/` before each race.

## Results so far (test races 2025–26, 44 races, walk-forward)

| After qualifying | Exact winner | Winner in our top 3 | Podium places | Log-loss ↓ |
|---|---|---|---|---|
| **Ranking model + conditions** (current) | 61.4% | 90.9% | 68.2% | **0.976** |
| Previous model (Phase 2, with the data fix) | 61.4% | 93.2% | 70.4% | 1.055 |
| “Pole-sitter wins” (calibrated) | **68.2%** | 93.2% | 68.2% | 1.176 |

| Before qualifying | Exact winner | Winner in our top 3 | Podium places | Log-loss ↓ |
|---|---|---|---|---|
| **Logistic regression + conditions** (current) | 25.0% | 77.3% | 61.4% | **1.763** |
| “Championship leader wins” (calibrated) | 27.3% | 75.0% | 57.6% | 1.891 |

Honest reading: the model now gives the **best-calibrated probabilities** (log-loss under 1),
but it still **does not beat “the pole-sitter wins” at naming the exact winner**, and the
“90% winner in our top 3 before qualifying” target was **not reached** (77%). Weather, rain
records and Elo ratings were added and leakage-tested but barely moved the test numbers. Full
breakdown and next ideas: [reports/EVALUATION.md](reports/EVALUATION.md).

## Setup

```bash
uv sync --all-extras
```

## Race-weekend workflow

```bash
# 1. refresh data (Jolpica current season + OpenF1 practice/grid)
uv run f1pred-ingest --from 2014 --to 2026 --refresh-current
uv run f1pred-ingest-openf1 --from 2023 --to 2026
uv run f1pred-ingest-weather          # measured weather + forecasts (Open-Meteo)

# 2. after practice: prediction before qualifying (T1)
uv run f1pred-predict --season 2026 --round 21 --stage t1

# 3. after qualifying: prediction with the grid (T2)
uv run f1pred-predict --season 2026 --round 21 --stage t2

# 4. after the race: score the saved predictions (appends predictions/scoreboard.csv)
uv run f1pred-score --season 2026 --round 21
```

Commit `predictions/` after steps 2 and 3, before the race starts, then publish the site data:

```bash
uv run f1pred-export            # writes site_data/ (committed; the static site serves it as /data)
git add predictions site_data && git commit -m "prediction: <race> <stage>" && git push
```

## Website (static React site + optional FastAPI)

The deployed site is **static**: the React build plus the JSON exported to `site_data/`, copied
to `/data` at build time. No server, so it never sleeps; every push to `main` redeploys it.

```bash
cd frontend && npm ci
npm run dev        # http://localhost:5173, serves ../site_data at /data
npm run build      # dist/ with dist/data/ — what Render publishes (render.yaml, static site)
```

- The same JSON is also available as a REST API (FastAPI, Swagger at `/docs`):
  `cd frontend && npm run build && cd .. && uv run uvicorn f1pred.api.app:app --port 8000`.
- `Dockerfile` packages that API + site (FastAPI only, no pandas, no model) for any container host.

## Pipeline

| Step | Module | Notes |
|---|---|---|
| Ingest Jolpica | `f1pred.ingest` | 500 req/h, runs at 1 req/s (429s appear below the documented 4 req/s); hourly window persisted; finished seasons cached forever; aborts on API/schema errors instead of filling gaps |
| Ingest weather | `f1pred.weather` | Open-Meteo: measured weather 2014+, forecasts 1–2 days ahead 2024+, live forecast for the next races |
| Ingest OpenF1 | `f1pred.openf1` | 2023+, 25 req/min (429s at 40/min); practice laps/stints, starting grid, race weather |
| Clean | `f1pred.cleaning` | status categories, team lineage across rebrands, quali pace from lap times |
| Features | `f1pred.features` | T1 (pre-quali) / T2 (post-quali); every outcome-derived feature is lagged |
| Evaluate | `f1pred.evaluate`, `scripts/run_evaluation.py` | walk-forward; tune 2023–24, holdout 2025–26 |
| Model | `f1pred.model` | logistic regression and LightGBM, one classifier per target (win, podium), probabilities normalised per race |
| Predict | `f1pred.predict` | `f1pred-predict`, `f1pred-score` |

## Docs

- [docs/SOURCES.md](docs/SOURCES.md) — what Jolpica, FastF1 and OpenF1 offer
- [docs/DATA_MAP.md](docs/DATA_MAP.md) — tables, columns, join keys, gaps, leakage tags
- [docs/FEATURES.md](docs/FEATURES.md) — features and baselines
- [reports/EVALUATION.md](reports/EVALUATION.md) — tuning grid and holdout results
- `notebooks/01_sanity.ipynb`, `notebooks/02_baselines_and_model.ipynb`

## Tests

```bash
uv run pytest
```

Includes leakage tests: scrambling a race's outcome must not change that race's features, and
features computed from truncated history must equal those computed from full history.
