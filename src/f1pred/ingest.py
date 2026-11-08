"""Idempotent ingestion: Jolpica-F1 → data/raw (JSON cache) → data/processed (Parquet).

Usage:
    uv run f1pred-ingest --from 2014 --to 2026 [--refresh-current] [--current-ttl-hours 6]

Re-running is safe: finished seasons are served from the disk cache forever, the current season
is re-fetched when its cache is older than --current-ttl-hours (or immediately with
--refresh-current), and every Parquet file is rewritten atomically from the full cache.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from f1pred.http import ApiError, CachedClient, DiskCache, RateLimiter
from f1pred.jolpica import BASE_URL, Jolpica
from f1pred.schema import (
    SchemaError,
    collect_dimensions,
    parse_constructor_standings,
    parse_driver_standings,
    parse_qualifying,
    parse_results,
    parse_schedule,
)

log = logging.getLogger("f1pred.ingest")

FIRST_SPRINT_SEASON = 2021

TABLE_KEYS = {
    "races": ["season", "round"],
    "results": ["season", "round", "position"],
    "qualifying": ["season", "round", "position"],
    "sprint_results": ["season", "round", "position"],
    "driver_standings": ["season", "round", "points", "driver_id"],
    "constructor_standings": ["season", "round", "points", "constructor_id"],
    "drivers": ["driver_id"],
    "constructors": ["constructor_id"],
    "circuits": ["circuit_id"],
}

INT_COLUMNS = {
    "season", "round", "number", "grid", "position", "laps", "time_millis", "wins",
    "fastest_lap_rank", "fastest_lap_lap", "permanent_number",
}


class Api(Protocol):
    def schedule(self, season: int, max_age: float | None = None) -> list[dict]: ...
    def season_races(
        self, season: int, endpoint: str, max_age: float | None = None
    ) -> list[dict]: ...
    def standings(self, season: int, rnd: int, kind: str, max_age: float | None = None) -> dict: ...


@dataclass
class Report:
    generated_at: str = ""
    seasons: list[int] = field(default_factory=list)
    latest_round: dict[str, Any] = field(default_factory=dict)
    row_counts: dict[str, int] = field(default_factory=dict)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    network_requests: int = 0
    cache_hits: int = 0

    def gap(self, kind: str, season: int, rnd: int | None = None, **detail: Any) -> None:
        entry = {"kind": kind, "season": season, "round": rnd, **detail}
        self.gaps.append(entry)
        log.warning("GAP %s", entry)


def build_tables(
    api: Api,
    seasons: list[int],
    current_season: int | None,
    current_max_age: float,
    now: pd.Timestamp,
) -> tuple[dict[str, pd.DataFrame], Report]:
    report = Report(seasons=seasons)
    rows: dict[str, list[dict]] = {k: [] for k in TABLE_KEYS}
    raw_races: list[dict] = []
    raw_standings: list[dict] = []

    for season in seasons:
        is_current = season == current_season
        max_age = current_max_age if is_current else None
        log.info("Season %s%s", season, " (current)" if is_current else "")

        schedule = api.schedule(season, max_age=max_age)
        sched_rows = parse_schedule(schedule)
        rows["races"].extend(sched_rows)
        raw_races.extend(schedule)

        results = api.season_races(season, "results", max_age=max_age)
        quali = api.season_races(season, "qualifying", max_age=max_age)
        sprint = (
            api.season_races(season, "sprint", max_age=max_age)
            if season >= FIRST_SPRINT_SEASON else []
        )
        raw_races.extend(results + quali + sprint)
        res_rows = parse_results(results)
        rows["results"].extend(res_rows)
        rows["qualifying"].extend(parse_qualifying(quali))
        rows["sprint_results"].extend(parse_results(sprint, list_key="SprintResults"))

        completed = sorted({int(r["round"]) for r in results})
        _check_season(report, season, sched_rows, results, quali, sprint, res_rows, now)

        for rnd in completed:
            # Standings of older rounds no longer change; only the latest round may be revised.
            age = max_age if (is_current and rnd == completed[-1]) else None
            ds = api.standings(season, rnd, "driverStandings", max_age=age)
            cs = api.standings(season, rnd, "constructorStandings", max_age=age)
            raw_standings += [ds, cs]
            d_rows, c_rows = parse_driver_standings(ds), parse_constructor_standings(cs)
            if not d_rows or not c_rows:
                report.gap("standings_missing", season, rnd,
                           driver_rows=len(d_rows), constructor_rows=len(c_rows))
            rows["driver_standings"].extend(d_rows)
            rows["constructor_standings"].extend(c_rows)

        if is_current and completed:
            last = next(r for r in sched_rows if r["round"] == completed[-1])
            report.latest_round = {"season": season, "round": completed[-1],
                                   "race_name": last["race_name"], "date": last["race_date"]}

    rows.update(collect_dimensions(raw_races, raw_standings))
    tables = {name: _frame(name, rs) for name, rs in rows.items()}
    report.row_counts = {name: len(df) for name, df in tables.items()}
    return tables, report


def _check_season(report, season, sched_rows, results, quali, sprint, res_rows, now) -> None:
    with_results = {int(r["round"]) for r in results}
    with_quali = {int(r["round"]) for r in quali}
    with_sprint = {int(r["round"]) for r in sprint}
    for race in sched_rows:
        rnd = race["round"]
        started = race["race_start_utc"] is not None and race["race_start_utc"] < now
        if started and rnd not in with_results:
            report.gap("results_missing_for_past_race", season, rnd, race=race["race_name"])
        if rnd in with_results and rnd not in with_quali:
            report.gap("qualifying_missing", season, rnd, race=race["race_name"])
        if race["is_sprint_weekend"] and rnd in with_results and rnd not in with_sprint:
            report.gap("sprint_results_missing", season, rnd, race=race["race_name"])
    by_round: dict[int, list[dict]] = {}
    for r in res_rows:
        by_round.setdefault(r["round"], []).append(r)
    for rnd, rs in sorted(by_round.items()):
        null_grid = sum(r["grid"] is None for r in rs)
        if null_grid:
            report.gap("grid_null", season, rnd, rows=null_grid, of=len(rs))
        null_fl = sum(r["fastest_lap_rank"] is None for r in rs)
        if null_fl == len(rs):
            report.gap("fastest_lap_missing", season, rnd)


def _frame(name: str, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in df.columns:
        if col in INT_COLUMNS:
            df[col] = df[col].astype("Int64")
    sort_cols = [c for c in TABLE_KEYS[name] if c in df.columns]
    ascending = [c != "points" for c in sort_cols]
    df = df.drop_duplicates()
    return df.sort_values(sort_cols, ascending=ascending, kind="mergesort").reset_index(drop=True)


def write_tables(tables: dict[str, pd.DataFrame], report: Report, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        path = out_dir / f"{name}.parquet"
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    report_path = out_dir / "ingest_report.json"
    report_path.write_text(json.dumps(report.__dict__, indent=2, default=str), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--from", dest="first", type=int, default=2014)
    p.add_argument("--to", dest="last", type=int, default=dt.date.today().year)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--refresh-current", action="store_true",
                   help="ignore the cache for the current season")
    p.add_argument("--current-ttl-hours", type=float, default=6.0)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    today = dt.date.today()
    current = today.year if args.first <= today.year <= args.last else None
    client = CachedClient(
        cache=DiskCache(args.data_dir / "raw" / "jolpica", base_url=BASE_URL),
        # Documented burst is 4 req/s, but 429s were observed at ~1.6 req/s (2026-11-08).
        # The 500 req/h cap dominates total runtime anyway, so 1 req/s costs nothing.
        limiter=RateLimiter(per_second=1, per_hour=500,
                            state_path=Path(".cache") / "jolpica_limiter.json"),
        max_retries=6,
    )
    api = Jolpica(client)
    max_age = 0.0 if args.refresh_current else args.current_ttl_hours * 3600
    try:
        tables, report = build_tables(
            api, list(range(args.first, args.last + 1)), current, max_age,
            now=pd.Timestamp.now(tz="UTC"),
        )
    except (ApiError, SchemaError) as exc:
        log.error("Ingestion aborted — no Parquet files were changed: %s", exc)
        log.error("Requests this run: %s network, %s cache hits",
                  client.network_requests, client.cache_hits)
        return 1

    report.generated_at = pd.Timestamp.now(tz="UTC").isoformat()
    report.network_requests = client.network_requests
    report.cache_hits = client.cache_hits
    write_tables(tables, report, args.data_dir / "processed")
    log.info("Done: %s", report.row_counts)
    log.info("Requests: %s network, %s cache hits; %s gaps logged",
             client.network_requests, client.cache_hits, len(report.gaps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
