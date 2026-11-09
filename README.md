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
- **Phase 3 — showcase** ✅ FastAPI + React site, Docker image, Render blueprint, CI.
- **Live record** — predictions are committed to `predictions/` before each race.

## Results so far (holdout 2025–26, 44 races, walk-forward)

| After qualifying (T2) | Winner picked | Podium hit | Log-loss (winner) ↓ |
|---|---|---|---|
| **LightGBM** (chosen) | 56.8% | **71.2%** | **1.06** |
| "Pole-sitter wins" | **68.2%** | 68.2% | 1.18 (calibrated version) |

| Before qualifying (T1) | Winner picked | Podium hit | Log-loss (winner) ↓ |
|---|---|---|---|
| **Logistic regression** (chosen) | 27.3% | **61.4%** | **1.77** |
| "Championship leader wins" | 27.3% | 52.3% | 1.89 (calibrated version) |

Honest reading: the model gives **better-calibrated probabilities** and **better podiums** than
both baselines, but **it does not beat "the pole-sitter wins" at naming the winner** — in 2026
the pole-sitter won 14 of 20 races, and the model's top pick 13. Before qualifying, the winner
is hard to call for everyone (~30%). Next ideas are in the Phase 4 list of the evaluation report.

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
uv run f1pred-export            # writes site_data/ (committed; the deployed API only reads it)
git add predictions site_data && git commit -m "prediction: <race> <stage>" && git push
```

## Website (FastAPI + React)

```bash
cd frontend && npm ci && npm run build && cd ..   # build the front once
uv run uvicorn f1pred.api.app:app --port 8000     # API + site on http://localhost:8000
```

- API docs (Swagger): http://localhost:8000/docs
- Front-end development with hot reload: `uv run uvicorn f1pred.api.app:app --port 8000` and,
  in another terminal, `cd frontend && npm run dev` (http://localhost:5173, proxies `/api`).
- Deploy: `Dockerfile` + `render.yaml` (Render, free plan). The image contains only FastAPI,
  `site_data/` and the built front — no pandas, no model.

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
