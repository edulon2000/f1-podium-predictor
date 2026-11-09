"""Race weather from Open-Meteo (free, no key): what actually happened and what was forecast.

    uv run f1pred-ingest-weather

For every race (season, round), over the race window (start → +2 h, at the circuit):

- actual_*      observed (reanalysis) from the archive API, 2014+. Used to label wet races and
                to measure how each driver performs in the wet. Never a feature for that race.
- fc_d2_*       the forecast as it stood 2 days before (previous-runs API, 2024+). What we know
                on the Friday of a race weekend → feature for the "before qualifying" forecast.
- fc_d1_*       the forecast 1 day before (2024+) → feature for the "after qualifying" forecast.
- fc_live_*     the current forecast, only for races in the next 16 days (used live).

Before 2024 no archived forecast exists; the feature builder then falls back to the actual
weather as a stand-in (documented in docs/DATA_MAP.md).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

from f1pred.http import ApiError, CachedClient, DiskCache, RateLimiter

log = logging.getLogger("f1pred.weather")

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
PREVIOUS = "https://previous-runs-api.open-meteo.com/v1/forecast"
LIVE = "https://api.open-meteo.com/v1/forecast"
FIRST_PREVIOUS_RUNS_SEASON = 2024
WINDOW_HOURS = 3  # start hour + the next two (a Grand Prix lasts ~1.5–2 h)


def _window(hourly: dict, start: pd.Timestamp, keys: list[str]) -> dict[str, list]:
    times = pd.to_datetime(hourly["time"], utc=True)
    first = start.floor("h")
    mask = (times >= first) & (times < first + pd.Timedelta(hours=WINDOW_HOURS))
    return {k: [v for v, m in zip(hourly.get(k, []), mask, strict=False) if m] for k in keys}


def _sum(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs), 2) if xs else None


def _mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def race_weather(
    client: CachedClient,
    lat: float,
    lon: float,
    start: pd.Timestamp,
    season: int,
    now: pd.Timestamp,
) -> dict:
    day = start.strftime("%Y-%m-%d")
    next_day = (start + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    base = {
        "latitude": round(lat, 3),
        "longitude": round(lon, 3),
        "start_date": day,
        "end_date": next_day,
        "timezone": "UTC",
    }
    out: dict = {}
    finished = start + pd.Timedelta(hours=3) < now
    recent = now - start < pd.Timedelta(days=7)

    if finished:
        # the archive lags a few days; keep re-checking recent races
        body = client.get_json(
            ARCHIVE,
            {**base, "hourly": "precipitation,temperature_2m,wind_speed_10m"},
            max_age=6 * 3600 if recent else None,
        )
        w = _window(
            body.get("hourly", {}), start, ["precipitation", "temperature_2m", "wind_speed_10m"]
        )
        out.update(
            actual_rain_mm=_sum(w["precipitation"]),
            actual_temp_c=_mean(w["temperature_2m"]),
            actual_wind_kmh=_mean(w["wind_speed_10m"]),
        )

    if season >= FIRST_PREVIOUS_RUNS_SEASON and start - pd.Timedelta(days=1) < now:
        keys = [
            "precipitation_previous_day1",
            "precipitation_previous_day2",
            "temperature_2m_previous_day1",
            "temperature_2m_previous_day2",
        ]
        body = client.get_json(
            PREVIOUS, {**base, "hourly": ",".join(keys)}, max_age=6 * 3600 if recent else None
        )
        w = _window(body.get("hourly", {}), start, keys)
        out.update(
            fc_d1_rain_mm=_sum(w[keys[0]]),
            fc_d2_rain_mm=_sum(w[keys[1]]),
            fc_d1_temp_c=_mean(w[keys[2]]),
            fc_d2_temp_c=_mean(w[keys[3]]),
        )

    if not finished and start - now < pd.Timedelta(days=15):
        keys = ["precipitation", "precipitation_probability", "temperature_2m"]
        body = client.get_json(LIVE, {**base, "hourly": ",".join(keys)}, max_age=3 * 3600)
        w = _window(body.get("hourly", {}), start, keys)
        out.update(
            fc_live_rain_mm=_sum(w["precipitation"]),
            fc_live_rain_prob=_mean(w["precipitation_probability"]),
            fc_live_temp_c=_mean(w["temperature_2m"]),
            fc_live_fetched_at=now.isoformat(),
        )
    return out


def build_weather(
    client: CachedClient,
    races: pd.DataFrame,
    circuits: pd.DataFrame,
    of1_weather: pd.DataFrame | None,
    now: pd.Timestamp,
) -> pd.DataFrame:
    c = circuits.set_index("circuit_id")
    rows = []
    for r in races.sort_values(["season", "round"]).itertuples():
        if r.circuit_id not in c.index or pd.isna(r.race_start_utc):
            continue
        lat, lon = float(c.loc[r.circuit_id, "lat"]), float(c.loc[r.circuit_id, "long"])
        start = pd.Timestamp(r.race_start_utc)
        if start - now > pd.Timedelta(days=15):
            continue
        rows.append(
            {
                "season": int(r.season),
                "round": int(r.round),
                **race_weather(client, lat, lon, start, int(r.season), now),
            }
        )
    df = pd.DataFrame(rows)
    # OpenF1's in-session rain sensor (2023+) is the better "did it rain" signal when present
    if of1_weather is not None and len(of1_weather):
        df = df.merge(
            of1_weather[["season", "round", "rainfall_any"]], on=["season", "round"], how="left"
        )
    else:
        df["rainfall_any"] = pd.NA
    df["wet_race"] = df["rainfall_any"].astype("boolean").fillna(False) | (
        df["actual_rain_mm"].fillna(0) >= 0.5
    )
    df.loc[df["actual_rain_mm"].isna() & df["rainfall_any"].isna(), "wet_race"] = pd.NA
    return df.drop(columns=["rainfall_any"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    proc = args.data_dir / "processed"
    races = pd.read_parquet(proc / "races.parquet")
    circuits = pd.read_parquet(proc / "circuits.parquet")
    of1 = (
        pd.read_parquet(proc / "of1_weather.parquet")
        if (proc / "of1_weather.parquet").exists()
        else None
    )
    client = CachedClient(
        cache=DiskCache(args.data_dir / "raw" / "open-meteo", base_url="https://"),
        limiter=RateLimiter(
            per_second=2,
            per_minute=300,
            per_hour=4000,
            state_path=Path(".cache") / "openmeteo_limiter.json",
        ),
        max_retries=4,
    )
    try:
        df = build_weather(client, races, circuits, of1, pd.Timestamp.now(tz="UTC"))
    except ApiError as exc:
        log.error("Weather ingestion aborted — nothing written: %s", exc)
        return 1
    path = proc / "weather.parquet"
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    log.info(
        "weather: %s races, %s wet, %s with archived forecasts; requests %s network / %s cached",
        len(df),
        int(df["wet_race"].fillna(False).sum()),
        int(df["fc_d1_rain_mm"].notna().sum()) if "fc_d1_rain_mm" in df else 0,
        client.network_requests,
        client.cache_hits,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
