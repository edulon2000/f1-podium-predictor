# f1-podium-predictor

Machine-learning model that predicts the winner (and podium) of Formula 1 Grands Prix.
First live tests: Las Vegas (2026-11-21), Qatar (2026-11-29), Abu Dhabi (2026-12-06).

The 2026 season runs under new power-unit and chassis regulations, so 2026 data will be
weighted more heavily than earlier eras.

## Status

**Phase 1 — data mapping and collection** (no models yet).

## Setup

```bash
uv sync --all-extras
```

## Ingestion

Downloads 2014 → latest completed 2026 round from the Jolpica-F1 (Ergast-compatible) API,
caches every response on disk, and writes Parquet tables to `data/processed/`.

```bash
uv run f1pred-ingest --from 2014 --to 2026
```

- Respects Jolpica's limits (500 req/h; runs at 1 req/s because 429s appear well below the
  documented 4 req/s burst) — the hourly window is persisted, so restarts don't reset it. A cold run takes ~1.5–2 h; re-runs are served from the cache in seconds.
- Finished seasons are cached forever; the current season is refreshed when stale or when the
  latest round is incomplete. Use `--refresh-current` to force it.
- If the API errors or its schema changes, the run stops with an error — it never fills gaps.

## Docs

- [docs/SOURCES.md](docs/SOURCES.md) — what Jolpica, FastF1 and OpenF1 offer
- [docs/DATA_MAP.md](docs/DATA_MAP.md) — tables, columns, join keys, gaps, leakage tags
- [docs/FEATURES.md](docs/FEATURES.md) — candidate features and baselines (proposal)

## Tests

```bash
uv run pytest
```
