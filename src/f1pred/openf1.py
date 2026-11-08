"""OpenF1 (https://api.openf1.org/v1) ingestion: practice laps/stints, starting grid, weather.

Historical data (2023+) is free without authentication. No rate limit is documented, so the
client runs at 1 req/s and at most 40 req/min, and backs off on 429.

    uv run f1pred-ingest-openf1 --from 2023 --to 2026

Requires the Jolpica tables (data/processed/races|results|drivers.parquet) to map OpenF1's
meeting/session keys to (season, round) and its driver_number/name_acronym to driver_id.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from f1pred.http import ApiError, CachedClient, DiskCache, RateLimiter
from f1pred.schema import SchemaError

log = logging.getLogger("f1pred.openf1")

BASE_URL = "https://api.openf1.org/v1"
PRACTICE = {"Practice 1", "Practice 2", "Practice 3"}
RECENT = pd.Timedelta(days=7)  # sessions newer than this may still be revised upstream


class OpenF1:
    def __init__(self, client: CachedClient, base_url: str = BASE_URL) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")

    def get(self, endpoint: str, max_age: float | None = None, **params: Any) -> list[dict]:
        body = self.client.get_json(f"{self.base_url}/{endpoint}", params, max_age=max_age)
        if not isinstance(body, list):
            raise SchemaError(f"OpenF1 {endpoint} {params}: expected a list, got {body!r:.200}")
        return body


def map_meetings(sessions: pd.DataFrame, races: pd.DataFrame) -> pd.DataFrame:
    """Attach (season, round) to each session: the first race starting within 5 days of the
    meeting's first session. Testing meetings match no race and drop out."""
    s = sessions.copy()
    s["date_start"] = pd.to_datetime(s["date_start"], utc=True)
    s["date_end"] = pd.to_datetime(s["date_end"], utc=True)
    first = s.groupby("meeting_key")["date_start"].min()
    starts = races.sort_values("race_start_utc")
    rows = []
    for mk, m_start in first.items():
        delta = starts["race_start_utc"] - m_start
        hit = starts[(delta >= pd.Timedelta(hours=-12)) & (delta <= pd.Timedelta(days=5))]
        if len(hit):
            rows.append({"meeting_key": mk, "season": int(hit.season.iloc[0]),
                         "round": int(hit["round"].iloc[0])})
    mapping = pd.DataFrame(rows, columns=["meeting_key", "season", "round"])
    return s.merge(mapping, on="meeting_key", how="inner")  # testing meetings drop out here


def driver_map(of1_drivers: list[dict], season: int, results: pd.DataFrame,
               drivers: pd.DataFrame) -> dict[int, str]:
    """driver_number -> driver_id for one meeting, via 3-letter code, then car number."""
    roster = results[results["season"].isin([season, season - 1])]
    roster_ids = set(roster["driver_id"])
    code_to_id = {r.code: r.driver_id for r in drivers.itertuples()
                  if r.driver_id in roster_ids and r.code}
    num_to_id = (roster[roster["season"] == season].dropna(subset=["number"])
                 .drop_duplicates("number", keep="last").set_index("number")["driver_id"].to_dict())
    out: dict[int, str] = {}
    for d in of1_drivers:
        num = d.get("driver_number")
        did = code_to_id.get(d.get("name_acronym")) or num_to_id.get(num)
        if num is not None and did:
            out[int(num)] = did
    return out


