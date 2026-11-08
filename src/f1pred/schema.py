"""Flatten Jolpica (Ergast-compatible) JSON into typed rows.

Every parser raises SchemaError when a field we rely on is missing, so an upstream format change
stops the pipeline loudly instead of silently producing empty or shifted columns. Fields that are
legitimately optional (e.g. FastestLap, Q2/Q3, Time for non-finishers) become None.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class SchemaError(ValueError):
    """The API payload no longer matches the structure this code expects."""


Row = dict[str, Any]

# Session keys seen across eras (SprintShootout = 2023 name, SprintQualifying = 2024+).
SESSION_KEYS = {
    "FirstPractice": "fp1",
    "SecondPractice": "fp2",
    "ThirdPractice": "fp3",
    "SprintQualifying": "sprint_quali",
    "SprintShootout": "sprint_quali",
    "Sprint": "sprint",
    "Qualifying": "quali",
}


def req(d: dict, key: str, ctx: str) -> Any:
    if not isinstance(d, dict) or key not in d:
        raise SchemaError(f"missing key {key!r} in {ctx}")
    return d[key]


def to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def laptime_to_seconds(v: Any) -> float | None:
    """'1:27.689' -> 87.689, '27.689' -> 27.689, ''/None/garbage -> None."""
    if not v or not isinstance(v, str):
        return None
    try:
        parts = v.strip().split(":")
        seconds = 0.0
        for p in parts:
            seconds = seconds * 60 + float(p)
        return seconds
    except ValueError:
        return None


def _utc(session: dict | None) -> pd.Timestamp | None:
    if not session or "date" not in session:
        return None
    # Ergast times are UTC ("06:00:00Z"); older seasons may omit the time entirely.
    time = (session.get("time") or "00:00:00").rstrip("Z")
    return pd.Timestamp(f"{session['date']}T{time}", tz="UTC")


def _race_key(race: dict, ctx: str) -> tuple[int, int]:
    return int(req(race, "season", ctx)), int(req(race, "round", ctx))


# --- dimensions ------------------------------------------------------------------------------


def driver_row(d: dict, ctx: str) -> Row:
    return {
        "driver_id": req(d, "driverId", ctx),
        "code": d.get("code"),
        "permanent_number": to_int(d.get("permanentNumber")),
        "given_name": d.get("givenName"),
        "family_name": d.get("familyName"),
        "date_of_birth": d.get("dateOfBirth"),
        "nationality": d.get("nationality"),
    }


def constructor_row(c: dict, ctx: str) -> Row:
    return {
        "constructor_id": req(c, "constructorId", ctx),
        "name": c.get("name"),
        "nationality": c.get("nationality"),
    }


def circuit_row(c: dict, ctx: str) -> Row:
    loc = c.get("Location", {})
    return {
        "circuit_id": req(c, "circuitId", ctx),
        "circuit_name": c.get("circuitName"),
        "locality": loc.get("locality"),
        "country": loc.get("country"),
        "lat": to_float(loc.get("lat")),
        "long": to_float(loc.get("long")),
    }


# --- fact tables -----------------------------------------------------------------------------


def parse_schedule(races: list[dict]) -> list[Row]:
    rows = []
    for race in races:
        ctx = f"schedule race {race.get('season')}/{race.get('round')}"
        season, rnd = _race_key(race, ctx)
        circuit = req(race, "Circuit", ctx)
        row: Row = {
            "season": season,
            "round": rnd,
            "race_name": req(race, "raceName", ctx),
            "circuit_id": req(circuit, "circuitId", ctx),
            "race_date": req(race, "date", ctx),
            "race_start_utc": _utc({"date": race["date"], "time": race.get("time")}),
            "url": race.get("url"),
        }
        for col in set(SESSION_KEYS.values()):
            row[f"{col}_utc"] = None
        for key, col in SESSION_KEYS.items():
            if key in race:
                row[f"{col}_utc"] = _utc(race[key])
        row["is_sprint_weekend"] = "Sprint" in race
        rows.append(row)
    return rows


def _result_row(race: dict, r: dict, ctx: str) -> Row:
    season, rnd = _race_key(race, ctx)
    driver = req(r, "Driver", ctx)
    constructor = req(r, "Constructor", ctx)
    fl = r.get("FastestLap") or {}
    return {
        "season": season,
        "round": rnd,
        "driver_id": req(driver, "driverId", ctx),
        "constructor_id": req(constructor, "constructorId", ctx),
        "number": to_int(r.get("number")),
        "grid": to_int(req(r, "grid", ctx)),  # 0 = pit-lane start; None = not published yet
        "position": to_int(req(r, "position", ctx)),  # classification order (always filled)
        "position_text": req(r, "positionText", ctx),  # R=retired, D=DSQ, W=withdrawn, N/E/F
        "points": to_float(req(r, "points", ctx)),
        "laps": to_int(r.get("laps")),
        "status": req(r, "status", ctx),
        "time_millis": to_int((r.get("Time") or {}).get("millis")),
        "fastest_lap_rank": to_int(fl.get("rank")),
        "fastest_lap_lap": to_int(fl.get("lap")),
        "fastest_lap_time_s": laptime_to_seconds((fl.get("Time") or {}).get("time")),
        "fastest_lap_avg_kph": to_float((fl.get("AverageSpeed") or {}).get("speed")),
    }


def parse_results(races: list[dict], list_key: str = "Results") -> list[Row]:
    """Race results (list_key='Results') or sprint results (list_key='SprintResults')."""
    rows = []
    for race in races:
        ctx = f"{list_key} {race.get('season')}/{race.get('round')}"
        for r in req(race, list_key, ctx):
            rows.append(_result_row(race, r, ctx))
    return rows


def parse_qualifying(races: list[dict]) -> list[Row]:
    rows = []
    for race in races:
        ctx = f"qualifying {race.get('season')}/{race.get('round')}"
        season, rnd = _race_key(race, ctx)
        for q in req(race, "QualifyingResults", ctx):
            rows.append(
                {
                    "season": season,
                    "round": rnd,
                    "driver_id": req(req(q, "Driver", ctx), "driverId", ctx),
                    "constructor_id": req(req(q, "Constructor", ctx), "constructorId", ctx),
                    "number": to_int(q.get("number")),
                    "position": to_int(req(q, "position", ctx)),
                    "q1_s": laptime_to_seconds(q.get("Q1")),
                    "q2_s": laptime_to_seconds(q.get("Q2")),
                    "q3_s": laptime_to_seconds(q.get("Q3")),
                }
            )
    return rows


def _standings_list(payload: dict, ctx: str) -> dict | None:
    lists = req(req(payload, "StandingsTable", ctx), "StandingsLists", ctx)
    if not lists:
        return None
    if len(lists) != 1:
        raise SchemaError(f"expected 1 StandingsList in {ctx}, got {len(lists)}")
    return lists[0]


def parse_driver_standings(mrdata: dict) -> list[Row]:
    ctx = "driverStandings"
    sl = _standings_list(mrdata, ctx)
    if sl is None:
        return []
    season, rnd = int(req(sl, "season", ctx)), int(req(sl, "round", ctx))
    rows = []
    for s in req(sl, "DriverStandings", ctx):
        constructors = s.get("Constructors") or []
        rows.append(
            {
                "season": season,
                "round": rnd,
                "driver_id": req(req(s, "Driver", ctx), "driverId", ctx),
                # A driver can appear with several teams in one season; the last one is current.
                "constructor_id": constructors[-1]["constructorId"] if constructors else None,
                "position": to_int(s.get("position")),  # absent for some unclassified drivers
                "position_text": s.get("positionText"),
                "points": to_float(req(s, "points", ctx)),
                "wins": to_int(req(s, "wins", ctx)),
            }
        )
    return rows


def parse_constructor_standings(mrdata: dict) -> list[Row]:
    ctx = "constructorStandings"
    sl = _standings_list(mrdata, ctx)
    if sl is None:
        return []
    season, rnd = int(req(sl, "season", ctx)), int(req(sl, "round", ctx))
    return [
        {
            "season": season,
            "round": rnd,
            "constructor_id": req(req(s, "Constructor", ctx), "constructorId", ctx),
            "position": to_int(s.get("position")),
            "position_text": s.get("positionText"),
            "points": to_float(req(s, "points", ctx)),
            "wins": to_int(req(s, "wins", ctx)),
        }
        for s in req(sl, "ConstructorStandings", ctx)
    ]


def collect_dimensions(races: list[dict], standings: list[dict]) -> dict[str, list[Row]]:
    """Gather drivers / constructors / circuits from objects embedded in other payloads.

    Avoids extra API calls: every result/standing already embeds the full Driver/Constructor.
    """
    drivers: dict[str, Row] = {}
    constructors: dict[str, Row] = {}
    circuits: dict[str, Row] = {}
    for race in races:
        if "Circuit" in race:
            c = circuit_row(race["Circuit"], "Circuit")
            circuits[c["circuit_id"]] = c
        for key in ("Results", "SprintResults", "QualifyingResults"):
            for r in race.get(key, []):
                d = driver_row(r["Driver"], key)
                drivers[d["driver_id"]] = d
                k = constructor_row(r["Constructor"], key)
                constructors[k["constructor_id"]] = k
    for payload in standings:
        for sl in payload.get("StandingsTable", {}).get("StandingsLists", []):
            for s in sl.get("DriverStandings", []):
                d = driver_row(s["Driver"], "DriverStandings")
                drivers[d["driver_id"]] = d
            for s in sl.get("ConstructorStandings", []):
                k = constructor_row(s["Constructor"], "ConstructorStandings")
                constructors[k["constructor_id"]] = k
    return {
        "drivers": sorted(drivers.values(), key=lambda r: r["driver_id"]),
        "constructors": sorted(constructors.values(), key=lambda r: r["constructor_id"]),
        "circuits": sorted(circuits.values(), key=lambda r: r["circuit_id"]),
    }