def ingest(api: OpenF1, years: list[int], races: pd.DataFrame, results: pd.DataFrame,
           drivers: pd.DataFrame, now: pd.Timestamp, ttl: float
           ) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    gaps: list[dict] = []
    all_sessions = []
    for y in years:
        age = ttl if y == now.year else None
        all_sessions.extend(api.get("sessions", max_age=age, year=y))
    sessions = map_meetings(pd.DataFrame(all_sessions), races)
    done = sessions[sessions["date_end"] < now]

    laps, stints, grid, weather, sess_rows = [], [], [], [], []
    for mk, meet in done.groupby("meeting_key"):
        season, rnd = int(meet.season.iloc[0]), int(meet["round"].iloc[0])

        def age(sess_end: pd.Timestamp) -> float | None:
            return ttl if now - sess_end < RECENT else None

        newest = meet["date_end"].max()
        dmap = driver_map(api.get("drivers", max_age=age(newest), meeting_key=int(mk)),
                          season, results, drivers)
        if not dmap:
            gaps.append({"kind": "openf1_no_driver_map", "season": season, "round": rnd})
            continue

        def tag(rows: list[dict], sess: Any, ctx=(season, rnd, dmap)) -> list[dict]:
            return _tag(rows, sess.session_name, *ctx, gaps)

        for sess in meet.itertuples():
            a = age(sess.date_end)
            key = int(sess.session_key)
            sess_rows.append({"season": season, "round": rnd, "meeting_key": int(mk),
                              "session_key": key, "session_name": sess.session_name,
                              "session_type": sess.session_type, "date_start": sess.date_start,
                              "date_end": sess.date_end})
            if sess.session_name in PRACTICE:
                got = tag(api.get("laps", max_age=a, session_key=key), sess)
                if not got:
                    gaps.append({"kind": "openf1_no_laps", "season": season, "round": rnd,
                                 "session": sess.session_name})
                laps += got
                stints += tag(api.get("stints", max_age=a, session_key=key), sess)
            elif sess.session_name == "Qualifying":
                # starting_grid is keyed by the *qualifying* session (404 with the race key)
                got = tag(api.get("starting_grid", max_age=a, session_key=key), sess)
                if not got:
                    gaps.append({"kind": "openf1_no_grid", "season": season, "round": rnd})
                grid += got
            elif sess.session_name == "Race":
                w = api.get("weather", max_age=a, session_key=key)
                if w:
                    wd = pd.DataFrame(w)
                    weather.append({
                        "season": season, "round": rnd,
                        "air_temp_mean": wd["air_temperature"].mean(),
                        "track_temp_mean": wd["track_temperature"].mean(),
                        "humidity_mean": wd["humidity"].mean(),
                        "wind_speed_mean": wd["wind_speed"].mean(),
                        "rainfall_any": bool((wd["rainfall"].fillna(0) > 0).any()),
                    })

    tables = {
        "of1_sessions": pd.DataFrame(sess_rows),
        "of1_laps": _cols(laps, ["season", "round", "session_name", "driver_id", "driver_number",
                                 "lap_number", "lap_duration", "is_pit_out_lap", "st_speed",
                                 "duration_sector_1", "duration_sector_2", "duration_sector_3"]),
        "of1_stints": _cols(stints, ["season", "round", "session_name", "driver_id", "stint_number",
                                     "compound", "lap_start", "lap_end", "tyre_age_at_start"]),
        "of1_grid": _cols(grid, ["season", "round", "driver_id", "position", "lap_duration"])
        .rename(columns={"position": "grid_position", "lap_duration": "quali_lap_s"}),
        "of1_weather": pd.DataFrame(weather),
    }
    return tables, gaps


def _tag(rows: list[dict], session_name: str, season: int, rnd: int, dmap: dict[int, str],
         gaps: list[dict]) -> list[dict]:
    """Attach season/round/driver_id; rows whose driver_number can't be mapped become gaps."""
    out = []
    for r in rows:
        num = r.get("driver_number")
        did = dmap.get(num)
        if did is None and num is not None:
            gaps.append({"kind": "openf1_unmapped_driver", "season": season, "round": rnd,
                         "driver_number": num})
            continue
        out.append({**r, "season": season, "round": rnd, "driver_id": did,
                    "session_name": session_name})
    return out


def _cols(rows: list[dict], cols: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols].sort_values(cols[:4], kind="mergesort").reset_index(drop=True) if len(df) \
        else df[cols]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--from", dest="first", type=int, default=2023)
    p.add_argument("--to", dest="last", type=int, default=dt.date.today().year)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--ttl-hours", type=float, default=6.0)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    proc = args.data_dir / "processed"
    races = pd.read_parquet(proc / "races.parquet")
    results = pd.read_parquet(proc / "results.parquet")
    drivers = pd.read_parquet(proc / "drivers.parquet")
    client = CachedClient(
        cache=DiskCache(args.data_dir / "raw" / "openf1", base_url=BASE_URL),
        limiter=RateLimiter(per_second=1, per_minute=40, per_hour=2000,
                            state_path=Path(".cache") / "openf1_limiter.json"),
        max_retries=6,
        not_found_value=[],
    )
    try:
        tables, gaps = ingest(OpenF1(client), list(range(args.first, args.last + 1)), races,
                              results, drivers, pd.Timestamp.now(tz="UTC"), args.ttl_hours * 3600)
    except (ApiError, SchemaError) as exc:
        log.error("OpenF1 ingestion aborted — no Parquet files were changed: %s", exc)
        return 1
    for name, df in tables.items():
        path = proc / f"{name}.parquet"
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    gap_df = pd.DataFrame(gaps)
    gap_df.to_csv(proc / "of1_gaps.csv", index=False)
    log.info("Done: %s", {k: len(v) for k, v in tables.items()})
    log.info("Requests: %s network, %s cache hits; %s gaps", client.network_requests,
             client.cache_hits, len(gaps))
    if len(gap_df):
        log.info("Gap kinds: %s", gap_df["kind"].value_counts().to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
